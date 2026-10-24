"""
FastAPI route handlers for SEC filing discovery, ingestion, cataloging, and indexing.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from veridocs.api.dependencies import get_catalog, get_sec_client
from veridocs.catalog.sqlite_store import SQLiteCatalog
from veridocs.chunking.narrative_chunker import NarrativeChunker
from veridocs.chunking.table_chunker import TableChunker
from veridocs.config.settings import settings
from veridocs.indexing.bm25_index import BM25Index
from veridocs.indexing.dense_indexer import DenseIndexer
from veridocs.ingestion.html_parser import FilingParser
from veridocs.schemas.data_models import DocumentStatus, FilingDocument, IngestionManifest, TableCell
from veridocs.sec.client import SECClient
from veridocs.sec.discovery import build_primary_doc_url, normalize_cik
from veridocs.sec.provenance import compute_sha256
from veridocs.utils.logging import get_logger


logger = get_logger("veridocs.api.filings")
router = APIRouter(prefix="/api/v1/filings", tags=["filings"])


class DiscoveryRequest(BaseModel):
    ticker: Optional[str] = None
    cik: Optional[str] = None
    form_types: List[str] = Field(default_factory=lambda: ["10-K", "10-Q"])
    limit: int = Field(default=10, ge=1, le=100)


class IngestFilingRequest(BaseModel):
    ticker: Optional[str] = None
    cik: Optional[str] = None
    form_type: str = "10-K"
    accession_number: Optional[str] = None
    primary_document_name: Optional[str] = None
    source_url: Optional[str] = None
    raw_html: Optional[str] = None  # Direct HTML ingestion for fixtures or custom uploads
    fiscal_year: Optional[int] = None
    fiscal_period: Optional[str] = None


@router.post("/discover")
async def discover_filings(
    req: DiscoveryRequest,
    sec_client: SECClient = Depends(get_sec_client),
) -> Dict[str, Any]:
    """Discover available SEC 10-K/10-Q filings for a ticker or CIK."""
    identifier = req.ticker or req.cik
    if not identifier:
        raise HTTPException(status_code=400, detail="Must provide either ticker or CIK")

    try:
        filings = await sec_client.discover_filings(
            cik_or_ticker=identifier,
            forms=req.form_types,
            max_count=req.limit,
        )
        return {
            "identifier": identifier,
            "total_found": len(filings),
            "filings": filings,
        }
    except Exception as e:
        logger.error(f"Discovery failed for {identifier}: {e}")
        raise HTTPException(status_code=502, detail=f"SEC discovery error: {str(e)}")


@router.post("/ingest", response_model=IngestionManifest)
async def ingest_filing(
    req: IngestFilingRequest,
    sec_client: SECClient = Depends(get_sec_client),
    catalog: SQLiteCatalog = Depends(get_catalog),
) -> IngestionManifest:
    """
    Ingest a filing: download raw HTML, parse sections & tables, chunk, catalog, and index.
    """
    raw_html = req.raw_html
    accession = req.accession_number or "0000000000-00-000000"
    doc_name = req.primary_document_name or "filing.htm"
    cik = req.cik or (normalize_cik(req.ticker) if req.ticker else "0000000000")
    source_url = req.source_url or build_primary_doc_url(cik, accession, doc_name)
    ticker = req.ticker or "UNKNOWN"
    company_name = f"{ticker} Inc."
    filing_date = "2023-11-01"
    period_end = "2023-09-30"

    # Fetch from SEC if raw HTML not directly provided
    if not raw_html:
        if not req.accession_number or not req.primary_document_name:
            # Try to discover the latest filing of requested form type
            ident = req.ticker or req.cik
            if not ident:
                raise HTTPException(status_code=400, detail="Must provide accession_number and primary_document_name or ticker/cik")
            candidates = await sec_client.discover_filings(ident, forms=[req.form_type], max_count=1)
            if not candidates:
                raise HTTPException(status_code=404, detail=f"No {req.form_type} filings found for {ident}")
            target_filing = candidates[0]
            accession = target_filing["accession_number"]
            doc_name = target_filing["primary_document_name"]
            filing_date = target_filing["filing_date"]
            period_end = target_filing["report_period"]
            cik = target_filing["cik"]
            company_name = target_filing["company_name"]
            ticker = target_filing.get("ticker") or ticker
            source_url = target_filing["source_url"]

        try:
            raw_bytes, prov = await sec_client.fetch_filing_document(cik, accession, doc_name, source_url)
            raw_html = raw_bytes.decode("utf-8", errors="replace")
        except Exception as e:
            logger.error(f"Failed to fetch filing document from SEC: {e}")
            raise HTTPException(status_code=502, detail=f"SEC fetch failed: {str(e)}")


    # Parse HTML
    raw_bytes = raw_html.encode("utf-8") if isinstance(raw_html, str) else raw_html
    metadata = {
        "cik": cik,
        "ticker": ticker,
        "company_name": company_name,
        "form_type": req.form_type,
        "accession_number": accession,
        "filing_date": filing_date,
        "report_period": period_end,
        "fiscal_year": req.fiscal_year or 2023,
        "fiscal_quarter": None,
        "primary_document_name": doc_name,
        "source_url": source_url,
    }

    try:
        parser = FilingParser(raw_html=raw_bytes, metadata=metadata)
        parsed = parser.parse()
    except Exception as e:
        logger.error(f"HTML parsing failed: {e}")
        raise HTTPException(status_code=500, detail=f"Parsing error: {str(e)}")

    # Chunking
    narrative_chunker = NarrativeChunker()
    table_chunker = TableChunker()

    all_chunks = []
    ordinal = 1
    for sec in parsed.sections:
        c_list = narrative_chunker.chunk_section(parsed.document, sec, starting_ordinal=ordinal)
        all_chunks.extend(c_list)
        ordinal += len(c_list)

    cells_by_table: Dict[str, List[TableCell]] = {}
    for cell in parsed.cells:
        t_id = cell.cell_id.rsplit("_r", 1)[0]
        cells_by_table.setdefault(t_id, []).append(cell)


    for tbl in parsed.tables:
        tbl_cells = cells_by_table.get(tbl.table_id, [])
        t_chunks = table_chunker.chunk_table(parsed.document, tbl, tbl_cells, starting_ordinal=ordinal)
        all_chunks.extend(t_chunks)
        ordinal += len(t_chunks)

    # Save to SQLite catalog
    try:
        catalog.save_document(
            document=parsed.document,
            tables=parsed.tables,
            cells=parsed.cells,
            chunks=all_chunks,
        )
        manifest = IngestionManifest(
            document_id=parsed.document.document_id,
            status=DocumentStatus.PARSED,
            ingested_at=datetime.now(timezone.utc).isoformat(),
            section_count=len(parsed.sections),
            table_count=len(parsed.tables),
            cell_count=len(parsed.cells),
            chunk_count=len(all_chunks),
            corpus_hash=compute_sha256(raw_bytes),
            diagnostics=parsed.warnings,
        )

    except Exception as e:
        logger.error(f"Catalog storage failed: {e}")
        raise HTTPException(status_code=500, detail=f"Catalog error: {str(e)}")


    # Re-index all chunks in catalog
    try:
        all_catalog_chunks = catalog.list_chunks()
        if all_catalog_chunks:
            # Build BM25 index
            bm25_idx = BM25Index.build(all_catalog_chunks)
            settings.bm25_index_dir.mkdir(parents=True, exist_ok=True)
            bm25_idx.save(settings.bm25_index_dir / "bm25.pkl")


            # Build Dense FAISS index
            dense_indexer = DenseIndexer(model_id=settings.embedding_model_id)
            settings.faiss_index_dir.mkdir(parents=True, exist_ok=True)
            dense_indexer.build(all_catalog_chunks, output_dir=settings.faiss_index_dir)

    except Exception as e:
        logger.warning(f"Indexing update warning: {e}")

    return manifest


@router.get("")
async def list_filings(
    ticker: Optional[str] = Query(None),
    form_type: Optional[str] = Query(None),
    catalog: SQLiteCatalog = Depends(get_catalog),
) -> Dict[str, Any]:
    """List all ingested filings in the catalog."""
    docs = catalog.list_documents(ticker=ticker, form_type=form_type)
    return {
        "count": len(docs),
        "filings": [d.model_dump() for d in docs],
    }


@router.get("/{document_id}")
async def get_filing_details(
    document_id: str,
    catalog: SQLiteCatalog = Depends(get_catalog),
) -> Dict[str, Any]:
    """Retrieve details, sections, and tables of a specific ingested filing."""
    doc = catalog.get_document(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    sections = catalog.list_sections(document_id)
    tables = catalog.list_tables(document_id)
    from veridocs.schemas.query_models import MetadataFilter
    chunks = catalog.list_chunks(MetadataFilter(document_ids=[document_id]))

    return {
        "document": doc.model_dump(),
        "section_count": len(sections),
        "table_count": len(tables),
        "chunk_count": len(chunks),
        "sections": sections,
        "tables": [t.model_dump() for t in tables],
    }


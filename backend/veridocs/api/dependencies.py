"""
Central dependencies and service singletons for FastAPI endpoints.
"""

from pathlib import Path
from typing import Dict, Optional

from veridocs.audit.nli_auditor import NLIAuditor
from veridocs.audit.response_policy import PolicyThresholds, ResponsePolicyEngine
from veridocs.catalog.sqlite_store import SQLiteCatalog
from veridocs.config.settings import settings
from veridocs.generation.ollama_adapter import OllamaGenerationProvider
from veridocs.generation.provider import GeneratorProvider
from veridocs.generation.structured_answerer import StructuredAnswerer
from veridocs.indexing.bm25_index import BM25Index
from veridocs.indexing.dense_indexer import DenseIndexer
from veridocs.retrieval.bm25_retriever import BM25Retriever
from veridocs.retrieval.dense_retriever import DenseRetriever
from veridocs.retrieval.pipeline import RetrievalPipeline
from veridocs.retrieval.reranker import CrossEncoderReranker
from veridocs.schemas.query_models import RetrievalTrace
from veridocs.sec.client import SECClient

# In-memory query trace cache
QUERY_TRACES: Dict[str, RetrievalTrace] = {}

# Global singletons
_catalog: Optional[SQLiteCatalog] = None
_sec_client: Optional[SECClient] = None
_generator_provider: Optional[GeneratorProvider] = None
_nli_auditor: Optional[NLIAuditor] = None
_policy_engine: Optional[ResponsePolicyEngine] = None


def get_catalog() -> SQLiteCatalog:
    global _catalog
    if _catalog is None:
        db_path = Path(settings.sqlite_db_path)
        _catalog = SQLiteCatalog(db_path=db_path)
    return _catalog


def get_sec_client() -> SECClient:
    global _sec_client
    if _sec_client is None:
        from veridocs.sec.cache import SECCache
        from veridocs.sec.rate_limiter import SECRateLimiter
        cache = SECCache(settings.cache_dir)
        rate_limiter = SECRateLimiter(settings.sec_request_rate_limit)
        _sec_client = SECClient(
            rate_limiter=rate_limiter,
            cache=cache,
            user_agent=settings.sec_user_agent,
            timeout_seconds=settings.sec_timeout_seconds,
        )
    return _sec_client



def get_generator_provider() -> GeneratorProvider:
    global _generator_provider
    if _generator_provider is None:
        _generator_provider = OllamaGenerationProvider(
            base_url=settings.ollama_base_url,
            model_name=settings.ollama_model_name,
            timeout_seconds=settings.generation_timeout_seconds,
        )
    return _generator_provider


def set_generator_provider(provider: GeneratorProvider) -> None:
    """Override provider for testing."""
    global _generator_provider
    _generator_provider = provider


def get_nli_auditor() -> NLIAuditor:
    global _nli_auditor
    if _nli_auditor is None:
        _nli_auditor = NLIAuditor.get_instance(model_name=settings.nli_model_name)
    return _nli_auditor


def get_policy_engine() -> ResponsePolicyEngine:
    global _policy_engine
    if _policy_engine is None:
        thresholds = PolicyThresholds(
            entailment_threshold=0.50,
            contradiction_threshold=0.40,
        )
        _policy_engine = ResponsePolicyEngine(thresholds=thresholds)
    return _policy_engine


def get_structured_answerer() -> StructuredAnswerer:
    provider = get_generator_provider()
    return StructuredAnswerer(provider=provider)


def get_numeric_comparator() -> "NumericComparator":
    from veridocs.audit.numeric_comparator import NumericComparator
    return NumericComparator()


def get_retrieval_pipeline() -> RetrievalPipeline:
    catalog = get_catalog()
    bm25_index_path = settings.bm25_index_dir / "bm25.pkl"
    faiss_dir = settings.faiss_index_dir

    bm25_retriever = None
    if bm25_index_path.exists():
        bm25_idx = BM25Index.load(bm25_index_path)
        bm25_retriever = BM25Retriever(bm25_idx, catalog)

    dense_retriever = None
    if (faiss_dir / "index.faiss").exists() and (faiss_dir / "id_map.json").exists():
        indexer = DenseIndexer(model_id=settings.embedding_model_id)
        index, id_map, _ = DenseIndexer.load_index(faiss_dir)
        dense_retriever = DenseRetriever(
            faiss_index=index,
            id_map=id_map,
            indexer=indexer,
            catalog=catalog,
        )



    reranker = None
    if settings.enable_reranker:
        try:
            reranker = CrossEncoderReranker(model_name=settings.reranker_model_name)
        except Exception:
            reranker = None

    return RetrievalPipeline(
        catalog=catalog,
        bm25_retriever=bm25_retriever,
        dense_retriever=dense_retriever,
        reranker=reranker,
    )

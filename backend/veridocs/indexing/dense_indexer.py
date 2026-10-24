"""
Dense vector indexing with BGE-Small embeddings, FAISS CPU, ID mapping, and manifests.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from veridocs.schemas.data_models import ChunkRecord, IndexManifest
from veridocs.sec.provenance import compute_sha256
from veridocs.utils.logging import logger


class DenseIndexer:
    """
    Computes dense vector embeddings in batches, normalizes them with L2 norm,
    builds a FAISS IndexFlatIP, and maintains a validated ID mapping and manifest.
    """

    def __init__(
        self,
        model_id: str = "BAAI/bge-small-en-v1.5",
        batch_size: int = 32,
    ):
        self.model_id = model_id
        self.batch_size = batch_size
        self._model: Optional[SentenceTransformer] = None

    def _get_model(self) -> SentenceTransformer:
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_id}")
            self._model = SentenceTransformer(self.model_id)
        return self._model

    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """Embeds a list of strings and normalizes each vector to unit L2 norm."""
        if not texts:
            return np.empty((0, 384), dtype=np.float32)
        model = self._get_model()
        embeddings = model.encode(
            texts,
            batch_size=self.batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,  # Critical for Inner Product = Cosine Similarity
        )
        return np.array(embeddings, dtype=np.float32)

    def build_and_save_index(
        self,
        chunks: List[ChunkRecord],
        output_dir: Path,
        chunker_version: str = "1.0.0",
        corpus_hash: str = "",
    ) -> IndexManifest:
        """
        Builds FAISS index and persists index binary, ID map, and manifest.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        chunk_ids = [c.chunk_id for c in chunks]
        texts = [c.text for c in chunks]

        dim = 384
        index = faiss.IndexFlatIP(dim)

        if texts:
            vectors = self.embed_texts(texts)
            index.add(vectors)

        # 1. Save FAISS index
        index_file = output_dir / "index.faiss"
        faiss.write_index(index, str(index_file))
        with open(index_file, "rb") as f:
            faiss_checksum = compute_sha256(f.read())

        # 2. Save ID map (0..N-1 -> chunk_id)
        id_map_file = output_dir / "id_map.json"
        id_map = {str(i): cid for i, cid in enumerate(chunk_ids)}
        id_map_bytes = json.dumps(id_map, indent=2).encode("utf-8")
        with open(id_map_file, "wb") as f:
            f.write(id_map_bytes)
        id_map_checksum = compute_sha256(id_map_bytes)

        # 3. Create and save Manifest
        manifest = IndexManifest(
            manifest_version="1.0",
            created_at=datetime.now(timezone.utc).isoformat(),
            chunker_version=chunker_version,
            embedding_model_id=self.model_id,
            embedding_dimension=dim,
            normalization="L2",
            total_chunks=len(chunks),
            source_document_ids=sorted(list(set(c.document_id for c in chunks))),
            source_corpus_hash=corpus_hash,
            faiss_index_checksum=faiss_checksum,
            id_map_checksum=id_map_checksum,
        )

        manifest_file = output_dir / "manifest.json"
        with open(manifest_file, "w", encoding="utf-8") as f:
            f.write(manifest.model_dump_json(indent=2))

        return manifest

    @classmethod
    def load_index(
        cls,
        index_dir: Path,
    ) -> Tuple[faiss.IndexFlatIP, Dict[int, str], IndexManifest]:
        """
        Loads FAISS index, verifies checksums against manifest, and returns (index, id_map, manifest).
        Raises ValueError if manifest or index integrity is compromised.
        """
        index_dir = Path(index_dir)
        manifest_file = index_dir / "manifest.json"
        if not manifest_file.exists():
            raise FileNotFoundError(f"Index manifest not found in {index_dir}")

        with open(manifest_file, "r", encoding="utf-8") as f:
            manifest = IndexManifest.model_validate_json(f.read())

        # Verify FAISS checksum
        index_file = index_dir / "index.faiss"
        with open(index_file, "rb") as f:
            if compute_sha256(f.read()) != manifest.faiss_index_checksum:
                raise ValueError("Corrupt FAISS index: checksum does not match manifest")

        # Verify ID map checksum
        id_map_file = index_dir / "id_map.json"
        with open(id_map_file, "rb") as f:
            raw_id_map = f.read()
            if compute_sha256(raw_id_map) != manifest.id_map_checksum:
                raise ValueError("Corrupt ID map: checksum does not match manifest")

        id_map_data = json.loads(raw_id_map.decode("utf-8"))
        id_map = {int(k): v for k, v in id_map_data.items()}

        index = faiss.read_index(str(index_file))
        return index, id_map, manifest

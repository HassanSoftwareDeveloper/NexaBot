# vector_store.py

import faiss
import numpy as np
from pathlib import Path
from typing import List, Dict
import pickle
import hashlib
from backend.config import settings
from backend.services.embedding_service import embedding_service
import logging


logger = logging.getLogger(__name__)


class VectorStore:
    def __init__(self):
        self.index = None
        self.documents: List[Dict] = []
        self.document_metadata: List[Dict] = []
        self.index_path = settings.index_dir / "faiss.index"
        self.documents_path = settings.index_dir / "documents.pkl"
        self.metadata_path = settings.index_dir / "metadata.pkl"

        settings.index_dir.mkdir(parents=True, exist_ok=True)
        self.load_index()

    # -------------------------
    # Document Management
    # -------------------------
    def add_documents(self, documents: List[Dict]):
        if not documents:
            logger.warning("No documents to add")
            return

        new_documents = self._filter_duplicates(documents)
        if not new_documents:
            logger.info("All documents already exist in index")
            return

        texts = [doc['text'] for doc in new_documents]
        logger.info(f"🔄 Generating embeddings for {len(texts)} documents...")

        try:
            embeddings = embedding_service.encode_texts(texts).astype(np.float32)
            faiss.normalize_L2(embeddings)

            if self.index is None:
                dimension = embeddings.shape[1]
                self.index = faiss.IndexFlatIP(dimension)
                logger.info(f"✅ Created new FAISS index with dimension {dimension}")

            self.index.add(embeddings)
            self.documents.extend(new_documents)

            for doc in new_documents:
                metadata = {
                    'source': doc.get('source', 'Unknown'),
                    'chunk_id': doc.get('chunk_id', 0),
                    'text_length': len(doc['text'])
                }
                self.document_metadata.append(metadata)

            logger.info(f"✅ Added {len(new_documents)} documents. Total: {len(self.documents)}")
            self.save_index()

        except Exception as e:
            logger.error(f"❌ Error adding documents: {e}")
            raise

    def _filter_duplicates(self, documents: List[Dict]) -> List[Dict]:
        existing_hashes = set(
            hashlib.sha256(doc['text'][:200].encode('utf-8')).hexdigest()
            for doc in self.documents
        )

        new_documents = []
        for doc in documents:
            text_hash = hashlib.sha256(doc['text'][:200].encode('utf-8')).hexdigest()
            if text_hash not in existing_hashes:
                new_documents.append(doc)
                existing_hashes.add(text_hash)

        if len(new_documents) < len(documents):
            logger.info(f"Filtered out {len(documents) - len(new_documents)} duplicate documents")

        return new_documents

    # -------------------------
    # Search
    # -------------------------
    def search(self, query: str, top_k: int = 5, min_score: float = 0.1) -> List[Dict]:
        if self.index is None or len(self.documents) == 0:
            logger.warning("⚠️ No documents in index")
            return []

        try:
            query_embedding = embedding_service.encode_query(query).astype(np.float32).reshape(1, -1)
            faiss.normalize_L2(query_embedding)

            k = min(top_k * 3, len(self.documents))
            distances, indices = self.index.search(query_embedding, k)

            results, seen_texts = [], set()
            for idx, (distance, doc_idx) in enumerate(zip(distances[0], indices[0])):
                if doc_idx >= len(self.documents):
                    continue

                if distance < min_score:
                    continue

                doc = self.documents[doc_idx].copy()
                doc['score'] = float(distance)
                doc['rank'] = idx + 1

                text_hash = hashlib.sha256(doc['text'][:100].encode('utf-8')).hexdigest()
                if text_hash not in seen_texts:
                    seen_texts.add(text_hash)
                    results.append(doc)

                if len(results) >= top_k:
                    break

            results.sort(key=lambda x: x['score'], reverse=True)
            logger.info(f"🔍 Found {len(results)} relevant results for: '{query[:50]}...'")
            return results

        except Exception as e:
            logger.error(f"❌ Search error: {e}")
            return []

    def search_by_category(self, query: str, category: str, top_k: int = 5) -> List[Dict]:
        results = self.search(query, top_k * 2)
        category_lower = category.lower()
        filtered = [r for r in results if category_lower in r.get('source', '').lower()]
        return filtered[:top_k]

    def get_document_by_source(self, source: str) -> List[Dict]:
        source_lower = source.lower()
        return [doc for doc in self.documents if source_lower in doc.get('source', '').lower()]

    # -------------------------
    # Index Persistence
    # -------------------------
    def save_index(self):
        if self.index is None:
            logger.warning("No index to save")
            return

        try:
            faiss.write_index(self.index, str(self.index_path))
            with open(self.documents_path, 'wb') as f:
                pickle.dump(self.documents, f)
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(self.document_metadata, f)
            logger.info(f"✅ Saved index with {len(self.documents)} documents")
        except Exception as e:
            logger.error(f"❌ Error saving index: {e}")

    def load_index(self):
        if self.index_path.exists() and self.documents_path.exists():
            try:
                self.index = faiss.read_index(str(self.index_path))
                with open(self.documents_path, 'rb') as f:
                    self.documents = pickle.load(f)
                if self.metadata_path.exists():
                    with open(self.metadata_path, 'rb') as f:
                        self.document_metadata = pickle.load(f)
                else:
                    self.document_metadata = [
                        {'source': doc.get('source', 'Unknown'),
                         'chunk_id': doc.get('chunk_id', 0),
                         'text_length': len(doc['text'])}
                        for doc in self.documents
                    ]
                logger.info(f"✅ Loaded index with {len(self.documents)} documents")
            except Exception as e:
                logger.error(f"❌ Error loading index: {e}")
                self.index = None
                self.documents, self.document_metadata = [], []
        else:
            logger.info("No existing index found - will create new one")

    def clear_index(self):
        self.index, self.documents, self.document_metadata = None, [], []

        for path in [self.index_path, self.documents_path, self.metadata_path]:
            if path.exists():
                path.unlink()
                logger.info(f"Deleted file: {path.name}")

        logger.info("✅ Cleared all index data")

    # -------------------------
    # Index Maintenance
    # -------------------------
    def rebuild_index(self):
        if not self.documents:
            logger.warning("No documents to rebuild index from")
            return

        logger.info(f"🔄 Rebuilding index for {len(self.documents)} documents...")
        self.index = None
        texts = [doc['text'] for doc in self.documents]

        embeddings = embedding_service.encode_texts(texts).astype(np.float32)
        faiss.normalize_L2(embeddings)

        dimension = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dimension)
        self.index.add(embeddings)

        logger.info("✅ Index rebuilt successfully")
        self.save_index()

    def optimize_index(self):
        if not self.index or len(self.documents) < 1000:
            logger.info("Index too small for optimization")
            return

        logger.info("🔄 Optimizing index...")
        self.rebuild_index()
        logger.info("✅ Index optimized")

    def get_stats(self) -> Dict:
        stats = {
            "total_documents": len(self.documents),
            "index_size": self.index.ntotal if self.index else 0,
            "has_index": self.index is not None,
            "sources": {},
            "avg_text_length": 0,
            "total_words": 0
        }

        if self.documents:
            for doc in self.documents:
                source = doc.get('source', 'Unknown')
                stats['sources'][source] = stats['sources'].get(source, 0) + 1

            total_length = sum(len(doc['text']) for doc in self.documents)
            total_words = sum(len(doc['text'].split()) for doc in self.documents)

            stats['avg_text_length'] = total_length // len(self.documents)
            stats['total_words'] = total_words

        return stats


# Global instance
vector_store = VectorStore()

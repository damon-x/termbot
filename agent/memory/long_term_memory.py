"""
Unified long-term memory component.

Provides:
- Hybrid retrieval (keyword + semantic)
- Unified storage (SQLite + FAISS + Whoosh)
- External API decoupling
"""
import json
import logging
import os
import time
from typing import Any, Dict, List, Optional

# 禁用 jieba 日志（必须在 import jieba 之前）
os.environ.setdefault('JIEBA_ENABLE_LOGGING', 'false')
for _name in ['jieba', 'jieba.analyse', 'jieba.posseg', 'jieba.tokenize']:
    _l = logging.getLogger(_name)
    _l.handlers = [logging.NullHandler()]
    _l.propagate = False
    _l.setLevel(logging.CRITICAL)
    _l.disabled = True

import faiss
import numpy as np
from whoosh.fields import ID, NUMERIC, TEXT, Schema
from whoosh.index import create_in, open_dir
from whoosh.qparser import QueryParser
from jieba.analyse import ChineseAnalyzer

# jieba 初始化后再次禁用（jieba 可能重新配置了 logger）
import jieba
jieba.setLogLevel(logging.CRITICAL)

from agent.memory.models import MemoryItem, MemoryManager, memory_manager
from infrastructure.config.settings import settings
from infrastructure.external.embedding_client import get_embedding_client
from infrastructure.external.rerank_client import get_rerank_client
from infrastructure.logging import get_logger, EventType

logger = get_logger("memory.long_term")


class MemoryResult:
    """Retrieval result"""

    def __init__(
        self,
        query: str,
        memories: List[Dict[str, Any]],
        retrieval_time: float = 0.0
    ):
        self.query = query
        self.memories = memories
        self.retrieval_time = retrieval_time

    def __repr__(self) -> str:
        return f"MemoryResult(query='{self.query}', count={len(self.memories)})"


class SetResult:
    """Write result"""

    def __init__(
        self,
        success: bool,
        memory_id: Optional[int] = None,
        message: str = ""
    ):
        self.success = success
        self.memory_id = memory_id
        self.message = message

    def __repr__(self) -> str:
        return f"SetResult(success={self.success}, id={self.memory_id})"


class LongTermMemory:
    """
    Unified long-term memory component.

    External interfaces:
    - get(queries): Batch retrieval from memory
    - set(content): Write to memory
    """

    # Whoosh config (overridden in __init__ from settings)
    WHOOSH_INDEX_DIR = "~/.termbot/memory/whoosh_index"
    CHUNK_SIZE = 500
    CHUNK_MARGIN = 50

    # FAISS config (overridden in __init__ from settings)
    FAISS_INDEX_DIR = "~/.termbot/memory/faiss"
    FAISS_DB_NAME = "memory"
    FAISS_DIM = 1024

    # Scoring weights
    KEYWORD_WEIGHT = 0.4
    SEMANTIC_WEIGHT = 0.6

    def __init__(self):
        """Initialize memory system."""
        logger.info("Initializing LongTermMemory")

        # Resolve storage paths from settings
        self.FAISS_INDEX_DIR = os.path.expanduser(
            settings.memory.get('vector_db_path', self.FAISS_INDEX_DIR)
        )
        self.WHOOSH_INDEX_DIR = os.path.expanduser(
            settings.memory.get('whoosh_index_dir', self.WHOOSH_INDEX_DIR)
        )

        # SQLite manager
        self.memory_manager = memory_manager
        logger.debug("SQLite manager initialized")

        # Embedding and rerank clients
        self.embedding_client = get_embedding_client()
        logger.debug("Embedding client ready", client=str(self.embedding_client))

        self.rerank_client = get_rerank_client()
        logger.debug("Rerank client ready", client=str(self.rerank_client))

        # Initialize FAISS
        self._init_faiss()

        # Initialize Whoosh
        self._init_whoosh()

    def _init_faiss(self) -> None:
        """Initialize FAISS vector database."""
        os.makedirs(self.FAISS_INDEX_DIR, exist_ok=True)

        # Create or load FAISS index
        index_path = os.path.join(self.FAISS_INDEX_DIR, f"{self.FAISS_DB_NAME}.index")

        if os.path.exists(index_path):
            # Load existing index
            self.faiss_index = faiss.read_index(index_path)

            # Convert to IndexIDMap if needed
            if not isinstance(self.faiss_index, faiss.IndexIDMap):
                self.faiss_index = faiss.IndexIDMap(self.faiss_index)

            # Load ID mapping (always load if index file exists)
            self.faiss_id_map = self._load_faiss_id_map()
            logger.debug("FAISS index loaded", vectors=self.faiss_index.ntotal)
        else:
            # Create new index
            base_index = faiss.IndexFlatL2(self.FAISS_DIM)
            self.faiss_index = faiss.IndexIDMap(base_index)
            self.faiss_id_map = {}
            logger.debug("FAISS index created")

    def _init_whoosh(self) -> None:
        """Initialize Whoosh full-text index."""
        os.makedirs(self.WHOOSH_INDEX_DIR, exist_ok=True)

        if os.path.exists(os.path.join(self.WHOOSH_INDEX_DIR, "segment.num")):
            self.whoosh_index = open_dir(self.WHOOSH_INDEX_DIR)
            logger.debug("Whoosh index loaded", path=self.WHOOSH_INDEX_DIR)
        else:
            self.whoosh_index = create_in(
                self.WHOOSH_INDEX_DIR,
                schema=self._create_whoosh_schema()
            )
            logger.debug("Whoosh index created", path=self.WHOOSH_INDEX_DIR)

    def _create_whoosh_schema(self) -> Schema:
        """Create Whoosh Schema"""
        return Schema(
            doc_id=ID(stored=True),
            content=TEXT(stored=True, analyzer=ChineseAnalyzer()),
            memory_id=NUMERIC(stored=True),
            chunk_index=NUMERIC(stored=True),
            total_chunks=NUMERIC(stored=True)
        )

    def _load_faiss_id_map(self) -> Dict[int, int]:
        """Load FAISS ID mapping."""
        mapping_path = os.path.join(self.FAISS_INDEX_DIR, f"{self.FAISS_DB_NAME}_id_map.json")
        if os.path.exists(mapping_path):
            with open(mapping_path, 'r') as f:
                str_map = json.load(f)
                # Convert string keys back to int
                return {int(k): v for k, v in str_map.items()}
        return {}

    def _save_faiss_id_map(self) -> None:
        """Save FAISS ID mapping."""
        mapping_path = os.path.join(self.FAISS_INDEX_DIR, f"{self.FAISS_DB_NAME}_id_map.json")
        # Convert int keys to strings for JSON serialization
        str_map = {str(k): v for k, v in self.faiss_id_map.items()}
        with open(mapping_path, 'w') as f:
            json.dump(str_map, f, indent=2)

    def _save_faiss_index(self) -> None:
        """Save FAISS index to disk."""
        index_path = os.path.join(self.FAISS_INDEX_DIR, f"{self.FAISS_DB_NAME}.index")
        faiss.write_index(self.faiss_index, index_path)
        logger.debug("FAISS index saved to disk")

    # ========== External interfaces ==========

    def get(
        self,
        queries: List[str],
        limit: int = 5,
        use_rerank: bool = False
    ) -> List[MemoryResult]:
        """
        Batch retrieval from memory (RAG flow).

        Args:
            queries: Query list
            limit: Max results per query
            use_rerank: Whether to use rerank API

        Returns:
            [
                MemoryResult(
                    query="docker config",
                    memories=[...]
                ),
                ...
            ]
        """
        # 删除冗余日志：内存查询是内部操作，用户不关心

        results = []

        for query in queries:
            start_time = time.time()

            # 1. Hybrid search
            memory_scores = self._hybrid_search(query, limit * 2)

            # 2. Get Top K
            top_ids = sorted(memory_scores.items(), key=lambda x: -x[1])[:limit]

            # 3. Get details from SQLite
            memories = []
            for mem_id, score in top_ids:
                item = self.memory_manager.get_memory(mem_id)
                if item is not None and item.enabled:
                    memories.append({
                        "id": item.id,
                        "content": item.content,
                        "tags": json.loads(item.tags) if item.tags else [],
                        "score": score,
                        "source_type": getattr(item, 'source_type', '用户'),
                        "created_at": item.created_at,
                        "access_count": item.access_count
                    })
                    # Update access statistics
                    self.memory_manager.update_access(mem_id)

            retrieval_time = time.time() - start_time

            # 4. Optional: Rerank
            if use_rerank and len(memories) > 1:
                memories = self._rerank_results(query, memories, limit)

            results.append(MemoryResult(
                query=query,
                memories=memories,
                retrieval_time=retrieval_time
            ))

        return results

    def set(
        self,
        content: str,
        tags: List[str] = None,
        metadata: Dict = None,
        source_type: str = "用户",
        overwrite: bool = False
    ) -> SetResult:
        """
        Write to memory.

        Args:
            content: Memory content
            tags: Manual tags (optional)
            metadata: Extra information (optional)
            source_type: 来源类型（"用户" 或 "自动记录"）
            overwrite: Whether to overwrite (not implemented yet)

        Returns:
            SetResult(success, memory_id, message)
        """
        logger.log_event(EventType.MEMORY_ADD, {
            "content_length": len(content),
            "tags": tags,
            "source_type": source_type,
        })

        try:
            # 1. Auto tagging (not implemented yet)
            auto_tags = self._auto_tag_content(content)
            all_tags = list(set((tags or []) + auto_tags))

            # 2. Compute embedding
            logger.debug("Computing embedding")
            embedding = self.embedding_client.embed(content)
            logger.debug("Embedding computed", shape=str(embedding.shape))

            # 3. SQLite storage
            logger.debug("Saving to SQLite")
            memory_id = self.memory_manager.add_memory(
                content=content,
                tags=all_tags,
                metadata=metadata or {},
                embedding=embedding.tobytes(),
                source_type=source_type
            )
            logger.debug("Memory saved to SQLite", memory_id=memory_id)

            # 4. FAISS storage
            logger.debug("Saving to FAISS")
            if memory_id not in self.faiss_id_map:
                # Add new vector
                self.faiss_index.add_with_ids(
                    embedding.reshape(1, -1),
                    np.array([memory_id], dtype=np.int64)
                )
                self.faiss_id_map[memory_id] = 1
                self._save_faiss_index()
                logger.debug("Vector saved to FAISS", 
                    memory_id=memory_id, 
                    total_vectors=self.faiss_index.ntotal)
            else:
                logger.warning("Vector ID already in FAISS, skipping", memory_id=memory_id)

            # 5. Whoosh indexing
            logger.debug("Indexing to Whoosh")
            self._index_to_whoosh(memory_id, content)
            logger.debug("Content indexed to Whoosh", memory_id=memory_id)

            return SetResult(
                success=True,
                memory_id=memory_id,
                message=f"Memory saved successfully (ID: {memory_id})"
            )

        except Exception as e:
            logger.error("Memory save failed", exc_info=True, error=str(e))
            return SetResult(
                success=False,
                message=f"Memory save failed: {str(e)}"
            )

    # ========== Internal implementations ==========

    def _hybrid_search(self, query: str, k: int) -> Dict[int, float]:
        """
        Hybrid search (keyword + semantic).

        Returns:
            {memory_id: combined_score}
        """
        # 1. Whoosh keyword search
        keyword_scores = self._search_whoosh(query)
        logger.debug("Whoosh search completed", results=len(keyword_scores))

        # 2. FAISS semantic search
        query_embedding = self.embedding_client.embed(query)
        # FAISS search needs 2D array (n, dimensions), but embed returns 1D
        distances, faiss_ids = self.faiss_index.search(query_embedding.reshape(1, -1), k)

        # Convert distance to score (higher is better)
        # Note: faiss returns shape (1, k), so we need to access [0]
        semantic_scores = {}
        for i, vec_id in enumerate(faiss_ids[0]):
            if vec_id != -1:  # -1 means invalid in FAISS
                score = 1.0 / (1.0 + distances[0][i])
                semantic_scores[int(vec_id)] = score
        logger.debug("FAISS search completed", results=len(semantic_scores))

        # 3. Merge scores
        combined = self._merge_scores(keyword_scores, semantic_scores)
        logger.debug("Scores merged", unique_results=len(combined))

        return combined

    def _search_whoosh(self, query: str) -> Dict[int, float]:
        """
        Whoosh keyword search.

        Returns:
            {memory_id: score}
        """
        memory_scores = {}

        with self.whoosh_index.searcher() as searcher:
            query_parser = QueryParser("content", self.whoosh_index.schema)
            q = query_parser.parse(query)

            results = searcher.search(q, limit=50)

            for hit in results:
                mem_id = hit['memory_id']
                score = hit.score

                # Same memory may have multiple chunks, take highest score
                if mem_id not in memory_scores or score > memory_scores[mem_id]:
                    memory_scores[mem_id] = score

        return memory_scores

    def _index_to_whoosh(self, memory_id: int, content: str) -> None:
        """Index memory to Whoosh (with chunking)."""
        chunks = []
        total_chunks = int(len(content) / self.CHUNK_SIZE) + 1

        for i in range(total_chunks):
            start = i * self.CHUNK_SIZE
            end = min(start + self.CHUNK_SIZE + self.CHUNK_MARGIN, len(content))
            chunk = content[start:end]
            chunks.append(chunk)

        # Write to index
        writer = self.whoosh_index.writer()
        for i, chunk in enumerate(chunks):
            writer.add_document(
                doc_id=f"mem_{memory_id}_chunk_{i}",
                content=chunk,
                memory_id=memory_id,
                chunk_index=i,
                total_chunks=total_chunks
            )
        writer.commit()

    def _merge_scores(
        self,
        keyword_scores: Dict[int, float],
        semantic_scores: Dict[int, float]
    ) -> Dict[int, float]:
        """Merge keyword and semantic scores."""
        # Normalize to 0-1
        all_ids = set(keyword_scores.keys()) | set(semantic_scores.keys())

        max_kw = max(keyword_scores.values()) if keyword_scores else 1.0
        max_sem = max(semantic_scores.values()) if semantic_scores else 1.0

        final_scores = {}
        for mem_id in all_ids:
            kw_score = keyword_scores.get(mem_id, 0.0) / max_kw
            sem_score = semantic_scores.get(mem_id, 0.0) / max_sem

            # Weighted combination
            final_scores[mem_id] = (
                self.KEYWORD_WEIGHT * kw_score +
                self.SEMANTIC_WEIGHT * sem_score
            )

        return final_scores

    def _rerank_results(self, query: str, memories: List[Dict], top_n: int) -> List[Dict]:
        """Use Rerank API to reorder results."""
        try:
            documents = [m["content"] for m in memories]
            rerank_results = self.rerank_client.rerank(
                query=query,
                documents=documents,
                top_n=top_n
            )

            # Reorder memories based on rerank results
            reranked = []
            for result in rerank_results:
                idx = result["index"]
                memory = memories[idx].copy()
                memory["rerank_score"] = result["relevance_score"]
                reranked.append(memory)

            logger.debug("Rerank completed", results=len(reranked))
            return reranked

        except Exception as e:
            # If rerank fails, return original results
            logger.warning("Rerank failed, using original order", error=str(e))
            return memories

    def _auto_tag_content(self, content: str) -> List[str]:
        """
        Auto-tagging.

        Methods:
        1. Local rules (keyword matching)
        2. LLM generation (API call)

        Currently returns empty, implement later.
        """
        # Simple keyword extraction (future: use LLM)
        auto_tags = []

        # Common tech keywords
        tech_keywords = [
            "docker", "kubernetes", "container", "image",
            "python", "java", "javascript", "golang", "rust",
            "api", "rest", "graphql", "grpc",
            "database", "mysql", "postgresql", "mongodb", "redis",
            "linux", "shell", "bash", "command",
            "frontend", "backend", "fullstack",
            "config", "setting", "debug"
        ]

        content_lower = content.lower()
        for keyword in tech_keywords:
            if keyword in content_lower:
                auto_tags.append(keyword)

        return list(set(auto_tags))


# Global singleton
_long_term_memory: LongTermMemory = None


def get_long_term_memory() -> LongTermMemory:
    """Get global memory component singleton."""
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = LongTermMemory()
    return _long_term_memory

# 长期记忆系统重构方案

## 一、设计目标

### 1.1 核心原则
- **统一接口**：对外只提供 `get()` 和 `set()` 两个方法
- **多层存储**：SQLite（详情）+ FAISS（语义）+ Whoosh（关键词）
- **计算外包**：嵌入计算和重排序使用外部 API，本地轻量化
- **API 解耦**：外部 API 封装一层，便于未来更换
- **不再兼容**：废弃旧的 `NoteManager`、`ExperienceManager`、`QuickCommandManager`

### 1.2 废弃组件
```
agent/memory/long_term.py      → 删除
agent/memory/experience.py      → 删除
agent/memory/quick_command.py   → 删除
agent/memory/tool.py           → 删除
infrastructure/memory/vector.py → 删除（功能合并到新组件）
infrastructure/memory/text_search.py → 删除（功能合并到新组件）
```

### 1.3 新组件结构
```
infrastructure/external/
├── __init__.py
├── embedding_client.py    # 嵌入 API 封装
└── rerank_client.py       # 重排序 API 封装

agent/memory/
├── __init__.py
├── long_term_memory.py    # 核心组件（统一接口）
└── models.py             # 数据模型
```

---

## 二、API 封装层设计

### 2.1 嵌入 API 客户端

**位置**: `infrastructure/external/embedding_client.py`

```python
"""
文本嵌入计算客户端 - 封装外部 API

支持：
- 阿里云 DashScope API（当前）
- 未来可扩展到 OpenAI、其他服务商
"""
import os
from typing import List, Union

import numpy as np
from openai import OpenAI


class EmbeddingClient:
    """
    文本嵌入计算客户端

    统一的嵌入计算接口，便于未来更换 API 服务商
    """

    # 支持的服务商
    PROVIDER_DASHSCOPE = "dashscope"
    PROVIDER_OPENAI = "openai"

    def __init__(
        self,
        provider: str = PROVIDER_DASHSCOPE,
        api_key: str = None,
        model: str = None,
        dimensions: int = 1024
    ):
        """
        初始化嵌入客户端

        Args:
            provider: 服务商（dashscope | openai）
            api_key: API 密钥（默认从环境变量读取）
            model: 模型名称
            dimensions: 向量维度
        """
        self.provider = provider
        self.dimensions = dimensions

        if provider == self.PROVIDER_DASHSCOPE:
            # 阿里云 DashScope（使用 OpenAI 兼容接口）
            self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
            self.model = model or "text-embedding-v4"
            self.base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

        elif provider == self.PROVIDER_OPENAI:
            # OpenAI（未来支持）
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.model = model or "text-embedding-3-small"
            self.client = OpenAI(api_key=self.api_key)

        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def embed(self, text: str) -> np.ndarray:
        """
        计算单个文本的嵌入向量

        Args:
            text: 输入文本

        Returns:
            向量数组 (dimensions,)
        """
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=text,
                dimensions=self.dimensions if self.provider == self.PROVIDER_DASHSCOPE else None,
                encoding_format="float"
            )

            # 提取向量
            embedding = np.array(response.data[0].embedding, dtype=np.float32)
            return embedding

        except Exception as e:
            raise RuntimeError(f"Embedding computation failed: {e}")

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """
        批量计算嵌入向量（更高效）

        Args:
            texts: 输入文本列表

        Returns:
            向量矩阵 (n, dimensions)
        """
        if not texts:
            return np.array([], dtype=np.float32).reshape(0, self.dimensions)

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=texts,
                dimensions=self.dimensions if self.provider == self.PROVIDER_DASHSCOPE else None,
                encoding_format="float"
            )

            # 提取向量矩阵
            embeddings = np.array(
                [item.embedding for item in response.data],
                dtype=np.float32
            )
            return embeddings

        except Exception as e:
            raise RuntimeError(f"Batch embedding failed: {e}")

    def __repr__(self) -> str:
        return f"EmbeddingClient(provider={self.provider}, model={self.model})"


# 全局单例
_embedding_client: EmbeddingClient = None


def get_embedding_client() -> EmbeddingClient:
    """获取全局嵌入客户端单例"""
    global _embedding_client
    if _embedding_client is None:
        from infrastructure.config.settings import settings
        config = settings.get("embedding", {})
        _embedding_client = EmbeddingClient(
            provider=config.get("provider", "dashscope"),
            api_key=config.get("api_key"),
            model=config.get("model"),
            dimensions=config.get("dimensions", 1024)
        )
    return _embedding_client
```

### 2.2 重排序 API 客户端

**位置**: `infrastructure/external/rerank_client.py`

```python
"""
文档重排序客户端 - 封装外部 API

支持：
- 阿里云 DashScope API（当前）
- 未来可扩展到其他服务商
"""
import os
from typing import Any, Dict, List

import requests


class RerankClient:
    """
    文档重排序客户端

    对检索结果进行相关性重排序，提高准确性
    """

    # 支持的服务商
    PROVIDER_DASHSCOPE = "dashscope"

    def __init__(
        self,
        provider: str = PROVIDER_DASHSCOPE,
        api_key: str = None,
        model: str = None
    ):
        """
        初始化重排序客户端

        Args:
            provider: 服务商
            api_key: API 密钥
            model: 模型名称
        """
        self.provider = provider

        if provider == self.PROVIDER_DASHSCOPE:
            self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
            self.model = model or "qwen3-rerank"
            self.base_url = "https://dashscope.aliyuncs.com/api/v1/services/rerank"

        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def rerank(
        self,
        query: str,
        documents: List[str],
        top_n: int = None,
        return_documents: bool = True
    ) -> List[Dict[str, Any]]:
        """
        对文档进行重排序

        Args:
            query: 查询文本
            documents: 候选文档列表
            top_n: 返回前 N 个结果
            return_documents: 是否返回文档内容

        Returns:
            重排序结果列表：
            [
                {
                    "index": 0,
                    "relevance_score": 0.933,
                    "document": {"text": "..."}
                },
                ...
            ]
        """
        try:
            url = f"{self.base_url}/{self.model}/text-rerank/text-rerank"

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }

            data = {
                "model": self.model,
                "input": {
                    "query": query,
                    "documents": [{"text": doc} for doc in documents]
                },
                "parameters": {
                    "return_documents": return_documents,
                    "top_n": top_n or len(documents)
                }
            }

            response = requests.post(url, json=data, headers=headers, timeout=30)
            response.raise_for_status()

            result = response.json()

            # 提取结果
            if result.get("status_code") == 200:
                return result.get("output", {}).get("results", [])
            else:
                raise RuntimeError(f"Rerank API error: {result.get('message')}")

        except Exception as e:
            raise RuntimeError(f"Rerank failed: {e}")

    def __repr__(self) -> str:
        return f"RerankClient(provider={self.provider}, model={self.model})"


# 全局单例
_rerank_client: RerankClient = None


def get_rerank_client() -> RerankClient:
    """获取全局重排序客户端单例"""
    global _rerank_client
    if _rerank_client is None:
        from infrastructure.config.settings import settings
        config = settings.get("rerank", {})
        _rerank_client = RerankClient(
            provider=config.get("provider", "dashscope"),
            api_key=config.get("api_key"),
            model=config.get("model")
        )
    return _rerank_client
```

---

## 三、数据存储方案

### 3.1 SQLite 数据模型

**位置**: `agent/memory/models.py`

```python
"""
长期记忆数据模型
"""
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import Boolean, Column, Integer, LargeBinary, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import Index

from infrastructure.config.settings import settings

Base = declarative_base()


class MemoryItem(Base):
    """
    长期记忆数据模型

    统一存储所有类型的记忆（笔记、经验、命令等）
    """

    __tablename__ = "long_term_memory"

    # 主键和内容
    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(Text, nullable=False)

    # 标签和元数据（JSON 存储）
    tags = Column(String(500))  # JSON: ["docker", "配置", "dev"]
    metadata = Column(Text)  # JSON: {"source": "user", ...}

    # 嵌入向量（备份）
    embedding = Column(LargeBinary)  # numpy array bytes (可选）

    # 时间戳
    created_at = Column(String(50), nullable=False)
    updated_at = Column(String(50))

    # 统计信息
    access_count = Column(Integer, default=0)
    last_accessed = Column(String(50))

    # 状态
    enabled = Column(Boolean, default=True)  # 可禁用某条记忆

    # 索引
    __table_args__ = (
        Index('idx_created', 'created_at'),
        Index('idx_tags', 'tags'),
        Index('idx_enabled', 'enabled'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        import json

        return {
            "id": self.id,
            "content": self.content,
            "tags": json.loads(self.tags) if self.tags else [],
            "metadata": json.loads(self.metadata) if self.metadata else {},
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
            "enabled": self.enabled
        }


class MemoryManager:
    """数据库管理器"""

    def __init__(self, db_path: str = None) -> None:
        if db_path is None:
            db_path = f"sqlite:///{settings.memory.get('database_path', 'data/termbot.db')}"

        self.engine = create_engine(db_path)
        Base.metadata.create_all(self.engine)
        self._session_factory = sessionmaker(bind=self.engine)

    def get_session(self) -> Session:
        """获取数据库会话"""
        return self._session_factory()

    def add_memory(
        self,
        content: str,
        tags: List[str] = None,
        metadata: Dict = None,
        embedding: bytes = None
    ) -> int:
        """
        添加记忆

        Returns:
            新记忆的 ID
        """
        session = self.get_session()
        try:
            import json

            memory = MemoryItem(
                content=content,
                tags=json.dumps(tags or [], ensure_ascii=False),
                metadata=json.dumps(metadata or {}, ensure_ascii=False),
                embedding=embedding,
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            session.add(memory)
            session.commit()
            return memory.id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_memory(self, memory_id: int) -> MemoryItem:
        """获取单条记忆"""
        session = self.get_session()
        try:
            return session.query(MemoryItem).filter_by(id=memory_id).first()
        finally:
            session.close()

    def update_access(self, memory_id: int) -> None:
        """更新访问统计"""
        session = self.get_session()
        try:
            memory = session.query(MemoryItem).filter_by(id=memory_id).first()
            if memory:
                memory.access_count += 1
                memory.last_accessed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                session.commit()
        finally:
            session.close()


# 全局实例
memory_manager = MemoryManager()
```

### 3.2 FAISS 向量存储

**特点**：
- 使用统一 ID（与 SQLite 的 ID 一致）
- 存储位置：`data/faiss/memory.index`
- 向量维度：1024（与嵌入 API 一致）

**ID 映射关系**：
```
SQLite ID = 1  ─→  FAISS vector_id = 1
SQLite ID = 5  ─→  FAISS vector_id = 5
```

### 3.3 Whoosh 全文索引

**分段索引策略**：
```
Memory ID = 1, Content = "..." (2000 字符)

Whoosh 索引：
  mem_1_chunk_0  → content[0:500]
  mem_1_chunk_1  → content[500:1000]
  mem_1_chunk_2  → content[1000:1500]
  mem_1_chunk_3  → content[1500:2000]
```

**Schema**：
```python
Schema(
    doc_id=TEXT(stored=True),
    content=TEXT(stored=True, analyzer=ChineseAnalyzer()),
    memory_id=NUMERIC(stored=True),  # ← 关联字段
    chunk_index=NUMERIC(stored=True),
    total_chunks=NUMERIC(stored=True)
)
```

---

## 四、核心组件设计

### 4.1 LongTermMemory 类

**位置**: `agent/memory/long_term_memory.py`

```python
"""
统一的长期记忆组件

提供：
- 混合检索（关键词 + 语义）
- 统一存储（SQLite + FAISS + Whoosh）
- 外部 API 解耦
"""
import json
import os
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from agent.memory.models import MemoryItem, MemoryManager, memory_manager
from infrastructure.external.embedding_client import get_embedding_client
from infrastructure.external.rerank_client import get_rerank_client
from infrastructure.memory.vector import VectorDatabase

# Whoosh 导入
from whoosh.fields import ID, NUMERIC, TEXT, Schema
from whoosh.index import create_in, open_dir
from whoosh.qparser import QueryParser
from jieba.analyse import ChineseAnalyzer


class MemoryResult:
    """检索结果"""

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
    """写入结果"""

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
    统一的长期记忆组件

    对外接口：
    - get(queries): 批量检索记忆
    - set(content): 写入记忆
    """

    # Whoosh 配置
    WHOOSH_INDEX_DIR = "./whoosh_memory_index"
    CHUNK_SIZE = 500
    CHUNK_MARGIN = 50

    # FAISS 配置
    FAISS_INDEX_DIR = "data/faiss"
    FAISS_DB_NAME = "memory"

    def __init__(self):
        """初始化记忆系统"""
        self.memory_manager = memory_manager
        self.embedding_client = get_embedding_client()
        self.rerank_client = get_rerank_client()

        # 初始化 FAISS
        self.vector_db = VectorDatabase(
            dim=1024,
            metric="L2",
            index_dir=self.FAISS_INDEX_DIR
        )

        # 初始化 Whoosh
        self._init_whoosh()

    def _init_whoosh(self) -> None:
        """初始化 Whoosh 索引"""
        os.makedirs(self.WHOOSH_INDEX_DIR, exist_ok=True)

        if os.path.exists(os.path.join(self.WHOOSH_INDEX_DIR, "segment.num")):
            self.whoosh_index = open_dir(self.WHOOSH_INDEX_DIR)
        else:
            self.whoosh_index = create_in(
                self.WHOOSH_INDEX_DIR,
                schema=self._create_whoosh_schema()
            )

    def _create_whoosh_schema(self) -> Schema:
        """创建 Whoosh Schema"""
        return Schema(
            doc_id=ID(stored=True),
            content=TEXT(stored=True, analyzer=ChineseAnalyzer()),
            memory_id=NUMERIC(stored=True),
            chunk_index=NUMERIC(stored=True),
            total_chunks=NUMERIC(stored=True)
        )

    # ========== 对外接口 ==========

    def get(self, queries: List[str], limit: int = 5, use_rerank: bool = True) -> List[MemoryResult]:
        """
        批量检索记忆（RAG 流程）

        Args:
            queries: 查询列表
            limit: 每个查询返回多少条
            use_rerank: 是否使用重排序 API

        Returns:
            [
                MemoryResult(
                    query="docker配置",
                    memories=[...]
                ),
                ...
            ]
        """
        results = []

        for query in queries:
            import time
            start_time = time.time()

            # 1. 混合检索
            memory_scores = self._hybrid_search(query, limit * 2)

            # 2. 取 Top K
            top_ids = sorted(memory_scores.items(), key=lambda x: -x[1])[:limit]

            # 3. 获取详情
            memories = []
            for mem_id, score in top_ids:
                item = self.memory_manager.get_memory(mem_id)
                if item and item.enabled:
                    memories.append({
                        "id": item.id,
                        "content": item.content,
                        "tags": json.loads(item.tags) if item.tags else [],
                        "score": score,
                        "created_at": item.created_at
                    })
                    # 更新访问统计
                    self.memory_manager.update_access(mem_id)

            # 4. 可选：重排序
            if use_rerank and len(memories) > 1:
                memories = self._rerank_results(query, memories, limit)

            retrieval_time = time.time() - start_time
            results.append(MemoryResult(query=query, memories=memories, retrieval_time=retrieval_time))

        return results

    def set(
        self,
        content: str,
        tags: List[str] = None,
        metadata: Dict = None,
        overwrite: bool = False
    ) -> SetResult:
        """
        写入记忆

        Args:
            content: 记忆内容
            tags: 手动标签（可选）
            metadata: 额外信息（可选）
            overwrite: 是否覆盖（暂未实现）

        Returns:
            SetResult(success, memory_id, message)
        """
        try:
            # 1. 自动打标
            auto_tags = self._auto_tag_content(content)
            all_tags = list(set((tags or []) + auto_tags))

            # 2. 计算嵌入
            embedding = self.embedding_client.embed(content)

            # 3. SQLite 存储
            memory_id = self.memory_manager.add_memory(
                content=content,
                tags=all_tags,
                metadata=metadata or {},
                embedding=embedding.tobytes()
            )

            # 4. FAISS 存储
            self.vector_db.insert(
                db=self.FAISS_DB_NAME,
                data=embedding,
                ids=memory_id
            )

            # 5. Whoosh 索引
            self._index_to_whoosh(memory_id, content)

            return SetResult(
                success=True,
                memory_id=memory_id,
                message=f"记忆保存成功（ID: {memory_id}）"
            )

        except Exception as e:
            return SetResult(
                success=False,
                message=f"记忆保存失败: {str(e)}"
            )

    # ========== 内部实现 ==========

    def _hybrid_search(self, query: str, k: int) -> Dict[int, float]:
        """
        混合检索（关键词 + 语义）

        Returns:
            {memory_id: combined_score}
        """
        # 1. Whoosh 关键词检索
        keyword_scores = self._search_whoosh(query)

        # 2. FAISS 语义检索
        query_embedding = self.embedding_client.embed(query)
        distances, faiss_ids = self.vector_db.query(
            db=self.FAISS_DB_NAME,
            data=query_embedding,
            k=k
        )

        # 距离转分数
        semantic_scores = {}
        for i, vec_id in enumerate(faiss_ids):
            if vec_id != -1:  # FAISS 返回 -1 表示无效
                score = 1.0 / (1.0 + distances[i])
                semantic_scores[vec_id] = score

        # 3. 融合评分
        return self._merge_scores(keyword_scores, semantic_scores)

    def _search_whoosh(self, query: str) -> Dict[int, float]:
        """
        Whoosh 关键词检索

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

                # 同一记忆的多块，取最高分
                if mem_id not in memory_scores or score > memory_scores[mem_id]:
                    memory_scores[mem_id] = score

        return memory_scores

    def _index_to_whoosh(self, memory_id: int, content: str) -> None:
        """将记忆索引到 Whoosh（分块）"""
        chunks = []
        total_chunks = int(len(content) / self.CHUNK_SIZE) + 1

        for i in range(total_chunks):
            start = i * self.CHUNK_SIZE
            end = min(start + self.CHUNK_SIZE + self.CHUNK_MARGIN, len(content))
            chunk = content[start:end]
            chunks.append(chunk)

        # 写入索引
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
        semantic_scores: Dict[int, float],
        kw_weight: float = 0.4,
        sem_weight: float = 0.6
    ) -> Dict[int, float]:
        """融合关键词和语义评分"""
        all_ids = set(keyword_scores.keys()) | set(semantic_scores.keys())

        final_scores = {}
        for mem_id in all_ids:
            kw_score = keyword_scores.get(mem_id, 0.0)
            sem_score = semantic_scores.get(mem_id, 0.0)

            # 归一化后加权
            final_scores[mem_id] = kw_weight * kw_score + sem_weight * sem_score

        return final_scores

    def _rerank_results(self, query: str, memories: List[Dict], top_n: int) -> List[Dict]:
        """使用 Rerank API 重排序"""
        try:
            documents = [m["content"] for m in memories]
            rerank_results = self.rerank_client.rerank(
                query=query,
                documents=documents,
                top_n=top_n
            )

            # 根据重排序结果重新排列
            reranked = []
            for result in rerank_results:
                idx = result["index"]
                memory = memories[idx].copy()
                memory["rerank_score"] = result["relevance_score"]
                reranked.append(memory)

            return reranked

        except Exception as e:
            # 重排序失败，返回原结果
            print(f"Rerank failed: {e}, using original order")
            return memories

    def _auto_tag_content(self, content: str) -> List[str]:
        """
        自动打标（可后续实现）

        方案：
        1. 本地规则（关键词匹配）
        2. LLM 生成（调用 API）
        """
        # 暂时返回空，后续可接入 LLM
        return []


# 全局单例
_long_term_memory: LongTermMemory = None


def get_long_term_memory() -> LongTermMemory:
    """获取全局记忆组件单例"""
    global _long_term_memory
    if _long_term_memory is None:
        _long_term_memory = LongTermMemory()
    return _long_term_memory
```

---

## 五、配置文件更新

**位置**: `config/default.json`

```json
{
  "memory": {
    "database_path": "data/termbot.db"
  },
  "embedding": {
    "provider": "dashscope",
    "api_key": "${DASHSCOPE_API_KEY}",
    "model": "text-embedding-v4",
    "dimensions": 1024
  },
  "rerank": {
    "provider": "dashscope",
    "api_key": "${DASHSCOPE_API_KEY}",
    "model": "qwen3-rerank"
  }
}
```

---

## 六、工具层更新

### 6.1 更新工具实现

**位置**: `agent/tools/impl.py`

```python
# 废弃旧工具
# NoteTool, GetAllNotesTool, QuickCommandTool, GetAllQuickCommandsTool

# 新增统一记忆工具
class AddMemoryTool(Tool):
    """添加记忆（替代 NoteTool, QuickCommandTool）"""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="add_memory",
            description="记录信息到长期记忆，包括笔记、经验、命令等",
            parameters=[
                ToolParameter(
                    name="content",
                    type=ToolParameterType.STRING,
                    description="要记录的内容",
                    required=True
                ),
                ToolParameter(
                    name="tags",
                    type=ToolParameterType.ARRAY,
                    description="可选的标签列表",
                    required=False
                )
            ]
        )

    def execute(self, **kwargs: Any) -> Any:
        from agent.memory.long_term_memory import get_long_term_memory

        memory = get_long_term_memory()
        result = memory.set(
            content=kwargs.get("content", ""),
            tags=kwargs.get("tags")
        )
        return result.message


class SearchMemoryTool(Tool):
    """检索记忆（替代 GetAllNotesTool）"""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="search_memory",
            description="检索长期记忆，支持多问题并行查询",
            parameters=[
                ToolParameter(
                    name="queries",
                    type=ToolParameterType.ARRAY,
                    description="查询列表",
                    required=True
                )
            ]
        )

    def execute(self, **kwargs: Any) -> Any:
        from agent.memory.long_term_memory import get_long_term_memory

        memory = get_long_term_memory()
        queries = kwargs.get("queries", [])
        results = memory.get(queries)

        # 格式化返回
        output = []
        for result in results:
            output.append(f"查询：{result.query}")
            for mem in result.memories[:3]:  # 最多返回 3 条
                output.append(f"- {mem['content'][:100]}...")

        return "\n".join(output)
```

---

## 七、实现步骤

### Phase 1: API 封装层（第 1 周）
- [x] `infrastructure/external/__init__.py`
- [x] `infrastructure/external/embedding_client.py`
- [x] `infrastructure/external/rerank_client.py`
- [x] 单元测试
- [x] 更新配置文件
- ✅ **完成**

### Phase 2: 数据模型和存储（第 2 周）
- [x] `agent/memory/models.py`
- [x] `agent/memory/long_term_memory.py` 框架
- [x] SQLite + FAISS + Whoosh 统一管理
- [x] 单元测试
- ✅ **完成**

### Phase 3: 核心逻辑（第 3 周）
- [x] 混合检索实现
- [x] 打标和分段
- [x] 集成测试
- ✅ **完成**

### Phase 4: 工具层更新（第 4 周）
- [x] 更新 `impl.py` 工具
- [x] 更新 `create_default_tools()` 工具注册
- [x] 集成测试
- ✅ **完成**（2026-02-14）

### Phase 5: 清理旧代码（第 5 周）
- [x] 删除旧的记忆组件
- [x] 更新文档
- [x] 回归测试
- ✅ **完成**（2026-02-14）

---

## 八、风险和注意事项

### 8.1 技术风险
- **FAISS 兼容性**：ID 映射需要正确处理
- **Whoosh 分段**：需要正确聚合评分
- **API 调用量**：嵌入和重排序频繁调用，注意限流

### 8.2 性能考虑
- **嵌入计算**：批量调用 API，减少网络开销
- **缓存策略**：热点查询可以缓存嵌入
- **索引优化**：Whoosh 分块不宜过小

### 8.3 数据迁移
- **旧数据**：需要脚本迁移旧的 notes/experiences/commands 到新表
- **ID 冲突**：如果有历史数据，需要保留旧 ID

---

## 九、未来扩展

### 9.1 自动打标
- 本地规则（关键词匹配）
- LLM 生成（调用 API）

### 9.2 冲突检测
- 内容去重（相似度 > 0.9）
- 语义矛盾检测（可选）

### 9.3 记忆类型
- 通过 metadata["type"] 区分
- 支持：note | experience | command | preference

### 9.4 学习机制
- 访问统计（access_count）
- 时间衰减（旧记忆降低权重）
- 用户反馈（点赞/点踩）

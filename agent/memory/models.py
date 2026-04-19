"""
Long-term memory data models.

Unified storage for all memory types (notes, experiences, commands, etc.)
"""
import os
from datetime import datetime
from typing import Any, Dict, List

from sqlalchemy import Boolean, Column, Integer, LargeBinary, String, Text, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.schema import Index

from infrastructure.config.settings import settings
from infrastructure.logging import get_logger

logger = get_logger("memory.models")

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
    meta_data = Column(Text)  # JSON: {"source": "user", ...}  # 改名避免冲突

    # 来源类型
    source_type = Column(String(20), default="用户")  # "用户" 或 "自动记录"

    # 嵌入向量（备份）
    embedding = Column(LargeBinary)  # numpy array bytes (可选)

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
        Index('idx_source_type', 'source_type'),
    )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        import json

        return {
            "id": self.id,
            "content": self.content,
            "tags": json.loads(self.tags) if self.tags else [],
            "metadata": json.loads(self.meta_data) if self.meta_data else {},  # 改用 meta_data
            "source_type": self.source_type or "用户",
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "access_count": self.access_count,
            "enabled": self.enabled
        }


class MemoryManager:
    """数据库管理器"""

    def __init__(self, db_path: str = None) -> None:
        if db_path is None:
            raw_path = settings.memory.get('database_path', '~/.termbot/memory/termbot.db')
            expanded_path = os.path.expanduser(raw_path)
            os.makedirs(os.path.dirname(expanded_path), exist_ok=True)
            db_path = f"sqlite:///{expanded_path}"

        self.engine = create_engine(db_path)
        Base.metadata.create_all(self.engine)
        self._session_factory = sessionmaker(bind=self.engine)

        # 迁移：添加缺失的列
        self._migrate_add_source_type()

    def _migrate_add_source_type(self) -> None:
        """迁移：添加 source_type 列（如果不存在）"""
        try:
            # 获取现有列
            with self.engine.connect() as conn:
                result = conn.execute("PRAGMA table_info(long_term_memory)")
                columns = [row[1] for row in result.fetchall()]

            if 'source_type' not in columns:
                # 列不存在，添加它
                with self.engine.connect() as conn:
                    conn.execute(
                        "ALTER TABLE long_term_memory ADD COLUMN source_type VARCHAR(20) DEFAULT '用户'"
                    )
                    conn.commit()
                logger.info("Migration: added source_type column")
        except Exception as e:
            logger.warning("Migration check failed", error=str(e))

    def get_session(self) -> Session:
        """获取数据库会话"""
        return self._session_factory()

    def add_memory(
        self,
        content: str,
        tags: List[str] = None,
        metadata: Dict = None,
        embedding: bytes = None,
        source_type: str = "用户"
    ) -> int:
        """
        添加记忆

        Args:
            content: 记忆内容
            tags: 标签列表
            metadata: 元数据字典
            embedding: 嵌入向量字节
            source_type: 来源类型（"用户" 或 "自动记录"）

        Returns:
            新记忆的 ID

        Raises:
            Exception: 如果数据库操作失败
        """
        session = self.get_session()
        try:
            import json

            memory = MemoryItem(
                content=content,
                tags=json.dumps(tags or [], ensure_ascii=False),
                meta_data=json.dumps(metadata or {}, ensure_ascii=False),  # 改用 meta_data
                source_type=source_type,
                embedding=embedding,
                created_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                updated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            )
            session.add(memory)
            session.commit()
            logger.debug("Memory added to SQLite", memory_id=memory.id, source_type=source_type)
            return memory.id
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def get_memory(self, memory_id: int) -> MemoryItem:
        """
        获取单条记忆

        Args:
            memory_id: 记忆 ID

        Returns:
            MemoryItem 对象，如果不存在返回 None
        """
        session = self.get_session()
        try:
            return session.query(MemoryItem).filter_by(id=memory_id).first()
        finally:
            session.close()

    def get_all_memories(
        self,
        enabled_only: bool = True,
        limit: int = None
    ) -> List[MemoryItem]:
        """
        获取所有记忆

        Args:
            enabled_only: 是否只返回启用的记忆
            limit: 最多返回多少条

        Returns:
            MemoryItem 对象列表
        """
        session = self.get_session()
        try:
            query = session.query(MemoryItem)

            if enabled_only:
                query = query.filter(MemoryItem.enabled == True)

            if limit:
                query = query.limit(limit)

            return query.all()
        finally:
            session.close()

    def update_access(self, memory_id: int) -> None:
        """
        更新访问统计

        Args:
            memory_id: 记忆 ID
        """
        session = self.get_session()
        try:
            memory = session.query(MemoryItem).filter_by(id=memory_id).first()
            if memory:
                memory.access_count += 1
                memory.last_accessed = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                session.commit()
        finally:
            session.close()

    def delete_memory(self, memory_id: int) -> bool:
        """
        删除记忆

        Args:
            memory_id: 记忆 ID

        Returns:
            是否删除成功
        """
        session = self.get_session()
        try:
            memory = session.query(MemoryItem).filter_by(id=memory_id).first()
            if memory:
                session.delete(memory)
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def disable_memory(self, memory_id: int) -> bool:
        """
        禁用记忆（软删除）

        Args:
            memory_id: 记忆 ID

        Returns:
            是否禁用成功
        """
        session = self.get_session()
        try:
            memory = session.query(MemoryItem).filter_by(id=memory_id).first()
            if memory:
                memory.enabled = False
                session.commit()
                return True
            return False
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    def list_memories(
        self,
        enabled_only: bool = True,
        tag_filter: str = None,
        search_query: str = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
        offset: int = 0,
        limit: int = 5
    ) -> tuple[List[MemoryItem], int]:
        """
        获取笔记列表（分页）

        Args:
            enabled_only: 只返回启用的笔记
            tag_filter: 按标签筛选（JSON 包含）
            search_query: 在内容中搜索关键词
            sort_by: 排序字段 (created_at | updated_at | access_count)
            sort_order: 排序方向 (desc | asc)
            offset: 跳过前 N 条（分页用）
            limit: 最多返回 N 条

        Returns:
            (笔记列表, 总数)
        """
        session = self.get_session()
        try:
            query = session.query(MemoryItem)

            # 筛选条件
            if enabled_only:
                query = query.filter(MemoryItem.enabled == True)

            if tag_filter:
                # SQLite JSON 查询（包含匹配）
                query = query.filter(MemoryItem.tags.contains(tag_filter))

            if search_query:
                # 内容模糊匹配
                query = query.filter(MemoryItem.content.contains(search_query))

            # 总数（分页前）
            total = query.count()

            # 排序
            order_column = {
                "created_at": MemoryItem.created_at,
                "updated_at": MemoryItem.updated_at,
                "access_count": MemoryItem.access_count
            }.get(sort_by, MemoryItem.created_at)

            if sort_order == "desc":
                query = query.order_by(order_column.desc())
            else:
                query = query.order_by(order_column.asc())

            # 分页
            memories = query.offset(offset).limit(limit).all()

            return memories, total

        finally:
            session.close()

    def update_memory(
        self,
        memory_id: int,
        content: str = None,
        tags: List[str] = None
    ) -> bool:
        """
        更新笔记

        Args:
            memory_id: 笔记 ID
            content: 新内容（可选）
            tags: 新标签列表（可选）

        Returns:
            是否更新成功
        """
        session = self.get_session()
        try:
            import json

            memory = session.query(MemoryItem).filter_by(id=memory_id).first()
            if not memory:
                return False

            if content is not None:
                memory.content = content

            if tags is not None:
                memory.tags = json.dumps(tags, ensure_ascii=False)

            memory.updated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            session.commit()
            return True

        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()


# 全局实例
memory_manager = MemoryManager()

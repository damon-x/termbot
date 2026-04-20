"""
Text embedding computation client - Wrapper for external APIs.

Supports:
- Alibaba Cloud DashScope API (current)
- Future: OpenAI and other providers
"""
import os
from typing import List, Union

import numpy as np
from openai import OpenAI


class EmbeddingClient:
    """
    Text embedding computation client.

    Unified interface for embedding APIs,便于未来更换服务商
    """

    # 支持的服务商
    PROVIDER_DASHSCOPE = "dashscope"
    PROVIDER_OPENAI = "openai"

    def __init__(
        self,
        provider: str = PROVIDER_DASHSCOPE,
        api_key: str = None,
        base_url: str = None,
        model: str = None,
        dimensions: int = 1024
    ):
        """
        初始化嵌入客户端

        Args:
            provider: 服务商（dashscope | openai）
            api_key: API 密钥（默认从环境变量读取）
            base_url: API 基础 URL（覆盖默认值）
            model: 模型名称
            dimensions: 向量维度
        """
        self.provider = provider
        self.dimensions = dimensions

        if provider == self.PROVIDER_DASHSCOPE:
            # 阿里云 DashScope（使用 OpenAI 兼容接口）
            self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
            self.model = model or "text-embedding-v4"
            self.base_url = base_url or "https://dashscope.aliyuncs.com/compatible-mode/v1"

            if not self.api_key:
                raise ValueError("DASHSCOPE_API_KEY not found in environment or config")

            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

        elif provider == self.PROVIDER_OPENAI:
            # OpenAI（未来支持）
            self.api_key = api_key or os.getenv("OPENAI_API_KEY")
            self.model = model or "text-embedding-3-small"
            self.base_url = base_url

            if not self.api_key:
                raise ValueError("OPENAI_API_KEY not found in environment or config")

            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def embed(self, text: str) -> np.ndarray:
        """
        计算单个文本的嵌入向量

        Args:
            text: 输入文本

        Returns:
            向量数组 (dimensions,)

        Raises:
            RuntimeError: 如果 API 调用失败
        """
        if not text or not text.strip():
            raise ValueError("Input text cannot be empty")

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

        Raises:
            RuntimeError: 如果 API 调用失败
        """
        if not texts:
            return np.array([], dtype=np.float32).reshape(0, self.dimensions)

        # 过滤空文本
        valid_texts = [t for t in texts if t and t.strip()]
        if not valid_texts:
            return np.array([], dtype=np.float32).reshape(0, self.dimensions)

        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=valid_texts,
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
    """
    获取全局嵌入客户端单例

    Returns:
        全局 EmbeddingClient 实例
    """
    global _embedding_client
    if _embedding_client is None:
        from infrastructure.config.settings import settings
        config = settings.get("embedding", {})
        _embedding_client = EmbeddingClient(
            provider=config.get("provider", "dashscope"),
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            model=config.get("model"),
            dimensions=config.get("dimensions", 1024)
        )
    return _embedding_client

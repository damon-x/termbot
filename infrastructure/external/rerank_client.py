"""
Document reranking client - Wrapper for external APIs.

Supports:
- Alibaba Cloud DashScope API (current)
- Future: Other providers
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

            if not self.api_key:
                raise ValueError("DASHSCOPE_API_KEY not found in environment or config")

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

        Raises:
            RuntimeError: 如果 API 调用失败
        """
        if not query or not query.strip():
            raise ValueError("Query cannot be empty")

        if not documents:
            return []

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

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Rerank request failed: {e}")
        except Exception as e:
            raise RuntimeError(f"Rerank failed: {e}")

    def __repr__(self) -> str:
        return f"RerankClient(provider={self.provider}, model={self.model})"


# 全局单例
_rerank_client: RerankClient = None


def get_rerank_client() -> RerankClient:
    """
    获取全局重排序客户端单例

    Returns:
        全局 RerankClient 实例
    """
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

# 文件用途：Mem0 记忆模块，使用本地模式 + DeepSeek LLM

import os

from dotenv import load_dotenv

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

_mem0_client = None


def _get_mem0_client():
    """懒加载 Mem0 客户端（本地模式，使用 DeepSeek 作为 LLM）"""
    global _mem0_client
    if _mem0_client is not None:
        return _mem0_client

    try:
        from mem0 import Memory

        config = {
            "llm": {
                "provider": "openai",
                "config": {
                    "model": DEEPSEEK_MODEL,
                    "openai_api_key": DEEPSEEK_API_KEY,
                    "openai_api_base": "https://api.deepseek.com",
                    "temperature": 0.1,
                    "max_tokens": 2000,
                },
            },
            "embedder": {
                "provider": "openai",
                "config": {
                    "model": "text-embedding-3-small",
                    "openai_api_key": DEEPSEEK_API_KEY,
                    "openai_api_base": "https://api.deepseek.com",
                },
            },
            "vector_store": {
                "provider": "chroma",
                "config": {
                    "collection_name": "techpath_memories",
                    "path": str(
                        __import__("pathlib").Path(__file__).parent.parent / "data" / "chroma_db"
                    ),
                },
            },
        }
        _mem0_client = Memory.from_config(config)
    except Exception as e:
        # Mem0 初始化失败时返回 None，使用降级模式
        print(f"[memory] Mem0 初始化失败，使用降级模式：{e}")
        _mem0_client = _FallbackMemory()

    return _mem0_client


class _FallbackMemory:
    """Mem0 不可用时的降级内存实现（基于内存字典）"""

    def __init__(self):
        self._store: dict[str, list[dict]] = {}

    def add(self, content: str, user_id: str = "default", **kwargs):
        self._store.setdefault(user_id, []).append({"memory": content})
        return {"results": [{"memory": content}]}

    def search(self, query: str, user_id: str = "default", limit: int = 5, **kwargs):
        entries = self._store.get(user_id, [])
        # 简单关键词匹配
        matched = [e for e in entries if any(w in e["memory"] for w in query.split())]
        return {"results": (matched or entries)[:limit]}

    def get_all(self, user_id: str = "default", **kwargs):
        return {"results": self._store.get(user_id, [])}


# ============================================================
# 公开接口
# ============================================================

def save_memory(content: str, user_id: str = "default") -> None:
    """将一条内容存入 Mem0 记忆库"""
    if not content.strip():
        return
    try:
        client = _get_mem0_client()
        client.add(content, user_id=user_id)
    except Exception as e:
        print(f"[memory] 存储记忆失败：{e}")


def get_relevant_memory(query: str, user_id: str = "default") -> str:
    """
    检索与 query 相关的记忆，返回格式化字符串。

    Args:
        query: 查询内容
        user_id: 用户 ID

    Returns:
        格式化的记忆字符串，无记忆时返回空字符串
    """
    if not query.strip():
        return ""
    try:
        client = _get_mem0_client()
        result = client.search(query, user_id=user_id, limit=5)
        memories = result.get("results", [])
        if not memories:
            return ""
        lines = [f"- {m.get('memory', m.get('text', ''))}" for m in memories if m]
        return "【相关学习记忆】\n" + "\n".join(lines)
    except Exception as e:
        print(f"[memory] 检索记忆失败：{e}")
        return ""


def get_all_memories(user_id: str = "default") -> list:
    """
    获取用户所有记忆条目。

    Returns:
        记忆条目列表，每条为包含 'memory' 字段的字典
    """
    try:
        client = _get_mem0_client()
        result = client.get_all(user_id=user_id)
        return result.get("results", [])
    except Exception as e:
        print(f"[memory] 获取所有记忆失败：{e}")
        return []

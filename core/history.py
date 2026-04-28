# 文件用途：学习历史记录模块（Phase 4），负责保存学习记录并更新知识网络

import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from core.database import (
    get_knowledge_node_by_name,
    get_learning_histories,
    get_learning_history_by_id,
    save_knowledge_node,
    save_learning_history,
    update_knowledge_node,
)

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

_client = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
    return _client


def _extract_tags_via_llm(report_text: str) -> list[str]:
    """调用 DeepSeek 从报告内容中提取知识点标签列表"""
    if not DEEPSEEK_API_KEY:
        return []
    try:
        client = _get_client()
        prompt = (
            "从以下技术报告中提取最多10个核心知识点标签（简洁中文或英文技术名词，如：LoRA微调/扩散模型/Shader/ComfyUI）。\n\n"
            f"报告内容（前2000字）：\n{report_text[:2000]}\n\n"
            "严格返回JSON数组，不加其他内容：[\"标签1\", \"标签2\", ...]"
        )
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        raw = resp.choices[0].message.content.strip()
        match = re.search(r"\[.*?\]", raw, re.DOTALL)
        if match:
            return json.loads(match.group())[:10]
    except Exception as e:
        print(f"[history] 提取标签失败：{e}")
    return []


# ============================================================
# 核心函数
# ============================================================

def save_study_record(
    session_type: str,
    title: str,
    input_content: str,
    full_report: str,
    qa_history: list = None,
    knowledge_tags: list = None,
) -> int:
    """
    将完整学习记录存入 learning_history 表。

    Args:
        session_type: repo_analysis / topic_explain / learning_path / exam
        title: 记录标题
        input_content: 用户输入内容
        full_report: 完整报告 Markdown 文本
        qa_history: 问答记录列表（检验模式使用）
        knowledge_tags: 相关知识点标签；为 None 则自动提取

    Returns:
        记录 id
    """
    if knowledge_tags is None:
        knowledge_tags = _extract_tags_via_llm(full_report)

    history_id = save_learning_history(
        session_type=session_type,
        title=title,
        input_content=input_content,
        full_report=full_report,
        qa_history=qa_history or [],
        knowledge_tags=knowledge_tags,
    )
    return history_id


def get_history_list(session_type: str = None, limit: int = 50) -> list[dict]:
    """
    获取历史记录列表（不含完整报告）。

    Returns:
        每条包含 id / session_type / title / knowledge_tags / created_at
    """
    return get_learning_histories(session_type=session_type, limit=limit)


def get_history_detail(history_id: int) -> dict | None:
    """获取单条历史记录的完整内容（含 full_report 和 qa_history）"""
    return get_learning_history_by_id(history_id)


def extract_and_update_knowledge_nodes(history_id: int) -> list[dict]:
    """
    从历史记录中提取知识点，在 knowledge_nodes 表中新增或更新，并建立关联关系。

    Returns:
        新增/更新的知识点列表
    """
    record = get_learning_history_by_id(history_id)
    if not record:
        return []

    report_text = record.get("full_report", "")
    if not report_text or not DEEPSEEK_API_KEY:
        return []

    try:
        client = _get_client()
        prompt = f"""请分析以下技术学习报告，提取其中涉及的知识点，并建立关联关系。

报告内容（前3000字）：
{report_text[:3000]}

请识别 5-15 个核心知识点，每个知识点包含：
- name: 知识点名称（简洁，如"LoRA微调"、"扩散模型"、"Unity Shader"）
- category: 分类（渲染/AIGC/工具/编程/其他）
- description: 一句话描述（不超过50字）
- related: 与本知识点最相关的其他知识点名称列表（2-4个）

严格输出JSON数组，不加其他内容：
[{{"name": "知识点1", "category": "分类", "description": "描述", "related": ["关联1", "关联2"]}}, ...]"""

        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        raw = resp.choices[0].message.content.strip()
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if not match:
            return []
        nodes_data = json.loads(match.group())
    except Exception as e:
        print(f"[history] 提取知识节点失败：{e}")
        return []

    updated_nodes = []
    for node_info in nodes_data:
        name = node_info.get("name", "").strip()
        if not name:
            continue
        category = node_info.get("category", "其他")
        description = node_info.get("description", "")
        related = node_info.get("related", [])

        existing = get_knowledge_node_by_name(name)
        if existing:
            # 合并关联节点（去重）
            merged_related = list(dict.fromkeys(existing.get("related_nodes", []) + related))
            update_knowledge_node(
                name=name,
                category=category,
                description=description,
                related_nodes=merged_related[:10],
                source_history_ids=[history_id],
            )
            updated_nodes.append({"name": name, "action": "updated"})
        else:
            save_knowledge_node(
                name=name,
                category=category,
                description=description,
                related_nodes=related[:10],
                source_history_ids=[history_id],
                mastery_level=0,
            )
            updated_nodes.append({"name": name, "action": "created"})

    return updated_nodes


print("✅ T02 完成")

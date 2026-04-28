# 文件用途：Agent Loop 核心逻辑（Phase 1 + Phase 2），使用 LangChain 1.2+ create_agent + DeepSeek

import json
import os
import uuid
from typing import Any

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.messages import AIMessage, AnyMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI

from core.database import save_conversation, save_exam_session
from core.memory import get_relevant_memory, save_memory
from core.intel import analyze_jd_requirements
from core.tools import (
    import_text_content,
    import_video,
    read_github_repo,
    search_knowledge_base,
)

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

SYSTEM_PROMPT = """你是 TechPath 的学习检验助手，专门帮助 AI TA 求职者检验学习成果。

你有以下工具可以使用：
- read_github_repo：读取 GitHub 仓库的代码和文档
- import_text_content：导入文本或 URL 内容到知识库
- search_knowledge_base：在知识库中搜索相关内容
- import_video：导入 B 站视频内容（转录音频 + 分析画面）到知识库
- analyze_jd_requirements：分析 JD 数据，生成技能需求报告和 Gap 分析
- crawl_jd：爬取指定平台的 JD 数据

**检验流程：**
当用户要求检验某个知识点时：
1. 先用 search_knowledge_base 搜索知识库中的相关内容
2. 根据找到的内容，生成 3-5 道由浅入深的苏格拉底式追问
3. 追问要求：不给标准答案、逐步深入、结合实际应用场景
4. 每次用户回答后，评估其掌握程度（优秀/良好/需加强），给出针对性的下一个问题
5. 对话超过 10 轮或用户说"结束检验"时，生成掌握度报告

**视频导入：** 当用户提供 B 站链接时，调用 import_video 导入后再进行检验。

**岗位情报：** 当用户询问岗位需求时，调用 analyze_jd_requirements 分析数据库中的 JD 数据。

**掌握度报告格式：**
【掌握度报告】
总体评级：[优秀/良好/基础/需加强]
掌握的核心概念：...
薄弱点分析：...
建议深入学习的方向：...

**语言风格：** 使用中文，简洁专业，不过度鼓励，直接指出不足。
"""

# 会话消息历史（按 session_id 存储，in-memory）
_session_histories: dict[str, list[AnyMessage]] = {}
# 会话轮数计数
_session_round_counts: dict[str, int] = {}


def _crawl_jd_tool(platform: str, keyword: str) -> str:
    """爬取指定平台 JD 数据的包装函数（供 Agent 调用）"""
    from core.crawlers.bosszp import crawl_bosszp
    from core.crawlers.general import crawl_niuke, crawl_zhihu

    platform = platform.lower().strip()
    try:
        if platform in ("bosszp", "boss", "boss直聘"):
            results = crawl_bosszp(keyword=keyword, max_count=10)
        elif platform in ("niuke", "牛客"):
            results = crawl_niuke(keyword=keyword)
        elif platform in ("zhihu", "知乎"):
            results = crawl_zhihu(keyword=keyword)
        else:
            return f"不支持的平台：{platform}，可选：bosszp / niuke / zhihu"

        return f"爬取完成，共获取 {len(results)} 条 {platform} 数据。"
    except Exception as e:
        return f"爬取失败：{e}"


def _build_tools() -> list:
    """构建 LangChain 工具列表（Phase 1 + Phase 2）"""
    return [
        StructuredTool.from_function(
            func=read_github_repo,
            name="read_github_repo",
            description="读取 GitHub 仓库内容。输入参数：url（仓库完整 URL）。返回仓库名称、描述、README、文件树和关键代码文件。",
        ),
        StructuredTool.from_function(
            func=import_text_content,
            name="import_text_content",
            description="导入文本或 URL 内容到知识库。参数：content（文本内容或 URL），source_url（来源 URL，可选），title（标题，可选）。",
        ),
        StructuredTool.from_function(
            func=search_knowledge_base,
            name="search_knowledge_base",
            description="在知识库中搜索相关内容。参数：query（搜索关键词）。返回最多5条匹配结果。",
        ),
        StructuredTool.from_function(
            func=import_video,
            name="import_video",
            description="导入 B 站视频内容到知识库（转录音频 + 可选画面分析）。参数：url（B 站视频 URL），title（自定义标题，可选）。",
        ),
        StructuredTool.from_function(
            func=analyze_jd_requirements,
            name="analyze_jd_requirements",
            description="分析 JD 列表，提取技能频次、新关键词和 Gap 分析。参数：jd_list（JD 列表，可传空列表从数据库读取）。",
        ),
        StructuredTool.from_function(
            func=_crawl_jd_tool,
            name="crawl_jd",
            description="爬取指定平台的 JD 数据。参数：platform（bosszp/niuke/zhihu），keyword（搜索关键词）。",
        ),
    ]


def _build_agent(memory_context: str = ""):
    """构建 Agent 实例"""
    llm = ChatOpenAI(
    model=DEEPSEEK_MODEL,
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com",
    temperature=0.7,
    model_kwargs={
        "extra_body": {
            "thinking": {"type": "disabled"}
        }
    }
)

    system_content = SYSTEM_PROMPT
    if memory_context:
        system_content += f"\n\n{memory_context}"

    tools = _build_tools()
    agent = create_agent(
        model=llm,
        tools=tools,
        system_prompt=system_content,
    )
    return agent


def _extract_tool_calls(messages: list[AnyMessage]) -> list[dict]:
    """从消息列表中提取工具调用记录"""
    tool_calls = []
    # 构建 tool_call_id -> result 映射
    tool_results: dict[str, str] = {}
    for msg in messages:
        if isinstance(msg, ToolMessage):
            tool_results[msg.tool_call_id] = str(msg.content)[:500]

    for msg in messages:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                tool_calls.append({
                    "tool": tc["name"],
                    "input": tc["args"],
                    "output": tool_results.get(tc["id"], ""),
                })
    return tool_calls


def chat(
    message: str,
    session_id: str = "",
    memory_context: str = "",
) -> dict[str, Any]:
    """
    处理一次用户消息，返回 Agent 回复和工具调用信息。

    Args:
        message: 用户消息
        session_id: 会话 ID，为空时自动生成
        memory_context: 从 Mem0 检索到的相关记忆，注入系统提示

    Returns:
        {"reply": str, "tool_calls": list, "session_id": str, "report": str, "round_count": int}
    """
    if not session_id:
        session_id = str(uuid.uuid4())

    if session_id not in _session_histories:
        _session_histories[session_id] = []
        _session_round_counts[session_id] = 0

    if not memory_context:
        memory_context = get_relevant_memory(message)

    save_conversation(session_id=session_id, role="user", content=message)

    history = _session_histories[session_id]
    new_user_msg = HumanMessage(content=message)
    all_messages = history + [new_user_msg]

    try:
        agent = _build_agent(memory_context=memory_context)
        result = agent.invoke({"messages": all_messages})

        result_messages: list[AnyMessage] = result.get("messages", [])

        # 提取本次新增的消息（历史之后的部分）
        new_messages = result_messages[len(all_messages):]

        # 获取最后一条 AI 回复
        reply = ""
        for msg in reversed(new_messages):
            if isinstance(msg, AIMessage) and msg.content:
                reply = msg.content if isinstance(msg.content, str) else str(msg.content)
                break

        if not reply:
            reply = "（Agent 未生成文字回复）"

        # 提取工具调用
        tool_calls = _extract_tool_calls(new_messages)

        # 更新内存历史（保留完整消息链）
        _session_histories[session_id] = result_messages
        _session_round_counts[session_id] += 1
        round_count = _session_round_counts[session_id]

        save_conversation(
            session_id=session_id,
            role="assistant",
            content=reply,
            tool_calls_json=json.dumps(tool_calls, ensure_ascii=False),
        )

        report = ""
        if "【掌握度报告】" in reply:
            report = reply
            save_memory(
                f"检验报告（会话 {session_id[:8]}）：\n{report}",
                user_id="default",
            )
            save_exam_session(
                knowledge_item_ids=[],
                report_json=json.dumps({"report": report}, ensure_ascii=False),
            )

        return {
            "reply": reply,
            "tool_calls": tool_calls,
            "session_id": session_id,
            "report": report,
            "round_count": round_count,
        }

    except Exception as e:
        error_msg = f"Agent 处理出错：{e}"
        save_conversation(session_id=session_id, role="assistant", content=error_msg)
        return {
            "reply": error_msg,
            "tool_calls": [],
            "session_id": session_id,
            "report": "",
            "round_count": _session_round_counts.get(session_id, 0),
        }


def reset_session(session_id: str) -> None:
    """清除指定会话的内存历史"""
    _session_histories.pop(session_id, None)
    _session_round_counts.pop(session_id, None)

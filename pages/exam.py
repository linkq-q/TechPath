# 文件用途：检验对话页，实现苏格拉底式追问、工具调用展示、掌握度报告

import uuid

import streamlit as st

from core.agent import chat, reset_session
from core.database import get_all_knowledge_items
from core.memory import get_all_memories


def render() -> None:
    """渲染检验对话页面"""
    st.title("学习检验")
    st.markdown("选择知识点开始检验，或直接输入想检验的内容。")

    # ---- Session State 初始化 ----
    if "exam_session_id" not in st.session_state:
        st.session_state.exam_session_id = str(uuid.uuid4())
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []
    if "tool_call_count" not in st.session_state:
        st.session_state.tool_call_count = 0
    if "exam_finished" not in st.session_state:
        st.session_state.exam_finished = False
    if "report_content" not in st.session_state:
        st.session_state.report_content = ""

    # ---- 侧边栏：会话统计 + 记忆摘要 ----
    with st.sidebar:
        st.markdown("### 本次会话统计")
        round_count = len([m for m in st.session_state.chat_history if m[0] == "user"])
        st.metric("对话轮数", round_count)
        st.metric("工具调用次数", st.session_state.tool_call_count)

        if st.button("重置会话", use_container_width=True):
            reset_session(st.session_state.exam_session_id)
            st.session_state.exam_session_id = str(uuid.uuid4())
            st.session_state.chat_history = []
            st.session_state.tool_call_count = 0
            st.session_state.exam_finished = False
            st.session_state.report_content = ""
            st.rerun()

        st.markdown("---")
        st.markdown("### 记忆摘要")
        try:
            memories = get_all_memories()
        except Exception:
            memories = []
        if memories:
            for m in reversed(memories[-3:]):
                text = m.get("memory", m.get("text", ""))
                if text:
                    st.markdown(f"<small style='color:#8b949e'>- {text[:100]}</small>", unsafe_allow_html=True)
        else:
            st.markdown("<small style='color:#8b949e'>暂无记忆</small>", unsafe_allow_html=True)

    # ---- 页面顶部：知识点选择区域 ----
    items = get_all_knowledge_items()

    if not items:
        st.warning("知识库为空，请先在知识库或学习中心导入学习内容。")
    else:
        st.markdown("### 快速开始检验")

        # 获取所有标签供筛选
        all_tags: list[str] = []
        for item in items:
            for tag in item.get("tags", []):
                if tag and tag not in all_tags:
                    all_tags.append(tag)
        all_tags.sort()

        col_tag, col_select, col_btn = st.columns([2, 3, 1])

        with col_tag:
            selected_tag = st.selectbox(
                "按技术标签筛选",
                options=["全部"] + all_tags,
                key="exam_tag_filter",
            )

        filtered_items = items if selected_tag == "全部" else [
            i for i in items
            if selected_tag in i.get("tags", [])
        ]

        with col_select:
            selected_title = st.selectbox(
                "从知识库选择知识点",
                options=["（手动输入）"] + [i["title"] for i in filtered_items],
                key="kb_select",
            )

        with col_btn:
            st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
            start_btn = st.button("开始检验", use_container_width=True, key="btn_start_exam")

        if start_btn and selected_title != "（手动输入）":
            _send_message(f"请检验我对「{selected_title}」的理解")

        st.markdown("---")

    # ---- 处理来自其他页面的预填充消息 ----
    prefill = st.session_state.pop("prefill_exam_message", None)
    if prefill and not st.session_state.chat_history:
        _send_message(prefill)

    # ---- 最近记忆摘要（可展开） ----
    try:
        memories = get_all_memories()
    except Exception:
        memories = []
    if memories:
        with st.expander("最近学习记忆（最新3条）", expanded=False):
            for m in reversed(memories[-3:]):
                text = m.get("memory", m.get("text", ""))
                if text:
                    st.markdown(f"- {text[:150]}")

    # ---- 对话区域 ----
    # 超过20条时折叠早期对话
    history = st.session_state.chat_history
    if len(history) > 20:
        with st.expander(f"早期对话（共 {len(history) - 20} 条，点击展开）", expanded=False):
            for role, content, tool_calls in history[:-20]:
                _render_message(role, content, tool_calls)
        recent_history = history[-20:]
    else:
        recent_history = history

    for role, content, tool_calls in recent_history:
        _render_message(role, content, tool_calls)

    # ---- 输入框 ----
    if not st.session_state.exam_finished:
        user_input = st.chat_input("输入消息，或输入「结束检验」生成报告...")
        if user_input:
            _send_message(user_input)
    else:
        st.success("检验已结束，查看上方的掌握度报告。点击侧边栏「重置会话」开始新的检验。")


def _render_message(role: str, content: str, tool_calls: list) -> None:
    """渲染单条对话消息"""
    if role == "user":
        with st.chat_message("user"):
            st.markdown(content)
    else:
        with st.chat_message("assistant"):
            if "【掌握度报告】" in content:
                st.markdown(
                    f"""<div style="
                        background-color:#1a3a1a;
                        border-left: 4px solid #3fb950;
                        padding: 12px 16px;
                        border-radius: 6px;
                        color: #c9d1d9;
                        white-space: pre-wrap;
                    ">{content}</div>""",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(content)

            if tool_calls:
                with st.expander(f"工具调用（{len(tool_calls)} 次）", expanded=False):
                    for tc in tool_calls:
                        st.markdown(f"**工具：** `{tc['tool']}`")
                        if isinstance(tc.get("input"), dict):
                            st.code(
                                "\n".join(f"{k}: {v}" for k, v in tc["input"].items()),
                                language="yaml",
                            )
                        else:
                            st.code(str(tc.get("input", "")))
                        st.markdown(
                            f"<small style='color:#8b949e'>结果：{str(tc.get('output',''))[:200]}</small>",
                            unsafe_allow_html=True,
                        )


def _send_message(user_input: str) -> None:
    """发送用户消息并获取 Agent 回复"""
    session_id = st.session_state.exam_session_id

    st.session_state.chat_history.append(("user", user_input, []))

    with st.status("Agent 思考中...", expanded=True) as status:
        st.write(f"用户消息：{user_input[:80]}")

        try:
            result = chat(
                message=user_input,
                session_id=session_id,
            )
        except Exception as e:
            status.update(label="❌ 调用失败", state="error")
            err_msg = str(e)
            if "api" in err_msg.lower() or "key" in err_msg.lower():
                st.error("API调用失败，请检查网络连接和API Key配置")
            elif "connect" in err_msg.lower() or "timeout" in err_msg.lower():
                st.error("网络连接失败，请检查网络后重试")
            else:
                st.error(f"调用失败，请稍后重试")
            print(f"[exam] Agent 调用出错：{e}")
            return

        tool_calls = result.get("tool_calls", [])
        if tool_calls:
            for tc in tool_calls:
                st.write(f"调用工具：`{tc['tool']}`")

        status.update(label="回复生成完成", state="complete", expanded=False)

    st.session_state.tool_call_count += len(tool_calls)

    reply = result.get("reply", "")
    report = result.get("report", "")

    st.session_state.chat_history.append(("assistant", reply, tool_calls))

    if report or "【掌握度报告】" in reply:
        st.session_state.exam_finished = True
        st.session_state.report_content = report or reply

    st.rerun()

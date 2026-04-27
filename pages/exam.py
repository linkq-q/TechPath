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
        st.session_state.chat_history = []  # [(role, content, tool_calls)]
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
        st.markdown("### 快速开始检验")
        items = get_all_knowledge_items()
        if items:
            selected_title = st.selectbox(
                "从知识库选择",
                options=["（手动输入）"] + [i["title"] for i in items],
                key="kb_select",
            )
            if selected_title != "（手动输入）" and st.button("开始检验此内容", use_container_width=True):
                _send_message(f"请检验我对「{selected_title}」的理解")
        else:
            st.info("知识库为空，请先导入内容")

    # ---- 页面顶部：最近记忆摘要 ----
    memories = get_all_memories()
    if memories:
        recent = memories[-3:]
        with st.expander("最近学习记忆（最新3条）", expanded=False):
            for m in reversed(recent):
                text = m.get("memory", m.get("text", ""))
                if text:
                    st.markdown(f"- {text[:150]}")

    # ---- 对话区域 ----
    st.markdown("---")

    # 展示历史消息
    for role, content, tool_calls in st.session_state.chat_history:
        if role == "user":
            with st.chat_message("user"):
                st.markdown(content)
        else:
            with st.chat_message("assistant"):
                # 检测是否包含掌握度报告
                if "【掌握度报告】" in content:
                    # 报告用绿色高亮展示
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

                # 展示工具调用（如有）
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

    # ---- 输入框 ----
    if not st.session_state.exam_finished:
        user_input = st.chat_input("输入消息，或输入「结束检验」生成报告...")
        if user_input:
            _send_message(user_input)
    else:
        st.success("检验已结束，查看上方的掌握度报告。点击侧边栏「重置会话」开始新的检验。")


def _send_message(user_input: str) -> None:
    """发送用户消息并获取 Agent 回复"""
    session_id = st.session_state.exam_session_id

    # 立即显示用户消息
    st.session_state.chat_history.append(("user", user_input, []))

    with st.status("Agent 思考中...", expanded=True) as status:
        st.write(f"用户消息：{user_input[:80]}")

        result = chat(
            message=user_input,
            session_id=session_id,
        )

        tool_calls = result.get("tool_calls", [])
        if tool_calls:
            for tc in tool_calls:
                st.write(f"调用工具：`{tc['tool']}`")

        status.update(label="回复生成完成", state="complete", expanded=False)

    # 更新统计
    st.session_state.tool_call_count += len(tool_calls)

    reply = result.get("reply", "")
    report = result.get("report", "")

    # 保存 assistant 消息
    st.session_state.chat_history.append(("assistant", reply, tool_calls))

    if report or "【掌握度报告】" in reply:
        st.session_state.exam_finished = True
        st.session_state.report_content = report or reply

    st.rerun()

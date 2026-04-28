# 文件用途：学习历史页面（Phase 4），展示完整学习记录和问答历史

import json

import streamlit as st

from core.history import get_history_detail, get_history_list

# 会话类型对应的图标和中文名
SESSION_TYPE_MAP = {
    "repo_analysis": ("📦", "项目解读"),
    "topic_explain": ("📖", "知识点讲解"),
    "learning_path": ("🗺️", "学习路径"),
    "exam": ("🎯", "检验记录"),
}


def render():
    st.title("📚 学习历史")

    # ---- 统计数据 ----
    all_records = get_history_list(limit=200)
    total = len(all_records)
    all_tags = []
    for r in all_records:
        all_tags.extend(r.get("knowledge_tags", []))
    unique_tags = len(set(all_tags))
    latest_time = all_records[0]["created_at"][:10] if all_records else "暂无记录"

    col1, col2, col3 = st.columns(3)
    col1.metric("总学习次数", total)
    col2.metric("涉及知识点", unique_tags)
    col3.metric("最近学习", latest_time)

    st.markdown("---")

    # ---- 左侧筛选栏 ----
    with st.sidebar:
        st.markdown("### 筛选")
        filter_type = st.radio(
            "按类型过滤",
            options=["全部", "项目解读", "知识点讲解", "学习路径", "检验记录"],
            index=0,
        )

    # 将中文类型映射回英文 key
    type_reverse_map = {v: k for k, (_, v) in SESSION_TYPE_MAP.items()}
    filter_key = type_reverse_map.get(filter_type, None)

    # ---- 加载记录 ----
    records = get_history_list(session_type=filter_key, limit=50)

    if not records:
        st.info("暂无学习历史记录。完成带学功能后，记录会自动保存在这里。")
        return

    # ---- 历史列表 ----
    for record in records:
        session_type = record.get("session_type", "")
        icon, type_name = SESSION_TYPE_MAP.get(session_type, ("📝", session_type))
        title = record.get("title", "未命名")
        tags = record.get("knowledge_tags", [])
        created_at = record.get("created_at", "")[:16].replace("T", " ")
        history_id = record["id"]

        # 每条记录用 expander 折叠展示
        header = f"{icon} **{title}** — {type_name} · {created_at}"
        with st.expander(header, expanded=False):
            # 知识点标签
            if tags:
                tag_html = " ".join(
                    f'<span style="background:#21262d;color:#58a6ff;padding:2px 8px;border-radius:10px;margin:2px;font-size:12px">{t}</span>'
                    for t in tags[:8]
                )
                st.markdown(tag_html, unsafe_allow_html=True)
                st.markdown("")

            # 加载完整内容（点击展开时才加载）
            if st.button(f"加载完整内容", key=f"load_{history_id}"):
                st.session_state[f"loaded_{history_id}"] = True

            if st.session_state.get(f"loaded_{history_id}"):
                detail = get_history_detail(history_id)
                if detail:
                    full_report = detail.get("full_report", "")
                    qa_history = detail.get("qa_history", [])

                    if full_report:
                        st.markdown("#### 完整报告")
                        st.markdown(full_report)

                    # 检验记录：展示完整问答历史
                    if session_type == "exam" and qa_history:
                        st.markdown("#### 问答记录")
                        for i, qa in enumerate(qa_history):
                            role = qa.get("role", "")
                            content = qa.get("content", "")
                            if role == "assistant":
                                st.markdown(
                                    f'<div style="background:#1a2a3a;padding:8px 12px;border-radius:6px;margin:4px 0">'
                                    f'<strong style="color:#58a6ff">🤖 助手</strong><br>{content}</div>',
                                    unsafe_allow_html=True,
                                )
                            elif role == "user":
                                st.markdown(
                                    f'<div style="background:#161b22;padding:8px 12px;border-radius:6px;margin:4px 0">'
                                    f'<strong style="color:#3fb950">👤 我</strong><br>{content}</div>',
                                    unsafe_allow_html=True,
                                )
                else:
                    st.error("加载失败，记录可能已被删除。")

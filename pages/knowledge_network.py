# 文件用途：知识网络页面（Phase 4），展示可交互知识图谱和学习推荐

import streamlit as st
import streamlit.components.v1 as components
from pathlib import Path

from core.knowledge_graph import (
    build_knowledge_graph,
    export_graph_html,
    get_related_topics,
    suggest_next_topic,
)
from core.history import get_history_list

GRAPH_HTML_PATH = Path(__file__).parent.parent / "data" / "knowledge_graph.html"


def _format_mastery_bar(level: int) -> str:
    """生成掌握度进度条 HTML"""
    if level >= 60:
        color = "#3fb950"
    elif level >= 20:
        color = "#d29922"
    else:
        color = "#f85149"
    return (
        f'<div style="background:#21262d;border-radius:4px;height:8px;width:100%">'
        f'<div style="background:{color};border-radius:4px;height:8px;width:{level}%"></div>'
        f'</div><small style="color:#8b949e">{level}%</small>'
    )


def render():
    st.title("🕸️ 知识网络")

    # ---- 构建图数据 ----
    graph_data = build_knowledge_graph()
    stats = graph_data.get("stats", {})
    total_nodes = stats.get("total_nodes", 0)
    mastered_nodes = stats.get("mastered_nodes", 0)
    pending_nodes = total_nodes - mastered_nodes

    # ---- 顶部统计 ----
    col1, col2, col3 = st.columns(3)
    col1.metric("总知识点", total_nodes)
    col2.metric("已掌握（>60%）", mastered_nodes)
    col3.metric("待学习", pending_nodes)

    if total_nodes == 0:
        st.info("知识网络还是空的。请先在学习中心完成一次「项目解读」或「知识点讲解」，系统会自动提取并生成知识节点。")

        if st.button("🔄 刷新知识网络（从历史记录重建）"):
            _rebuild_graph_from_history()
        return

    # ---- 图例说明 ----
    st.markdown(
        '<div style="display:flex;gap:16px;margin-bottom:8px">'
        '<span style="color:#f85149">⬤ 未学（<20%）</span>'
        '<span style="color:#d29922">⬤ 学过（20-60%）</span>'
        '<span style="color:#3fb950">⬤ 已掌握（>60%）</span>'
        '<span style="color:#8b949e;font-size:12px">节点大小 = JD 出现频率</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ---- 主区域：左图 + 右侧详情 ----
    left_col, right_col = st.columns([2, 1])

    with left_col:
        # 生成 pyvis HTML
        html_path = export_graph_html(str(GRAPH_HTML_PATH))
        if html_path and Path(html_path).exists():
            html_content = Path(html_path).read_text(encoding="utf-8")
            components.html(html_content, height=620, scrolling=False)
        else:
            st.warning("知识网络图生成失败（可能缺少 pyvis 库）。运行 `pip install pyvis` 后重试。")
            # 降级显示表格
            nodes = graph_data.get("nodes", [])
            for node in sorted(nodes, key=lambda x: x["mastery_level"], reverse=True)[:20]:
                icon = "🟢" if node["mastery_level"] >= 60 else ("🟡" if node["mastery_level"] >= 20 else "🔴")
                st.markdown(
                    f"{icon} **{node['name']}** ({node['category']}) — 掌握度: {node['mastery_level']}%"
                )

    with right_col:
        st.markdown("### 节点详情")

        # 节点搜索/选择
        nodes = graph_data.get("nodes", [])
        node_names = [n["name"] for n in nodes]
        selected_node = st.selectbox("选择知识点查看详情", options=[""] + node_names, index=0)

        if selected_node:
            node_data = next((n for n in nodes if n["name"] == selected_node), None)
            if node_data:
                st.markdown(f"**分类**：{node_data['category']}")
                st.markdown(f"**描述**：{node_data['description'] or '暂无描述'}")
                st.markdown("**掌握度**：")
                st.markdown(_format_mastery_bar(node_data["mastery_level"]), unsafe_allow_html=True)

                # 相关知识点
                related = get_related_topics(selected_node, depth=1)
                if related:
                    st.markdown("**关联知识点**：")
                    for r in related[:5]:
                        icon = "🟢" if r["mastery_level"] >= 60 else ("🟡" if r["mastery_level"] >= 20 else "🔴")
                        st.markdown(f"{icon} {r['name']} ({r['category']})")

                # 相关学习历史
                st.markdown("**相关学习记录**：")
                histories = get_history_list(limit=50)
                related_histories = [
                    h for h in histories
                    if selected_node in h.get("knowledge_tags", [])
                ]
                if related_histories:
                    for h in related_histories[:3]:
                        type_icons = {"repo_analysis": "📦", "topic_explain": "📖",
                                      "learning_path": "🗺️", "exam": "🎯"}
                        icon = type_icons.get(h["session_type"], "📝")
                        st.markdown(f"{icon} {h['title'][:30]}")
                else:
                    st.markdown("暂无相关记录")

                # 跳转到学习中心按钮
                st.markdown("---")
                if st.button(f"📖 去学习「{selected_node}」", use_container_width=True):
                    st.session_state.current_page = "study"
                    st.session_state.prefill_topic = selected_node
                    st.rerun()

        st.markdown("---")
        st.markdown("### 🎯 建议下一步学习")
        suggestions = suggest_next_topic()
        if suggestions:
            for s in suggestions:
                with st.container():
                    freq_text = f"（JD频次: {s['jd_frequency']}）" if s['jd_frequency'] > 0 else ""
                    st.markdown(f"**{s['name']}** {freq_text}")
                    st.markdown(f"<small style='color:#8b949e'>{s['reason']}</small>", unsafe_allow_html=True)
                    if st.button(f"去学习", key=f"suggest_{s['name']}", use_container_width=True):
                        st.session_state.current_page = "study"
                        st.session_state.prefill_topic = s["name"]
                        st.rerun()
        else:
            st.info("暂无推荐，继续学习后会自动生成。")

    st.markdown("---")
    col_rebuild, _ = st.columns([1, 3])
    with col_rebuild:
        if st.button("🔄 刷新知识网络", use_container_width=True):
            _rebuild_graph_from_history()


def _rebuild_graph_from_history():
    """从所有历史记录重新提取并更新知识节点"""
    from core.history import extract_and_update_knowledge_nodes, get_history_list

    with st.spinner("正在从历史记录重建知识网络..."):
        histories = get_history_list(limit=100)
        updated_count = 0
        for h in histories:
            try:
                nodes = extract_and_update_knowledge_nodes(h["id"])
                updated_count += len(nodes)
            except Exception:
                pass
    st.success(f"知识网络已更新，共处理 {updated_count} 个知识节点。")
    st.rerun()

# 文件用途：知识网络页面（Phase 4 + Phase 5），展示可交互知识图谱和学习推荐

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
    try:
        graph_data = build_knowledge_graph()
    except Exception as e:
        st.error(f"知识网络构建失败：{e}")
        graph_data = {"nodes": [], "edges": [], "stats": {}}

    stats = graph_data.get("stats", {})
    total_nodes = stats.get("total_nodes", 0)
    mastered_nodes = stats.get("mastered_nodes", 0)
    pending_nodes = total_nodes - mastered_nodes

    # ---- 顶部统计 ----
    col1, col2, col3, col_rebuild = st.columns([1, 1, 1, 1])
    col1.metric("总知识点", total_nodes)
    col2.metric("已掌握（>60%）", mastered_nodes)
    col3.metric("待学习", pending_nodes)
    with col_rebuild:
        st.markdown("<div style='margin-top:8px'></div>", unsafe_allow_html=True)
        if st.button("🔄 强制重建", use_container_width=True, help="清空旧数据，从历史记录重新提取知识节点"):
            _rebuild_graph_from_history()
            return

    # ---- 无节点时显示友好提示 ----
    if total_nodes == 0:
        st.info("暂无知识节点，请先在学习中心学习一个知识点。\n\n"
                "学习完成后，点击「强制重建」按钮从历史记录中提取知识节点。")
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
        _render_graph(graph_data)

    with right_col:
        _render_right_panel(graph_data)


def _render_graph(graph_data: dict):
    """渲染知识图谱，pyvis 失败时降级为列表展示"""
    nodes = graph_data.get("nodes", [])

    # 尝试 pyvis 渲染
    try:
        GRAPH_HTML_PATH.parent.mkdir(parents=True, exist_ok=True)
        html_path = export_graph_html(str(GRAPH_HTML_PATH))
        if html_path and Path(html_path).exists():
            html_content = Path(html_path).read_text(encoding="utf-8")
            if len(html_content) > 500:
                components.html(html_content, height=620, scrolling=False)
                return
    except Exception as e:
        print(f"[knowledge_network] pyvis 渲染失败，降级为列表展示：{e}")

    # 降级：st.graphviz_chart（如果有 graphviz）
    try:
        import graphviz
        dot = graphviz.Digraph()
        dot.attr(bgcolor="#0d1117")
        for node in nodes[:30]:
            mastery = node["mastery_level"]
            color = "#3fb950" if mastery >= 60 else ("#d29922" if mastery >= 20 else "#f85149")
            dot.node(node["name"], style="filled", fillcolor=color, fontcolor="#c9d1d9")
        for edge in graph_data.get("edges", [])[:50]:
            dot.edge(edge["source"], edge["target"])
        st.graphviz_chart(dot)
        return
    except Exception:
        pass

    # 最终降级：纯文字列表
    st.markdown("**知识图谱（文字模式，缺少 pyvis 库）**")
    st.caption("运行 `pip install pyvis` 后重启可启用可视化图谱")
    for node in sorted(nodes, key=lambda x: x["mastery_level"], reverse=True)[:30]:
        icon = "🟢" if node["mastery_level"] >= 60 else ("🟡" if node["mastery_level"] >= 20 else "🔴")
        st.markdown(f"{icon} **{node['name']}** ({node['category']}) — 掌握度: {node['mastery_level']}%")


def _render_right_panel(graph_data: dict):
    """渲染右侧节点详情和推荐面板"""
    st.markdown("### 节点详情")

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

            related = get_related_topics(selected_node, depth=1)
            if related:
                st.markdown("**关联知识点**：")
                for r in related[:5]:
                    icon = "🟢" if r["mastery_level"] >= 60 else ("🟡" if r["mastery_level"] >= 20 else "🔴")
                    st.markdown(f"{icon} {r['name']} ({r['category']})")

            st.markdown("**相关学习记录**：")
            try:
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
            except Exception:
                st.markdown("暂无相关记录")

            st.markdown("---")
            if st.button(f"📖 去学习「{selected_node}」", use_container_width=True):
                st.session_state.current_page = "study"
                st.session_state.prefill_topic = selected_node
                st.rerun()

    st.markdown("---")
    st.markdown("### 🎯 建议下一步学习")
    try:
        suggestions = suggest_next_topic()
    except Exception:
        suggestions = []

    if suggestions:
        for s in suggestions:
            freq_text = f"（JD频次: {s['jd_frequency']}）" if s['jd_frequency'] > 0 else ""
            st.markdown(f"**{s['name']}** {freq_text}")
            st.markdown(f"<small style='color:#8b949e'>{s['reason']}</small>", unsafe_allow_html=True)
            if st.button(f"去学习", key=f"suggest_{s['name']}", use_container_width=True):
                st.session_state.current_page = "study"
                st.session_state.prefill_topic = s["name"]
                st.rerun()
    else:
        st.info("暂无推荐，继续学习后会自动生成。")


def _rebuild_graph_from_history():
    """从所有历史记录重新提取并更新知识节点"""
    from core.history import extract_and_update_knowledge_nodes, get_history_list

    with st.spinner("正在从历史记录重建知识网络..."):
        try:
            histories = get_history_list(limit=100)
            if not histories:
                st.warning("暂无历史记录，请先在学习中心学习一个知识点。")
                return
            updated_count = 0
            for h in histories:
                try:
                    nodes = extract_and_update_knowledge_nodes(h["id"])
                    updated_count += len(nodes)
                except Exception as e:
                    print(f"[knowledge_network] 处理历史记录 {h['id']} 失败：{e}")

            # 删除旧 HTML 缓存，强制重新生成
            if GRAPH_HTML_PATH.exists():
                GRAPH_HTML_PATH.unlink()

        except Exception as e:
            st.error(f"重建失败：{e}")
            return

    st.success(f"知识网络已更新，共处理 {updated_count} 个知识节点。")
    st.rerun()

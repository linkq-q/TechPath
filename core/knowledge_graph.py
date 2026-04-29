# 文件用途：知识网络构建模块（Phase 4），使用 networkx + pyvis 生成可交互知识图谱

import json
import os
from pathlib import Path

from core.database import get_all_knowledge_nodes, get_all_jd_records

# 输出 HTML 的默认路径
DEFAULT_HTML_PATH = Path(__file__).parent.parent / "data" / "knowledge_graph.html"


def _get_jd_frequency() -> dict[str, int]:
    """统计各技能在 JD 记录中出现的频次，返回 {skill_name: count}"""
    freq: dict[str, int] = {}
    try:
        records = get_all_jd_records(limit=500)
        for r in records:
            skills = r.get("skills_extracted", [])
            for s in skills:
                name = s.strip().lower()
                freq[name] = freq.get(name, 0) + 1
    except Exception as e:
        print(f"[graph] 获取 JD 频次失败：{e}")
    return freq


def build_knowledge_graph() -> dict:
    """
    从 knowledge_nodes 表构建 networkx 图对象，返回节点/边/统计数据。

    Returns:
        {
            "nodes": [{"name", "category", "mastery_level", "description"}, ...],
            "edges": [{"source", "target", "weight"}, ...],
            "stats": {"total_nodes", "total_edges", "mastered_nodes"}
        }
    """
    try:
        import networkx as nx
    except ImportError:
        return {"nodes": [], "edges": [], "stats": {"total_nodes": 0, "total_edges": 0, "mastered_nodes": 0}}

    nodes_data = get_all_knowledge_nodes()
    G = nx.Graph()

    for node in nodes_data:
        G.add_node(
            node["name"],
            category=node["category"],
            mastery_level=node["mastery_level"],
            description=node["description"],
        )

    # 建立边（双向关联）
    for node in nodes_data:
        for related_name in node.get("related_nodes", []):
            if related_name and related_name != node["name"]:
                if G.has_node(related_name):
                    if not G.has_edge(node["name"], related_name):
                        G.add_edge(node["name"], related_name, weight=1)
                else:
                    # 关联节点不存在，仍建立边（以备日后添加节点）
                    G.add_node(related_name, category="其他", mastery_level=0, description="")
                    G.add_edge(node["name"], related_name, weight=1)

    nodes_list = [
        {
            "name": n,
            "category": G.nodes[n].get("category", ""),
            "mastery_level": G.nodes[n].get("mastery_level", 0),
            "description": G.nodes[n].get("description", ""),
        }
        for n in G.nodes
    ]
    edges_list = [
        {"source": u, "target": v, "weight": data.get("weight", 1)}
        for u, v, data in G.edges(data=True)
    ]
    mastered = sum(1 for n in nodes_list if n["mastery_level"] >= 60)

    return {
        "nodes": nodes_list,
        "edges": edges_list,
        "stats": {
            "total_nodes": G.number_of_nodes(),
            "total_edges": G.number_of_edges(),
            "mastered_nodes": mastered,
        },
    }


def get_related_topics(topic: str, depth: int = 2) -> list[dict]:
    """
    找到指定知识点的关联知识点（BFS depth 层）。

    Returns:
        关联知识点列表，按关联层级排序
    """
    try:
        import networkx as nx
    except ImportError:
        return []

    nodes_data = get_all_knowledge_nodes()
    name_to_data = {n["name"]: n for n in nodes_data}

    G = nx.Graph()
    for node in nodes_data:
        G.add_node(node["name"])
        for r in node.get("related_nodes", []):
            if r:
                G.add_edge(node["name"], r)

    if topic not in G:
        return []

    result = []
    visited = {topic}
    queue = [(topic, 0)]
    while queue:
        current, cur_depth = queue.pop(0)
        if cur_depth >= depth:
            continue
        for neighbor in G.neighbors(current):
            if neighbor not in visited:
                visited.add(neighbor)
                node_info = name_to_data.get(neighbor, {"name": neighbor, "category": "", "mastery_level": 0})
                result.append({
                    "name": neighbor,
                    "depth": cur_depth + 1,
                    "category": node_info.get("category", ""),
                    "mastery_level": node_info.get("mastery_level", 0),
                })
                queue.append((neighbor, cur_depth + 1))

    result.sort(key=lambda x: x["depth"])
    return result


def suggest_next_topic(current_mastery: dict = None) -> list[dict]:
    """
    根据已掌握知识点推荐下一步学习的知识点（最多5个）。

    Returns:
        [{"name", "reason", "jd_frequency"}, ...]
    """
    nodes_data = get_all_knowledge_nodes()
    if not nodes_data:
        return []

    jd_freq = _get_jd_frequency()
    name_to_data = {n["name"]: n for n in nodes_data}

    # 已有关联但 mastery_level < 20 的节点优先
    suggestions = []
    for node in nodes_data:
        if node["mastery_level"] >= 20:
            # 检查其未学习的关联节点
            for related in node.get("related_nodes", []):
                related_data = name_to_data.get(related)
                if related_data and related_data["mastery_level"] < 20:
                    freq = jd_freq.get(related.lower(), 0)
                    suggestions.append({
                        "name": related,
                        "reason": f"与已学「{node['name']}」强关联",
                        "jd_frequency": freq,
                    })

    # 补充 JD 高频但完全未学习的节点
    not_started = [n for n in nodes_data if n["mastery_level"] < 5]
    for node in sorted(not_started, key=lambda x: jd_freq.get(x["name"].lower(), 0), reverse=True):
        freq = jd_freq.get(node["name"].lower(), 0)
        if not any(s["name"] == node["name"] for s in suggestions):
            suggestions.append({
                "name": node["name"],
                "reason": "JD 高频技能，尚未学习",
                "jd_frequency": freq,
            })

    # 去重并按 jd_frequency 排序，取前5
    seen = set()
    deduped = []
    for s in suggestions:
        if s["name"] not in seen:
            seen.add(s["name"])
            deduped.append(s)

    deduped.sort(key=lambda x: x["jd_frequency"], reverse=True)
    return deduped[:5]


def export_graph_html(output_path: str = None) -> str:
    """
    使用 pyvis 生成可交互的知识网络 HTML 文件。

    节点颜色：红=未学（mastery<20）/ 橙=学过（20-60）/ 绿=已掌握（>60）
    节点大小：按 JD 频次（高频更大）
    鼠标悬停显示描述

    Returns:
        生成的 HTML 文件路径
    """
    if output_path is None:
        output_path = str(DEFAULT_HTML_PATH)

    try:
        from pyvis.network import Network
    except ImportError:
        return ""

    graph_data = build_knowledge_graph()
    jd_freq = _get_jd_frequency()

    net = Network(
        height="600px",
        width="100%",
        bgcolor="#0d1117",
        font_color="#c9d1d9",
        directed=False,
    )
    net.set_options("""
    {
      "nodes": {
        "borderWidth": 2,
        "shadow": true
      },
      "edges": {
        "color": {"color": "#30363d"},
        "smooth": {"type": "continuous"}
      },
      "physics": {
        "barnesHut": {
          "gravitationalConstant": -8000,
          "springLength": 120
        }
      },
      "interaction": {
        "hover": true,
        "tooltipDelay": 200
      }
    }
    """)

    for node in graph_data["nodes"]:
        mastery = node["mastery_level"]
        # 颜色
        if mastery >= 60:
            color = "#3fb950"  # 绿色：已掌握
        elif mastery >= 20:
            color = "#d29922"  # 橙色：学过
        else:
            color = "#f85149"  # 红色：未学

        # 大小（基于 JD 频次，最小15最大45）
        freq = jd_freq.get(node["name"].lower(), 0)
        size = min(15 + freq * 3, 45)

        tooltip = f"{node['name']}\n分类：{node['category']}\n掌握度：{mastery}%\n{node['description']}"
        net.add_node(
            node["name"],
            label=node["name"],
            title=tooltip,
            color=color,
            size=size,
        )

    for edge in graph_data["edges"]:
        net.add_edge(edge["source"], edge["target"])

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    net.save_graph(output_path)
    return output_path


print("[knowledge_graph] 模块加载完成")

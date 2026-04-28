# 文件用途：竞品监测页面（Phase 3），展示 B站作品集采集、评级分析和「我的对标」功能

import json
from collections import Counter

import streamlit as st


def render():
    """渲染竞品监测页面"""
    st.title("🏆 竞品监测")
    st.markdown("实时采集 B 站技术美术作品集，生成 S/A/B/C 评级，帮你找准学习目标。")

    # ---- 顶部状态栏 ----
    from core.database import get_bilibili_portfolios, get_portfolio_stats

    stats = get_portfolio_stats()
    total = stats.get("total", 0)
    last_analyzed = stats.get("last_analyzed", "")

    col_stat1, col_stat2, col_stat3 = st.columns(3)
    with col_stat1:
        st.metric("样本总数", total)
    with col_stat2:
        st.metric(
            "上次分析",
            last_analyzed[:10] if last_analyzed else "尚未分析",
        )
    with col_stat3:
        grade_counts = stats.get("grade_counts", {})
        s_count = grade_counts.get("S", 0)
        st.metric("S 级样本", s_count)

    # ---- 刷新数据按钮 ----
    st.markdown("---")
    col_refresh, col_info = st.columns([2, 3])
    with col_refresh:
        if st.button("🔄 刷新竞品数据", key="btn_refresh_portfolio", use_container_width=True):
            _run_refresh()
    with col_info:
        st.markdown(
            "<small>采集 B 站「技术美术 作品集」等关键词的最新视频，"
            "分析技术标签并生成相对评级（约需 3-10 分钟）。</small>",
            unsafe_allow_html=True,
        )

    # ---- 主内容区 ----
    if total == 0:
        st.info("暂无数据，请点击「刷新竞品数据」按钮采集分析。")
        return

    portfolios = get_bilibili_portfolios(limit=200)

    # ---- 评级分布 ----
    st.markdown("## 📊 评级分布")
    _render_grade_distribution(portfolios)

    # ---- S 级特征高亮 ----
    _render_s_grade_features(portfolios)

    # ---- 作品集列表 ----
    st.markdown("---")
    st.markdown("## 📋 作品集列表")
    _render_portfolio_list(portfolios)

    # ---- 我的对标 ----
    st.markdown("---")
    st.markdown("## 🎯 我的对标")
    _render_my_benchmark(portfolios)


def _run_refresh():
    """执行刷新流程并显示进度"""
    from core.intel import refresh_bilibili_portfolios

    with st.status("正在采集和分析 B 站竞品数据...", expanded=True) as status:
        st.write("📡 搜索关键词：技术美术作品集、TA实习、AI TA 作品集...")
        st.write("🤖 分析视频技术标签（可能需要几分钟）...")
        st.write("📊 计算 S/A/B/C 评级...")

        try:
            result = refresh_bilibili_portfolios()
            if "error" in result:
                status.update(label=f"⚠️ 部分完成：{result['error']}", state="error")
                st.warning(result["error"])
            else:
                total = result.get("total_count", 0)
                dist = result.get("grade_distribution", {})
                status.update(label=f"✅ 刷新完成！共分析 {total} 条作品集", state="complete")
                st.success(
                    f"S级：{dist.get('S', 0)} | A级：{dist.get('A', 0)} | "
                    f"B级：{dist.get('B', 0)} | C级：{dist.get('C', 0)}"
                )
        except Exception as e:
            status.update(label=f"❌ 刷新失败：{e}", state="error")
            st.error(f"刷新失败：{e}")

    st.rerun()


def _render_grade_distribution(portfolios: list):
    """渲染评级分布柱状图和色块"""
    grade_order = ["S", "A", "B", "C"]
    grade_colors = {"S": "#f0c420", "A": "#58a6ff", "B": "#3fb950", "C": "#8b949e"}
    grade_emoji = {"S": "🥇", "A": "🥈", "B": "🥉", "C": "📌"}

    grade_counts: dict[str, int] = {}
    for p in portfolios:
        grade = p.get("grade", "").rstrip("*")
        if grade in grade_order:
            grade_counts[grade] = grade_counts.get(grade, 0) + 1

    total = sum(grade_counts.values()) or 1

    cols = st.columns(4)
    for i, grade in enumerate(grade_order):
        count = grade_counts.get(grade, 0)
        pct = round(count / total * 100, 1)
        with cols[i]:
            st.markdown(
                f"""<div style="background-color:{grade_colors[grade]}22; border:2px solid {grade_colors[grade]};
                border-radius:8px; padding:16px; text-align:center;">
                <div style="font-size:28px; font-weight:bold; color:{grade_colors[grade]}">
                {grade_emoji[grade]} {grade} 级</div>
                <div style="font-size:22px; font-weight:bold; color:#c9d1d9">{count} 条</div>
                <div style="font-size:14px; color:#8b949e">{pct}%</div>
                </div>""",
                unsafe_allow_html=True,
            )


def _render_s_grade_features(portfolios: list):
    """渲染 S 级作品集最常见的技术标签"""
    s_portfolios = [p for p in portfolios if p.get("grade", "").rstrip("*") == "S"]
    if not s_portfolios:
        return

    tag_counter = Counter()
    for p in s_portfolios:
        for tag in p.get("tech_tags", []):
            tag_counter[tag] += 1

    top_tags = tag_counter.most_common(10)
    if not top_tags:
        return

    st.markdown("---")
    st.markdown("## ⭐ S 级作品集核心特征")
    st.markdown("以下是 S 级作品集中最常见的技术标签，**这些就是你的学习目标**：")

    tag_html = " ".join([
        f'<span style="background-color:#f0c42033; border:1px solid #f0c420; '
        f'border-radius:12px; padding:4px 12px; margin:4px; display:inline-block; '
        f'color:#f0c420; font-weight:bold;">{tag} ×{count}</span>'
        for tag, count in top_tags
    ])
    st.markdown(f'<div style="line-height:2.5">{tag_html}</div>', unsafe_allow_html=True)


def _render_portfolio_list(portfolios: list):
    """渲染作品集列表，按评级排序"""
    grade_order = {"S": 0, "A": 1, "B": 2, "C": 3}
    sorted_portfolios = sorted(
        portfolios,
        key=lambda p: (grade_order.get(p.get("grade", "C").rstrip("*"), 4), -float(p.get("score", "0") or 0)),
    )

    grade_colors = {"S": "#f0c420", "A": "#58a6ff", "B": "#3fb950", "C": "#8b949e"}

    # 过滤控件
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        filter_grade = st.selectbox("按评级过滤", ["全部", "S", "A", "B", "C"], key="filter_grade")
    with col_f2:
        all_cohorts = sorted({p.get("cohort", "未知") for p in portfolios})
        filter_cohort = st.selectbox("按届别过滤", ["全部"] + all_cohorts, key="filter_cohort")
    with col_f3:
        all_stages = sorted({p.get("stage", "未知") for p in portfolios})
        filter_stage = st.selectbox("按阶段过滤", ["全部"] + all_stages, key="filter_stage")

    # 应用过滤
    filtered = sorted_portfolios
    if filter_grade != "全部":
        filtered = [p for p in filtered if p.get("grade", "").rstrip("*") == filter_grade]
    if filter_cohort != "全部":
        filtered = [p for p in filtered if p.get("cohort", "") == filter_cohort]
    if filter_stage != "全部":
        filtered = [p for p in filtered if p.get("stage", "") == filter_stage]

    st.markdown(f"显示 **{len(filtered)}** 条（共 {len(portfolios)} 条）")

    for p in filtered[:50]:  # 最多显示 50 条
        grade = p.get("grade", "?").rstrip("*")
        grade_note = p.get("grade_note", "")
        color = grade_colors.get(grade, "#8b949e")
        tags = p.get("tech_tags", [])
        tag_str = " | ".join(tags[:5]) if tags else "无标签"
        score = p.get("score", "")
        video_url = p.get("video_url", "")
        title = p.get("title", "未知标题")
        uploader = p.get("uploader", "未知UP主")
        cohort = p.get("cohort", "")
        stage = p.get("stage", "")

        note_html = f'<span style="color:#f0c420;font-size:11px"> ⚠️{grade_note}</span>' if grade_note else ""

        st.markdown(
            f"""<div style="background-color:#161b22; border:1px solid #30363d; border-left:4px solid {color};
            border-radius:6px; padding:12px; margin-bottom:8px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <span style="font-size:18px; font-weight:bold; color:{color}">{grade} 级</span>
                <span style="color:#8b949e; font-size:12px">评分: {score} | {cohort} · {stage}</span>
            </div>
            <div style="color:#c9d1d9; font-weight:bold; margin:4px 0">
                <a href="{video_url}" target="_blank" style="color:#58a6ff; text-decoration:none">{title}</a>
            </div>
            <div style="color:#8b949e; font-size:13px">UP主：{uploader}{note_html}</div>
            <div style="margin-top:6px; color:#58a6ff; font-size:12px">🏷️ {tag_str}</div>
            </div>""",
            unsafe_allow_html=True,
        )


def _render_my_benchmark(portfolios: list):
    """渲染「我的对标」功能"""
    st.markdown("输入你目前掌握的技术标签，系统计算预估评级和与 S 级的差距。")

    my_tags_input = st.text_input(
        "我的技术标签（逗号分隔）",
        placeholder="如：Unity Shader, Python, Houdini程序化, LoRA微调",
        key="my_tags_input",
    )

    col_stage, col_cohort = st.columns(2)
    with col_stage:
        my_stage = st.selectbox("求职阶段", ["实习", "秋招"], key="my_stage")
    with col_cohort:
        all_cohorts = sorted({p.get("cohort", "") for p in portfolios if p.get("cohort")})
        my_cohort = st.selectbox(
            "目标届别",
            all_cohorts if all_cohorts else ["2026届"],
            key="my_cohort",
        )

    if st.button("📊 分析我的对标位置", key="btn_benchmark", use_container_width=True):
        if not my_tags_input.strip():
            st.warning("请先输入你掌握的技术标签")
            return

        my_tags = [t.strip() for t in my_tags_input.split(",") if t.strip()]

        # 获取同届同阶段的样本
        same_group = [
            p for p in portfolios
            if p.get("cohort", "") == my_cohort and p.get("stage", "") == my_stage
        ]

        # 构造一个虚拟的「我」的作品集，用评分函数计算
        from core.crawlers.bilibili import _compute_score

        my_virtual = {
            "tech_tags": my_tags,
            "complexity": _estimate_complexity(my_tags),
            "has_pipeline": _has_pipeline_hint(my_tags),
            "visual_quality": _estimate_visual_quality(my_tags),
        }
        my_score = _compute_score(my_virtual)

        # 获取 S 级样本的标签
        s_portfolios = [p for p in same_group if p.get("grade", "").rstrip("*") == "S"]
        s_tags_counter = Counter()
        for p in s_portfolios:
            for tag in p.get("tech_tags", []):
                s_tags_counter[tag] += 1

        s_top_tags = [tag for tag, _ in s_tags_counter.most_common(10)]
        missing_tags = [tag for tag in s_top_tags if tag not in my_tags]

        # 在同组中排名
        group_scores = sorted(
            [float(p.get("score", "0") or "0") for p in same_group],
            reverse=True,
        )
        if group_scores:
            rank = sum(1 for s in group_scores if s > my_score)
            percentile = rank / len(group_scores)
            if percentile < 0.05:
                estimated_grade = "S"
            elif percentile < 0.20:
                estimated_grade = "A"
            elif percentile < 0.50:
                estimated_grade = "B"
            else:
                estimated_grade = "C"
        else:
            estimated_grade = "C"
            percentile = 1.0

        grade_colors = {"S": "#f0c420", "A": "#58a6ff", "B": "#3fb950", "C": "#8b949e"}
        color = grade_colors.get(estimated_grade, "#8b949e")

        st.markdown("---")
        st.markdown(f"### 📊 你的预估位置（{my_cohort} · {my_stage}）")

        col_grade, col_score = st.columns(2)
        with col_grade:
            st.markdown(
                f'<div style="background-color:{color}22; border:2px solid {color}; '
                f'border-radius:8px; padding:20px; text-align:center;">'
                f'<div style="font-size:32px; font-weight:bold; color:{color}">预估 {estimated_grade} 级</div>'
                f'<div style="color:#8b949e">综合评分 {my_score:.1f} / 100</div>'
                f'</div>',
                unsafe_allow_html=True,
            )
        with col_score:
            sample_size = len(same_group)
            st.markdown(
                f'<div style="background-color:#161b22; border:1px solid #30363d; '
                f'border-radius:8px; padding:20px;">'
                f'<div style="color:#c9d1d9">参考样本数：{sample_size}</div>'
                f'<div style="color:#c9d1d9">超越了 {max(0, 100 - int(percentile * 100))}% 的同届样本</div>'
                f'<div style="color:#8b949e; font-size:12px; margin-top:8px">'
                f'{"（样本不足，仅供参考）" if sample_size < 10 else ""}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        if missing_tags:
            st.markdown("### 📌 与 S 级的差距")
            st.markdown("你还需要学习以下技能才能接近 S 级水平：")
            missing_html = " ".join([
                f'<span style="background-color:#f0c42022; border:1px solid #f0c420; '
                f'border-radius:12px; padding:4px 12px; margin:4px; display:inline-block; '
                f'color:#f0c420;">📚 {tag}</span>'
                for tag in missing_tags[:8]
            ])
            st.markdown(f'<div style="line-height:2.5">{missing_html}</div>', unsafe_allow_html=True)

            # 推荐学习这些差距技能
            if st.button("🎯 去学习这些差距技能", key="btn_learn_gaps", use_container_width=True):
                gap_topics = "、".join(missing_tags[:3])
                st.session_state["prefill_study_topic"] = missing_tags[0] if missing_tags else ""
                st.session_state["current_page"] = "study"
                st.rerun()
        else:
            st.success("🎉 你的技术标签已覆盖 S 级所有核心标签！继续深化每项技能的深度。")


def _estimate_complexity(tags: list) -> str:
    """根据技术标签估算复杂度"""
    high_complexity_keywords = [
        "LoRA", "ComfyUI", "Houdini", "程序化", "Shader", "HLSL", "图形学",
        "ControlNet", "神经网络", "机器学习", "渲染管线", "SDF", "光线追踪",
    ]
    mid_complexity_keywords = [
        "Unity", "UE", "材质", "粒子", "动画", "脚本", "Python", "特效",
    ]
    tags_str = " ".join(tags).lower()
    high_count = sum(1 for kw in high_complexity_keywords if kw.lower() in tags_str)
    mid_count = sum(1 for kw in mid_complexity_keywords if kw.lower() in tags_str)

    if high_count >= 2:
        return "高级"
    elif high_count >= 1 or mid_count >= 2:
        return "中级"
    return "基础"


def _has_pipeline_hint(tags: list) -> bool:
    """根据标签判断是否有完整流程"""
    pipeline_keywords = ["流程", "工程", "pipeline", "workflow", "ComfyUI", "Houdini", "程序化"]
    tags_str = " ".join(tags).lower()
    return any(kw.lower() in tags_str for kw in pipeline_keywords)


def _estimate_visual_quality(tags: list) -> str:
    """根据标签估算展示质量"""
    high_quality_keywords = ["Houdini", "UE5", "光线追踪", "全局光照", "PBR", "特效"]
    mid_quality_keywords = ["Unity", "材质", "Shader", "渲染"]
    tags_str = " ".join(tags).lower()

    if any(kw.lower() in tags_str for kw in high_quality_keywords):
        return "高"
    elif any(kw.lower() in tags_str for kw in mid_quality_keywords):
        return "中"
    return "低"

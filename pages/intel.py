# 文件用途：岗位情报页面，展示 JD 技能分析、新词高亮、Gap 分析和历史记录

import streamlit as st

from core.database import get_all_jd_records, get_latest_jd_analysis
from core.intel import analyze_jd_requirements, refresh_intel


def render() -> None:
    """渲染岗位情报页面"""
    st.title("岗位情报")
    st.markdown("实时分析 AI TA 岗位需求，帮你找到学习 Gap。")

    # ---- 上次刷新时间 ----
    analyses = get_latest_jd_analysis(n=3)
    if analyses:
        last_time = analyses[0].get("analysis_date", "")[:16]
        jd_count = get_all_jd_records.__doc__ and len(get_all_jd_records())
        st.caption(f"上次分析时间：{last_time}  |  数据库 JD 记录：{len(get_all_jd_records())} 条")
    else:
        st.caption("尚未进行过情报分析，点击下方按钮开始。")

    st.markdown("---")

    # ---- 刷新按钮 ----
    col_btn, col_kw = st.columns([2, 3])
    with col_kw:
        keyword = st.text_input(
            "搜索关键词",
            value="AI TA",
            placeholder="AI TA / 技术美术 / Technical Artist",
            key="intel_keyword",
        )
    with col_btn:
        st.markdown("<div style='margin-top:28px'></div>", unsafe_allow_html=True)
        refresh_clicked = st.button("刷新情报", use_container_width=True, key="btn_refresh_intel")

    if refresh_clicked:
        import time as _time
        st.info("⏱️ 预计需要 60-180 秒，请耐心等待...")
        _t0 = _time.time()
        with st.status("正在刷新情报...", expanded=True) as status:
            st.write("🔍 爬取 Boss 直聘...")
            st.write("📋 爬取牛客网面经...")

            try:
                result = refresh_intel(keyword=keyword.strip() or "AI TA")
            except Exception as e:
                status.update(label="❌ 刷新失败", state="error")
                _intel_error(e)
                result = {}

            crawl_count = result.get("crawl_count", 0)
            errors = result.get("crawl_errors", [])
            if crawl_count > 0:
                st.write(f"✅ 共获取 {crawl_count} 条数据，正在 AI 分析...")

            if errors:
                for err in errors:
                    st.warning(f"部分来源爬取失败：{err}")

            _elapsed = round(_time.time() - _t0)
            status.update(label=f"✅ 情报分析完成，共用时 {_elapsed} 秒", state="complete", expanded=False)

        st.session_state["intel_result"] = result
        st.rerun()

    # ---- 显示分析结果 ----
    # 从 session_state 获取最新结果，或从数据库加载
    intel = st.session_state.get("intel_result")
    if intel is None and analyses:
        # 从最新历史记录恢复展示
        latest = analyses[0]
        intel = {
            "top_skills": latest.get("top_skills", []),
            "new_keywords": latest.get("new_keywords", []),
            "trend_changes": latest.get("trend_changes", ""),
            "gap_analysis": "（历史分析，Gap 分析请点击刷新情报重新生成）",
            "sample_count": latest.get("sample_count", 0),
        }

    if intel:
        _render_intel_result(intel)

    # ---- 历史记录 ----
    if analyses:
        st.markdown("---")
        st.markdown("### 历史分析记录")
        for a in analyses:
            cols = st.columns([3, 2, 2])
            with cols[0]:
                st.markdown(f"**{a['analysis_date'][:16]}**")
            with cols[1]:
                st.markdown(f"样本数：{a['sample_count']}")
            with cols[2]:
                top = a.get("top_skills", [])
                if top:
                    first = top[0]
                    name = first.get("skill", str(first)) if isinstance(first, dict) else str(first)
                    st.markdown(f"TOP1：`{name}`")


def _render_intel_result(intel: dict) -> None:
    """渲染情报分析结果区域"""
    top_skills = intel.get("top_skills", [])
    new_keywords = intel.get("new_keywords", [])
    trend_changes = intel.get("trend_changes", "")
    gap_analysis = intel.get("gap_analysis", "")
    sample_count = intel.get("sample_count", 0)

    st.markdown(f"**分析样本：{sample_count} 条 JD**")

    col_left, col_right = st.columns(2)

    # ---- 左栏：TOP10 技能排行榜 ----
    with col_left:
        st.markdown("#### TOP 技能需求")
        if top_skills:
            max_count = max(
                (sk.get("count", 1) if isinstance(sk, dict) else 1) for sk in top_skills
            ) or 1
            for sk in top_skills[:10]:
                if isinstance(sk, dict):
                    name = sk.get("skill", "未知")
                    count = sk.get("count", 0)
                else:
                    name = str(sk)
                    count = 0

                is_new = name.lower() in [kw.lower() for kw in new_keywords]
                label = f"{'🆕 ' if is_new else ''}{name}"
                st.markdown(f"**{label}**")
                st.progress(count / max_count if max_count > 0 else 0)
                st.caption(f"出现 {count} 次")
        else:
            st.info("暂无技能数据，请点击刷新情报。")

    # ---- 右栏：新增关键词 + 趋势 ----
    with col_right:
        st.markdown("#### 新增热门关键词")
        if new_keywords:
            badges = " ".join(
                f"<span style='background:#1f4e3d;color:#3fb950;padding:3px 8px;border-radius:12px;margin:3px;display:inline-block'>{kw}</span>"
                for kw in new_keywords
            )
            st.markdown(badges, unsafe_allow_html=True)
        else:
            st.info("无新增关键词（与上次对比）")

        if trend_changes:
            st.markdown("#### 趋势变化")
            st.info(trend_changes)

    # ---- Gap 分析 ----
    if gap_analysis:
        st.markdown("---")
        st.markdown("#### Gap 分析")
        _render_gap_analysis(gap_analysis)


def _intel_error(e: Exception) -> None:
    """根据异常类型显示友好的错误提示"""
    msg = str(e).lower()
    if "403" in msg or "412" in msg:
        st.error("访问受限，请稍后重试或手动登录后刷新")
    elif "connect" in msg or "timeout" in msg:
        st.error("网络连接失败，请检查网络后重试")
    elif "api" in msg or "key" in msg:
        st.error("API调用失败，请检查网络连接和API Key配置")
    else:
        st.error("刷新失败，请稍后重试")
    print(f"[intel] 错误详情：{e}")


def _render_gap_analysis(gap_text: str) -> None:
    """渲染 Gap 分析，按未学/已涉及/建议着色"""
    lines = gap_text.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        lower = line.lower()
        if "未学" in line or "缺少" in line or "没有" in line:
            st.markdown(
                f"<div style='background:#3a1a1a;border-left:4px solid #f85149;padding:8px 12px;margin:4px 0;border-radius:4px;color:#c9d1d9'>{line}</div>",
                unsafe_allow_html=True,
            )
        elif "已涉及" in line or "已学" in line or "掌握" in line:
            st.markdown(
                f"<div style='background:#1a3a1a;border-left:4px solid #3fb950;padding:8px 12px;margin:4px 0;border-radius:4px;color:#c9d1d9'>{line}</div>",
                unsafe_allow_html=True,
            )
        elif "建议" in line or "优先" in line or "推荐" in line:
            st.markdown(
                f"<div style='background:#1a2a3a;border-left:4px solid #d29922;padding:8px 12px;margin:4px 0;border-radius:4px;color:#c9d1d9'>{line}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"<div style='padding:4px 12px;color:#c9d1d9'>{line}</div>",
                unsafe_allow_html=True,
            )

# 文件用途：职业路径分析页面
# T11: Tab1 路径分析 / Tab2 路径对比

import json

import streamlit as st


# ============================================================
# Tab 1：路径分析
# ============================================================

def _render_tab1():
    st.subheader("职业路径分析")
    st.caption("选择一个背景匹配会话中的职位，分析其完整职业发展路径（校招→1-3年→3-5年→5年以上）。")

    from core.database import get_all_match_sessions, get_match_records

    # 选择历史会话
    sessions = get_all_match_sessions(limit=20)
    if not sessions:
        st.info("暂无背景匹配历史，请先完成一次背景匹配。")
        return

    session_options = {
        f"#{s['id']} | {s['created_at'][:16]} | {', '.join(s['keywords_used'][:3])}": s["id"]
        for s in sessions
    }
    selected_label = st.selectbox("选择背景匹配会话", list(session_options.keys()))
    selected_session_id = session_options[selected_label]

    # 显示该会话的高分职位（可多选）
    records = get_match_records(selected_session_id)
    if not records:
        st.info("该会话暂无匹配记录。")
        return

    # 只展示有职位名的记录
    valid_records = [r for r in records if r.get("title") and r["title"] != "未知职位"]
    if not valid_records:
        valid_records = records

    job_options = {
        f"{r.get('title','未知职位')} @ {r.get('company','未知公司')} | 评分:{r.get('match_score',0)}分": r.get("title", "")
        for r in valid_records[:20]
    }

    st.markdown("**选择要分析的职位（可多选，建议1-3个）：**")
    selected_labels = st.multiselect(
        "职位列表",
        list(job_options.keys()),
        key="cp_selected_jobs",
        label_visibility="collapsed",
    )
    selected_titles = list({job_options[lbl] for lbl in selected_labels if job_options.get(lbl)})

    if not selected_titles:
        st.info("请至少选择一个职位。")
        return

    city_input = st.text_input(
        "目标城市（可选，留空则全国）",
        key="cp_city",
        placeholder="如：上海",
    )

    if st.button("📊 分析选中职位的职业路径", type="primary"):
        _run_career_analysis(selected_titles, city_input, str(selected_session_id))


def _run_career_analysis(titles: list, city: str, session_id: str):
    """执行职业路径分析流程"""
    from core.career_path import crawl_career_levels, analyze_career_path

    results = {}

    for title in titles:
        st.markdown(f"---\n### 🔍 分析职位：{title}")
        prog = st.progress(0, text=f"正在爬取「{title}」校招岗位…")

        try:
            prog.progress(10, text=f"爬取「{title}」校招岗位…")
            level_data = crawl_career_levels(
                job_title=title,
                base_city=city,
                session_id=f"{session_id}_{title}",
            )

            prog.progress(70, text=f"生成「{title}」分析报告…")
            analysis = analyze_career_path(
                session_id=f"{session_id}_{title}",
                target_role=title,
            )
            results[title] = analysis

            prog.progress(100, text=f"「{title}」分析完成！")
            _display_career_analysis(title, analysis)

        except Exception as e:
            st.error(f"「{title}」分析失败：{e}")

    if results:
        st.session_state["cp_last_analyses"] = results
        st.success(f"✅ 共完成 {len(results)} 个职位的路径分析，可在「路径对比」Tab 进行对比。")


def _display_career_analysis(title: str, analysis: dict):
    """展示单个职位的职业路径分析结果"""
    import pandas as pd

    st.markdown(f"#### {title} — 职业路径分析")

    # 薪资增长折线图
    salary_trend = analysis.get("salary_trend", {})
    levels = ["校招", "1-3年", "3-5年", "5年以上"]

    chart_data = {
        "经验段": [],
        "最低薪资(K)": [],
        "中位薪资(K)": [],
        "最高薪资(K)": [],
    }
    for lv in levels:
        stats = salary_trend.get(lv, {})
        if stats.get("count", 0) > 0:
            chart_data["经验段"].append(lv)
            chart_data["最低薪资(K)"].append(stats.get("min", 0))
            chart_data["中位薪资(K)"].append(stats.get("median", 0))
            chart_data["最高薪资(K)"].append(stats.get("max", 0))

    if chart_data["经验段"]:
        df_salary = pd.DataFrame({
            "经验段": chart_data["经验段"],
            "最低": chart_data["最低薪资(K)"],
            "中位数": chart_data["中位薪资(K)"],
            "最高": chart_data["最高薪资(K)"],
        }).set_index("经验段")
        st.markdown("**薪资增长趋势（K/月）**")
        st.line_chart(df_salary)
    else:
        st.info("薪资数据不足，无法显示折线图。")

    # 技能要求表格
    skills_by_level = analysis.get("skills_by_level", {})
    all_skills = set()
    for skills in skills_by_level.values():
        all_skills.update(skills)

    if all_skills:
        st.markdown("**各年限段技能要求**")
        skill_matrix = {}
        for skill in sorted(all_skills):
            row = {}
            for lv in levels:
                row[lv] = "✅" if skill in skills_by_level.get(lv, []) else ""
            skill_matrix[skill] = row
        df_skills = pd.DataFrame(skill_matrix).T
        df_skills.index.name = "技能"
        st.dataframe(df_skills, use_container_width=True)

    # AI 替代风险仪表盘
    ai_risk = analysis.get("ai_risk_score", 0)
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("**AI 替代风险**")
        color = "#f85149" if ai_risk >= 70 else "#d29922" if ai_risk >= 40 else "#3fb950"
        st.markdown(
            f'<div style="text-align:center;font-size:48px;font-weight:bold;color:{color}">'
            f'{ai_risk}<small style="font-size:18px">/100</small></div>',
            unsafe_allow_html=True,
        )
        risk_label = "高风险" if ai_risk >= 70 else "中等风险" if ai_risk >= 40 else "低风险"
        st.markdown(f"<div style='text-align:center;color:{color}'>{risk_label}</div>",
                    unsafe_allow_html=True)
    with col2:
        if analysis.get("ai_risk_detail"):
            st.info(analysis["ai_risk_detail"])

    # DeepSeek 生成的总结
    if analysis.get("summary"):
        st.markdown("**职业路径总结**")
        st.markdown(analysis["summary"])

    if analysis.get("salary_prediction"):
        st.markdown("**薪资增长预测**")
        st.markdown(analysis["salary_prediction"])

    if analysis.get("growth_ceiling"):
        st.markdown("**上升瓶颈**")
        st.warning(analysis["growth_ceiling"])

    if analysis.get("learning_advice"):
        st.markdown("**各阶段学习建议**")
        st.markdown(analysis["learning_advice"])


# ============================================================
# Tab 2：路径对比
# ============================================================

def _render_tab2():
    st.subheader("多路径对比")
    st.caption("选择2-3个已分析的职位路径，生成对比报告。")

    from core.database import get_career_analyses

    # 获取所有已完成的分析
    all_analyses = get_career_analyses()
    if not all_analyses:
        st.info("暂无已完成的路径分析，请先在「路径分析」Tab 完成分析。")
        # 如果本 session 有临时结果也可以用
        if st.session_state.get("cp_last_analyses"):
            st.info("当前会话有分析结果，可以继续。")
        return

    role_options = list({a["target_role"] for a in all_analyses if a.get("target_role")})
    if len(role_options) < 2:
        st.info("需要至少2个不同职位的分析结果才能对比。")
        return

    selected_roles = st.multiselect(
        "选择要对比的职位路径（2-3个）",
        role_options,
        key="cp_compare_roles",
        help="先在「路径分析」Tab 完成分析，再回来对比",
    )

    if len(selected_roles) < 2:
        st.info("请至少选择2个职位。")
        return

    if st.button("📈 生成对比报告", type="primary"):
        with st.spinner("正在生成对比报告…"):
            try:
                from core.career_path import compare_career_paths
                result = compare_career_paths(selected_roles)
                st.session_state["cp_compare_result"] = result
            except Exception as e:
                st.error(f"对比报告生成失败：{e}")

    compare_result = st.session_state.get("cp_compare_result", {})
    if not compare_result:
        return

    if "error" in compare_result:
        st.error(compare_result["error"])
        return

    _display_compare_result(compare_result)


def _display_compare_result(result: dict):
    """展示多路径对比结果"""
    import pandas as pd

    roles = result.get("roles", [])
    salary_comparison = result.get("salary_comparison", {})
    ai_risks = result.get("ai_risks", {})
    growth_ceilings = result.get("growth_ceilings", {})
    skill_overlap = result.get("skill_overlap", {})

    # 薪资对比折线图（多条线）
    if salary_comparison:
        st.markdown("**薪资增长对比（中位数 K/月）**")
        levels = ["校招", "1-3年", "3-5年", "5年以上"]
        chart_dict = {}
        for role, sal_data in salary_comparison.items():
            chart_dict[role] = [sal_data.get(lv, None) for lv in levels]

        df_compare = pd.DataFrame(chart_dict, index=levels)
        df_compare = df_compare.dropna(how="all")
        if not df_compare.empty:
            st.line_chart(df_compare)

    # 对比表格
    st.markdown("**综合对比表**")
    compare_rows = []
    all_salary = {}
    for role, sal in salary_comparison.items():
        all_salary[role] = sal

    dimensions = [
        ("校招中位薪资(K)", lambda r: salary_comparison.get(r, {}).get("校招", "-")),
        ("3年中位薪资(K)",  lambda r: salary_comparison.get(r, {}).get("1-3年", "-")),
        ("5年中位薪资(K)",  lambda r: salary_comparison.get(r, {}).get("3-5年", "-")),
        ("AI替代风险(0-100)", lambda r: ai_risks.get(r, "-")),
        ("上升天花板",      lambda r: (growth_ceilings.get(r, "") or "")[:50]),
    ]

    table_data = {}
    for dim_name, fn in dimensions:
        table_data[dim_name] = {role: fn(role) for role in roles}
    df_table = pd.DataFrame(table_data).T
    st.dataframe(df_table, use_container_width=True)

    # 技能重叠
    if skill_overlap:
        st.markdown("**技能重叠度**")
        for pair, skills in skill_overlap.items():
            if skills:
                st.markdown(f"**{pair}**：{', '.join(skills[:10])}")
            else:
                st.markdown(f"**{pair}**：（无重叠技能）")

    # DeepSeek 对比总结
    if result.get("comparison_summary"):
        st.markdown("---")
        st.markdown("**AI 对比分析与选择建议**")
        st.markdown(result["comparison_summary"])


# ============================================================
# 主入口
# ============================================================

def render():
    st.title("📈 职业路径分析")
    st.caption("分析目标职位在不同经验段的薪资、技能要求和成长路径，辅助求职决策。")

    tab1, tab2 = st.tabs(["🔍 路径分析", "📊 路径对比"])

    with tab1:
        _render_tab1()

    with tab2:
        _render_tab2()


print("✅ T11 完成")

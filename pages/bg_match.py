# 文件用途：背景匹配页面 —— Tab1 录入 / Tab2 结果+分析 / Tab3 历史记录
# T04: 支持本科+硕士两段学历，新增筛选条件组
# T06: 结果页新增推荐投递顺序

import json

import streamlit as st

# ============================================================
# 静态选项常量
# ============================================================

_EDU_LEVELS = ["985", "211", "双一流", "普通本科", "海外", "其他"]

_EXP_DURATIONS = ["1个月以内", "1–3个月", "3–6个月", "6个月以上"]
_EXP_TYPES = ["大厂实习", "实验室科研", "独立项目", "外包接单"]
_EXP_DIRECTIONS = ["技术美术", "游戏程序", "AI工具链", "Agent开发", "数据/算法", "其他"]

_AI_STACKS = {
    "LLM应用开发": ["Function Calling", "RAG", "Prompt Engineering", "Agent框架", "Fine-tuning", "本地部署"],
    "图像/3D生成": ["Stable Diffusion", "ComfyUI", "LoRA微调", "3D生成(Meshy/Tripo)", "ControlNet"],
    "AI工程": ["LangChain", "LlamaIndex", "FastAPI", "DeepSeek API", "Doubao TTS", "STT接入"],
}

_OTHER_STACKS = {
    "游戏引擎": ["Unity(C#)", "Unreal Engine(C++/蓝图)", "Godot", "Cocos"],
    "图形/Shader": ["HLSL", "GLSL", "ShaderLab", "Shader Graph", "VFX Graph", "Niagara"],
    "DCC工具": ["Blender", "Maya", "3ds Max", "Houdini", "Substance Designer", "ZBrush"],
    "编程语言": ["Python", "C++", "C#", "JavaScript", "TypeScript", "Rust"],
    "其他": ["Live2D", "Spine", "Figma", "Arduino", "自然语言处理(非LLM)"],
}

# T04 筛选选项
_TARGET_CITIES = ["北京", "上海", "深圳", "广州", "杭州", "成都", "武汉", "不限"]
_COMPANY_STAGES = ["上市公司", "D轮及以上", "C轮", "B轮", "A轮", "不限"]
_EXP_PREFS = ["只看校招", "看1-3年", "看3-5年", "全部"]

_GRAD_YEARS = [""] + [str(y) for y in range(2018, 2031)]


# ============================================================
# 辅助：从 session_state 读取表单数据
# ============================================================

def _collect_profile_from_state() -> dict:
    """收集当前 session_state 中的所有表单数据，返回 profile dict"""
    experiences = []
    exp_count = st.session_state.get("bgm_exp_count", 1)
    for i in range(exp_count):
        company = st.session_state.get(f"bgm_exp_company_{i}", "")
        if not company:
            continue
        experiences.append({
            "company": company,
            "duration": st.session_state.get(f"bgm_exp_duration_{i}", ""),
            "exp_type": st.session_state.get(f"bgm_exp_type_{i}", ""),
            "directions": st.session_state.get(f"bgm_exp_directions_{i}", []),
            "desc": st.session_state.get(f"bgm_exp_desc_{i}", ""),
        })

    ai_stacks = []
    for group in _AI_STACKS:
        items = st.session_state.get(f"bgm_ai_{group}", [])
        note = st.session_state.get(f"bgm_ai_note_{group}", "")
        ai_stacks.append({"stack_group": group, "items": items, "extra_note": note})

    other_stacks = []
    for group in _OTHER_STACKS:
        items = st.session_state.get(f"bgm_other_{group}", [])
        other_stacks.append({"stack_group": group, "items": items})

    return {
        "edu_major": st.session_state.get("bgm_edu_major", ""),
        "edu_level": st.session_state.get("bgm_edu_level", ""),
        "undergrad_school": st.session_state.get("bgm_undergrad_school", ""),
        "undergrad_grad_year": st.session_state.get("bgm_undergrad_grad_year", ""),
        # 硕士部分
        "has_master": st.session_state.get("bgm_has_master", False),
        "master_school": st.session_state.get("bgm_master_school", ""),
        "master_major": st.session_state.get("bgm_master_major", ""),
        "master_grad_year": st.session_state.get("bgm_master_grad_year", ""),
        "cross_tags": st.session_state.get("bgm_cross_tags", []),
        "experiences": experiences,
        "ai_stacks": ai_stacks,
        "other_stacks": other_stacks,
        "free_text": st.session_state.get("bgm_free_text", ""),
    }


def _collect_filters_from_state() -> dict:
    """收集筛选条件"""
    cities = st.session_state.get("bgm_filter_cities", ["不限"])
    stages = st.session_state.get("bgm_filter_stages", ["不限"])
    return {
        "target_cities": [c for c in cities if c != "不限"],
        "salary_min_k": st.session_state.get("bgm_filter_salary_floor", 0),
        "company_stages": [s for s in stages if s != "不限"],
        "experience_pref": st.session_state.get("bgm_filter_exp_pref", "只看校招"),
    }


# ============================================================
# Tab 1：背景录入（T04）
# ============================================================

def _render_tab1():
    # A. 本科背景
    st.subheader("A. 本科背景")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.text_input("本科专业", key="bgm_edu_major", placeholder="如：计算机科学")
    with col2:
        st.selectbox("学校类型", _EDU_LEVELS, key="bgm_edu_level")
    with col3:
        st.text_input("本科学校名称（可选）", key="bgm_undergrad_school", placeholder="如：北京大学")

    col4, col5 = st.columns(2)
    with col4:
        st.selectbox("本科毕业年份", _GRAD_YEARS, key="bgm_undergrad_grad_year")
    with col5:
        st.multiselect("跨学科标签", ["美术", "音乐", "设计", "管理", "无"], key="bgm_cross_tags")

    # A2. 硕士（可选）
    st.markdown("---")
    has_master = st.checkbox("📚 我有/正在读研究生（硕士）", key="bgm_has_master")
    if has_master:
        with st.container():
            st.caption("硕士信息")
            mc1, mc2, mc3 = st.columns(3)
            with mc1:
                st.text_input("硕士学校名称", key="bgm_master_school", placeholder="如：清华大学")
            with mc2:
                st.text_input("硕士专业", key="bgm_master_major", placeholder="如：人工智能")
            with mc3:
                st.selectbox("硕士毕业年份", _GRAD_YEARS, key="bgm_master_grad_year")

    # B. 实习/科研经历
    st.divider()
    st.subheader("B. 实习 / 科研经历")

    if "bgm_exp_count" not in st.session_state:
        st.session_state.bgm_exp_count = 1

    for i in range(st.session_state.bgm_exp_count):
        with st.expander(f"经历 #{i + 1}", expanded=(i == 0)):
            c1, c2, c3 = st.columns([3, 2, 2])
            with c1:
                st.text_input("公司/机构名称", key=f"bgm_exp_company_{i}", placeholder="如：网易互娱")
            with c2:
                st.selectbox("时长", _EXP_DURATIONS, key=f"bgm_exp_duration_{i}")
            with c3:
                st.selectbox("类型", _EXP_TYPES, key=f"bgm_exp_type_{i}")
            st.multiselect("职能方向", _EXP_DIRECTIONS, key=f"bgm_exp_directions_{i}")
            st.text_input(
                "一句话描述（可选，≤80字）",
                key=f"bgm_exp_desc_{i}",
                max_chars=80,
            )

    bcol1, bcol2 = st.columns(2)
    with bcol1:
        if st.button("➕ 添加经历"):
            st.session_state.bgm_exp_count += 1
            st.rerun()
    with bcol2:
        if st.session_state.bgm_exp_count > 1 and st.button("➖ 删除最后一条"):
            st.session_state.bgm_exp_count -= 1
            st.rerun()

    # C. AI 技术栈
    st.divider()
    st.subheader("C. AI 相关技术栈")
    for group, options in _AI_STACKS.items():
        st.markdown(f"**{group}**")
        st.multiselect("", options, key=f"bgm_ai_{group}", label_visibility="collapsed")
    st.text_area(
        "补充说明（未覆盖的 AI 技术栈）",
        key="bgm_ai_note_all",
        max_chars=300,
        placeholder='如"用 DeepSeek + Unity 做过 NPC 对话系统"',
        height=80,
    )
    for group in _AI_STACKS:
        if f"bgm_ai_note_{group}" not in st.session_state:
            st.session_state[f"bgm_ai_note_{group}"] = ""

    # D. 其他技术栈
    st.divider()
    st.subheader("D. 其他相关技术栈")
    cols = st.columns(2)
    for idx, (group, options) in enumerate(_OTHER_STACKS.items()):
        with cols[idx % 2]:
            st.markdown(f"**{group}**")
            st.multiselect("", options, key=f"bgm_other_{group}", label_visibility="collapsed")

    # E. 自然语言补充
    st.divider()
    st.subheader("自然语言补充（可选，≤500字）")
    st.text_area(
        "用自己的话描述任何上方表单未能覆盖的内容",
        key="bgm_free_text",
        max_chars=500,
        height=120,
        placeholder='如"我做过一个 LLM 驱动的心理悬疑游戏，用了四层 prompt pipeline……"',
    )

    # F. 筛选条件（T04）
    st.divider()
    st.subheader("🔍 搜索筛选条件（可选）")
    st.caption("这些条件用于在爬取结果中预先过滤，减少无效评分调用。")

    fc1, fc2 = st.columns(2)
    with fc1:
        st.multiselect(
            "目标城市",
            _TARGET_CITIES,
            default=["不限"],
            key="bgm_filter_cities",
        )
        st.slider(
            "薪资底线（K/月，低于此值不进入评分）",
            min_value=0,
            max_value=50,
            value=0,
            step=1,
            key="bgm_filter_salary_floor",
            help="设置为0表示不限",
        )
    with fc2:
        st.multiselect(
            "公司规模要求",
            _COMPANY_STAGES,
            default=["不限"],
            key="bgm_filter_stages",
        )
        st.radio(
            "工作年限要求",
            _EXP_PREFS,
            index=0,
            key="bgm_filter_exp_pref",
            horizontal=True,
        )

    st.divider()
    if st.button("🚀 生成匹配", type="primary", use_container_width=True):
        _run_match_pipeline()


def _run_match_pipeline():
    """执行完整匹配流程（摘要 → 搜索 → 预筛选 → 评分），结果存入 session_state"""
    from core.bg_match import generate_bg_summary, run_match_session
    from core.database import (
        upsert_user_profile,
        replace_user_experiences,
        replace_user_ai_stacks,
        replace_user_other_stacks,
    )

    profile = _collect_profile_from_state()
    filters = _collect_filters_from_state()

    # 保存到数据库
    try:
        ai_note = st.session_state.get("bgm_ai_note_all", "")
        for group in _AI_STACKS:
            st.session_state[f"bgm_ai_note_{group}"] = ai_note

        profile_id = upsert_user_profile(
            edu_major=profile["edu_major"],
            edu_level=profile["edu_level"],
            free_text=profile["free_text"],
        )
        replace_user_experiences(profile_id, profile["experiences"])
        replace_user_ai_stacks(profile_id, profile["ai_stacks"])
        replace_user_other_stacks(profile_id, profile["other_stacks"])
    except Exception as e:
        st.warning(f"画像保存失败（不影响匹配）：{e}")
        profile_id = 0

    progress_bar = st.progress(0, text="生成背景摘要中…")

    # Step 1: 生成摘要
    try:
        bg_summary = generate_bg_summary(profile)
        if "error" in bg_summary and not bg_summary.get("core_strengths"):
            st.error(f"背景摘要生成失败：{bg_summary['error']}")
            return
        if profile_id:
            from core.database import update_profile_summary
            update_profile_summary(profile_id, json.dumps(bg_summary, ensure_ascii=False))
    except Exception as e:
        st.error(f"背景摘要生成出错：{e}")
        return

    progress_bar.progress(
        20,
        text=f"摘要生成完成，开始搜索岗位（关键词：{', '.join(bg_summary.get('search_keywords', []))}）…",
    )

    # Step 2 + 3: 搜索 + 预筛选 + 评分
    def on_progress(stage, current, total):
        if stage == "crawl":
            pct = 20 + int(40 * current / max(total, 1))
            progress_bar.progress(pct, text=f"搜索岗位中… ({current + 1}/{total})")
        elif stage == "score":
            pct = 60 + int(38 * current / max(total, 1))
            progress_bar.progress(pct, text=f"评分匹配中… ({current + 1}/{total})")

    try:
        session_id, scored = run_match_session(
            bg_summary=bg_summary,
            profile_snapshot=profile,
            on_progress=on_progress,
            filters=filters,
        )
        st.session_state["bgm_last_session_id"] = session_id
        st.session_state["bgm_last_results"] = scored
        st.session_state["bgm_last_summary"] = bg_summary
        progress_bar.progress(100, text=f"完成！共匹配 {len(scored)} 条岗位。")
        st.success(f"匹配完成，共 {len(scored)} 条岗位，请切换到「匹配结果」Tab 查看。")
    except Exception as e:
        st.error(f"匹配过程出错：{e}")


# ============================================================
# 推荐投递顺序（T06）
# ============================================================

def _compute_composite_score(r: dict) -> float:
    """
    综合评分 = 竞争力*0.4 + 匹配度*0.4 + 薪资吸引力*0.2
    """
    comp_map = {"强": 90, "中": 60, "弱": 30}
    comp_score = comp_map.get(r.get("competitiveness", "中"), 60)
    match = r.get("match_score", 50)
    sal_max = r.get("salary_max", 0) or 0
    sal_score = min(100, sal_max * 2.5) if sal_max > 0 else 50
    return comp_score * 0.4 + match * 0.4 + sal_score * 0.2


def _render_recommended_order(records: list[dict]):
    """T06：显示推荐投递顺序分三档"""
    if not records:
        return

    scored = [(r, _compute_composite_score(r)) for r in records]
    scored.sort(key=lambda x: x[1], reverse=True)

    tier_a = [(r, s) for r, s in scored if s >= 75][:3]   # 重点投递
    tier_b = [(r, s) for r, s in scored if 50 <= s < 75][:3]  # 积极尝试
    tier_c = [(r, s) for r, s in scored if s < 50][:3]    # 保底备选

    st.markdown("### 🎯 推荐投递顺序")
    st.caption("综合评分 = 竞争力×0.4 + 技术匹配度×0.4 + 薪资吸引力×0.2")

    def _render_tier(title: str, color: str, items: list):
        if not items:
            return
        st.markdown(f"**{title}**")
        for r, s in items:
            sal = ""
            if r.get("salary_min") or r.get("salary_max"):
                lo, hi = r.get("salary_min", 0), r.get("salary_max", 0)
                sal = f"💰{lo}–{hi}K " if lo != hi else f"💰{lo}K "
            reasons = r.get("match_reasons", [])
            reason_str = "、".join(reasons[:3]) if reasons else ""
            st.markdown(
                f'<div style="border-left:4px solid {color};padding:6px 12px;margin:4px 0;'
                f'background:#161b22;border-radius:4px">'
                f'<b>{r.get("title","未知岗位")}</b> @ {r.get("company","未知公司")} '
                f'{sal}'
                f'<span style="color:#8b949e">综合:{s:.0f}分</span>'
                + (f'<br><small style="color:#58a6ff">✅ {reason_str}</small>' if reason_str else "")
                + "</div>",
                unsafe_allow_html=True,
            )

    _render_tier("🌟 重点投递（综合>75）", "#3fb950", tier_a)
    _render_tier("🚀 积极尝试（综合50-75）", "#d29922", tier_b)
    _render_tier("🛡️ 保底备选（综合<50）", "#f85149", tier_c)


# ============================================================
# Tab 2：匹配结果 + 数据分析
# ============================================================

def _render_tab2(records: list[dict] = None, bg_summary: dict = None):
    if records is None:
        records = st.session_state.get("bgm_last_results", [])
    if bg_summary is None:
        bg_summary = st.session_state.get("bgm_last_summary", {})

    if not records:
        st.info("暂无匹配结果。请先在「背景录入」Tab 点击「生成匹配」。")
        return

    # 推荐投递顺序（T06）
    _render_recommended_order(records)
    st.divider()

    # 筛选器
    st.markdown("#### 全部结果筛选")
    fcol1, fcol2, fcol3 = st.columns(3)
    with fcol1:
        filter_comp = st.multiselect(
            "竞争力", ["强", "中", "弱"],
            default=["强", "中", "弱"],
            key="bgm_filter_comp",
        )
    with fcol2:
        filter_intensity = st.multiselect(
            "工作强度", ["高", "中", "低"],
            default=["高", "中", "低"],
            key="bgm_filter_intensity",
        )
    with fcol3:
        all_salaries = [r["salary_max"] for r in records if r.get("salary_max", 0) > 0]
        max_salary = max(all_salaries) if all_salaries else 100
        filter_salary = st.slider(
            "薪资上限（K/月）",
            min_value=0,
            max_value=max(max_salary, 100),
            value=max(max_salary, 100),
            key="bgm_filter_salary",
        )

    filtered = [
        r for r in records
        if r.get("competitiveness", "中") in filter_comp
        and r.get("work_intensity", "中") in filter_intensity
        and (r.get("salary_max", 0) <= filter_salary or r.get("salary_max", 0) == 0)
    ]

    st.markdown(f"**共 {len(filtered)} 条结果**（总计 {len(records)} 条）")
    st.divider()

    _comp_color = {"强": "🟢", "中": "🟡", "弱": "🔴"}
    _intensity_label = {"高": "🔥高强度", "中": "⚡中强度", "低": "🌿低强度"}

    for idx, r in enumerate(filtered):
        is_top3 = idx < 3
        border_style = "border-left: 4px solid #3fb950;" if is_top3 else "border-left: 4px solid #30363d;"
        score_badge = f"**{r['match_score']}分**"

        salary_str = ""
        if r.get("salary_min") or r.get("salary_max"):
            lo, hi = r.get("salary_min", 0), r.get("salary_max", 0)
            salary_str = f"{lo}–{hi}K" if lo != hi else f"{lo}K"

        header = (
            f"{score_badge} | {r.get('title','未知岗位')} @ **{r.get('company','未知公司')}**"
            + (f" | 💰{salary_str}" if salary_str else "")
            + (f" | {r.get('location','')}" if r.get("location") else "")
            + f" | {_comp_color.get(r.get('competitiveness','中'), '🟡')} 竞争力{r.get('competitiveness','中')}"
            + f" | {_intensity_label.get(r.get('work_intensity','中'), '⚡中强度')}"
        )

        with st.container():
            st.markdown(
                f'<div style="{border_style} padding-left:12px; margin-bottom:4px">',
                unsafe_allow_html=True,
            )
            with st.expander(header, expanded=is_top3):
                if r.get("match_highlight"):
                    st.success(f"✨ 亮点：{r['match_highlight']}")
                if r.get("skill_match"):
                    st.info(f"🎯 技能匹配：{r['skill_match']}")
                # T06: 匹配的技术点
                if r.get("match_reasons"):
                    st.markdown("**✅ 匹配技术点：** " + " · ".join(r["match_reasons"][:5]))
                if r.get("gap_skills"):
                    st.markdown("**⚠️ 待补技术点：** " + " · ".join(r["gap_skills"][:5]))
                if r.get("gap_analysis"):
                    st.warning(f"⚠️ 差距分析：{r['gap_analysis']}")
                extra_info = []
                if r.get("experience_required"):
                    extra_info.append(f"经验：{r['experience_required']}")
                if r.get("education_required"):
                    extra_info.append(f"学历：{r['education_required']}")
                if r.get("company_stage"):
                    extra_info.append(f"阶段：{r['company_stage']}")
                if extra_info:
                    st.caption(" | ".join(extra_info))
                if r.get("jd_raw"):
                    with st.expander("查看 JD 原文"):
                        st.text(r["jd_raw"][:2000])
            st.markdown("</div>", unsafe_allow_html=True)

    # 数据分析区块
    st.divider()
    st.subheader("📊 数据分析")
    _render_data_analysis(filtered, bg_summary)


def _render_data_analysis(records: list[dict], bg_summary: dict):
    if not records:
        st.info("无数据，无法生成分析。")
        return

    col1, col2 = st.columns(2)

    # 薪资分布
    with col1:
        st.markdown("**薪资分布（K/月）**")
        try:
            import pandas as pd
            salary_data = [
                (r["salary_min"] + r["salary_max"]) / 2
                for r in records
                if r.get("salary_min", 0) > 0 or r.get("salary_max", 0) > 0
            ]
            if salary_data:
                bins = [0, 10, 15, 20, 25, 30, 40, 200]
                labels = ["<10K", "10–15K", "15–20K", "20–25K", "25–30K", "30–40K", ">40K"]
                counts = [0] * len(labels)
                for s in salary_data:
                    for i in range(len(bins) - 1):
                        if bins[i] <= s < bins[i + 1]:
                            counts[i] += 1
                            break
                df = pd.DataFrame({"薪资区间": labels, "岗位数": counts})
                df = df[df["岗位数"] > 0]
                st.bar_chart(df.set_index("薪资区间"))
                median = sorted(salary_data)[len(salary_data) // 2]
                st.caption(f"中位数薪资约 {median:.0f}K/月")
            else:
                st.caption("暂无薪资数据")
        except Exception as e:
            st.caption(f"薪资图表生成失败：{e}")

    # 工作强度分布
    with col2:
        st.markdown("**工作强度分布**")
        try:
            from collections import Counter
            intensity_counts = Counter(r.get("work_intensity", "中") for r in records)
            labels_map = {"高": "🔥 高强度", "中": "⚡ 中强度", "低": "🌿 低强度"}
            for level in ["高", "中", "低"]:
                cnt = intensity_counts.get(level, 0)
                if cnt:
                    pct = int(100 * cnt / len(records))
                    st.markdown(f"{labels_map[level]}：**{cnt}** 条（{pct}%）")
                    st.progress(pct / 100)
        except Exception as e:
            st.caption(f"强度分析失败：{e}")

    # 竞争力评估
    st.markdown("---")
    st.markdown("**竞争力评估**")
    if "bgm_comp_analysis" not in st.session_state:
        st.session_state["bgm_comp_analysis"] = ""

    if st.button("生成竞争力评价", key="bgm_gen_comp"):
        with st.spinner("分析中…"):
            try:
                from core.bg_match import generate_competitiveness_analysis
                analysis = generate_competitiveness_analysis(bg_summary, records)
                st.session_state["bgm_comp_analysis"] = analysis
            except Exception as e:
                st.session_state["bgm_comp_analysis"] = f"生成失败：{e}"

    if st.session_state.get("bgm_comp_analysis"):
        st.markdown(st.session_state["bgm_comp_analysis"])

    # 高频技能缺口 Top10
    st.markdown("---")
    st.markdown("**高频技能缺口 Top 10**")
    try:
        from collections import Counter
        import re
        # 优先使用 gap_skills 字段（T06）
        all_gaps = []
        for r in records:
            gs = r.get("gap_skills", [])
            if isinstance(gs, list):
                all_gaps.extend(gs)
        if all_gaps:
            top10 = Counter(all_gaps).most_common(10)
            for word, cnt in top10:
                st.markdown(f"- **{word}**（出现 {cnt} 次）")
        else:
            # 回退到文本分析
            gap_texts = " ".join(r.get("gap_analysis", "") for r in records if r.get("gap_analysis"))
            words = re.findall(r"[一-鿿]{2,10}|[A-Za-z]{3,15}", gap_texts)
            stop = {"缺乏", "需要", "建议", "补充", "经验", "相关", "能力", "技能", "工作", "开发", "实习", "项目"}
            filtered_words = [w for w in words if w not in stop and len(w) >= 2]
            top10 = Counter(filtered_words).most_common(10)
            if top10:
                for word, cnt in top10:
                    st.markdown(f"- **{word}**（出现 {cnt} 次）")
            else:
                st.caption("暂无缺口数据")
    except Exception as e:
        st.caption(f"缺口分析失败：{e}")


# ============================================================
# Tab 3：历史记录
# ============================================================

def _render_tab3():
    from core.database import get_all_match_sessions, get_match_records, delete_match_session

    sessions = get_all_match_sessions(limit=50)

    if not sessions:
        st.info("暂无历史记录。")
        return

    for s in sessions:
        kws = ", ".join(s.get("keywords_used", []))
        label = f"{s['created_at'][:16]}  |  关键词：{kws}  |  共 {s['total_jd_count']} 条"
        with st.expander(label):
            col1, col2 = st.columns([5, 1])
            with col2:
                if st.button("🗑️ 删除", key=f"bgm_del_{s['id']}"):
                    delete_match_session(s["id"])
                    st.success("已删除")
                    st.rerun()
            with col1:
                if st.button("查看详情", key=f"bgm_view_{s['id']}"):
                    records = get_match_records(s["id"])
                    st.session_state["bgm_history_view_records"] = records
                    st.session_state["bgm_history_view_id"] = s["id"]

        if st.session_state.get("bgm_history_view_id") == s["id"]:
            records = st.session_state.get("bgm_history_view_records", [])
            if records:
                st.markdown(f"**Session #{s['id']} 详细结果（{len(records)} 条）**")
                _render_tab2(records=records, bg_summary={})


# ============================================================
# 主入口
# ============================================================

def render():
    st.title("🎯 背景匹配")
    st.caption("填写你的背景信息，AI 自动生成搜索词、爬取岗位并语义评分。")

    tab1, tab2, tab3 = st.tabs(["📝 背景录入", "📊 匹配结果", "🕑 历史记录"])

    with tab1:
        _render_tab1()

    with tab2:
        _render_tab2()

    with tab3:
        _render_tab3()


print("✅ T04 完成")
print("✅ T06 完成（pages）")

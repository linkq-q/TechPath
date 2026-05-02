# 文件用途：背景匹配页面 —— Tab1 录入 / Tab2 结果+分析 / Tab3 历史记录

import json

import streamlit as st

# ============================================================
# 静态选项常量
# ============================================================

_EDU_LEVELS = ["985", "211", "双一流", "普通本科", "海外", "其他"]
_GPA_LEVELS = ["3.8+", "3.5–3.8", "3.0–3.5", "3.0以下", "不展示"]
_CROSS_TAGS = ["美术", "音乐", "设计", "管理", "无"]

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
        "gpa_level": st.session_state.get("bgm_gpa_level", ""),
        "cross_tags": st.session_state.get("bgm_cross_tags", []),
        "experiences": experiences,
        "ai_stacks": ai_stacks,
        "other_stacks": other_stacks,
        "free_text": st.session_state.get("bgm_free_text", ""),
    }


# ============================================================
# Tab 1：背景录入
# ============================================================

def _render_tab1():
    st.subheader("A. 本科背景")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.text_input("本科专业", key="bgm_edu_major", placeholder="如：计算机科学")
    with col2:
        st.selectbox("学校类型", _EDU_LEVELS, key="bgm_edu_level")
    with col3:
        st.selectbox("GPA 水平", _GPA_LEVELS, key="bgm_gpa_level")
    st.multiselect("跨学科标签", _CROSS_TAGS, key="bgm_cross_tags")

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
    # 将同一个 note 存到每个 group（简化存储，只用第一个 group 的 note）
    for group in _AI_STACKS:
        if f"bgm_ai_note_{group}" not in st.session_state:
            st.session_state[f"bgm_ai_note_{group}"] = ""

    st.divider()
    st.subheader("D. 其他相关技术栈")
    cols = st.columns(2)
    for idx, (group, options) in enumerate(_OTHER_STACKS.items()):
        with cols[idx % 2]:
            st.markdown(f"**{group}**")
            st.multiselect("", options, key=f"bgm_other_{group}", label_visibility="collapsed")

    st.divider()
    st.subheader("自然语言补充（可选，≤500字）")
    st.text_area(
        "用自己的话描述任何上方表单未能覆盖的内容",
        key="bgm_free_text",
        max_chars=500,
        height=120,
        placeholder='如"我做过一个 LLM 驱动的心理悬疑游戏，用了四层 prompt pipeline……"',
    )

    st.divider()
    if st.button("🚀 生成匹配", type="primary", use_container_width=True):
        _run_match_pipeline()


def _run_match_pipeline():
    """执行完整匹配流程（摘要 → 搜索 → 评分），结果存入 session_state"""
    from core.bg_match import generate_bg_summary, run_match_session
    from core.database import (
        upsert_user_profile,
        replace_user_experiences,
        replace_user_ai_stacks,
        replace_user_other_stacks,
    )

    profile = _collect_profile_from_state()

    # 保存到数据库
    try:
        # 同步 AI note
        ai_note = st.session_state.get("bgm_ai_note_all", "")
        for group in _AI_STACKS:
            st.session_state[f"bgm_ai_note_{group}"] = ai_note

        profile_id = upsert_user_profile(
            edu_major=profile["edu_major"],
            edu_level=profile["edu_level"],
            gpa_level=profile["gpa_level"],
            cross_tags=profile["cross_tags"],
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
        # 更新数据库中的摘要
        if profile_id:
            from core.database import update_profile_summary
            update_profile_summary(profile_id, json.dumps(bg_summary, ensure_ascii=False))
    except Exception as e:
        st.error(f"背景摘要生成出错：{e}")
        return

    progress_bar.progress(20, text=f"摘要生成完成，开始搜索岗位（关键词：{', '.join(bg_summary.get('search_keywords', []))}）…")

    # Step 2 + 3: 搜索 + 评分
    total_kws = len(bg_summary.get("search_keywords", []))

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
        )
        st.session_state["bgm_last_session_id"] = session_id
        st.session_state["bgm_last_results"] = scored
        st.session_state["bgm_last_summary"] = bg_summary
        progress_bar.progress(100, text=f"完成！共匹配 {len(scored)} 条岗位。")
        st.success(f"匹配完成，共 {len(scored)} 条岗位，请切换到「匹配结果」Tab 查看。")
    except Exception as e:
        st.error(f"匹配过程出错：{e}")


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

    # 筛选器
    st.markdown("#### 筛选")
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
            + f" | {r.get('location','')}"
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
                if r.get("gap_analysis"):
                    st.warning(f"⚠️ 差距分析：{r['gap_analysis']}")
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

    # 4.1 薪资分布
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
                if salary_data:
                    median = sorted(salary_data)[len(salary_data) // 2]
                    st.caption(f"中位数薪资约 {median:.0f}K/月")
            else:
                st.caption("暂无薪资数据")
        except Exception as e:
            st.caption(f"薪资图表生成失败：{e}")

    # 4.3 工作强度分布
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

    # 4.2 竞争力评估
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

    # 4.4 技能缺口 Top10
    st.markdown("---")
    st.markdown("**高频技能缺口 Top 10**")
    try:
        from collections import Counter
        import re
        gap_texts = " ".join(r.get("gap_analysis", "") for r in records if r.get("gap_analysis"))
        # 简单提取中文词语（2-10字）作为关键词
        words = re.findall(r"[一-鿿]{2,10}|[A-Za-z]{3,15}", gap_texts)
        # 过滤停用词
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

        # 若当前正在查看此 session
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


print("✅ T03 完成")

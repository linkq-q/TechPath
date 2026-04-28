# 文件用途：学习中心页面（Phase 3），包含项目解读、知识点讲解、学习路径三个功能

import streamlit as st


def render():
    """渲染学习中心页面"""
    st.title("📖 学习中心")
    st.markdown("三种带学模式，学完直接进入检验，快速巩固 AI TA 技能。")

    # 处理来自知识网络页面的跳转预填充
    prefill_topic = st.session_state.pop("prefill_topic", None)
    if prefill_topic:
        st.session_state["study_topic"] = prefill_topic

    tab1, tab2, tab3 = st.tabs(["🔍 项目解读", "💡 知识点讲解", "🗺️ 学习路径"])

    # ============================================================
    # Tab 1: 项目解读
    # ============================================================
    with tab1:
        st.markdown("### 输入 GitHub 仓库 URL，生成完整学习报告")
        st.markdown("报告包含：项目概述、技术栈、目录结构、核心模块、数据流、设计模式、新手建议 共7个章节。")

        repo_url = st.text_input(
            "GitHub 仓库 URL",
            placeholder="https://github.com/owner/repo",
            key="study_repo_url",
        )

        if st.button("🚀 开始解读", key="btn_analyze_repo", use_container_width=True):
            if not repo_url.strip():
                st.warning("请先输入 GitHub 仓库 URL")
            else:
                st.session_state.pop("repo_report", None)
                st.session_state.pop("repo_suggested_questions", None)
                st.session_state.pop("repo_name", None)

                with st.status("正在解读仓库，请稍候...", expanded=True) as status:
                    st.write("📥 读取仓库中（README、文件树、代码文件）...")
                    from core.study import analyze_repo_for_learning
                    result = analyze_repo_for_learning(repo_url.strip())

                    if "error" in result:
                        status.update(label="❌ 解读失败", state="error")
                        st.error(result["error"])
                    else:
                        st.write("✨ 生成学习报告中...")
                        status.update(label="✅ 解读完成！", state="complete")
                        st.session_state["repo_report"] = result["report_markdown"]
                        st.session_state["repo_suggested_questions"] = result.get("suggested_questions", [])
                        st.session_state["repo_name"] = result.get("repo_name", repo_url)
                        st.session_state["repo_key_concepts"] = result.get("key_concepts", [])

        # 显示报告
        if "repo_report" in st.session_state:
            report = st.session_state["repo_report"]
            repo_name = st.session_state.get("repo_name", "")
            key_concepts = st.session_state.get("repo_key_concepts", [])

            st.markdown("---")
            st.markdown(f"## 📋 学习报告：{repo_name}")

            if key_concepts:
                st.markdown("**核心概念：** " + " | ".join([f"`{c}`" for c in key_concepts]))

            st.markdown(report)

            # 建议检验问题
            questions = st.session_state.get("repo_suggested_questions", [])
            if questions:
                st.markdown("---")
                st.markdown("### 🎯 建议检验问题")
                st.markdown("点击任意问题，跳转到检验页并自动填入：")

                for i, q in enumerate(questions):
                    col1, col2 = st.columns([5, 1])
                    with col1:
                        st.markdown(f"**Q{i+1}：** {q}")
                    with col2:
                        if st.button("去检验", key=f"goto_exam_repo_{i}"):
                            st.session_state["prefill_exam_message"] = q
                            st.session_state["current_page"] = "exam"
                            st.rerun()

            st.markdown("---")
            if st.button("🎯 开始检验这个项目", key="start_exam_repo", use_container_width=True):
                st.session_state["prefill_exam_message"] = (
                    f"请帮我检验关于 {repo_name} 这个仓库的学习成果，"
                    f"核心概念包括：{', '.join(key_concepts[:3])}"
                )
                st.session_state["current_page"] = "exam"
                st.rerun()

    # ============================================================
    # Tab 2: 知识点讲解
    # ============================================================
    with tab2:
        st.markdown("### 输入想学的知识点，获取个性化讲解")
        st.markdown("讲解结合 AI TA 岗位需求，包含定义、原理、应用场景、代码示例、常见误区。")

        col_topic, col_level = st.columns([3, 1])
        with col_topic:
            topic_input = st.text_input(
                "知识点",
                placeholder="如：LoRA微调、ComfyUI工作流、卡通渲染、Houdini程序化",
                key="study_topic",
            )
        with col_level:
            user_level = st.selectbox(
                "学习级别",
                ["初学者", "有一定基础", "进阶"],
                key="study_level",
            )

        if st.button("💡 开始讲解", key="btn_explain_topic", use_container_width=True):
            if not topic_input.strip():
                st.warning("请先输入想学的知识点")
            else:
                st.session_state.pop("topic_explanation", None)
                st.session_state.pop("topic_quiz_questions", None)
                st.session_state.pop("topic_name", None)

                with st.status(f"正在生成「{topic_input}」的讲解...", expanded=True) as status:
                    st.write("🔍 搜索知识库相关内容...")
                    st.write("📊 分析岗位需求深度...")
                    st.write("✍️ 生成个性化讲解中...")

                    from core.study import explain_topic
                    result = explain_topic(topic_input.strip(), user_level)

                    if "error" in result:
                        status.update(label="❌ 讲解生成失败", state="error")
                        st.error(result["error"])
                    else:
                        status.update(label="✅ 讲解完成！", state="complete")
                        st.session_state["topic_explanation"] = result["explanation_markdown"]
                        st.session_state["topic_quiz_questions"] = result.get("quiz_questions", [])
                        st.session_state["topic_related"] = result.get("related_topics", [])
                        st.session_state["topic_name"] = result["topic"]

        # 显示讲解内容
        if "topic_explanation" in st.session_state:
            topic_name = st.session_state.get("topic_name", "")
            explanation = st.session_state["topic_explanation"]
            quiz_questions = st.session_state.get("topic_quiz_questions", [])
            related = st.session_state.get("topic_related", [])

            st.markdown("---")
            st.markdown(f"## 📚 {topic_name} 讲解")
            st.markdown(explanation)

            # 相关话题
            if related:
                st.markdown("**相关话题：** " + " | ".join([f"`{t}`" for t in related]))

            # 检验题
            if quiz_questions:
                st.markdown("---")
                st.markdown("### 🧪 检验一下，你真的懂了吗？")
                st.markdown("以下是 3 道检验题，点击「开始检验」进入苏格拉底式检验：")

                for i, q in enumerate(quiz_questions):
                    st.markdown(f"**第{i+1}题：** {q}")

                col_start, col_skip = st.columns([1, 1])
                with col_start:
                    if st.button("🎯 开始检验这个知识点", key="start_exam_topic", use_container_width=True):
                        st.session_state["prefill_exam_message"] = (
                            f"请帮我检验「{topic_name}」这个知识点的掌握情况，"
                            f"从以下问题开始：{quiz_questions[0] if quiz_questions else ''}"
                        )
                        st.session_state["current_page"] = "exam"
                        st.rerun()
                with col_skip:
                    if st.button("📚 继续学其他知识点", key="skip_exam_topic", use_container_width=True):
                        st.session_state.pop("topic_explanation", None)
                        st.rerun()

    # ============================================================
    # Tab 3: 学习路径
    # ============================================================
    with tab3:
        st.markdown("### 生成个性化学习路径")
        st.markdown("基于当前岗位需求分析 + 你的历史学习记录，生成量身定制的学习计划。")

        col_role, col_weeks = st.columns([2, 1])
        with col_role:
            target_role = st.text_input(
                "目标岗位",
                value="AI TA",
                key="study_target_role",
            )
        with col_weeks:
            timeframe_weeks = st.slider(
                "准备时间（周）",
                min_value=4,
                max_value=52,
                value=14,
                key="study_weeks",
            )

        if st.button("🗺️ 生成学习路径", key="btn_gen_path", use_container_width=True):
            st.session_state.pop("learning_path_result", None)

            with st.status(f"正在为「{target_role}」生成 {timeframe_weeks} 周学习路径...", expanded=True) as status:
                st.write("📊 分析岗位核心技能需求...")
                st.write("🧠 读取你的学习记录...")
                st.write("📚 检索知识库内容...")
                st.write("✍️ 生成个性化路径中...")

                from core.study import generate_learning_path
                result = generate_learning_path(target_role.strip(), timeframe_weeks)

                if "error" in result:
                    status.update(label="❌ 生成失败", state="error")
                    st.error(result["error"])
                else:
                    status.update(label="✅ 学习路径生成完成！", state="complete")
                    st.session_state["learning_path_result"] = result

        # 显示学习路径
        if "learning_path_result" in st.session_state:
            r = st.session_state["learning_path_result"]
            path_md = r.get("path_markdown", "")
            current_gaps = r.get("current_gaps", [])
            weekly_plan = r.get("weekly_plan", [])
            milestones = r.get("milestones", [])
            portfolio_suggestions = r.get("portfolio_suggestions", [])

            st.markdown("---")
            st.markdown(f"## 🗺️ {r.get('target_role', 'AI TA')} {r.get('timeframe_weeks', 14)} 周学习路径")

            # 当前差距高亮
            if current_gaps:
                st.markdown("### ⚠️ 当前核心差距")
                for gap in current_gaps:
                    st.markdown(f"- 🔴 {gap}")

            # 详细路径（折叠展示）
            if path_md:
                # 把 Markdown 按 ## 章节切分，用 expander 展示
                sections = re.split(r"\n(?=## )", path_md)
                for section in sections:
                    if not section.strip():
                        continue
                    # 提取标题
                    lines = section.strip().split("\n")
                    title_line = lines[0].lstrip("#").strip() if lines else "内容"
                    body = "\n".join(lines[1:]).strip()

                    with st.expander(f"📌 {title_line}", expanded=False):
                        st.markdown(body)

            # 里程碑检验节点
            if milestones:
                st.markdown("### 🏁 里程碑检验节点")
                for i, milestone in enumerate(milestones):
                    st.markdown(f"**里程碑 {i+1}：** {milestone}")

            # 作品集建议
            if portfolio_suggestions:
                st.markdown("---")
                st.markdown("### 🎨 作品集建议")
                st.markdown("建议通过以下项目证明你的 AI TA 能力：")
                for i, suggestion in enumerate(portfolio_suggestions):
                    st.markdown(f"**项目 {i+1}：** {suggestion}")

            st.markdown("---")
            if st.button("🎯 开始检验当前掌握情况", key="start_exam_path", use_container_width=True):
                gap_text = "、".join(current_gaps[:3]) if current_gaps else "AI TA 核心技能"
                st.session_state["prefill_exam_message"] = (
                    f"请帮我评估当前的 AI TA 技能掌握情况，重点检验：{gap_text}"
                )
                st.session_state["current_page"] = "exam"
                st.rerun()


# 需要 re 模块用于章节切分
import re

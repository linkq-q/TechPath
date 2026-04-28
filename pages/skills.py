# 文件用途：技能包管理页面（Phase 4），查看/安装/启用禁用 Agent Skills

import streamlit as st

from core.database import delete_skill, get_all_skills
from core.skills_manager import (
    install_skill,
    scan_skills_directory,
    sync_skills_to_db,
    toggle_skill_active,
)

# 预置技能包简介
PRESET_SKILLS_INFO = [
    {
        "name": "AI_TA核心知识",
        "file": "ai_ta_core.skill.md",
        "desc": "AI TA岗位的核心技术考察标准，包含扩散模型、LoRA、ComfyUI、Shader的深度考察点。面试前必备，涵盖常见追问方向。",
    },
    {
        "name": "米哈游面试风格",
        "file": "mihoyo_style.skill.md",
        "desc": "模拟米哈游AI TA面试官的追问方式。启用后，Agent在模拟面试时会采用「先考概念，再追问工程落地经验」的追问节奏。",
    },
    {
        "name": "B站作品集评级标准",
        "file": "bilibili_grading.skill.md",
        "desc": "基于B站200+条TA求职作品集视频分析的评级逻辑。S/A/B/C评级标准，以及技术深度/广度/完整度的评分权重。",
    },
    {
        "name": "牛客面经精华",
        "file": "nowcoder_interview.skill.md",
        "desc": "从牛客网面经汇总的AI TA/技术美术高频考察点。包括渲染管线、PBR、LoRA参数、ComfyUI等高频追问和加分回答策略。",
    },
]


def render():
    st.title("⚡ 技能包管理")
    st.markdown("技能包（Skills）是 Agent 的专业知识模块，激活后会影响 Agent 的追问风格和分析深度。")

    # 确保目录扫描同步到数据库
    try:
        sync_skills_to_db()
    except Exception:
        pass

    st.markdown("---")

    # ---- 已安装技能列表 ----
    st.markdown("## 已安装技能包")
    skills = get_all_skills()

    if not skills:
        st.info("暂无已安装的技能包。")
    else:
        for skill in skills:
            name = skill["name"]
            desc = skill["description"]
            keywords = skill["trigger_keywords"]
            is_active = skill["is_active"]

            with st.container():
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    status_icon = "🟢" if is_active else "⚫"
                    st.markdown(f"**{status_icon} {name}**")
                    st.markdown(f"<small style='color:#8b949e'>{desc[:80]}...</small>", unsafe_allow_html=True)
                    if keywords:
                        kw_display = " · ".join(keywords[:6])
                        st.markdown(f"<small style='color:#58a6ff'>触发词：{kw_display}</small>", unsafe_allow_html=True)
                with col2:
                    new_active = st.toggle(
                        "启用",
                        value=is_active,
                        key=f"toggle_{name}",
                        help="启用后 Agent 会加载此技能包的内容",
                    )
                    if new_active != is_active:
                        toggle_skill_active(name, new_active)
                        action = "已启用" if new_active else "已禁用"
                        st.success(f"{action}「{name}」")
                        st.rerun()
                with col3:
                    if st.button("🗑️", key=f"del_{name}", help=f"删除 {name}"):
                        delete_skill(name)
                        st.warning(f"已删除「{name}」")
                        st.rerun()
                st.markdown("---")

    # ---- 新建技能包表单 ----
    st.markdown("## 新建技能包")
    with st.form("create_skill_form"):
        new_name = st.text_input("技能名称", placeholder="例如：网易面试风格")
        new_desc = st.text_input("描述", placeholder="一句话说明这个技能包的作用")
        new_keywords_str = st.text_input(
            "触发关键词（逗号分隔）",
            placeholder="例如：网易, 面试, 笔试, 游研社",
        )
        new_content = st.text_area(
            "技能内容（Markdown 格式）",
            height=200,
            placeholder="在这里写入技能的详细内容...",
        )
        submit = st.form_submit_button("📦 安装技能包", use_container_width=True)

        if submit:
            if not new_name.strip():
                st.error("技能名称不能为空")
            elif not new_content.strip():
                st.error("技能内容不能为空")
            else:
                kws = [k.strip() for k in new_keywords_str.split(",") if k.strip()]
                ok = install_skill(
                    name=new_name.strip(),
                    description=new_desc.strip(),
                    trigger_keywords=kws,
                    content=new_content.strip(),
                )
                if ok:
                    st.success(f"✅ 技能包「{new_name}」安装成功！")
                    st.rerun()
                else:
                    st.error("安装失败，请检查日志")

    st.markdown("---")

    # ---- 导入技能包 ----
    st.markdown("## 导入技能包文件")
    uploaded = st.file_uploader(
        "上传 .skill.md 文件",
        type=["md"],
        help="上传符合 YAML frontmatter 规范的技能包文件",
    )
    if uploaded:
        try:
            content_bytes = uploaded.read().decode("utf-8")
            from core.skills_manager import _parse_frontmatter
            meta, body = _parse_frontmatter(content_bytes)
            if not meta.get("name"):
                st.error("文件缺少 YAML frontmatter 或 name 字段，请检查格式。")
            else:
                ok = install_skill(
                    name=meta["name"],
                    description=meta.get("description", ""),
                    trigger_keywords=meta.get("trigger_keywords", []),
                    content=body,
                    level=meta.get("level", 1),
                )
                if ok:
                    st.success(f"✅ 已导入技能包「{meta['name']}」")
                    st.rerun()
                else:
                    st.error("导入失败，请检查日志")
        except Exception as e:
            st.error(f"文件解析失败：{e}")

    st.markdown("---")

    # ---- 预置技能包说明 ----
    st.markdown("## 预置技能包说明")
    st.markdown("以下 4 个预置技能包已随项目安装，你可以根据自己的需求修改 `skills/` 目录下的对应文件：")

    for info in PRESET_SKILLS_INFO:
        with st.expander(f"📄 {info['name']}（`{info['file']}`）"):
            st.markdown(info["desc"])
            st.markdown(
                f"<small style='color:#8b949e'>文件路径：`skills/{info['file']}`，"
                f"可直接编辑文件内容后重启应用生效。</small>",
                unsafe_allow_html=True,
            )

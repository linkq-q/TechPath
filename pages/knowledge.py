# 文件用途：知识库管理页（Phase 1 + Phase 2），支持 GitHub / URL / 文本 / 视频四种导入方式

import os

import streamlit as st

from core.database import (
    delete_knowledge_item,
    get_all_knowledge_items,
    save_knowledge_item,
)
from core.tools import import_text_content, import_video, read_github_repo

# 检测 QWEN_API_KEY 是否配置
_HAS_QWEN = bool(os.getenv("QWEN_API_KEY", ""))


def render() -> None:
    """渲染知识库管理页面"""
    st.title("知识库")
    st.markdown("管理你的学习材料，支持 GitHub 仓库、文章 URL、纯文本、B 站视频四种导入方式。")

    tab_github, tab_url, tab_text, tab_video = st.tabs(["GitHub 仓库", "文章 / URL", "直接输入", "视频导入"])

    # ---- Tab 4: 视频导入 ----
    with tab_video:
        st.markdown("#### 导入 B 站视频")

        if not _HAS_QWEN:
            st.warning("未配置 QWEN_API_KEY，将跳过画面分析，仅进行音频转录。")

        video_url = st.text_input(
            "B 站视频 URL",
            placeholder="https://www.bilibili.com/video/BVxxxxxxxxx",
            key="video_url_input",
        )
        video_title = st.text_input(
            "自定义标题（可选）",
            placeholder="留空则自动从视频信息获取",
            key="video_title_input",
        )

        if st.button("导入视频", key="btn_video"):
            if not video_url.strip():
                st.error("请输入 B 站视频 URL")
            else:
                with st.status("正在导入视频...", expanded=True) as status:
                    st.write("步骤 1/2：转录音频中（可能需要数分钟）...")

                    # import_video 内部会先转录再分析
                    result = import_video(
                        url=video_url.strip(),
                        title=video_title.strip(),
                    )

                    if "error" in result:
                        status.update(label="导入失败", state="error", expanded=True)
                        st.error(f"导入失败：{result['error']}")
                    else:
                        has_visual = result.get("has_visual", False)
                        if _HAS_QWEN:
                            st.write("步骤 2/2：画面分析完成" if has_visual else "步骤 2/2：画面分析跳过（分析失败）")
                        else:
                            st.write("步骤 2/2：已跳过画面分析（未配置 QWEN_API_KEY）")

                        status.update(label="视频导入完成", state="complete", expanded=False)

                        st.success(f"视频导入成功！（ID: {result['id']}）")
                        st.info(f"**摘要：** {result['summary']}")
                        if result.get("tags"):
                            st.markdown(
                                "**识别到的技术标签：** " + " ".join(f"`{t}`" for t in result["tags"])
                            )
                        st.rerun()

    # ---- Tab 1: GitHub 仓库 ----
    with tab_github:
        st.markdown("#### 导入 GitHub 仓库")
        github_url = st.text_input(
            "仓库 URL",
            placeholder="https://github.com/owner/repo",
            key="github_url_input",
        )
        custom_title = st.text_input(
            "自定义标题（可选）",
            placeholder="留空则使用仓库名",
            key="github_title_input",
        )

        if st.button("导入仓库", key="btn_github"):
            if not github_url.strip():
                st.error("请输入仓库 URL")
            else:
                with st.spinner("正在读取 GitHub 仓库，请稍候..."):
                    result = read_github_repo(github_url.strip())

                if "error" in result:
                    st.error(f"导入失败：{result['error']}")
                else:
                    # 组合成 full_text 存储
                    full_text_parts = [
                        f"# {result['repo_name']}\n",
                        f"描述：{result['description']}\n\n",
                        "## README\n",
                        result["readme"],
                        "\n\n## 文件树\n",
                        "\n".join(
                            f"{'[目录]' if f.get('type') == 'dir' else '[文件]'} {f.get('path', '')}"
                            for f in result.get("file_tree", [])
                            if isinstance(f, dict) and "path" in f
                        ),
                    ]
                    for path, content in result.get("key_files", {}).items():
                        full_text_parts.append(f"\n\n## 文件：{path}\n```\n{content}\n```")

                    full_text = "".join(full_text_parts)

                    # 生成摘要（复用 import_text_content 的 AI 能力）
                    with st.spinner("正在生成摘要..."):
                        summary_result = import_text_content(
                            content=full_text[:4000],
                            source_url=github_url.strip(),
                            title=custom_title.strip() or result["repo_name"],
                        )

                    if "error" in summary_result:
                        # AI 摘要失败，直接存储
                        item_id = save_knowledge_item(
                            title=custom_title.strip() or result["repo_name"],
                            content_summary=result["description"] or result["readme"][:100],
                            full_text=full_text,
                            source_type="github",
                            source_url=github_url.strip(),
                            tags=[],
                        )
                        st.success(f"仓库已导入（ID: {item_id}），AI 摘要生成失败，使用默认摘要。")
                    else:
                        st.success(f"仓库导入成功！（ID: {summary_result['id']}）")
                        st.info(f"**摘要：** {summary_result['summary']}")
                        if summary_result.get("tags"):
                            st.markdown(
                                "**标签：** " + " ".join(f"`{t}`" for t in summary_result["tags"])
                            )

                    st.rerun()

    # ---- Tab 2: URL / 文章 ----
    with tab_url:
        st.markdown("#### 导入 URL 或粘贴文章")
        url_or_text = st.text_area(
            "URL 或文章内容",
            placeholder="输入以 http 开头的 URL，或粘贴文章正文",
            height=150,
            key="url_input",
        )
        url_title = st.text_input(
            "自定义标题（可选）",
            placeholder="留空则自动生成",
            key="url_title_input",
        )

        if st.button("导入", key="btn_url"):
            if not url_or_text.strip():
                st.error("请输入 URL 或文章内容")
            else:
                with st.spinner("正在导入，AI 生成摘要中..."):
                    result = import_text_content(
                        content=url_or_text.strip(),
                        title=url_title.strip(),
                    )

                if "error" in result:
                    st.error(f"导入失败：{result['error']}")
                else:
                    st.success(f"导入成功！（ID: {result['id']}）")
                    st.info(f"**摘要：** {result['summary']}")
                    if result.get("tags"):
                        st.markdown(
                            "**标签：** " + " ".join(f"`{t}`" for t in result["tags"])
                        )
                    st.rerun()

    # ---- Tab 3: 直接输入文本 ----
    with tab_text:
        st.markdown("#### 直接输入文本")
        text_title = st.text_input(
            "标题",
            placeholder="请输入标题",
            key="text_title_input",
        )
        text_content = st.text_area(
            "文本内容",
            placeholder="粘贴或输入你想学习的技术内容",
            height=200,
            key="text_content_input",
        )

        if st.button("导入", key="btn_text"):
            if not text_content.strip():
                st.error("请输入文本内容")
            elif not text_title.strip():
                st.error("请输入标题")
            else:
                with st.spinner("正在导入，AI 生成摘要中..."):
                    result = import_text_content(
                        content=text_content.strip(),
                        title=text_title.strip(),
                    )

                if "error" in result:
                    st.error(f"导入失败：{result['error']}")
                else:
                    st.success(f"导入成功！（ID: {result['id']}）")
                    st.info(f"**摘要：** {result['summary']}")
                    st.rerun()

    # ---- 已导入内容列表 ----
    st.markdown("---")
    st.markdown("### 已导入内容")

    items = get_all_knowledge_items()
    if not items:
        st.info("知识库为空，请导入内容后开始学习。")
        return

    for item in items:
        with st.container():
            col_info, col_del = st.columns([5, 1])
            with col_info:
                source_badge = {
                    "github": "GitHub",
                    "article": "文章",
                    "text": "文本",
                    "video": "视频",
                }.get(item["source_type"], item["source_type"])

                st.markdown(
                    f"**{item['title']}** &nbsp;&nbsp;"
                    f"<span style='color:#8b949e;font-size:0.85em'>"
                    f"[{source_badge}] &nbsp; {item['created_at'][:10] if item['created_at'] else ''}"
                    f"</span>",
                    unsafe_allow_html=True,
                )
                if item["content_summary"]:
                    st.markdown(
                        f"<small style='color:#8b949e'>{item['content_summary'][:120]}</small>",
                        unsafe_allow_html=True,
                    )
                tags = item.get("tags", [])
                if tags:
                    st.markdown(
                        " ".join(f"`{t}`" for t in tags),
                        unsafe_allow_html=False,
                    )

            with col_del:
                if st.button("删除", key=f"del_{item['id']}"):
                    delete_knowledge_item(item["id"])
                    st.rerun()

            st.markdown(
                "<hr style='margin:6px 0;border-color:#21262d'>",
                unsafe_allow_html=True,
            )

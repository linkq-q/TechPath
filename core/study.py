# 文件用途：带学功能核心模块（Phase 3 + Phase 4），包含仓库解读、知识点讲解、学习路径规划三大功能
# Phase 4 新增：完成后自动保存学习历史并更新知识网络

import json
import os
import re

from dotenv import load_dotenv
from openai import OpenAI

from core.database import (
    get_all_knowledge_items,
    get_latest_jd_analysis,
    save_knowledge_item,
    save_study_session,
)
from core.memory import get_all_memories
from core.tools import read_github_repo, search_knowledge_base

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

_client = None


def _get_client() -> OpenAI:
    """懒加载 DeepSeek 客户端"""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )
    return _client


def _call_deepseek(prompt: str, temperature: float = 0.5) -> str:
    """调用 DeepSeek 生成内容，返回文本字符串"""
    client = _get_client()
    resp = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


# ============================================================
# T02：仓库解读模式
# ============================================================

def analyze_repo_for_learning(url: str) -> dict:
    """
    读取 GitHub 仓库并生成面向学习者的完整解读报告。

    Args:
        url: GitHub 仓库 URL

    Returns:
        {repo_name, report_markdown, key_concepts, suggested_questions}
        出错时返回 {"error": "..."}
    """
    # Step 1: 读取仓库内容
    repo_data = read_github_repo(url)
    if "error" in repo_data:
        return {"error": repo_data["error"]}

    repo_name = repo_data.get("repo_name", "未知仓库")
    description = repo_data.get("description", "")
    readme = repo_data.get("readme", "")
    file_tree = repo_data.get("file_tree", [])
    key_files = repo_data.get("key_files", {})

    # 构造文件树文本
    tree_text = "\n".join([
        f"{'📁' if item.get('type') == 'dir' else '📄'} {item.get('path', '')}"
        for item in file_tree[:50]
    ])

    # 取前 5 个关键代码文件的内容片段
    code_snippets = ""
    for path, content in list(key_files.items())[:5]:
        code_snippets += f"\n### {path}\n```\n{content[:800]}\n```\n"

    # Step 2: 调用 DeepSeek 生成学习报告
    prompt = f"""你是一位资深技术导师，请帮助一位 Python 初学者深度理解以下 GitHub 仓库。

仓库名称：{repo_name}
仓库描述：{description}

README 内容（部分）：
{readme[:3000]}

文件目录结构：
{tree_text}

关键代码文件（部分）：
{code_snippets}

请生成一份完整的学习报告，必须包含以下 7 个章节，使用 Markdown 格式，代码用代码块标注：

## 1. 项目概述
- 这个项目是什么
- 解决什么问题
- 适合什么人学习

## 2. 技术栈分析
列出所有使用的技术，每个技术说明其作用

## 3. 目录结构解读
逐一解释每个重要文件夹和文件的职责

## 4. 核心模块详解
选出最重要的 3-5 个模块，详细说明每个模块做什么、怎么做

## 5. 数据流分析
用文字描述数据是如何在各个模块之间流动的（可以用 ASCII 流程图）

## 6. 设计模式识别
识别代码中使用了哪些设计模式，在哪里用的，为什么这样用

## 7. 新手阅读建议
建议按什么顺序阅读代码，从哪个文件开始，每步能学到什么

报告末尾另起一行，严格按以下 JSON 格式输出关键信息（不要加 markdown 代码块标记）：
REPORT_META_JSON::{{"key_concepts": ["概念1", "概念2", "概念3"], "suggested_questions": ["问题1?", "问题2?", "问题3?", "问题4?", "问题5?"]}}"""

    try:
        raw = _call_deepseek(prompt, temperature=0.4)
    except Exception as e:
        return {"error": f"DeepSeek 调用失败：{e}"}

    # 提取元数据 JSON
    key_concepts = []
    suggested_questions = []
    report_markdown = raw

    meta_match = re.search(r"REPORT_META_JSON::(\{.*\})", raw, re.DOTALL)
    if meta_match:
        try:
            meta = json.loads(meta_match.group(1))
            key_concepts = meta.get("key_concepts", [])
            suggested_questions = meta.get("suggested_questions", [])
        except Exception:
            pass
        # 从报告中去掉元数据行
        report_markdown = raw[:meta_match.start()].strip()

    # Step 3: 存入知识库（source_type 标记为 repo_analysis）
    try:
        save_knowledge_item(
            title=f"【仓库解读】{repo_name}",
            content_summary=f"GitHub 仓库 {repo_name} 的完整学习报告，包含技术栈、目录结构、核心模块等7个章节。",
            full_text=report_markdown,
            source_type="repo_analysis",
            source_url=url,
            tags=key_concepts[:5],
        )
    except Exception as e:
        print(f"[study] 存入知识库失败：{e}")

    # Step 4: 存入 study_sessions
    try:
        save_study_session(
            mode="repo_analysis",
            input_content=url,
            report_json=json.dumps(
                {"repo_name": repo_name, "key_concepts": key_concepts,
                 "suggested_questions": suggested_questions},
                ensure_ascii=False,
            ),
        )
    except Exception as e:
        print(f"[study] 存入 study_sessions 失败：{e}")

    # Step 5 (Phase 4): 保存学习历史并更新知识网络
    try:
        from core.history import extract_and_update_knowledge_nodes, save_study_record
        history_id = save_study_record(
            session_type="repo_analysis",
            title=f"仓库解读：{repo_name}",
            input_content=url,
            full_report=report_markdown,
            knowledge_tags=key_concepts[:10],
        )
        extract_and_update_knowledge_nodes(history_id)
    except Exception as e:
        print(f"[study] Phase4 保存历史失败：{e}")

    return {
        "repo_name": repo_name,
        "report_markdown": report_markdown,
        "key_concepts": key_concepts,
        "suggested_questions": suggested_questions,
    }


# ============================================================
# T03：知识点讲解模式
# ============================================================

def explain_topic(topic: str, user_level: str = "初学者") -> dict:
    """
    生成知识点讲解，结合知识库内容和 JD 岗位需求。

    Args:
        topic: 要学习的知识点，如「LoRA微调」「卡通渲染」
        user_level: 学习级别（初学者/有一定基础/进阶）

    Returns:
        {topic, explanation_markdown, quiz_questions, related_topics}
    """
    # Step 1: 搜索知识库
    kb_results = search_knowledge_base(topic)
    kb_context = ""
    if kb_results and not any("error" in r for r in kb_results):
        kb_context = "知识库中的相关内容：\n"
        for r in kb_results[:3]:
            kb_context += f"- {r.get('title', '')}: {r.get('content_summary', '')}\n"

    # Step 2: 获取 JD 岗位要求（了解市场对这个知识点的深度需求）
    jd_analyses = get_latest_jd_analysis(n=1)
    jd_context = ""
    if jd_analyses:
        latest = jd_analyses[0]
        top_skills = latest.get("top_skills", [])
        jd_context = f"当前 AI TA 岗位高频技能：{', '.join([s.get('skill', s) if isinstance(s, dict) else s for s in top_skills[:8]])}"

    # Step 3: 生成讲解内容
    prompt = f"""你是一位耐心的技术导师，专门为 AI TA（技术美术）求职者讲解技术知识点。
目标学员级别：{user_level}

{kb_context}
{jd_context}

请为学员讲解「{topic}」，必须包含以下 7 个部分，使用通俗易懂的中文，适合 {user_level} 理解：

## 一句话定义
用最简洁的语言说清楚{topic}是什么（不超过 30 字）

## 为什么重要
结合 AI TA 岗位实际需求，说明这个知识点为什么值得学（1-3 条）

## 核心原理
用类比和图示文字把原理说清楚，避免堆砌术语

## 实际应用场景
在游戏开发和 AI TA 工作中，这个知识点具体怎么用（2-3 个真实场景）

## 最小可运行示例
如果涉及代码/工具操作，给出最简单的入门示例（用代码块标注语言）

## 常见误区
初学者容易犯的 2-3 个错误或误解

## 进阶方向
学完基础之后可以深入的 2-3 个方向

报告末尾另起一行，严格按以下格式输出（不加 markdown 代码块标记）：
EXPLAIN_META_JSON::{{"quiz_questions": ["检验题1?", "检验题2?", "检验题3?"], "related_topics": ["相关话题1", "相关话题2", "相关话题3"]}}"""

    try:
        raw = _call_deepseek(prompt, temperature=0.5)
    except Exception as e:
        return {"error": f"DeepSeek 调用失败：{e}"}

    # 提取元数据
    quiz_questions = []
    related_topics = []
    explanation_markdown = raw

    meta_match = re.search(r"EXPLAIN_META_JSON::(\{.*\})", raw, re.DOTALL)
    if meta_match:
        try:
            meta = json.loads(meta_match.group(1))
            quiz_questions = meta.get("quiz_questions", [])
            related_topics = meta.get("related_topics", [])
        except Exception:
            pass
        explanation_markdown = raw[:meta_match.start()].strip()

    # 存入 study_sessions
    try:
        save_study_session(
            mode="topic_explain",
            input_content=topic,
            report_json=json.dumps(
                {"topic": topic, "user_level": user_level,
                 "quiz_questions": quiz_questions, "related_topics": related_topics},
                ensure_ascii=False,
            ),
        )
    except Exception as e:
        print(f"[study] 存入 study_sessions 失败：{e}")

    # Phase 4: 保存学习历史并更新知识网络
    try:
        from core.history import extract_and_update_knowledge_nodes, save_study_record
        tags = [topic] + related_topics[:5]
        history_id = save_study_record(
            session_type="topic_explain",
            title=f"知识点讲解：{topic}",
            input_content=topic,
            full_report=explanation_markdown,
            knowledge_tags=tags,
        )
        extract_and_update_knowledge_nodes(history_id)
    except Exception as e:
        print(f"[study] Phase4 保存历史失败：{e}")

    return {
        "topic": topic,
        "explanation_markdown": explanation_markdown,
        "quiz_questions": quiz_questions,
        "related_topics": related_topics,
    }


# ============================================================
# T04：学习路径规划模式
# ============================================================

def generate_learning_path(target_role: str = "AI TA", timeframe_weeks: int = 14) -> dict:
    """
    基于 JD 需求、用户记忆和知识库内容，生成个性化学习路径。

    Args:
        target_role: 目标岗位，默认 "AI TA"
        timeframe_weeks: 准备时间（周），默认 14 周

    Returns:
        {current_gaps, weekly_plan, milestones, portfolio_suggestions}
    """
    # Step 1: 获取 JD 核心技能要求
    jd_analyses = get_latest_jd_analysis(n=1)
    jd_skills_text = "暂无 JD 分析数据"
    if jd_analyses:
        latest = jd_analyses[0]
        top_skills = latest.get("top_skills", [])
        skills_list = [
            f"{s.get('skill', s)}（频次:{s.get('count', '未知')}）" if isinstance(s, dict) else s
            for s in top_skills[:10]
        ]
        jd_skills_text = "岗位核心技能：" + "、".join(skills_list)
        trend = latest.get("trend_changes", "")
        if trend:
            jd_skills_text += f"\n趋势：{trend}"

    # Step 2: 获取用户已掌握的知识（Mem0 记忆）
    memories = get_all_memories()
    mastered_text = "暂无学习记录"
    if memories:
        memory_lines = [m.get("memory", m.get("text", "")) for m in memories[:10] if m]
        mastered_text = "用户学习记录：\n" + "\n".join(f"- {line}" for line in memory_lines if line)

    # Step 3: 获取知识库内容
    kb_items = get_all_knowledge_items()
    kb_text = "知识库为空"
    if kb_items:
        kb_list = [f"{item['title']}（{item['source_type']}）" for item in kb_items[:15]]
        kb_text = "知识库已有内容：" + "；".join(kb_list)

    # Step 4: 生成学习路径
    prompt = f"""你是一位 AI TA（技术美术）领域的职业规划导师。
请根据以下信息，为学员生成一份个性化的 {timeframe_weeks} 周学习计划，目标是求职 {target_role} 岗位。

【岗位需求】
{jd_skills_text}

【学员当前状态】
{mastered_text}

【学员知识库】
{kb_text}

请生成完整的学习路径报告，格式如下：

## 当前状态分析
- 已掌握的技能（根据学习记录推断）
- 核心差距（与岗位要求的差距）
- 建议优先补足的 3-5 个技能

## 分阶段学习计划（按周）
将 {timeframe_weeks} 周划分为若干阶段，每个阶段包含：
- 阶段名称和目标
- 每周具体学习内容
- 推荐资源（GitHub 项目名称、B站视频搜索关键词、文档链接描述）

## 里程碑检验节点
每个阶段结束时，学员应该能够做到什么（可量化的输出物）

## 作品集建议
建议做哪 3-5 个项目来证明 {target_role} 能力，每个项目说明技术点和预期效果

报告末尾另起一行，严格按以下格式输出（不加 markdown 代码块标记）：
PATH_META_JSON::{{"current_gaps": ["差距1", "差距2", "差距3"], "weekly_plan_summary": ["第1-N周：..."], "milestones": ["里程碑1", "里程碑2"], "portfolio_suggestions": ["项目1", "项目2", "项目3"]}}"""

    try:
        raw = _call_deepseek(prompt, temperature=0.4)
    except Exception as e:
        return {"error": f"DeepSeek 调用失败：{e}"}

    # 提取元数据
    current_gaps = []
    weekly_plan = []
    milestones = []
    portfolio_suggestions = []
    path_markdown = raw

    meta_match = re.search(r"PATH_META_JSON::(\{.*\})", raw, re.DOTALL)
    if meta_match:
        try:
            meta = json.loads(meta_match.group(1))
            current_gaps = meta.get("current_gaps", [])
            weekly_plan = meta.get("weekly_plan_summary", [])
            milestones = meta.get("milestones", [])
            portfolio_suggestions = meta.get("portfolio_suggestions", [])
        except Exception:
            pass
        path_markdown = raw[:meta_match.start()].strip()

    # 存入 study_sessions
    try:
        save_study_session(
            mode="learning_path",
            input_content=f"{target_role}/{timeframe_weeks}周",
            report_json=json.dumps(
                {
                    "target_role": target_role,
                    "timeframe_weeks": timeframe_weeks,
                    "current_gaps": current_gaps,
                    "weekly_plan": weekly_plan,
                    "milestones": milestones,
                    "portfolio_suggestions": portfolio_suggestions,
                },
                ensure_ascii=False,
            ),
        )
    except Exception as e:
        print(f"[study] 存入 study_sessions 失败：{e}")

    # Phase 4: 保存学习历史
    try:
        from core.history import save_study_record
        save_study_record(
            session_type="learning_path",
            title=f"学习路径：{target_role} / {timeframe_weeks}周",
            input_content=f"{target_role}/{timeframe_weeks}周",
            full_report=path_markdown,
            knowledge_tags=current_gaps[:8],
        )
    except Exception as e:
        print(f"[study] Phase4 保存历史失败：{e}")

    return {
        "target_role": target_role,
        "timeframe_weeks": timeframe_weeks,
        "path_markdown": path_markdown,
        "current_gaps": current_gaps,
        "weekly_plan": weekly_plan,
        "milestones": milestones,
        "portfolio_suggestions": portfolio_suggestions,
    }


print("✅ T02/T03/T04 完成（Phase 3 + Phase 4 历史记录集成）")

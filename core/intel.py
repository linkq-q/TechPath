# 文件用途：岗位情报分析模块（Phase 2 + Phase 3），整合 JD 爬取和 B站竞品监测

import json
import os
from collections import Counter

from dotenv import load_dotenv
from openai import OpenAI

from core.database import (
    get_all_jd_records,
    get_all_knowledge_items,
    get_bilibili_portfolios,
    get_latest_jd_analysis,
    save_bilibili_portfolio,
    save_jd_analysis,
    update_portfolio_grade,
)
from core.tools import search_knowledge_base

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

_deepseek_client = None


def _get_client() -> OpenAI:
    """懒加载 DeepSeek 客户端"""
    global _deepseek_client
    if _deepseek_client is None:
        _deepseek_client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )
    return _deepseek_client


def analyze_jd_requirements(jd_list: list) -> dict:
    """
    分析 JD 列表，提取技能频次、新关键词，并生成 Gap 分析。

    Args:
        jd_list: JD 列表，每条至少包含 requirements_raw 字段

    Returns:
        {"top_skills": list, "new_keywords": list, "gap_analysis": str,
         "trend_changes": str, "sample_count": int}
    """
    if not jd_list:
        return {
            "top_skills": [],
            "new_keywords": [],
            "gap_analysis": "暂无 JD 数据，请先爬取岗位信息。",
            "trend_changes": "",
            "sample_count": 0,
        }

    # 拼接所有 JD 文本（最多 50 条，避免 token 超支）
    jd_texts = []
    for jd in jd_list[:50]:
        raw = jd.get("requirements_raw", "")
        if raw:
            jd_texts.append(raw[:500])

    combined = "\n---\n".join(jd_texts)
    sample_count = len(jd_list)

    # 获取上次分析的关键词（用于对比新词）
    prev_analyses = get_latest_jd_analysis(n=2)
    prev_skills = set()
    if len(prev_analyses) > 1:
        # 取上上次的作为对比基准（最新的是这次之前保存的）
        for sk in prev_analyses[-1].get("top_skills", []):
            if isinstance(sk, dict):
                prev_skills.add(sk.get("skill", "").lower())
            elif isinstance(sk, str):
                prev_skills.add(sk.lower())

    # 获取用户知识库内容，用于 Gap 分析
    kb_items = get_all_knowledge_items()
    kb_summary = "；".join([
        f"{item['title']}（{item['source_type']}）"
        for item in kb_items[:20]
    ]) or "（知识库为空）"

    # 调用 DeepSeek 分析
    try:
        client = _get_client()
        prompt = f"""请分析以下 {sample_count} 条 AI TA（技术美术助理/AI 技术美术）岗位的 JD：

{combined[:6000]}

请完成以下任务并严格按 JSON 格式返回：

1. 提取出现频次最高的 TOP 10 技术技能，每个包含技能名和频次估计
2. 识别新兴/高热词汇（近期出现频率上升的词）
3. 总结技能需求趋势变化（2-3句话）
4. 基于以下用户已学内容，给出 Gap 分析（哪些技能未学、哪些已涉及）：
   用户知识库：{kb_summary}

返回格式（严格 JSON，不加其他内容）：
{{
  "top_skills": [{{"skill": "Python", "count": 15}}, ...],
  "new_keywords": ["关键词1", "关键词2"],
  "trend_changes": "趋势描述...",
  "gap_analysis": "Gap 分析：\\n未学：...\\n已涉及：...\\n建议优先学习：..."
}}"""

        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        raw = resp.choices[0].message.content.strip()

        import re
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
        else:
            parsed = {}

        top_skills = parsed.get("top_skills", [])
        new_keywords = parsed.get("new_keywords", [])
        trend_changes = parsed.get("trend_changes", "")
        gap_analysis = parsed.get("gap_analysis", "")

    except Exception as e:
        # AI 分析失败时做简单词频统计
        top_skills = _simple_skill_count(combined)
        new_keywords = []
        trend_changes = f"AI 分析失败：{e}"
        gap_analysis = "AI 分析失败，无法生成 Gap 分析。"

    # 识别新出现的关键词
    if prev_skills and top_skills:
        current_skill_names = {
            (sk.get("skill", "") if isinstance(sk, dict) else sk).lower()
            for sk in top_skills
        }
        detected_new = [s for s in current_skill_names if s not in prev_skills]
        if detected_new and not new_keywords:
            new_keywords = detected_new[:5]

    # 保存分析结果
    try:
        save_jd_analysis(
            top_skills_json=json.dumps(top_skills, ensure_ascii=False),
            new_keywords_json=json.dumps(new_keywords, ensure_ascii=False),
            trend_changes=trend_changes,
            sample_count=sample_count,
        )
    except Exception as e:
        print(f"[intel] 保存分析结果失败：{e}")

    return {
        "top_skills": top_skills,
        "new_keywords": new_keywords,
        "gap_analysis": gap_analysis,
        "trend_changes": trend_changes,
        "sample_count": sample_count,
    }


def _simple_skill_count(text: str) -> list:
    """简单关键词频次统计（AI 分析失败时的降级方案）"""
    keywords = [
        "Python", "C#", "Unity", "Houdini", "Shader", "HLSL", "GLSL",
        "ComfyUI", "Stable Diffusion", "LoRA", "ControlNet", "AI",
        "机器学习", "深度学习", "图形学", "渲染", "特效", "VFX",
        "材质", "动画", "3ds Max", "Maya", "Blender", "UE5",
    ]
    counter = Counter()
    text_lower = text.lower()
    for kw in keywords:
        count = text_lower.count(kw.lower())
        if count > 0:
            counter[kw] = count

    return [{"skill": k, "count": v} for k, v in counter.most_common(10)]


def refresh_intel(keyword: str = "AI TA") -> dict:
    """
    刷新情报：爬取最新 JD 数据并执行分析，返回完整分析结果。

    Args:
        keyword: 搜索关键词

    Returns:
        与 analyze_jd_requirements 相同的字典结构，额外包含 crawl_count 字段
    """
    from core.crawlers.bosszp import crawl_bosszp
    from core.crawlers.general import crawl_niuke

    all_jd = []
    crawl_errors = []

    # 爬取 Boss 直聘（优先）
    try:
        print(f"[intel] 开始爬取 Boss 直聘，关键词：{keyword}")
        bz_results = crawl_bosszp(keyword=keyword, max_count=10)
        all_jd.extend(bz_results)
        print(f"[intel] Boss 直聘爬取 {len(bz_results)} 条")
    except Exception as e:
        crawl_errors.append(f"Boss 直聘：{e}")
        print(f"[intel] Boss 直聘爬取失败：{e}")

    # 爬取牛客网面经
    try:
        print(f"[intel] 开始爬取牛客网，关键词：{keyword}")
        nk_results = crawl_niuke(keyword=f"{keyword} 面经")
        for r in nk_results:
            all_jd.append({
                "requirements_raw": f"{r.get('title', '')} {r.get('summary', '')}",
                "platform": "niuke",
            })
        print(f"[intel] 牛客网爬取 {len(nk_results)} 条")
    except Exception as e:
        crawl_errors.append(f"牛客网：{e}")
        print(f"[intel] 牛客网爬取失败：{e}")

    # 若两个渠道都失败，从数据库取历史数据
    if not all_jd:
        print("[intel] 网络爬取均失败，从数据库加载历史 JD 数据")
        all_jd = get_all_jd_records(limit=50)

    result = analyze_jd_requirements(all_jd)
    result["crawl_count"] = len(all_jd)
    result["crawl_errors"] = crawl_errors

    return result


# ============================================================
# T09：B站竞品监测完整流程
# ============================================================

def refresh_bilibili_portfolios(force_reanalyze: bool = False) -> dict:
    """
    串联采集、分析、评级的完整竞品监测流程。

    Args:
        force_reanalyze: 是否强制重新分析（忽略已有数据）

    Returns:
        {total_count, grade_distribution, s_grade_tags, analyzed_at}
    """
    from core.crawlers.bilibili import (
        analyze_portfolio_video,
        crawl_bilibili_portfolios,
        grade_portfolios,
    )
    from datetime import datetime
    from collections import Counter

    print("[intel] 开始 B站竞品监测流程...")

    # Step 1: 采集视频列表
    print("[intel] Step 1: 采集视频列表...")
    try:
        raw_videos = crawl_bilibili_portfolios(max_count=30)
    except Exception as e:
        print(f"[intel] 采集失败：{e}")
        raw_videos = []

    if not raw_videos:
        return {
            "total_count": 0,
            "grade_distribution": {"S": 0, "A": 0, "B": 0, "C": 0},
            "s_grade_tags": [],
            "analyzed_at": datetime.utcnow().isoformat(),
            "error": "采集到 0 条视频，请检查网络连接",
        }

    # Step 2: 逐条分析打标并存库
    print(f"[intel] Step 2: 分析 {len(raw_videos)} 条视频...")
    analyzed_videos = []
    for i, video in enumerate(raw_videos):
        try:
            analysis = analyze_portfolio_video(video)
            merged = {**video, **analysis}
            analyzed_videos.append(merged)

            # 存入数据库
            save_bilibili_portfolio(
                video_url=video.get("video_url", ""),
                uploader=video.get("uploader", ""),
                title=video.get("title", ""),
                publish_date=video.get("publish_date", ""),
                cohort=video.get("cohort", "未知届别"),
                stage=video.get("stage", "未知阶段"),
                tech_tags=analysis.get("tech_tags", []),
            )
            print(f"[intel]   已分析 {i + 1}/{len(raw_videos)}: {video.get('title', '')[:30]}")
        except Exception as e:
            print(f"[intel]   分析失败（{video.get('title', '')}）：{e}")
            analyzed_videos.append(video)

    # Step 3: 评级
    print("[intel] Step 3: 计算评级...")
    try:
        graded_videos = grade_portfolios(analyzed_videos)
    except Exception as e:
        print(f"[intel] 评级失败：{e}")
        graded_videos = analyzed_videos

    # Step 4: 更新数据库评级
    for v in graded_videos:
        url = v.get("video_url", "")
        grade = v.get("grade", "")
        score = v.get("score", "")
        if url and grade:
            try:
                update_portfolio_grade(url, grade, score)
            except Exception as e:
                print(f"[intel]   更新评级失败（{url}）：{e}")

    # Step 5: 汇总统计
    grade_dist = {"S": 0, "A": 0, "B": 0, "C": 0}
    s_tags_counter = Counter()

    for v in graded_videos:
        grade = v.get("grade", "").rstrip("*")  # 去掉样本不足标注
        if grade in grade_dist:
            grade_dist[grade] += 1
        if grade == "S":
            for tag in v.get("tech_tags", []):
                s_tags_counter[tag] += 1

    s_grade_tags = [tag for tag, _ in s_tags_counter.most_common(10)]
    analyzed_at = datetime.utcnow().isoformat()

    print(f"[intel] 竞品监测完成：{len(graded_videos)} 条，分布 {grade_dist}")

    return {
        "total_count": len(graded_videos),
        "grade_distribution": grade_dist,
        "s_grade_tags": s_grade_tags,
        "analyzed_at": analyzed_at,
        "portfolios": graded_videos,
    }


print("✅ T09 完成")

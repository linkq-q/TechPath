# 文件用途：背景匹配模块核心逻辑 —— AI 摘要生成 + 多关键词搜索 + 语义评分

import json
import os
import re
import time

from openai import OpenAI


def _get_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url="https://api.deepseek.com/v1",
    )


def _call_deepseek(messages: list, purpose: str = "bg_match") -> str:
    """调用 DeepSeek API，返回文本；失败时抛出异常"""
    client = _get_client()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.3,
    )
    # 费用追踪
    try:
        from core.cost_tracker import log_api_call
        usage = resp.usage
        log_api_call(model, usage.prompt_tokens, usage.completion_tokens, purpose)
    except Exception:
        pass
    return resp.choices[0].message.content or ""


def _extract_json(text: str) -> dict:
    """从文本中提取第一个 JSON 对象"""
    text = text.strip()
    # 去掉 markdown 代码块
    text = re.sub(r"```(?:json)?\s*", "", text)
    text = re.sub(r"```\s*$", "", text)
    try:
        return json.loads(text)
    except Exception:
        # 尝试找到第一个 { ... }
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group())
            except Exception:
                pass
    return {}


def _build_profile_text(profile: dict) -> str:
    """将画像 dict 转为可读文本，供 prompt 使用"""
    lines = []
    if profile.get("edu_major"):
        lines.append(f"本科专业：{profile['edu_major']}")
    if profile.get("edu_level"):
        lines.append(f"学校类型：{profile['edu_level']}")
    if profile.get("gpa_level"):
        lines.append(f"GPA 水平：{profile['gpa_level']}")
    if profile.get("cross_tags"):
        lines.append(f"跨学科背景：{', '.join(profile['cross_tags'])}")

    experiences = profile.get("experiences", [])
    if experiences:
        lines.append("\n【实习/科研经历】")
        for exp in experiences:
            directions = ", ".join(exp.get("directions", []))
            desc = exp.get("desc", "")
            lines.append(
                f"- {exp.get('company', '')}，{exp.get('exp_type', '')}，"
                f"{exp.get('duration', '')}，方向：{directions}"
                + (f"，{desc}" if desc else "")
            )

    ai_stacks = profile.get("ai_stacks", [])
    if ai_stacks:
        lines.append("\n【AI 技术栈】")
        for s in ai_stacks:
            items = ", ".join(s.get("items", []))
            note = s.get("extra_note", "")
            lines.append(f"- {s.get('stack_group', '')}：{items}" + (f"（{note}）" if note else ""))

    other_stacks = profile.get("other_stacks", [])
    if other_stacks:
        lines.append("\n【其他技术栈】")
        for s in other_stacks:
            items = ", ".join(s.get("items", []))
            if items:
                lines.append(f"- {s.get('stack_group', '')}：{items}")

    if profile.get("free_text"):
        lines.append(f"\n【补充说明】\n{profile['free_text']}")

    return "\n".join(lines)


def generate_bg_summary(profile: dict) -> dict:
    """
    根据用户画像生成结构化背景摘要。

    Args:
        profile: 包含 edu_major / edu_level / gpa_level / cross_tags /
                 experiences / ai_stacks / other_stacks / free_text 的字典

    Returns:
        包含 core_strengths / target_roles / search_keywords /
        profile_level / differentiators 的字典；失败时返回含 error 字段的字典
    """
    profile_text = _build_profile_text(profile)

    messages = [
        {
            "role": "system",
            "content": (
                "你是游戏/互联网行业资深 HR 顾问，专注于 AI 相关岗位的求职匹配。"
                "请根据候选人背景，生成结构化的能力摘要，用于驱动岗位搜索和匹配评分。"
                "输出必须是合法 JSON，不得包含多余文字。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"候选人背景信息如下：\n\n{profile_text}\n\n"
                "请输出 JSON，格式：\n"
                "{\n"
                '  "core_strengths": ["核心能力1", "核心能力2", ...],\n'
                '  "target_roles": ["目标岗位1", "目标岗位2", ...],\n'
                '  "search_keywords": ["搜索词1", "搜索词2", ...],\n'
                '  "profile_level": "学历/阶段描述，如应届本科/在读硕士",\n'
                '  "differentiators": "与其他候选人相比的差异化亮点（1-2句话）"\n'
                "}\n"
                "search_keywords 生成 4-6 个，优先选择 Boss 直聘上常见的职位搜索词，"
                "如「技术美术」「AI工具链」「Agent工程师」等。"
            ),
        },
    ]

    try:
        raw = _call_deepseek(messages, purpose="bg_match")
        result = _extract_json(raw)
        if not result.get("search_keywords"):
            raise ValueError("AI 未返回 search_keywords")
        # 确保关键词数量在 3-6 之间
        kws = result["search_keywords"][:6]
        if len(kws) < 3:
            kws.append("AI工程师")
        result["search_keywords"] = kws
        return result
    except Exception as e:
        return {"error": str(e), "search_keywords": ["AI工程师", "技术美术", "AI TA"]}


def _parse_salary(salary_str: str) -> tuple[int, int]:
    """解析薪资字符串，返回 (min_k, max_k) 单位为千元/月；解析失败返回 (0, 0)"""
    if not salary_str:
        return 0, 0
    # 匹配 "15-25K" 或 "15K-25K" 或 "15-25k·13薪" 等格式
    m = re.search(r"(\d+)[Kk]?\s*[-–—]\s*(\d+)\s*[Kk]", salary_str)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"(\d+)\s*[Kk]", salary_str)
    if m:
        v = int(m.group(1))
        return v, v
    return 0, 0


def _score_jd(bg_summary: dict, jd: dict) -> dict:
    """
    对单条 JD 进行语义匹配评分。

    Returns:
        包含 match_score / skill_match / competitiveness /
        work_intensity / gap_analysis / match_highlight 的字典
    """
    summary_text = json.dumps(bg_summary, ensure_ascii=False)
    jd_text = jd.get("requirements_raw", "") or f"{jd.get('title','')} @ {jd.get('company','')}"

    messages = [
        {
            "role": "system",
            "content": (
                "你是游戏行业求职顾问，请评估候选人背景与岗位的匹配度。"
                "只输出 JSON，不含其他文字。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"【候选人背景摘要】\n{summary_text}\n\n"
                f"【岗位 JD】\n公司：{jd.get('company','')}\n"
                f"职位：{jd.get('title','')}\n"
                f"薪资：{jd.get('salary','')}\n"
                f"描述：{jd_text[:2000]}\n\n"
                "请输出 JSON：\n"
                "{\n"
                '  "match_score": 0-100,\n'
                '  "skill_match": "技能匹配简述（1-2句）",\n'
                '  "competitiveness": "强|中|弱",\n'
                '  "work_intensity": "高|中|低",\n'
                '  "gap_analysis": "主要差距（1句）",\n'
                '  "match_highlight": "最大亮点（1句）"\n'
                "}"
            ),
        },
    ]

    try:
        raw = _call_deepseek(messages, purpose="bg_match")
        result = _extract_json(raw)
        return {
            "match_score": int(result.get("match_score", 50)),
            "skill_match": result.get("skill_match", ""),
            "competitiveness": result.get("competitiveness", "中"),
            "work_intensity": result.get("work_intensity", "中"),
            "gap_analysis": result.get("gap_analysis", ""),
            "match_highlight": result.get("match_highlight", ""),
        }
    except Exception as e:
        return {
            "match_score": 50,
            "skill_match": "",
            "competitiveness": "中",
            "work_intensity": "中",
            "gap_analysis": f"评分失败：{e}",
            "match_highlight": "",
        }


def run_match_session(
    bg_summary: dict,
    profile_snapshot: dict,
    on_progress=None,
) -> tuple[int, list[dict]]:
    """
    执行完整匹配流程：多关键词搜索 → 去重 → 语义评分 → 存库。

    Args:
        bg_summary:       generate_bg_summary() 返回的字典
        profile_snapshot: 用于存入 match_sessions 的画像快照
        on_progress:      可选回调 fn(stage: str, current: int, total: int)

    Returns:
        (session_id, scored_jd_list)
    """
    from core.crawlers.bosszp import crawl_bosszp
    from core.database import (
        save_match_session,
        save_match_record,
        update_match_session_count,
    )

    keywords = bg_summary.get("search_keywords", ["AI工程师"])[:6]

    # 创建 session（先占位，后更新数量）
    session_id = save_match_session(
        profile_snapshot=profile_snapshot,
        keywords_used=keywords,
        total_jd_count=0,
    )

    # Step 1: 多关键词搜索 + 去重
    seen: dict[tuple, dict] = {}  # (company, title) -> jd dict
    for idx, kw in enumerate(keywords):
        if on_progress:
            on_progress("crawl", idx, len(keywords))
        try:
            results = crawl_bosszp(keyword=kw, max_count=15)
            for jd in results:
                key = (jd.get("company", ""), jd.get("title", ""))
                if key not in seen:
                    seen[key] = jd
                if len(seen) >= 60:
                    break
        except Exception as e:
            print(f"[bg_match] 关键词「{kw}」爬取失败：{e}")
        if len(seen) >= 60:
            break
        time.sleep(1)

    jd_pool = list(seen.values())

    # Step 2: 语义评分
    scored = []
    for idx, jd in enumerate(jd_pool):
        if on_progress:
            on_progress("score", idx, len(jd_pool))
        scores = _score_jd(bg_summary, jd)
        salary_min, salary_max = _parse_salary(jd.get("salary", ""))
        record = {
            **jd,
            "salary_min": salary_min,
            "salary_max": salary_max,
            **scores,
        }
        scored.append(record)
        # 存入数据库
        try:
            save_match_record(
                session_id=session_id,
                company=jd.get("company", ""),
                title=jd.get("title", ""),
                salary_min=salary_min,
                salary_max=salary_max,
                location=jd.get("location", ""),
                jd_raw=jd.get("requirements_raw", ""),
                match_score=scores["match_score"],
                competitiveness=scores["competitiveness"],
                work_intensity=scores["work_intensity"],
                gap_analysis=scores["gap_analysis"],
                match_highlight=scores["match_highlight"],
                skill_match=scores["skill_match"],
            )
        except Exception as e:
            print(f"[bg_match] 存储 match_record 失败：{e}")
        time.sleep(0.5)

    # 更新数量
    update_match_session_count(session_id, len(scored))

    scored.sort(key=lambda x: x["match_score"], reverse=True)
    return session_id, scored


def generate_competitiveness_analysis(bg_summary: dict, records: list[dict]) -> str:
    """
    根据本次匹配结果，生成竞争力综合评价（100-150字）。

    Returns:
        格式化文本（含【优势】【差距】【综合判断】）；失败时返回简短提示。
    """
    if not records:
        return "暂无数据，无法生成竞争力评价。"

    summary_text = json.dumps(bg_summary, ensure_ascii=False)
    gap_texts = [r.get("gap_analysis", "") for r in records if r.get("gap_analysis")]
    highlight_texts = [r.get("match_highlight", "") for r in records if r.get("match_highlight")]
    comp_dist = {
        "强": sum(1 for r in records if r.get("competitiveness") == "强"),
        "中": sum(1 for r in records if r.get("competitiveness") == "中"),
        "弱": sum(1 for r in records if r.get("competitiveness") == "弱"),
    }

    messages = [
        {
            "role": "system",
            "content": "你是游戏行业资深招聘顾问，请给出简洁精准的竞争力评价。",
        },
        {
            "role": "user",
            "content": (
                f"候选人背景摘要：\n{summary_text}\n\n"
                f"本次搜索到 {len(records)} 条岗位。"
                f"竞争力分布：强 {comp_dist['强']} 条 / 中 {comp_dist['中']} 条 / 弱 {comp_dist['弱']} 条。\n"
                f"高频差距提示：{'; '.join(gap_texts[:5])}\n"
                f"高频亮点：{'; '.join(highlight_texts[:5])}\n\n"
                "请生成100-150字竞争力评价，格式：\n"
                "【优势】...\n【差距】...\n【综合判断】..."
            ),
        },
    ]

    try:
        return _call_deepseek(messages, purpose="bg_match")
    except Exception as e:
        return f"竞争力分析生成失败：{e}"


print("✅ T02 完成")

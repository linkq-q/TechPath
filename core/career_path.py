# 文件用途：职业路径分析模块
# T08: crawl_career_levels —— 分年限段爬取职位数据
# T09: analyze_career_path —— 薪资/技能演进分析 + DeepSeek 总结
# T10: compare_career_paths —— 多路径对比

import json
import os
import re
import time
from collections import Counter
from statistics import median, mean
from typing import Optional

from openai import OpenAI


def _get_client() -> OpenAI:
    return OpenAI(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        base_url="https://api.deepseek.com/v1",
    )


def _call_deepseek(messages: list, purpose: str = "职业路径分析") -> str:
    client = _get_client()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.4,
    )
    try:
        from core.cost_tracker import log_api_call
        if resp.usage:
            log_api_call(model, resp.usage.prompt_tokens,
                         resp.usage.completion_tokens, purpose)
    except Exception:
        pass
    return resp.choices[0].message.content or ""


# ============================================================
# T08：分年限段爬取
# ============================================================

# Boss 直聘经验筛选参数（url param experience=xxx）
_EXP_FILTERS = {
    "校招": "101",   # 应届
    "1-3年": "102",
    "3-5年": "103",
    "5年以上": "104",
}


def crawl_career_levels(job_title: str, base_city: str = "", session_id: str = "") -> dict:
    """
    分四个年限段搜索同一职位，采集薪资/技能/公司信息。

    Args:
        job_title:  职位名称，如「技术美术」「AI工程师」
        base_city:  城市（可选）
        session_id: 关联的背景匹配 session id（可选）

    Returns:
        {"校招": [...], "1-3年": [...], "3-5年": [...], "5年以上": [...]}
        每条记录包含: title, company, salary, experience_level, skills_extracted,
                      company_stage, base_city, requirements_raw
    """
    from core.crawlers.bosszp import crawl_bosszp
    from core.database import save_career_path_job
    from core.bg_match import _parse_salary

    result = {}

    for level, exp_filter in _EXP_FILTERS.items():
        print(f"[career_path] 爬取{level}岗位：{job_title}…")
        try:
            raw_jobs = crawl_bosszp(
                keyword=job_title,
                max_count=18,
                experience_filter=exp_filter,
            )
        except Exception as e:
            print(f"[career_path] {level} 爬取失败：{e}")
            raw_jobs = []

        level_jobs = []
        for jd in raw_jobs:
            # 从 JD 文本提取技能关键词
            skills = _extract_skills_from_jd(jd.get("requirements_raw", ""))
            sal_min, sal_max = _parse_salary(jd.get("salary", ""))
            entry = {
                "title": jd.get("title", ""),
                "company": jd.get("company", ""),
                "salary": jd.get("salary", ""),
                "salary_min": sal_min,
                "salary_max": sal_max,
                "experience_level": level,
                "skills_required": skills,
                "company_stage": jd.get("company_stage", ""),
                "base_city": jd.get("base_city", ""),
                "requirements_raw": jd.get("requirements_raw", ""),
            }
            level_jobs.append(entry)

            # 存入数据库
            try:
                save_career_path_job(
                    session_id=session_id or job_title,
                    job_title=jd.get("title", job_title),
                    company=jd.get("company", ""),
                    experience_level=level,
                    salary_min=sal_min,
                    salary_max=sal_max,
                    skills_required=skills,
                    company_stage=jd.get("company_stage", ""),
                    base_city=jd.get("base_city", ""),
                    raw_requirements=jd.get("requirements_raw", ""),
                )
            except Exception:
                pass

        result[level] = level_jobs
        print(f"[career_path] {level} 爬取完成：{len(level_jobs)} 条")
        time.sleep(2)

    return result


def _extract_skills_from_jd(jd_text: str) -> list:
    """从 JD 文本中提取常见技能关键词（简单规则）"""
    if not jd_text:
        return []

    keywords = [
        "Python", "C++", "C#", "Unity", "Unreal", "UE5", "Houdini",
        "Shader", "HLSL", "GLSL", "ShaderLab", "Shader Graph",
        "ComfyUI", "Stable Diffusion", "LoRA", "ControlNet",
        "LangChain", "LlamaIndex", "RAG", "Agent", "Fine-tuning",
        "Blender", "Maya", "3ds Max", "Substance", "ZBrush",
        "AIGC", "Diffusion", "NeRF", "3DGS", "OpenGL", "Vulkan",
        "DirectX", "VFX", "Niagara", "Live2D", "Spine",
        "机器学习", "深度学习", "计算机视觉", "自然语言处理",
        "渲染", "图形学", "动画", "材质", "特效",
    ]

    found = []
    text_lower = jd_text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            found.append(kw)
    return found


# ============================================================
# T09：职业路径分析
# ============================================================

def _compute_salary_stats(jobs: list) -> dict:
    """计算一组职位的薪资统计"""
    salaries = []
    for j in jobs:
        lo = j.get("salary_min", 0)
        hi = j.get("salary_max", 0)
        if lo > 0 and hi > 0:
            salaries.append((lo + hi) / 2)
        elif lo > 0:
            salaries.append(lo)
        elif hi > 0:
            salaries.append(hi)

    if not salaries:
        return {"min": 0, "max": 0, "median": 0, "mean": 0, "count": 0}

    return {
        "min": int(min(salaries)),
        "max": int(max(salaries)),
        "median": int(median(salaries)),
        "mean": int(mean(salaries)),
        "count": len(salaries),
    }


def _get_high_freq_skills(jobs: list, threshold: float = 0.3) -> list:
    """提取出现超过30%岗位的高频技能"""
    if not jobs:
        return []
    all_skills = []
    for j in jobs:
        all_skills.extend(j.get("skills_required", []))
    counter = Counter(all_skills)
    min_count = max(1, int(len(jobs) * threshold))
    return [skill for skill, cnt in counter.most_common() if cnt >= min_count]


def analyze_career_path(session_id: str, target_role: str) -> dict:
    """
    从 career_path_jobs 读取数据，计算统计，调用 DeepSeek 生成综合分析。

    Args:
        session_id:  crawl_career_levels 时使用的 session_id
        target_role: 职位名称（用于展示）

    Returns:
        完整分析结果字典
    """
    from core.database import get_career_path_jobs, save_career_analysis

    # 读取四个年限段数据
    level_data = {}
    for level in ["校招", "1-3年", "3-5年", "5年以上"]:
        jobs = get_career_path_jobs(session_id=session_id, experience_level=level)
        level_data[level] = jobs

    # 计算各年段薪资统计
    salary_trend = {}
    for level, jobs in level_data.items():
        salary_trend[level] = _compute_salary_stats(jobs)

    # 提取各年段高频技能
    skills_by_level = {}
    for level, jobs in level_data.items():
        skills_by_level[level] = _get_high_freq_skills(jobs)

    # 技能演进：识别各阶段新增的技能
    all_entry_skills = set(skills_by_level.get("校招", []))
    skills_evolution = {
        "校招": skills_by_level.get("校招", []),
        "1-3年_新增": [s for s in skills_by_level.get("1-3年", []) if s not in all_entry_skills],
        "3-5年_新增": [s for s in skills_by_level.get("3-5年", []) if s not in all_entry_skills
                       and s not in skills_by_level.get("1-3年", [])],
        "5年以上_新增": [s for s in skills_by_level.get("5年以上", []) if s not in all_entry_skills
                         and s not in skills_by_level.get("1-3年", [])
                         and s not in skills_by_level.get("3-5年", [])],
        "贯穿全程": [s for s in all_entry_skills if all(
            s in skills_by_level.get(lv, []) for lv in ["1-3年", "3-5年", "5年以上"]
        )],
    }

    # 构建 DeepSeek 分析 prompt
    salary_text = "\n".join([
        f"  {lv}：中位数{stats['median']}K，范围{stats['min']}-{stats['max']}K（{stats['count']}条数据）"
        for lv, stats in salary_trend.items()
        if stats["count"] > 0
    ]) or "（数据不足）"

    skills_text = "\n".join([
        f"  {lv}：{', '.join(skills[:10]) or '（暂无）'}"
        for lv, skills in skills_by_level.items()
    ])

    messages = [
        {
            "role": "system",
            "content": (
                "你是游戏/互联网行业职业发展顾问，专注于技术岗位的职业路径分析。"
                "请给出准确、实用的分析，语言简洁。"
            ),
        },
        {
            "role": "user",
            "content": (
                f"请分析「{target_role}」这个职位的职业发展路径。\n\n"
                f"【各年限段薪资数据】\n{salary_text}\n\n"
                f"【各年限段高频技能要求】\n{skills_text}\n\n"
                "请生成完整的职业路径分析，包含以下内容：\n\n"
                "1. **职业路径总结**（200字以内）：这个职位的典型成长路径\n"
                "2. **薪资增长预测**：从校招到5年以上的薪资增长规律和预期\n"
                "3. **AI 替代风险评估**（0-100分，附说明）：\n"
                "   - 使用 TASKS 框架：任务标准化程度/创意判断需求/人际协作需求\n"
                "   - 给出综合 AI 替代风险分数（0=完全不可替代，100=极易被替代）\n"
                "4. **上升瓶颈分析**：这个职业路径的天花板在哪里，突破方向\n"
                "5. **学习建议**：针对各阶段的关键技能投入建议\n\n"
                "请严格按以下 JSON 格式输出，不要有其他文字：\n"
                "{\n"
                '  "summary": "职业路径总结文字",\n'
                '  "salary_prediction": "薪资增长预测文字",\n'
                '  "ai_risk_score": 整数0-100,\n'
                '  "ai_risk_detail": "AI替代风险详细分析",\n'
                '  "growth_ceiling": "上升瓶颈分析",\n'
                '  "learning_advice": "各阶段学习建议"\n'
                "}"
            ),
        },
    ]

    try:
        raw = _call_deepseek(messages, purpose="职业路径分析")
        # 提取 JSON
        raw = raw.strip()
        raw = re.sub(r"```(?:json)?\s*", "", raw)
        raw = re.sub(r"```\s*$", "", raw)
        ai_result = json.loads(raw)
    except Exception as e:
        ai_result = {
            "summary": f"AI 分析失败：{e}",
            "salary_prediction": "",
            "ai_risk_score": 50,
            "ai_risk_detail": "",
            "growth_ceiling": "",
            "learning_advice": "",
        }

    # 保存到数据库
    try:
        save_career_analysis(
            session_id=session_id,
            target_role=target_role,
            salary_trend_json=json.dumps(salary_trend, ensure_ascii=False),
            skills_evolution_json=json.dumps(skills_evolution, ensure_ascii=False),
            ai_replacement_risk=ai_result.get("ai_risk_score", 50),
            ai_analysis_detail=ai_result.get("ai_risk_detail", ""),
            growth_ceiling=ai_result.get("growth_ceiling", ""),
            summary_text=ai_result.get("summary", ""),
        )
    except Exception as e:
        print(f"[career_path] 保存分析结果失败：{e}")

    return {
        "target_role": target_role,
        "salary_trend": salary_trend,
        "skills_by_level": skills_by_level,
        "skills_evolution": skills_evolution,
        "ai_risk_score": ai_result.get("ai_risk_score", 50),
        "ai_risk_detail": ai_result.get("ai_risk_detail", ""),
        "growth_ceiling": ai_result.get("growth_ceiling", ""),
        "summary": ai_result.get("summary", ""),
        "salary_prediction": ai_result.get("salary_prediction", ""),
        "learning_advice": ai_result.get("learning_advice", ""),
    }


# ============================================================
# T10：多路径对比
# ============================================================

def compare_career_paths(role_list: list) -> dict:
    """
    对比多个职业路径。

    Args:
        role_list: 职位名称列表，如 ["技术美术", "AI工程师"]

    Returns:
        对比结果字典
    """
    from core.database import get_career_analysis_by_role

    analyses = {}
    for role in role_list:
        analysis = get_career_analysis_by_role(role)
        if analysis:
            analyses[role] = analysis
        else:
            print(f"[career_path] 未找到「{role}」的分析数据，跳过")

    if len(analyses) < 2:
        return {"error": "需要至少2个已分析的职位才能对比", "analyses": analyses}

    # 构建薪资对比数据
    salary_comparison = {}
    for role, ana in analyses.items():
        try:
            trend = json.loads(ana.get("salary_trend_json", "{}"))
            salary_comparison[role] = {
                lv: stats.get("median", 0)
                for lv, stats in trend.items()
                if stats.get("median", 0) > 0
            }
        except Exception:
            salary_comparison[role] = {}

    # 技能重叠度
    skill_overlap = {}
    skills_sets = {}
    for role, ana in analyses.items():
        try:
            evo = json.loads(ana.get("skills_evolution_json", "{}"))
            all_skills = set()
            for v in evo.values():
                if isinstance(v, list):
                    all_skills.update(v)
            skills_sets[role] = all_skills
        except Exception:
            skills_sets[role] = set()

    if len(skills_sets) >= 2:
        roles = list(skills_sets.keys())
        for i in range(len(roles)):
            for j in range(i + 1, len(roles)):
                key = f"{roles[i]} ∩ {roles[j]}"
                overlap = skills_sets[roles[i]] & skills_sets[roles[j]]
                skill_overlap[key] = sorted(overlap)

    # AI 替代风险对比
    ai_risks = {role: ana.get("ai_replacement_risk", 0) for role, ana in analyses.items()}

    # 上升天花板对比
    growth_ceilings = {role: ana.get("growth_ceiling", "") for role, ana in analyses.items()}

    # 调用 DeepSeek 生成对比总结
    compare_text = ""
    for role, ana in analyses.items():
        compare_text += f"\n【{role}】\n"
        compare_text += f"薪资趋势（中位数）：{salary_comparison.get(role, {})}\n"
        compare_text += f"AI替代风险：{ai_risks.get(role, 0)}分\n"
        compare_text += f"上升瓶颈：{growth_ceilings.get(role, '')[:100]}\n"
        compare_text += f"路径概述：{ana.get('summary_text', '')[:150]}\n"

    messages = [
        {
            "role": "system",
            "content": "你是职业规划顾问，帮助 AI TA 求职者做职业路径选择决策。",
        },
        {
            "role": "user",
            "content": (
                f"请对比以下 {len(analyses)} 条职业路径：\n{compare_text}\n\n"
                "请生成对比报告，重点说明：\n"
                "1. 各路径的核心差异（薪资增长/技能要求/AI风险）\n"
                "2. 适合人群分析（哪类背景的人更适合哪条路径）\n"
                "3. 选择建议（如果只能选一条，考虑什么因素）\n\n"
                "输出格式为自然语言，300-500字，直接给出观点。"
            ),
        },
    ]

    try:
        comparison_summary = _call_deepseek(messages, purpose="路径对比分析")
    except Exception as e:
        comparison_summary = f"对比分析生成失败：{e}"

    return {
        "roles": list(analyses.keys()),
        "salary_comparison": salary_comparison,
        "skill_overlap": skill_overlap,
        "ai_risks": ai_risks,
        "growth_ceilings": growth_ceilings,
        "comparison_summary": comparison_summary,
        "analyses": {role: {
            "summary": ana.get("summary_text", ""),
            "ai_risk": ana.get("ai_replacement_risk", 0),
        } for role, ana in analyses.items()},
    }


print("✅ T08 完成")
print("✅ T09 完成")
print("✅ T10 完成")

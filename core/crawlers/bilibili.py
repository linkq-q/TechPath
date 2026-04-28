# 文件用途：B站作品集竞品监测爬虫（Phase 3），包含采集、分析打标、相对评级三个功能

import base64
import json
import os
import random
import re
import time
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")

# 默认搜索关键词列表
DEFAULT_KEYWORDS = [
    "技术美术 作品集",
    "TA 实习 作品集",
    "技术美术 实习 2026",
    "技术美术 秋招 2026",
    "AI TA 作品集",
]

# 届别识别规则
COHORT_PATTERNS = [
    (r"2027届|2027年应届|27届", "2027届"),
    (r"2026届|2026年应届|26届", "2026届"),
    (r"2025届|2025年应届|25届", "2025届"),
    (r"2024届|2024年应届|24届", "2024届"),
]

# 求职阶段识别规则
STAGE_PATTERNS = [
    (r"秋招|秋季招聘|校招", "秋招"),
    (r"实习|intern|暑期实习|寒假实习", "实习"),
]

_deepseek_client = None
_qwen_client = None


def _get_deepseek_client() -> OpenAI:
    """懒加载 DeepSeek 客户端"""
    global _deepseek_client
    if _deepseek_client is None:
        _deepseek_client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )
    return _deepseek_client


def _get_qwen_client() -> OpenAI:
    """懒加载 Qwen VL 客户端"""
    global _qwen_client
    if _qwen_client is None:
        _qwen_client = OpenAI(
            api_key=QWEN_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
    return _qwen_client


def _extract_cohort(text: str) -> str:
    """从文本中识别届别"""
    for pattern, cohort in COHORT_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return cohort
    return "未知届别"


def _extract_stage(text: str) -> str:
    """从文本中识别求职阶段"""
    for pattern, stage in STAGE_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return stage
    return "未知阶段"


# ============================================================
# T06：B站作品集数据采集
# ============================================================

def _search_bilibili_videos(keyword: str, max_count: int = 10) -> list:
    """
    使用 B站搜索接口获取视频列表。
    降级方案：使用 requests + BeautifulSoup 解析搜索结果。
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.bilibili.com",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "zh-CN,zh;q=0.9",
    }

    results = []

    # 方法1：使用 B站搜索 API（无需登录）
    try:
        api_url = "https://api.bilibili.com/x/web-interface/search/type"
        params = {
            "search_type": "video",
            "keyword": keyword,
            "page": 1,
            "page_size": min(max_count, 20),
            "order": "pubdate",  # 按发布时间排序，获取最新内容
        }
        resp = requests.get(api_url, params=params, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("code") == 0:
            video_list = data.get("data", {}).get("result", [])
            for video in video_list:
                bvid = video.get("bvid", "")
                video_url = f"https://www.bilibili.com/video/{bvid}" if bvid else ""
                if not video_url:
                    continue

                title = video.get("title", "").replace("<em class=\"keyword\">", "").replace("</em>", "")
                uploader = video.get("author", "")
                pub_ts = video.get("pubdate", 0)
                publish_date = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d") if pub_ts else ""
                description = video.get("description", "")

                combined_text = f"{title} {description}"
                cohort = _extract_cohort(combined_text)
                stage = _extract_stage(combined_text)

                results.append({
                    "video_url": video_url,
                    "title": title,
                    "uploader": uploader,
                    "publish_date": publish_date,
                    "description": description,
                    "cohort": cohort,
                    "stage": stage,
                    "play_count": video.get("play", 0),
                    "like_count": video.get("like", 0),
                    "danmaku_count": video.get("video_review", 0),
                    "bvid": bvid,
                })

    except Exception as e:
        print(f"[bilibili] API 搜索失败（{keyword}）：{e}")

    # 方法2：如果 API 失败，用网页解析降级
    if not results:
        try:
            search_url = f"https://search.bilibili.com/video?keyword={requests.utils.quote(keyword)}"
            resp = requests.get(search_url, headers=headers, timeout=15)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")

            cards = soup.select(".video-item") or soup.select(".bili-video-card")
            for card in cards[:max_count]:
                a_tag = card.select_one("a[href*='/video/']")
                if not a_tag:
                    continue
                href = a_tag.get("href", "")
                video_url = f"https:{href}" if href.startswith("//") else href

                title_el = card.select_one(".title") or card.select_one(".bili-video-card__info--tit")
                title = title_el.get_text(strip=True) if title_el else "未知标题"

                uploader_el = card.select_one(".up-name") or card.select_one(".bili-video-card__info--author")
                uploader = uploader_el.get_text(strip=True) if uploader_el else "未知UP主"

                combined_text = f"{title}"
                cohort = _extract_cohort(combined_text)
                stage = _extract_stage(combined_text)

                results.append({
                    "video_url": video_url,
                    "title": title,
                    "uploader": uploader,
                    "publish_date": "",
                    "description": "",
                    "cohort": cohort,
                    "stage": stage,
                    "play_count": 0,
                    "like_count": 0,
                    "danmaku_count": 0,
                })
        except Exception as e:
            print(f"[bilibili] 网页解析降级失败（{keyword}）：{e}")

    return results


def crawl_bilibili_portfolios(
    keywords: list = None,
    max_count: int = 30,
) -> list:
    """
    采集 B站技术美术作品集视频列表。

    Args:
        keywords: 搜索关键词列表，默认使用 DEFAULT_KEYWORDS
        max_count: 最大采集总数

    Returns:
        视频信息列表，每条包含 video_url/title/uploader/publish_date/cohort/stage 等字段
    """
    if keywords is None:
        keywords = DEFAULT_KEYWORDS

    all_results = []
    seen_urls = set()
    per_keyword = max(max_count // len(keywords), 5)

    for keyword in keywords:
        print(f"[bilibili] 搜索关键词：{keyword}")
        try:
            videos = _search_bilibili_videos(keyword, max_count=per_keyword)
            for v in videos:
                url = v.get("video_url", "")
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_results.append(v)
        except Exception as e:
            print(f"[bilibili] 搜索失败（{keyword}）：{e}")

        # 随机等待 1-3 秒，避免被封
        wait_time = random.uniform(1, 3)
        time.sleep(wait_time)

    print(f"[bilibili] 共采集 {len(all_results)} 条去重视频（原始总数含重复）")
    return all_results[:max_count]


# ============================================================
# T07：视频内容分析与打标
# ============================================================

def _extract_frames_base64(video_url: str, max_frames: int = 15) -> list:
    """从视频 URL 抽取关键帧（每30秒一帧），返回 base64 列表"""
    import subprocess
    import tempfile
    from pathlib import Path
    import yt_dlp

    frames_b64 = []
    temp_dir = Path(tempfile.mkdtemp())
    video_path = temp_dir / "video.mp4"

    try:
        ydl_opts = {
            "format": "worstvideo[ext=mp4]/worst[ext=mp4]/worst",
            "outtmpl": str(video_path),
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([video_url])

        if not video_path.exists():
            candidates = list(temp_dir.glob("video*"))
            if candidates:
                video_path = candidates[0]
            else:
                return []

        frame_pattern = str(temp_dir / "frame_%04d.jpg")
        cmd = [
            "ffmpeg", "-i", str(video_path),
            "-vf", "fps=1/30",
            "-frames:v", str(max_frames),
            "-q:v", "5",
            frame_pattern,
            "-y", "-loglevel", "error",
        ]
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)

        frame_files = sorted(temp_dir.glob("frame_*.jpg"))
        for f in frame_files[:max_frames]:
            with open(f, "rb") as img:
                frames_b64.append(base64.b64encode(img.read()).decode())

    except Exception as e:
        print(f"[bilibili] 帧提取失败：{e}")
    finally:
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)

    return frames_b64


def _analyze_with_qwen(frames_b64: list) -> dict:
    """使用 Qwen2.5-VL 分析视频截帧"""
    qwen_client = _get_qwen_client()
    content = [
        {
            "type": "text",
            "text": (
                "分析这个技术美术求职作品集视频的截帧，识别：\n"
                "1. 使用了哪些软件工具（Unity/UE/Houdini/Substance Designer/ComfyUI/SD等）\n"
                "2. 实现了哪些技术效果（卡通渲染/粒子特效/程序化生成/LoRA微调/ControlNet等）\n"
                "3. 项目完整度（只有效果展示/有完整流程说明/有工程文件展示）\n"
                "4. 整体复杂度（基础/中级/高级）\n"
                "请输出严格的JSON格式，不加其他内容：\n"
                '{"tools": [], "techniques": [], "completeness": "只有效果展示/有完整流程说明/有工程文件展示", '
                '"complexity": "基础/中级/高级"}'
            ),
        }
    ]
    for b64 in frames_b64[:10]:  # 最多用 10 帧避免 token 超限
        content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
        })

    resp = qwen_client.chat.completions.create(
        model="qwen-vl-plus",
        messages=[{"role": "user", "content": content}],
        temperature=0.2,
    )
    raw = resp.choices[0].message.content.strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        return json.loads(match.group())
    return {}


def _analyze_with_text(title: str, description: str) -> dict:
    """仅用标题和简介进行文字分析（无视觉模型时的降级方案）"""
    client = _get_deepseek_client()
    prompt = f"""请分析以下技术美术求职作品集视频的标题和简介，提取技术信息。

标题：{title}
简介：{description}

请识别：
1. 使用的软件工具（Unity/UE/Houdini/Substance Designer/ComfyUI/SD等）
2. 实现的技术效果（卡通渲染/粒子特效/程序化生成/LoRA微调等）
3. 项目完整度（只有效果展示/有完整流程说明/有工程文件展示）
4. 整体复杂度（基础/中级/高级）

严格输出JSON（不加其他内容）：
{{"tools": [], "techniques": [], "completeness": "只有效果展示", "complexity": "基础"}}"""

    resp = client.chat.completions.create(
        model=DEEPSEEK_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )
    raw = resp.choices[0].message.content.strip()
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except Exception:
            pass
    return {"tools": [], "techniques": [], "completeness": "只有效果展示", "complexity": "基础"}


def _extract_tech_tags(tools: list, techniques: list) -> list:
    """合并工具和技术列表，提取最多8个标签"""
    combined = list(dict.fromkeys(tools + techniques))  # 去重保序
    return combined[:8]


def analyze_portfolio_video(video_info: dict) -> dict:
    """
    分析单个 B站作品集视频，打标技术标签和复杂度。

    Args:
        video_info: crawl_bilibili_portfolios 返回的单条视频信息字典

    Returns:
        包含 tech_tags/complexity/has_pipeline/visual_quality 的字典
    """
    title = video_info.get("title", "")
    description = video_info.get("description", "")
    video_url = video_info.get("video_url", "")

    visual_result = {}

    # 尝试使用 Qwen VL 视觉分析（需要 QWEN_API_KEY）
    if QWEN_API_KEY and video_url:
        try:
            print(f"[bilibili] 视觉分析：{title[:30]}...")
            frames = _extract_frames_base64(video_url, max_frames=15)
            if frames:
                visual_result = _analyze_with_qwen(frames)
        except Exception as e:
            print(f"[bilibili] 视觉分析失败，降级到文字分析：{e}")

    # 如果视觉分析失败或无 key，用文字分析降级
    if not visual_result:
        try:
            visual_result = _analyze_with_text(title, description)
        except Exception as e:
            print(f"[bilibili] 文字分析失败：{e}")
            visual_result = {"tools": [], "techniques": [], "completeness": "只有效果展示", "complexity": "基础"}

    tools = visual_result.get("tools", [])
    techniques = visual_result.get("techniques", [])
    completeness = visual_result.get("completeness", "只有效果展示")
    complexity = visual_result.get("complexity", "基础")

    # 用 DeepSeek 提炼最终技术标签列表
    tech_tags = []
    try:
        client = _get_deepseek_client()
        all_signals = tools + techniques + [title[:50]]
        prompt = (
            f"从以下技术信号中提炼最多8个技术标签（简洁中文或英文名称，如：Unity Shader/LoRA微调/Houdini程序化/卡通渲染）：\n"
            f"{', '.join(all_signals)}\n\n"
            f"严格返回JSON数组，不加其他内容：[\"标签1\", \"标签2\"]"
        )
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        raw = resp.choices[0].message.content.strip()
        match = re.search(r"\[.*\]", raw, re.DOTALL)
        if match:
            tech_tags = json.loads(match.group())[:8]
    except Exception:
        tech_tags = _extract_tech_tags(tools, techniques)

    if not tech_tags:
        tech_tags = _extract_tech_tags(tools, techniques)

    # 判断是否有完整制作流程（has_pipeline）
    has_pipeline = "流程" in completeness or "工程" in completeness

    # 视觉质量推断（从复杂度和完整度推断）
    if complexity == "高级" and has_pipeline:
        visual_quality = "高"
    elif complexity == "中级":
        visual_quality = "中"
    else:
        visual_quality = "低"

    return {
        "tech_tags": tech_tags,
        "complexity": complexity,
        "has_pipeline": has_pipeline,
        "visual_quality": visual_quality,
        "tools": tools,
        "techniques": techniques,
    }


# ============================================================
# T08：竞品相对评级
# ============================================================

def grade_portfolios(portfolios: list) -> list:
    """
    在同届同阶段的样本中做相对排名，生成 S/A/B/C 评级。

    Args:
        portfolios: 已打标的作品集列表（包含 tech_tags/complexity/has_pipeline/visual_quality 等字段）

    Returns:
        打了评级的作品集列表，每条新增 grade 和 score 字段
    """
    if not portfolios:
        return []

    # 按届别+阶段分组
    groups: dict[str, list] = {}
    for p in portfolios:
        cohort = p.get("cohort", "未知届别")
        stage = p.get("stage", "未知阶段")
        group_key = f"{cohort}_{stage}"
        groups.setdefault(group_key, []).append(p)

    graded_all = []

    for group_key, group in groups.items():
        sample_size = len(group)
        insufficient = sample_size < 10

        for p in group:
            score = _compute_score(p)
            p["_score"] = score

        # 按分数排序
        group.sort(key=lambda x: x["_score"], reverse=True)

        for rank, p in enumerate(group):
            percentile = rank / sample_size  # 0 = 最高, 1 = 最低

            if percentile < 0.05:
                grade = "S"
            elif percentile < 0.20:
                grade = "A"
            elif percentile < 0.50:
                grade = "B"
            else:
                grade = "C"

            if insufficient:
                grade = grade + "*"  # 标注样本量不足

            result = dict(p)
            result["grade"] = grade
            result["score"] = str(round(p["_score"], 2))
            result["grade_note"] = "样本量不足，仅供参考" if insufficient else ""
            result.pop("_score", None)
            graded_all.append(result)

    return graded_all


def _compute_score(portfolio: dict) -> float:
    """
    计算单个作品集的综合评分（0-100）。

    评分维度及权重：
    - 技术广度（tech_tags 数量）：25%
    - 技术深度（complexity）：30%
    - 项目完整度（has_pipeline）：25%
    - 展示质量（visual_quality）：20%
    """
    # 技术广度：标签数量，满分为8个
    tags = portfolio.get("tech_tags", [])
    breadth_score = min(len(tags) / 8.0, 1.0) * 100

    # 技术深度
    complexity_map = {"高级": 100, "中级": 60, "基础": 20}
    complexity = portfolio.get("complexity", "基础")
    depth_score = complexity_map.get(complexity, 20)

    # 项目完整度
    pipeline_score = 100 if portfolio.get("has_pipeline", False) else 20

    # 展示质量
    quality_map = {"高": 100, "中": 55, "低": 20}
    visual_quality = portfolio.get("visual_quality", "低")
    quality_score = quality_map.get(visual_quality, 20)

    total = (
        breadth_score * 0.25
        + depth_score * 0.30
        + pipeline_score * 0.25
        + quality_score * 0.20
    )
    return round(total, 2)


print("✅ T06/T07/T08 完成")

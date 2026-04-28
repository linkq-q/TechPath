# 文件用途：B站作品集竞品监测爬虫（Phase 3 + Phase 4），使用 DrissionPage 控制 Edge 浏览器
# Phase 4：改用 DrissionPage ChromiumPage，支持登录检测和 Edge 浏览器

import base64
import json
import os
import random
import re
import time
from datetime import datetime

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")

# Edge 浏览器路径
EDGE_PATH = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"

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
    global _deepseek_client
    if _deepseek_client is None:
        _deepseek_client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )
    return _deepseek_client


def _get_qwen_client() -> OpenAI:
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
# Phase 4：使用 DrissionPage 的采集函数
# ============================================================

def crawl_bilibili_portfolios(
    keywords: list = None,
    max_count: int = 30,
) -> list:
    """
    使用 DrissionPage + Edge 浏览器采集 B站作品集视频列表。

    流程：
    1. 打开 Edge 浏览器，访问 bilibili.com
    2. 检测是否已登录，未登录则提示用户扫码
    3. 对每个关键词搜索并采集视频卡片信息
    4. 滚动加载，提取标题/UP主/链接/发布时间/播放量/点赞
    5. 从标题提取届别和求职阶段

    Args:
        keywords: 搜索关键词列表，默认使用 DEFAULT_KEYWORDS
        max_count: 最大采集总数

    Returns:
        视频信息列表
    """
    try:
        from DrissionPage import ChromiumOptions, ChromiumPage
    except ImportError:
        print("[bilibili] DrissionPage 未安装，请先运行 pip install DrissionPage")
        return _crawl_bilibili_fallback(keywords, max_count)

    if keywords is None:
        keywords = DEFAULT_KEYWORDS

    all_results = []
    seen_urls = set()
    per_keyword = max(max_count // len(keywords), 5)

    page = None
    try:
        opts = ChromiumOptions()
        opts.set_browser_path(EDGE_PATH)
        opts.set_argument("--no-sandbox")
        opts.set_argument("--disable-dev-shm-usage")
        opts.set_argument("--disable-blink-features=AutomationControlled")
        opts.set_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )

        page = ChromiumPage(addr_or_opts=opts)

        # 访问主页并检测登录状态
        page.get("https://www.bilibili.com")
        time.sleep(3)

        page_html = page.html or ""
        is_logged_in = (
            "个人中心" in page_html
            or "我的" in page_html
            or "uid" in page_html.lower()
            or "login-btn" not in page_html
        )

        if not is_logged_in:
            print("[bilibili] 检测到未登录，请在弹出的 Edge 浏览器中扫码登录...")
            print("[bilibili] 登录完成后请按回车继续...")
            input()
            page.get("https://www.bilibili.com")
            time.sleep(3)

        # 对每个关键词执行搜索
        for keyword in keywords:
            if len(all_results) >= max_count:
                break

            print(f"[bilibili] 搜索关键词：{keyword}")
            search_url = f"https://search.bilibili.com/video?keyword={keyword}&order=pubdate"
            try:
                page.get(search_url)
                time.sleep(random.uniform(2, 4))

                # 滚动加载更多
                for _ in range(3):
                    page.scroll.to_bottom()
                    time.sleep(random.uniform(1, 2))

                # 尝试多种选择器提取视频卡片
                video_cards = (
                    page.eles("css:.bili-video-card")
                    or page.eles("css:.video-item")
                    or page.eles("css:[class*='video-card']")
                )

                print(f"[bilibili] 关键词「{keyword}」找到 {len(video_cards)} 个卡片")

                for card in video_cards[:per_keyword]:
                    if len(all_results) >= max_count:
                        break
                    try:
                        video_info = _extract_card_info(card)
                        if not video_info:
                            continue
                        url = video_info.get("video_url", "")
                        if url and url not in seen_urls:
                            seen_urls.add(url)
                            all_results.append(video_info)
                    except Exception as e:
                        print(f"[bilibili] 解析卡片失败：{e}")
                        continue

                time.sleep(random.uniform(1, 3))

            except Exception as e:
                print(f"[bilibili] 搜索关键词「{keyword}」失败：{e}")
                continue

    except Exception as e:
        print(f"[bilibili] DrissionPage 整体出错：{e}")
        print("[bilibili] 降级到 requests 模式...")
        if page:
            try:
                page.close()
            except Exception:
                pass
        return _crawl_bilibili_fallback(keywords, max_count)
    finally:
        if page:
            try:
                page.close()
            except Exception:
                pass

    print(f"[bilibili] 共采集 {len(all_results)} 条去重视频")
    return all_results[:max_count]


def _extract_card_info(card) -> dict | None:
    """从 DrissionPage 元素中提取视频卡片信息"""
    try:
        # 提取链接
        link_el = (
            card.ele("css:a[href*='/video/']", timeout=1)
            or card.ele("css:a", timeout=1)
        )
        href = link_el.attr("href") if link_el else ""
        if not href:
            return None
        video_url = f"https:{href}" if href.startswith("//") else href
        if not video_url.startswith("http"):
            video_url = "https://www.bilibili.com" + href

        # 提取标题
        title_el = (
            card.ele("css:.bili-video-card__info--tit", timeout=1)
            or card.ele("css:.title", timeout=1)
            or card.ele("css:[class*='title']", timeout=1)
        )
        title = title_el.text.strip() if title_el else "未知标题"

        # 提取 UP 主
        up_el = (
            card.ele("css:.bili-video-card__info--author", timeout=1)
            or card.ele("css:.up-name", timeout=1)
            or card.ele("css:[class*='author']", timeout=1)
        )
        uploader = up_el.text.strip() if up_el else "未知UP主"

        # 提取发布时间（部分卡片有）
        date_el = card.ele("css.[class*='date']", timeout=1)
        publish_date = date_el.text.strip() if date_el else ""

        # 提取播放量
        play_el = (
            card.ele("css.[class*='play']", timeout=1)
            or card.ele("css.[class*='view']", timeout=1)
        )
        play_count_str = play_el.text.strip() if play_el else "0"

        combined_text = f"{title}"
        cohort = _extract_cohort(combined_text)
        stage = _extract_stage(combined_text)

        return {
            "video_url": video_url,
            "title": title,
            "uploader": uploader,
            "publish_date": publish_date,
            "description": "",
            "cohort": cohort,
            "stage": stage,
            "play_count": _parse_count(play_count_str),
            "like_count": 0,
            "danmaku_count": 0,
        }
    except Exception:
        return None


def _parse_count(text: str) -> int:
    """解析播放量文字（如 '1.2万'）为整数"""
    try:
        text = text.strip()
        if "万" in text:
            return int(float(text.replace("万", "")) * 10000)
        if "亿" in text:
            return int(float(text.replace("亿", "")) * 100000000)
        return int(re.sub(r"[^\d]", "", text) or "0")
    except Exception:
        return 0


def _crawl_bilibili_fallback(keywords: list = None, max_count: int = 30) -> list:
    """DrissionPage 不可用时的 requests 降级方案"""
    import requests
    from bs4 import BeautifulSoup

    if keywords is None:
        keywords = DEFAULT_KEYWORDS

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

    all_results = []
    seen_urls = set()
    per_keyword = max(max_count // len(keywords), 5)

    for keyword in keywords:
        if len(all_results) >= max_count:
            break
        print(f"[bilibili] fallback 搜索：{keyword}")
        try:
            api_url = "https://api.bilibili.com/x/web-interface/search/type"
            params = {
                "search_type": "video",
                "keyword": keyword,
                "page": 1,
                "page_size": min(per_keyword, 20),
                "order": "pubdate",
            }
            resp = requests.get(api_url, params=params, headers=headers, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if data.get("code") == 0:
                video_list = data.get("data", {}).get("result", [])
                for video in video_list:
                    bvid = video.get("bvid", "")
                    video_url = f"https://www.bilibili.com/video/{bvid}" if bvid else ""
                    if not video_url or video_url in seen_urls:
                        continue
                    seen_urls.add(video_url)

                    title = video.get("title", "").replace("<em class=\"keyword\">", "").replace("</em>", "")
                    uploader = video.get("author", "")
                    pub_ts = video.get("pubdate", 0)
                    publish_date = datetime.fromtimestamp(pub_ts).strftime("%Y-%m-%d") if pub_ts else ""
                    description = video.get("description", "")

                    combined_text = f"{title} {description}"
                    cohort = _extract_cohort(combined_text)
                    stage = _extract_stage(combined_text)

                    all_results.append({
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
            print(f"[bilibili] fallback 失败（{keyword}）：{e}")

        time.sleep(random.uniform(1, 3))

    print(f"[bilibili] fallback 共采集 {len(all_results)} 条")
    return all_results[:max_count]


# ============================================================
# 视频内容分析与打标（保留原有逻辑）
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
    for b64 in frames_b64[:10]:
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
    combined = list(dict.fromkeys(tools + techniques))
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

    if QWEN_API_KEY and video_url:
        try:
            print(f"[bilibili] 视觉分析：{title[:30]}...")
            frames = _extract_frames_base64(video_url, max_frames=15)
            if frames:
                visual_result = _analyze_with_qwen(frames)
        except Exception as e:
            print(f"[bilibili] 视觉分析失败，降级到文字分析：{e}")

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

    has_pipeline = "流程" in completeness or "工程" in completeness

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
# 竞品相对评级（保留原有逻辑）
# ============================================================

def grade_portfolios(portfolios: list) -> list:
    """
    在同届同阶段的样本中做相对排名，生成 S/A/B/C 评级。

    Args:
        portfolios: 已打标的作品集列表

    Returns:
        打了评级的作品集列表，每条新增 grade 和 score 字段
    """
    if not portfolios:
        return []

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

        group.sort(key=lambda x: x["_score"], reverse=True)

        for rank, p in enumerate(group):
            percentile = rank / sample_size

            if percentile < 0.05:
                grade = "S"
            elif percentile < 0.20:
                grade = "A"
            elif percentile < 0.50:
                grade = "B"
            else:
                grade = "C"

            if insufficient:
                grade = grade + "*"

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
    tags = portfolio.get("tech_tags", [])
    breadth_score = min(len(tags) / 8.0, 1.0) * 100

    complexity_map = {"高级": 100, "中级": 60, "基础": 20}
    complexity = portfolio.get("complexity", "基础")
    depth_score = complexity_map.get(complexity, 20)

    pipeline_score = 100 if portfolio.get("has_pipeline", False) else 20

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


print("✅ T08 完成")

# 文件用途：Agent 工具函数定义（Phase 1 + Phase 2），包括 GitHub 导入、文本/URL 导入、知识库搜索、视频转录与分析

import base64
import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from github import Github, GithubException
from openai import OpenAI

from core.database import save_knowledge_item, search_knowledge_items

load_dotenv()

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")

# 临时文件目录
TEMP_DIR = Path(__file__).parent.parent / "data" / "temp"
FRAMES_DIR = TEMP_DIR / "frames"

# DeepSeek 客户端（OpenAI 兼容接口）
_deepseek_client = None


def _get_deepseek_client() -> OpenAI:
    """懒加载 DeepSeek 客户端"""
    global _deepseek_client
    if _deepseek_client is None:
        _deepseek_client = OpenAI(
            api_key=DEEPSEEK_API_KEY,
            base_url="https://api.deepseek.com",
        )
    return _deepseek_client


# ============================================================
# T02: GitHub 仓库导入工具
# ============================================================

def read_github_repo(url: str) -> dict:
    """
    读取 GitHub 仓库内容，返回仓库基本信息、README、文件树和关键代码文件。

    Args:
        url: GitHub 仓库 URL，如 https://github.com/owner/repo

    Returns:
        包含 repo_name, description, readme, file_tree, key_files 的字典；
        出错时返回 {"error": "错误信息"}
    """
    if not GITHUB_TOKEN:
        return {"error": "未配置 GITHUB_TOKEN，请在 .env 文件中设置"}

    # 解析 owner/repo
    try:
        parsed = urlparse(url.strip())
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) < 2:
            return {"error": f"无法解析仓库 URL：{url}，格式应为 https://github.com/owner/repo"}
        owner, repo_name = parts[0], parts[1]
    except Exception as e:
        return {"error": f"URL 解析失败：{e}"}

    try:
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(f"{owner}/{repo_name}")
    except GithubException as e:
        if e.status == 404:
            return {"error": f"仓库 {owner}/{repo_name} 不存在或无权限访问"}
        elif e.status == 401:
            return {"error": "GitHub Token 无效，请检查 .env 中的 GITHUB_TOKEN"}
        else:
            return {"error": f"GitHub API 错误（{e.status}）：{e.data.get('message', str(e))}"}
    except Exception as e:
        return {"error": f"网络错误：{e}"}

    result = {
        "repo_name": repo.full_name,
        "description": repo.description or "",
        "readme": "",
        "file_tree": [],
        "key_files": {},
    }

    # 读取 README
    try:
        readme = repo.get_readme()
        result["readme"] = readme.decoded_content.decode("utf-8", errors="ignore")[:5000]
    except Exception:
        result["readme"] = "（未找到 README 文件）"

    # 构建两层深度文件树，同时收集代码文件路径
    code_extensions = {".py", ".cs", ".hlsl"}
    code_file_paths = []

    try:
        root_contents = repo.get_contents("")
        for item in root_contents:
            result["file_tree"].append({"path": item.path, "type": item.type})
            if item.type == "dir":
                try:
                    sub_contents = repo.get_contents(item.path)
                    for sub_item in sub_contents:
                        result["file_tree"].append({"path": sub_item.path, "type": sub_item.type})
                        ext = os.path.splitext(sub_item.name)[1].lower()
                        if sub_item.type == "file" and ext in code_extensions:
                            code_file_paths.append(sub_item.path)
                except Exception:
                    pass
            else:
                ext = os.path.splitext(item.name)[1].lower()
                if ext in code_extensions:
                    code_file_paths.append(item.path)
    except Exception as e:
        result["file_tree"] = [{"error": f"无法读取文件树：{e}"}]

    # 读取代码文件（最多 20 个，单文件超 300 行只取前 300 行）
    for path in code_file_paths[:20]:
        try:
            file_content = repo.get_contents(path)
            text = file_content.decoded_content.decode("utf-8", errors="ignore")
            lines = text.splitlines()
            if len(lines) > 300:
                text = "\n".join(lines[:300]) + f"\n... （文件共 {len(lines)} 行，仅展示前 300 行）"
            result["key_files"][path] = text
        except Exception:
            result["key_files"][path] = "（读取失败）"

    return result


# ============================================================
# T03: 文本/URL 导入工具
# ============================================================

def import_text_content(
    content: str,
    source_url: str = "",
    title: str = "",
) -> dict:
    """
    导入文本或 URL 内容到知识库，自动生成摘要和标签后存入数据库。

    Args:
        content: 纯文本内容，或以 http 开头的 URL
        source_url: 内容来源 URL（纯文本时可选）
        title: 自定义标题（可选，不填则自动生成）

    Returns:
        包含 id, title, summary, tags 的字典；出错时返回 {"error": "..."}
    """
    raw_text = ""
    source_type = "text"
    actual_url = source_url

    # 如果 content 是 URL，则抓取页面正文
    if content.strip().startswith("http"):
        actual_url = content.strip()
        source_type = "article"
        try:
            resp = requests.get(actual_url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            # 去除脚本和样式标签
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            raw_text = soup.get_text(separator="\n", strip=True)
            # 截断避免 token 超支
            raw_text = raw_text[:8000]
        except requests.RequestException as e:
            return {"error": f"URL 抓取失败：{e}"}
        except Exception as e:
            return {"error": f"页面解析失败：{e}"}
    else:
        raw_text = content.strip()

    if not raw_text:
        return {"error": "内容为空，无法导入"}

    # 使用 DeepSeek 生成摘要和标签
    try:
        client = _get_deepseek_client()
        prompt = (
            f"请对以下技术内容生成：\n"
            f"1. 一个简短标题（15字以内，如未提供则自动生成）\n"
            f"2. 100字以内的中文摘要\n"
            f"3. 最多5个技术标签（英文小写，逗号分隔）\n\n"
            f"已提供标题：{title if title else '（无，请自动生成）'}\n\n"
            f"内容：\n{raw_text[:3000]}\n\n"
            f"请严格按以下 JSON 格式返回，不要添加其他内容：\n"
            f'{{"title": "...", "summary": "...", "tags": ["tag1", "tag2"]}}'
        )
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        raw_json = resp.choices[0].message.content.strip()
        # 提取 JSON 部分
        match = re.search(r"\{.*\}", raw_json, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
        else:
            parsed = {"title": title or "未命名", "summary": raw_text[:100], "tags": []}

        final_title = title if title else parsed.get("title", "未命名")
        summary = parsed.get("summary", raw_text[:100])
        tags = parsed.get("tags", [])[:5]
    except Exception as e:
        # AI 生成失败时用默认值
        final_title = title or actual_url or "未命名内容"
        summary = raw_text[:100]
        tags = []

    # 存入数据库
    try:
        item_id = save_knowledge_item(
            title=final_title,
            content_summary=summary,
            full_text=raw_text,
            source_type=source_type,
            source_url=actual_url,
            tags=tags,
        )
    except Exception as e:
        return {"error": f"数据库写入失败：{e}"}

    return {
        "id": item_id,
        "title": final_title,
        "summary": summary,
        "tags": tags,
        "source_type": source_type,
    }


# ============================================================
# T04: 知识库搜索工具
# ============================================================

def search_knowledge_base(query: str) -> list:
    """
    在知识库中关键词搜索，返回最多 5 条匹配结果。

    Args:
        query: 搜索关键词

    Returns:
        匹配条目列表，每条包含 id, title, content_summary, source_type, tags
    """
    if not query.strip():
        return []

    try:
        results = search_knowledge_items(query.strip())
        # 只返回前端需要的字段
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "content_summary": r["content_summary"],
                "source_type": r["source_type"],
                "tags": r["tags"],
            }
            for r in results
        ]
    except Exception as e:
        return [{"error": f"搜索失败：{e}"}]


# ============================================================
# T02: 视频音频转录工具
# ============================================================

def transcribe_video(url: str) -> dict:
    """
    下载视频音频并转录为文字，支持 B 站 URL 和本地文件路径。

    Args:
        url: B 站视频 URL 或本地视频文件路径

    Returns:
        包含 video_url, title, transcript, duration_seconds, language 的字典；
        出错时返回 {"error": "..."}
    """
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    audio_path = None

    try:
        # 判断是本地文件还是网络视频
        is_local = not url.strip().startswith("http")
        if is_local and not Path(url).exists():
            return {"error": f"本地文件不存在：{url}"}

        video_title = Path(url).stem if is_local else "视频"
        duration = 0

        if not is_local:
            # 使用 yt-dlp 下载音频
            import yt_dlp

            audio_path = str(TEMP_DIR / f"audio_{int(time.time())}.%(ext)s")
            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": audio_path,
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "128",
                }],
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_title = info.get("title", "视频") if info else "视频"
                duration = info.get("duration", 0) if info else 0

            # yt-dlp 会把 %(ext)s 替换成实际扩展名
            audio_path = audio_path.replace("%(ext)s", "mp3")
            if not Path(audio_path).exists():
                # 查找实际下载的文件
                candidates = list(TEMP_DIR.glob(f"audio_{int(time.time()) - 5}*.mp3"))
                candidates += list(TEMP_DIR.glob("audio_*.mp3"))
                if candidates:
                    audio_path = str(max(candidates, key=lambda p: p.stat().st_mtime))
                else:
                    return {"error": "音频下载失败，未找到输出文件"}
        else:
            audio_path = url

        # 转录：优先使用 OpenAI Whisper API，没有 key 则用本地模型
        transcript = ""
        language = "zh"

        if OPENAI_API_KEY:
            # 使用 OpenAI Whisper API
            openai_client = OpenAI(api_key=OPENAI_API_KEY)
            with open(audio_path, "rb") as f:
                resp = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=f,
                    language="zh",
                )
            transcript = resp.text
            language = getattr(resp, "language", "zh")
        else:
            # 使用本地 whisper 模型
            import whisper
            model = whisper.load_model("base")
            result = model.transcribe(audio_path, language="zh")
            transcript = result.get("text", "")
            language = result.get("language", "zh")

        return {
            "video_url": url,
            "title": video_title,
            "transcript": transcript,
            "duration_seconds": duration,
            "language": language,
        }

    except Exception as e:
        return {"error": f"视频转录失败：{e}"}
    finally:
        # 删除临时音频文件
        if audio_path and not url.strip().startswith("/") and Path(audio_path).exists():
            try:
                Path(audio_path).unlink()
            except Exception:
                pass


# ============================================================
# T03: 视频画面分析工具
# ============================================================

def analyze_video_visual(url: str) -> dict:
    """
    从视频中抽取关键帧并使用 Qwen VL 分析技术内容。

    Args:
        url: B 站视频 URL 或本地视频文件路径

    Returns:
        包含 tools, techniques, complexity, summary 的字典；
        出错时返回 {"error": "..."}
    """
    if not QWEN_API_KEY:
        return {"error": "未配置 QWEN_API_KEY，跳过画面分析"}

    FRAMES_DIR.mkdir(parents=True, exist_ok=True)
    frame_dir = FRAMES_DIR / f"frames_{int(time.time())}"
    frame_dir.mkdir(exist_ok=True)
    video_path = None
    downloaded = False

    try:
        import yt_dlp

        if url.strip().startswith("http"):
            # 下载视频（取最低画质以节省时间）
            video_path = str(TEMP_DIR / f"video_{int(time.time())}.%(ext)s")
            ydl_opts = {
                "format": "worstvideo[ext=mp4]/worst[ext=mp4]/worst",
                "outtmpl": video_path,
                "quiet": True,
                "no_warnings": True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                duration = info.get("duration", 0) if info else 0

            candidates = list(TEMP_DIR.glob("video_*.mp4"))
            if not candidates:
                return {"error": "视频下载失败"}
            video_path = str(max(candidates, key=lambda p: p.stat().st_mtime))
            downloaded = True
        else:
            video_path = url
            duration = 0

        # 使用 ffmpeg 每 30 秒抽一帧，最多 20 帧
        import subprocess
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vf", "fps=1/30",
            "-frames:v", "20",
            "-q:v", "3",
            str(frame_dir / "frame_%04d.jpg"),
            "-y", "-loglevel", "error",
        ]
        subprocess.run(cmd, check=True, capture_output=True)

        frame_files = sorted(frame_dir.glob("frame_*.jpg"))
        if not frame_files:
            return {"error": "关键帧提取失败"}

        # 将帧转为 base64
        images_b64 = []
        for f in frame_files[:20]:
            with open(f, "rb") as img:
                images_b64.append(base64.b64encode(img.read()).decode())

        # 调用 Qwen VL API
        qwen_client = OpenAI(
            api_key=QWEN_API_KEY,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        # 构建多图消息（取前 5 帧，避免 token 超限）
        content = [
            {
                "type": "text",
                "text": (
                    "分析这些视频截帧，判断视频展示了哪些技术内容。"
                    "关注：使用了什么软件工具、实现了什么技术效果、代码/界面截图中有什么关键信息。"
                    '输出JSON格式：{"tools": [], "techniques": [], "complexity": "基础/中级/高级", "summary": ""}'
                ),
            }
        ]
        for b64 in images_b64[:5]:
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            })

        resp = qwen_client.chat.completions.create(
            model="qwen-vl-plus",
            messages=[{"role": "user", "content": content}],
            temperature=0.3,
        )
        raw = resp.choices[0].message.content.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
        else:
            parsed = {"tools": [], "techniques": [], "complexity": "未知", "summary": raw}

        return {
            "tools": parsed.get("tools", []),
            "techniques": parsed.get("techniques", []),
            "complexity": parsed.get("complexity", "未知"),
            "summary": parsed.get("summary", ""),
        }

    except Exception as e:
        return {"error": f"视频画面分析失败：{e}"}
    finally:
        # 清理临时文件
        if downloaded and video_path and Path(video_path).exists():
            try:
                Path(video_path).unlink()
            except Exception:
                pass
        if frame_dir.exists():
            shutil.rmtree(frame_dir, ignore_errors=True)


# ============================================================
# T04: 视频完整导入流程
# ============================================================

def import_video(url: str, title: str = "") -> dict:
    """
    完整视频导入流程：转录音频 + 分析画面 + AI 综合摘要 + 存入知识库。

    Args:
        url: B 站视频 URL 或本地文件路径
        title: 自定义标题（可选）

    Returns:
        包含 id, title, summary, tags 的字典；出错时返回 {"error": "..."}
    """
    # Step 1: 转录音频
    transcript_result = transcribe_video(url)
    has_transcript = "error" not in transcript_result

    # Step 2: 分析画面（可选，QWEN_API_KEY 未配置则跳过）
    visual_result = {}
    if QWEN_API_KEY:
        visual_result = analyze_video_visual(url)
        if "error" in visual_result:
            # 画面分析失败不阻断流程
            visual_result = {}

    # 如果两步都失败则报错
    if not has_transcript and not visual_result:
        return {"error": transcript_result.get("error", "视频导入失败")}

    # 整合内容
    video_title = title or (transcript_result.get("title", "") if has_transcript else "视频内容")
    transcript_text = transcript_result.get("transcript", "") if has_transcript else ""
    visual_summary = visual_result.get("summary", "")
    visual_tools = visual_result.get("tools", [])
    visual_techniques = visual_result.get("techniques", [])

    combined_text = ""
    if transcript_text:
        combined_text += f"【音频转录】\n{transcript_text}\n\n"
    if visual_summary:
        combined_text += f"【画面分析】\n{visual_summary}\n"
        if visual_tools:
            combined_text += f"工具：{', '.join(visual_tools)}\n"
        if visual_techniques:
            combined_text += f"技术：{', '.join(visual_techniques)}\n"

    if not combined_text:
        combined_text = "（内容提取为空）"

    # 调用 DeepSeek 生成综合摘要和标签
    try:
        client = _get_deepseek_client()
        prompt = (
            f"以下是一个技术视频的内容（音频转录 + 画面分析）：\n\n{combined_text[:3000]}\n\n"
            f"请生成：\n"
            f"1. 100字以内的中文技术摘要\n"
            f"2. 最多6个技术标签（英文小写）\n\n"
            f'请严格返回 JSON：{{"summary": "...", "tags": ["tag1", "tag2"]}}'
        )
        resp = client.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        raw_json = resp.choices[0].message.content.strip()
        match = re.search(r"\{.*\}", raw_json, re.DOTALL)
        if match:
            parsed = json.loads(match.group())
            summary = parsed.get("summary", combined_text[:100])
            tags = parsed.get("tags", [])[:6]
        else:
            summary = combined_text[:100]
            tags = visual_techniques[:5]
    except Exception:
        summary = combined_text[:100]
        tags = visual_techniques[:5]

    # 合并视觉标签
    all_tags = list(dict.fromkeys(tags + visual_tools + visual_techniques))[:6]

    # 存入数据库
    try:
        item_id = save_knowledge_item(
            title=video_title,
            content_summary=summary,
            full_text=combined_text,
            source_type="video",
            source_url=url,
            tags=all_tags,
        )
    except Exception as e:
        return {"error": f"数据库写入失败：{e}"}

    return {
        "id": item_id,
        "title": video_title,
        "summary": summary,
        "tags": all_tags,
        "has_transcript": has_transcript,
        "has_visual": bool(visual_result),
    }

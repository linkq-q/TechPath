# 文件用途：Agent 工具函数定义，包括 GitHub 导入、文本/URL 导入、知识库搜索

import json
import os
import re
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

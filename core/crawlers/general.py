# 文件用途：牛客网、知乎内容爬虫，使用 Scrapling 库

import random
import time
from urllib.parse import quote

from core.database import save_jd_record


def crawl_niuke(keyword: str = "技术美术 面经") -> list:
    """
    爬取牛客网搜索结果，提取帖子标题和内容摘要。

    Args:
        keyword: 搜索关键词

    Returns:
        最多 20 条结果，每条包含 title, summary, url；失败返回空列表
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        encoded = quote(keyword)
        url = f"https://www.nowcoder.com/search?query={encoded}&type=post"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.nowcoder.com/",
        }

        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        # 尝试多种选择器适配页面结构
        items = (
            soup.select(".post-item")
            or soup.select(".search-item")
            or soup.select("[class*='post-item']")
            or soup.select("article")
        )

        for item in items[:20]:
            try:
                # 提取标题
                title_elem = (
                    item.select_one(".post-item-title a")
                    or item.select_one("h3 a")
                    or item.select_one("a[href*='/discuss/']")
                    or item.select_one("a")
                )
                title = title_elem.get_text(strip=True) if title_elem else ""
                href = title_elem.get("href", "") if title_elem else ""
                full_url = f"https://www.nowcoder.com{href}" if href.startswith("/") else href

                # 提取摘要
                summary_elem = (
                    item.select_one(".post-item-desc")
                    or item.select_one(".search-summary")
                    or item.select_one("p")
                )
                summary = summary_elem.get_text(strip=True)[:300] if summary_elem else ""

                if title:
                    results.append({"title": title, "summary": summary, "url": full_url})

                    # 将内容保存到 jd_records（平台标记为 niuke）
                    try:
                        save_jd_record(
                            platform="niuke",
                            company="",
                            title=title,
                            location="",
                            requirements_raw=summary,
                        )
                    except Exception:
                        pass

            except Exception:
                continue

        print(f"[niuke] 爬取完成，共 {len(results)} 条")
        return results

    except Exception as e:
        print(f"[niuke] 爬取失败：{e}")
        return []


def crawl_zhihu(keyword: str = "技术美术 AI TA 求职") -> list:
    """
    爬取知乎搜索结果，提取问题/文章标题和摘要。

    Args:
        keyword: 搜索关键词

    Returns:
        最多 20 条结果，每条包含 title, summary, url；失败返回空列表
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        encoded = quote(keyword)
        url = f"https://www.zhihu.com/search?type=content&q={encoded}"

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Referer": "https://www.zhihu.com/",
            "Cookie": "",  # 知乎搜索需要登录态，此处留空（降级返回部分结果）
        }

        resp = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(resp.text, "html.parser")

        results = []
        items = (
            soup.select(".SearchResult-Card")
            or soup.select("[class*='SearchResult']")
            or soup.select("article")
            or soup.select(".List-item")
        )

        for item in items[:20]:
            try:
                title_elem = (
                    item.select_one("h2 a")
                    or item.select_one(".ContentItem-title a")
                    or item.select_one("[class*='title'] a")
                    or item.select_one("a")
                )
                title = title_elem.get_text(strip=True) if title_elem else ""
                href = title_elem.get("href", "") if title_elem else ""

                summary_elem = (
                    item.select_one(".RichText")
                    or item.select_one("[class*='content']")
                    or item.select_one("p")
                )
                summary = summary_elem.get_text(strip=True)[:300] if summary_elem else ""

                if title:
                    results.append({"title": title, "summary": summary, "url": href})

                    try:
                        save_jd_record(
                            platform="zhihu",
                            company="",
                            title=title,
                            location="",
                            requirements_raw=summary,
                        )
                    except Exception:
                        pass

            except Exception:
                continue

        print(f"[zhihu] 爬取完成，共 {len(results)} 条")
        return results

    except Exception as e:
        print(f"[zhihu] 爬取失败：{e}")
        return []

# 文件用途：Boss 直聘职位 JD 爬虫，使用 DrissionPage 操作 Chrome 浏览器

import random
import time
from typing import Optional

from core.database import save_jd_record


def crawl_bosszp(keyword: str = "AI TA", max_count: int = 20) -> list:
    """
    爬取 Boss 直聘的职位列表和 JD 详情。

    Args:
        keyword: 搜索关键词，默认 "AI TA"
        max_count: 最多爬取条数，默认 20

    Returns:
        职位列表，每条包含 company, title, location, salary, requirements_raw；
        出错时返回空列表
    """
    try:
        from DrissionPage import ChromiumOptions, ChromiumPage
    except ImportError:
        print("[bosszp] DrissionPage 未安装，请先运行 pip install DrissionPage")
        return []

    results = []

    try:
        opts = ChromiumOptions()
        opts.headless()
        opts.set_argument("--no-sandbox")
        opts.set_argument("--disable-dev-shm-usage")
        opts.set_argument("--disable-blink-features=AutomationControlled")
        opts.set_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")

        page = ChromiumPage(addr_or_opts=opts)

        search_url = f"https://www.zhipin.com/web/geek/job?query={keyword}&city=100010000"
        page.get(search_url)
        time.sleep(3)

        # 检测是否需要登录
        current_url = page.url
        page_text = page.html or ""
        need_login = (
            "login" in current_url.lower()
            or "扫码" in page_text
            or "登录" in page_text[:2000]
        )

        if need_login:
            print("[bosszp] 检测到需要登录，请在弹出的浏览器窗口中手动登录后按回车继续...")
            input("[bosszp] 按回车继续爬取...")
            page.get(search_url)
            time.sleep(3)

        # 滚动加载更多
        for _ in range(3):
            page.scroll.to_bottom()
            time.sleep(random.uniform(1.5, 2.5))

        # 提取职位卡片
        job_cards = page.eles("css:.job-card-wrapper") or page.eles("css:.job-card-body")
        if not job_cards:
            job_cards = page.eles("css:[class*='job-card']")

        print(f"[bosszp] 找到 {len(job_cards)} 个职位卡片")

        for idx, card in enumerate(job_cards[:max_count]):
            if len(results) >= max_count:
                break
            try:
                # 提取卡片基本信息
                title = _safe_text(card, "css:.job-name") or _safe_text(card, "css:[class*='job-name']") or "未知职位"
                company = _safe_text(card, "css:.company-name") or _safe_text(card, "css:[class*='company-name']") or "未知公司"
                location = _safe_text(card, "css:.job-area") or _safe_text(card, "css:[class*='job-area']") or ""
                salary = _safe_text(card, "css:.salary") or _safe_text(card, "css:[class*='salary']") or ""

                # 点击进入详情页获取 JD
                requirements_raw = ""
                try:
                    link = card.ele("css:a", timeout=2)
                    if link:
                        detail_url = link.attr("href") or ""
                        if detail_url and not detail_url.startswith("http"):
                            detail_url = "https://www.zhipin.com" + detail_url
                        if detail_url:
                            page.get(detail_url)
                            time.sleep(random.uniform(2, 4))
                            jd_elem = page.ele("css:.job-detail-section") or page.ele("css:[class*='job-sec-text']")
                            if jd_elem:
                                requirements_raw = jd_elem.text[:3000]
                            page.back()
                            time.sleep(random.uniform(1, 2))
                except Exception:
                    pass

                if not requirements_raw:
                    requirements_raw = f"{title} @ {company}，{location}，薪资：{salary}"

                job_data = {
                    "company": company,
                    "title": title,
                    "location": location,
                    "salary": salary,
                    "requirements_raw": requirements_raw,
                }
                results.append(job_data)

                # 保存到数据库
                try:
                    save_jd_record(
                        platform="bosszp",
                        company=company,
                        title=title,
                        location=location,
                        requirements_raw=requirements_raw,
                    )
                except Exception:
                    pass

                print(f"[bosszp] 已爬取 {len(results)}/{min(max_count, len(job_cards))}: {title} @ {company}")
                time.sleep(random.uniform(2, 4))

            except Exception as e:
                print(f"[bosszp] 处理第 {idx+1} 条时出错：{e}")
                continue

        page.close()

    except Exception as e:
        print(f"[bosszp] 爬虫整体出错：{e}")

    print(f"[bosszp] 爬取完成，共 {len(results)} 条")
    return results


def _safe_text(elem, selector: str) -> str:
    """安全提取子元素文字，失败返回空字符串"""
    try:
        sub = elem.ele(selector, timeout=1)
        return sub.text.strip() if sub else ""
    except Exception:
        return ""

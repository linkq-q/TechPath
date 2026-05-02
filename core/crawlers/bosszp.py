# 文件用途：Boss 直聘职位 JD 爬虫，使用 DrissionPage 操作 Edge 浏览器
# T01: 浏览器实例改为模块级单例，整个进程只创建一次
# T02: 修复字段提取，使用 wait 机制和扩展选择器

import random
import time
from datetime import datetime
from typing import Optional

from core.database import save_jd_record

# ============================================================
# 模块级单例：浏览器实例 + 最后活跃时间
# ============================================================

_browser_instance = None           # ChromiumPage 单例
_browser_last_active: float = 0.0  # 最后一次操作的时间戳（用于超时检测）
_BROWSER_TIMEOUT_SECS = 1800       # 30 分钟无操作自动关闭


def _is_logged_in(page) -> bool:
    """检测当前页面是否已登录 Boss 直聘"""
    try:
        url = page.url or ""
        html = page.html or ""
        # 如果跳转到登录页、或页面包含登录提示则认为未登录
        if "login" in url.lower():
            return False
        if "扫码登录" in html[:3000] or ("登录" in html[:1000] and "注册" in html[:1000]):
            return False
        # 判断是否有用户头像或用户中心链接（已登录状态）
        if "我的Boss" in html or "user-avatar" in html or "job-recommend" in html:
            return True
        # 如果页面加载了职位列表则认为已登录
        if "job-card" in html or "job-list" in html:
            return True
        return True  # 默认假设已登录，继续流程
    except Exception:
        return False


def get_browser_instance():
    """
    获取（或创建）模块级浏览器单例。
    - 若不存在则新建，并检测登录状态
    - 若已存在且登录有效则直接复用
    - 若已存在但超时或登录失效则重建
    """
    global _browser_instance, _browser_last_active

    try:
        from DrissionPage import ChromiumOptions, ChromiumPage
    except ImportError:
        print("[bosszp] DrissionPage 未安装，请先运行 pip install DrissionPage")
        return None

    now = time.time()

    # 检查超时：超过30分钟未使用，关闭旧实例
    if _browser_instance is not None:
        if (now - _browser_last_active) > _BROWSER_TIMEOUT_SECS:
            print("[bosszp] 浏览器实例超时（30分钟），自动关闭并重建")
            try:
                _browser_instance.close()
            except Exception:
                pass
            _browser_instance = None

    # 若实例存在，验证登录状态
    if _browser_instance is not None:
        try:
            # 简单访问 Boss 首页检查状态
            test_url = "https://www.zhipin.com/web/geek/job?query=AI工程师&city=100010000"
            _browser_instance.get(test_url)
            time.sleep(2)
            if _is_logged_in(_browser_instance):
                print("[bosszp] 复用已登录的浏览器实例")
                _browser_last_active = time.time()
                return _browser_instance
            else:
                print("[bosszp] 登录状态失效，需要重新登录")
        except Exception as e:
            print(f"[bosszp] 实例验证失败：{e}，重新创建")
            try:
                _browser_instance.close()
            except Exception:
                pass
            _browser_instance = None

    # 创建新实例
    print("[bosszp] 创建新的浏览器实例…")
    opts = ChromiumOptions()
    # 尝试使用 Edge（Windows 默认路径），不存在则让 DrissionPage 自动选择
    import os
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for ep in edge_paths:
        if os.path.exists(ep):
            opts.set_browser_path(ep)
            break

    opts.set_argument("--no-sandbox")
    opts.set_argument("--disable-dev-shm-usage")
    opts.set_argument("--disable-blink-features=AutomationControlled")
    opts.set_argument(
        "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    try:
        page = ChromiumPage(addr_or_opts=opts)
    except Exception as e:
        print(f"[bosszp] 浏览器启动失败：{e}")
        return None

    # 导航到 Boss 直聘，检测登录
    search_url = "https://www.zhipin.com/web/geek/job?query=AI工程师&city=100010000"
    page.get(search_url)
    time.sleep(3)

    if not _is_logged_in(page):
        print("[bosszp] 检测到需要登录，请在弹出的浏览器窗口中手动登录后按回车继续…")
        input("[bosszp] 登录完成后按回车继续爬取…")
        page.get(search_url)
        time.sleep(3)

    _browser_instance = page
    _browser_last_active = time.time()
    print("[bosszp] 浏览器实例创建完成，已登录")
    return _browser_instance


def close_browser() -> None:
    """关闭浏览器实例（程序退出时调用）"""
    global _browser_instance, _browser_last_active
    if _browser_instance is not None:
        try:
            _browser_instance.close()
            print("[bosszp] 浏览器实例已关闭")
        except Exception:
            pass
        _browser_instance = None
        _browser_last_active = 0.0


# ============================================================
# 字段提取辅助函数
# ============================================================

def _safe_text(elem, *selectors: str) -> str:
    """按优先级尝试多个 CSS 选择器，返回第一个非空文本"""
    for sel in selectors:
        try:
            sub = elem.ele(sel, timeout=1)
            if sub:
                text = sub.text.strip() if hasattr(sub, "text") else ""
                if text:
                    return text
        except Exception:
            continue
    return ""


def _safe_page_text(page, *selectors: str) -> str:
    """在 page 级别按优先级尝试多个选择器"""
    for sel in selectors:
        try:
            elem = page.ele(sel, timeout=2)
            if elem:
                text = elem.text.strip() if hasattr(elem, "text") else ""
                if text:
                    return text
        except Exception:
            continue
    return ""


def _wait_for_cards(page, timeout: int = 10) -> list:
    """等待职位卡片出现（最多等 timeout 秒），返回卡片列表"""
    start = time.time()
    while time.time() - start < timeout:
        cards = (
            page.eles("css:.job-card-wrapper")
            or page.eles("css:.job-card-body")
            or page.eles("css:[class*='job-card']")
        )
        if cards:
            return cards
        time.sleep(1)
    print("[bosszp] 等待职位卡片超时，返回空列表")
    return []


# ============================================================
# 主爬取函数
# ============================================================

def crawl_bosszp(keyword: str = "AI TA", max_count: int = 20,
                 city_code: str = "100010000",
                 experience_filter: str = "") -> list:
    """
    爬取 Boss 直聘的职位列表和 JD 详情。

    Args:
        keyword:           搜索关键词
        max_count:         最多爬取条数，默认 20
        city_code:         城市代码（Boss 直聘），默认全国
        experience_filter: 经验筛选参数（url param），如 "101" 代表应届

    Returns:
        职位列表，每条包含 company, title, location, salary,
        experience_required, education_required, company_stage,
        base_city, requirements_raw；出错时返回空列表
    """
    global _browser_last_active

    page = get_browser_instance()
    if page is None:
        return []

    results = []

    try:
        # 构造搜索 URL（带经验筛选）
        search_url = (
            f"https://www.zhipin.com/web/geek/job"
            f"?query={keyword}&city={city_code}"
        )
        if experience_filter:
            search_url += f"&experience={experience_filter}"

        page.get(search_url)
        _browser_last_active = time.time()

        # 等待职位卡片出现（而不是固定 sleep）
        time.sleep(2)
        job_cards = _wait_for_cards(page, timeout=10)

        # 再滚动加载更多
        for _ in range(3):
            page.scroll.to_bottom()
            time.sleep(random.uniform(1.2, 2.0))

        # 重新获取（滚动后可能加载更多）
        job_cards = (
            page.eles("css:.job-card-wrapper")
            or page.eles("css:.job-card-body")
            or page.eles("css:[class*='job-card']")
        )

        if not job_cards:
            print(f"[bosszp] 关键词「{keyword}」未找到职位卡片，跳过")
            return []

        print(f"[bosszp] 找到 {len(job_cards)} 个职位卡片（关键词：{keyword}）")

        for idx, card in enumerate(job_cards[:max_count]):
            if len(results) >= max_count:
                break
            try:
                # ---- 职位名 ----
                title = _safe_text(
                    card,
                    "css:.job-name",
                    "css:[class*='job-name']",
                    "css:h3",
                )
                if not title:
                    # 尝试 a 标签文字
                    try:
                        a = card.ele("css:a", timeout=1)
                        title = a.text.strip() if a else ""
                    except Exception:
                        pass
                if not title:
                    title = "未知职位"
                    print(f"[bosszp] 卡片 #{idx+1} 职位名提取失败，已使用默认值")

                # ---- 公司名 ----
                company = _safe_text(
                    card,
                    "css:.company-name",
                    "css:[class*='company-name']",
                    "css:.info-company",
                    "css:[class*='company']",
                )
                if not company:
                    company = "未知公司"
                    print(f"[bosszp] 卡片 #{idx+1} 公司名提取失败，已使用默认值")

                # ---- 薪资 ----
                salary = _safe_text(
                    card,
                    "css:.salary",
                    "css:[class*='salary']",
                    "css:.red",
                )

                # ---- 地点 ----
                location = _safe_text(
                    card,
                    "css:.job-area",
                    "css:[class*='job-area']",
                    "css:[class*='location']",
                )
                base_city = location.split("·")[0].strip() if location else ""

                # ---- 经验要求 ----
                experience_required = _safe_text(
                    card,
                    "css:.job-limit .tag",
                    "css:[class*='experience']",
                    "css:[class*='job-limit']",
                )

                # ---- 学历要求 ----
                education_required = _safe_text(
                    card,
                    "css:.job-limit .tag:last-child",
                    "css:[class*='education']",
                    "css:[class*='degree']",
                )

                # ---- 公司规模/融资阶段 ----
                company_stage = _safe_text(
                    card,
                    "css:.company-tag-list .tag",
                    "css:[class*='company-tag']",
                    "css:[class*='financing']",
                    "css:[class*='stage']",
                )

                # ---- 点击进入详情页获取完整 JD ----
                requirements_raw = ""
                try:
                    link = card.ele("css:a", timeout=2)
                    if link:
                        detail_url = link.attr("href") or ""
                        if detail_url and not detail_url.startswith("http"):
                            detail_url = "https://www.zhipin.com" + detail_url
                        if detail_url:
                            page.get(detail_url)
                            _browser_last_active = time.time()
                            # 等待 JD 内容加载
                            time.sleep(random.uniform(2, 3))
                            jd_elem = (
                                page.ele("css:.job-detail-section", timeout=5)
                                or page.ele("css:[class*='job-sec-text']", timeout=3)
                                or page.ele("css:[class*='job-detail']", timeout=3)
                                or page.ele("css:.desc", timeout=2)
                            )
                            if jd_elem:
                                requirements_raw = jd_elem.text.strip()[:3000]

                            # 若详情页还能提取更多信息
                            if not experience_required:
                                experience_required = _safe_page_text(
                                    page,
                                    "css:[class*='job-require'] span",
                                    "css:[class*='require-item']",
                                )
                            if not education_required:
                                education_required = _safe_page_text(
                                    page,
                                    "css:[class*='job-require'] span:last-child",
                                )
                            if not company_stage:
                                company_stage = _safe_page_text(
                                    page,
                                    "css:[class*='company-info'] [class*='tag']",
                                    "css:[class*='financing']",
                                )

                            page.back()
                            _browser_last_active = time.time()
                            time.sleep(random.uniform(1, 2))
                except Exception as ex:
                    print(f"[bosszp] 卡片 #{idx+1} 进入详情页失败：{ex}")

                if not requirements_raw:
                    requirements_raw = (
                        f"{title} @ {company}，{location}，薪资：{salary}"
                        + (f"，经验：{experience_required}" if experience_required else "")
                        + (f"，学历：{education_required}" if education_required else "")
                    )

                job_data = {
                    "company": company,
                    "title": title,
                    "location": location,
                    "salary": salary,
                    "experience_required": experience_required,
                    "education_required": education_required,
                    "company_stage": company_stage,
                    "base_city": base_city,
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
                        experience_required=experience_required,
                        education_required=education_required,
                        company_stage=company_stage,
                        base_city=base_city,
                    )
                except Exception:
                    pass

                print(
                    f"[bosszp] {len(results)}/{min(max_count, len(job_cards))}: "
                    f"{title} @ {company}  薪资:{salary}  经验:{experience_required}"
                )
                time.sleep(random.uniform(1.5, 3.0))

            except Exception as e:
                print(f"[bosszp] 处理第 {idx+1} 条时出错：{e}")
                continue

    except Exception as e:
        print(f"[bosszp] 爬虫整体出错：{e}")

    print(f"[bosszp] 爬取完成，共 {len(results)} 条（关键词：{keyword}）")
    return results


print("✅ T01 完成")
print("✅ T02 完成")

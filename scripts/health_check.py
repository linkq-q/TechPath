#!/usr/bin/env python3
# 文件用途：TechPath 安装健康检查脚本，验证环境配置和核心依赖是否就绪

import sys
import os

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent.parent
PASS = "✅"
FAIL = "❌"

results = []


def check(label: str, ok: bool, detail: str = "") -> None:
    status = PASS if ok else FAIL
    msg = f"{status} {label}"
    if detail:
        msg += f"  →  {detail}"
    print(msg)
    results.append(ok)


# ---- 1. .env 文件 ----
env_file = ROOT / ".env"
check(".env 文件存在", env_file.exists(), str(env_file) if not env_file.exists() else "")

# ---- 2. 必要 API Key ----
deepseek_key = os.getenv("DEEPSEEK_API_KEY", "")
github_token = os.getenv("GITHUB_TOKEN", "")
check("DEEPSEEK_API_KEY 已配置", bool(deepseek_key), "请在 .env 中设置" if not deepseek_key else "")
check("GITHUB_TOKEN 已配置", bool(github_token), "请在 .env 中设置" if not github_token else "")

# ---- 3. 数据库文件与表结构 ----
try:
    from core.database import init_db, get_all_knowledge_items
    init_db()
    get_all_knowledge_items()
    check("数据库初始化正常", True)
except Exception as e:
    check("数据库初始化正常", False, str(e))

# ---- 4. skills/ 目录和预置技能包 ----
skills_dir = ROOT / "skills"
skill_files = list(skills_dir.glob("*.skill.md")) if skills_dir.exists() else []
check(f"skills/ 目录存在且有技能包文件（{len(skill_files)} 个）",
      len(skill_files) >= 4,
      f"找到 {len(skill_files)} 个，期望 ≥ 4" if len(skill_files) < 4 else "")

expected_skills = ["ai_ta_core.skill.md", "mihoyo_style.skill.md",
                   "bilibili_grading.skill.md", "nowcoder_interview.skill.md"]
for sf in expected_skills:
    check(f"  技能文件 {sf}", (skills_dir / sf).exists())

# ---- 5. core/ 模块 import ----
modules_to_check = [
    ("core.database", "数据库模块"),
    ("core.history", "历史记录模块"),
    ("core.knowledge_graph", "知识图谱模块"),
    ("core.skills_manager", "技能包管理模块"),
    ("core.cost_tracker", "费用追踪模块"),
    ("core.intel", "情报分析模块"),
    ("core.study", "学习中心模块"),
    ("core.agent", "Agent 模块"),
]
for mod, label in modules_to_check:
    try:
        __import__(mod)
        check(f"{label} import 正常", True)
    except Exception as e:
        check(f"{label} import 正常", False, str(e)[:80])

# ---- 6. 第三方库检查 ----
required_libs = [
    ("streamlit", "Streamlit"),
    ("openai", "OpenAI SDK"),
    ("sqlalchemy", "SQLAlchemy"),
    ("networkx", "NetworkX（知识网络）"),
    ("yaml", "PyYAML"),
    ("mem0", "Mem0（记忆系统）"),
]
optional_libs = [
    ("pyvis", "PyVis（知识图谱可视化）"),
    ("DrissionPage", "DrissionPage（爬虫）"),
]

for lib, label in required_libs:
    try:
        __import__(lib)
        check(f"必须库 {label}", True)
    except ImportError:
        check(f"必须库 {label}", False, f"请运行: pip install {lib}")

for lib, label in optional_libs:
    try:
        __import__(lib)
        print(f"✅ 可选库 {label}")
    except ImportError:
        print(f"⏭️  可选库 {label}  →  未安装（pip install {lib}），对应功能降级")

# ---- 7. DeepSeek API 连通性测试 ----
if deepseek_key:
    try:
        from openai import OpenAI
        client = OpenAI(api_key=deepseek_key, base_url="https://api.deepseek.com")
        resp = client.chat.completions.create(
            model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
            messages=[{"role": "user", "content": "ping"}],
            max_tokens=5,
        )
        check("DeepSeek API 连通性", True, f"模型：{resp.model}")
    except Exception as e:
        check("DeepSeek API 连通性", False, str(e)[:100])
else:
    print(f"⏭️  DeepSeek API 连通性  →  跳过（未配置 Key）")

# ---- 汇总 ----
print()
passed = sum(1 for r in results if r)
total = len(results)
print(f"{'=' * 50}")
if passed == total:
    print(f"✅ 全部通过（{passed}/{total}），可以启动应用：streamlit run app.py")
else:
    print(f"⚠️  {passed}/{total} 项通过，请修复上面标 ❌ 的项目后重试")
print(f"{'=' * 50}")

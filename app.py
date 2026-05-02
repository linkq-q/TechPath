# 文件用途：Streamlit 主入口，负责导航和页面路由

import os

import streamlit as st
from dotenv import load_dotenv

from core.database import init_db

load_dotenv()

# ---- 页面配置 ----
st.set_page_config(
    page_title="TechPath",
    page_icon="🎯",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- 自定义样式（深色科技风）----
st.markdown(
    """
    <style>
    /* 主背景 */
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    /* 侧边栏 */
    [data-testid="stSidebar"] { background-color: #161b22; }
    /* 标题 */
    h1, h2, h3 { color: #58a6ff; }
    /* 按钮 */
    .stButton > button {
        background-color: #21262d;
        color: #c9d1d9;
        border: 1px solid #30363d;
        border-radius: 6px;
    }
    .stButton > button:hover {
        background-color: #30363d;
        border-color: #58a6ff;
        color: #58a6ff;
    }
    /* 输入框 */
    .stTextInput > div > div > input,
    .stTextArea > div > div > textarea {
        background-color: #161b22;
        color: #c9d1d9;
        border-color: #30363d;
    }
    /* 成功/信息提示 */
    .stSuccess { background-color: #1a3a1a; }
    .stInfo { background-color: #1a2a3a; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---- 初始化数据库 ----
try:
    init_db()
except Exception as _e:
    st.error(f"数据库初始化失败：{_e}，请检查 data/ 目录权限")

# ---- API Key 配置检查 ----
_REQUIRED_KEYS = {
    "DEEPSEEK_API_KEY": "DeepSeek（检验/讲解/情报分析）",
    "GITHUB_TOKEN": "GitHub（项目解读）",
}
_OPTIONAL_KEYS = {
    "QWEN_API_KEY": "阿里云百炼 Qwen（B站视觉分析，可选）",
}
_missing = [f"`{k}` → {desc}" for k, desc in _REQUIRED_KEYS.items() if not os.getenv(k)]
if _missing:
    st.warning(
        "⚠️ **以下必填 API Key 未配置，相关功能将无法使用：**\n\n" +
        "\n".join(f"- {m}" for m in _missing) +
        "\n\n请在项目根目录创建 `.env` 文件并填写对应 Key。"
    )

# ---- Session State 初始化 ----
if "current_page" not in st.session_state:
    st.session_state.current_page = "knowledge"

# ---- 侧边栏导航 ----
with st.sidebar:
    st.markdown("## TechPath")
    st.markdown("AI TA 求职者的学习检验工具")
    st.markdown("---")

    if st.button("📚 知识库", use_container_width=True):
        st.session_state.current_page = "knowledge"

    if st.button("🎯 开始检验", use_container_width=True):
        st.session_state.current_page = "exam"

    if st.button("🔍 岗位情报", use_container_width=True):
        st.session_state.current_page = "intel"

    if st.button("📖 学习中心", use_container_width=True):
        st.session_state.current_page = "study"

    if st.button("🏆 竞品监测", use_container_width=True):
        st.session_state.current_page = "portfolio"

    if st.button("🎯 背景匹配", use_container_width=True):
        st.session_state.current_page = "bg_match"

    if st.button("📈 职业路径", use_container_width=True):
        st.session_state.current_page = "career_path"

    st.markdown("---")

    if st.button("📚 学习历史", use_container_width=True):
        st.session_state.current_page = "history"

    if st.button("🕸️ 知识网络", use_container_width=True):
        st.session_state.current_page = "knowledge_network"

    if st.button("⚡ 技能包", use_container_width=True):
        st.session_state.current_page = "skills"

    st.markdown("---")

    # ---- API 费用统计 ----
    try:
        from core.cost_tracker import get_cost_summary
        _cost = get_cost_summary()
        st.markdown(
            f"<small style='color:#8b949e'>"
            f"今日费用：¥{_cost['today_cost_yuan']:.4f}<br>"
            f"累计费用：¥{_cost['total_cost_yuan']:.4f}</small>",
            unsafe_allow_html=True,
        )
        with st.expander("💰 费用详情", expanded=False):
            st.markdown(f"**今日调用**：{_cost['today_calls']} 次")
            st.markdown(f"**今日 Tokens**：输入 {_cost['today_input_tokens']:,} / 输出 {_cost['today_output_tokens']:,}")
            st.markdown("---")
            st.markdown(f"**累计调用**：{_cost['total_calls']} 次")
            st.markdown(f"**累计 Tokens**：输入 {_cost['total_input_tokens']:,} / 输出 {_cost['total_output_tokens']:,}")
            if _cost.get("by_purpose"):
                st.markdown("**按功能分类：**")
                for p, s in sorted(_cost["by_purpose"].items(), key=lambda x: x[1]["cost_yuan"], reverse=True):
                    st.markdown(
                        f"- {s['label']}：{s['calls']} 次，¥{s['cost_yuan']:.4f}"
                    )
    except Exception:
        pass

    st.markdown(
        "<small style='color:#8b949e'>基于 DeepSeek + LangChain<br>数据本地存储</small>",
        unsafe_allow_html=True,
    )

    with st.expander("重启项目？"):
        st.markdown("如果页面连接断开，在 PowerShell 中执行以下命令重启：")
        st.code(
            "cd C:\\Projects\\techpath\\TechPath\n"
            "..\\venv\\Scripts\\activate\n"
            "streamlit run app.py",
            language="powershell",
        )
        st.markdown("或直接双击项目根目录的 `start_techpath.bat`")

# ---- 页面路由 ----
if st.session_state.current_page == "knowledge":
    from pages.knowledge import render
    render()
elif st.session_state.current_page == "exam":
    from pages.exam import render
    render()
elif st.session_state.current_page == "intel":
    from pages.intel import render
    render()
elif st.session_state.current_page == "study":
    from pages.study import render
    render()
elif st.session_state.current_page == "portfolio":
    from pages.portfolio import render
    render()
elif st.session_state.current_page == "history":
    from pages.history import render
    render()
elif st.session_state.current_page == "knowledge_network":
    from pages.knowledge_network import render
    render()
elif st.session_state.current_page == "skills":
    from pages.skills import render
    render()
elif st.session_state.current_page == "bg_match":
    from pages.bg_match import render
    render()
elif st.session_state.current_page == "career_path":
    from pages.career_path import render
    render()
else:
    from pages.knowledge import render
    render()

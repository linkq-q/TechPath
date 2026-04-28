# 文件用途：Streamlit 主入口，负责导航和页面路由

import streamlit as st

from core.database import init_db

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
init_db()

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

    st.markdown("---")
    st.markdown(
        "<small style='color:#8b949e'>基于 DeepSeek + LangChain<br>数据本地存储</small>",
        unsafe_allow_html=True,
    )

# ---- 页面路由 ----
if st.session_state.current_page == "knowledge":
    from pages.knowledge import render
    render()
elif st.session_state.current_page == "exam":
    from pages.exam import render
    render()
else:
    from pages.intel import render
    render()

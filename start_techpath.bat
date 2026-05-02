@echo off
echo 正在启动 TechPath...
cd /d C:\Projects\techpath\TechPath
call ..\venv\Scripts\activate
echo 虚拟环境已激活
echo 正在启动 Streamlit，请稍候...
streamlit run app.py
pause

TechPath 启动说明
==================

方法一（推荐，支持视觉分析）：
在 PowerShell 里执行：
C:\Projects\techpath\start_techpath.ps1

或者直接在 PowerShell 里输入：
cd C:\Projects\techpath\TechPath
..\venv\Scripts\activate
streamlit run app.py

方法二（不需要视觉分析时）：
双击 start_techpath.bat

访问地址：http://localhost:8501

注意：PowerShell 方式支持 ffmpeg（B站视觉分析），CMD 方式不支持。

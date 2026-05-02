Write-Host "正在启动 TechPath..." -ForegroundColor Cyan
Set-Location "C:\Projects\techpath\TechPath"
& "..\venv\Scripts\Activate.ps1"
Write-Host "虚拟环境已激活" -ForegroundColor Green
Write-Host "正在启动 Streamlit，请稍候..." -ForegroundColor Yellow
streamlit run app.py

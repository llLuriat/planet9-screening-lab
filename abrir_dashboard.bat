@echo off
rem ============================================================
rem  Planet9 Screening Lab - Dashboard (interface grafica)
rem  Abre em: http://127.0.0.1:8765 (somente localhost)
rem  Para PARAR: feche ESTA janela (ou Ctrl+C nela).
rem ============================================================
title Planet9 Dashboard - http://127.0.0.1:8765
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo [ERRO] .venv nao encontrada em "%~dp0".
    echo Rode os passos 2 e 3 do SETUP_DO_ZERO.md antes de abrir o dashboard.
    pause
    exit /b 1
)
echo Preparando o dashboard... o navegador abre sozinho em alguns segundos.
echo Se a pagina abrir antes do servidor, basta atualizar (F5).
echo Para PARAR: feche esta janela (ou Ctrl+C nela). Nada em runs\ e afetado.
start "abrir-navegador" /min cmd /c "timeout /t 12 /nobreak >nul & start http://127.0.0.1:8765"
".venv\Scripts\python.exe" -m dashboard
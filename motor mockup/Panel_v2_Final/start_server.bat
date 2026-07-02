@echo off
title Motor de Anidamiento — FastAPI
color 0A
echo.
echo  ============================================
echo   NESTING INDUSTRIAL - Motor de Optimizacion
echo  ============================================
echo.
echo  Iniciando servidor en http://127.0.0.1:8765
echo  (Mantener esta ventana abierta mientras usas el panel)
echo.

cd /d "%~dp0.."
python -m uvicorn engine.main:app --host 127.0.0.1 --port 8765 --reload

echo.
echo  Servidor detenido.
pause

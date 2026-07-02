@echo off
setlocal
title Instalador — Nesting Industrial CEP Panel
color 0B
echo.
echo  ============================================================
echo   INSTALADOR: Nesting Industrial CEP Panel
echo   Compatible con Adobe Illustrator 2020 al 2026+
echo  ============================================================
echo.

REM ── 1. Activar PlayerDebugMode en todas las versiones de CSXS ──
echo  [1/3] Activando modo desarrollo CEP...
reg add "HKCU\SOFTWARE\Adobe\CSXS.9"  /v PlayerDebugMode /t REG_SZ /d 1 /f >nul 2>&1
reg add "HKCU\SOFTWARE\Adobe\CSXS.10" /v PlayerDebugMode /t REG_SZ /d 1 /f >nul 2>&1
reg add "HKCU\SOFTWARE\Adobe\CSXS.11" /v PlayerDebugMode /t REG_SZ /d 1 /f >nul 2>&1
reg add "HKCU\SOFTWARE\Adobe\CSXS.12" /v PlayerDebugMode /t REG_SZ /d 1 /f >nul 2>&1
echo  OK: PlayerDebugMode activado (CSXS 9-12)

REM ── 2. Crear directorio de extensiones CEP ──
echo.
echo  [2/3] Copiando panel al directorio de extensiones...
set "DEST=%APPDATA%\Adobe\CEP\extensions\com.turboprint.nesting"

if exist "%DEST%" (
    echo  Eliminando version anterior...
    rmdir /s /q "%DEST%"
)

mkdir "%DEST%"

REM Copiar todos los archivos del panel
set "SRC=%~dp0"
xcopy "%SRC%*" "%DEST%\" /E /I /Q /Y

echo  OK: Panel copiado a %DEST%

REM ── 3. Verificación ──
echo.
echo  [3/3] Verificando instalacion...
if exist "%DEST%\CSXS\manifest.xml" (
    echo  OK: manifest.xml encontrado
) else (
    echo  ERROR: manifest.xml no encontrado en %DEST%\CSXS\
    echo  Asegurate de ejecutar este bat desde la carpeta "panel\"
    pause
    exit /b 1
)

if exist "%DEST%\host.jsx" (
    echo  OK: host.jsx encontrado
) else (
    echo  ERROR: host.jsx no encontrado
    pause
    exit /b 1
)

if exist "%DEST%\CSInterface.js" (
    echo  OK: CSInterface.js encontrado
) else (
    echo  ERROR: CSInterface.js no encontrado
    pause
    exit /b 1
)

echo.
echo  ============================================================
echo   INSTALACION COMPLETADA
echo  ============================================================
echo.
echo  PROXIMOS PASOS:
echo  1. Reinicia Adobe Illustrator
echo  2. Ve a: Ventana ^> Extensiones ^> Nesting Industrial
echo  3. Ejecuta "start_server.bat" para iniciar el motor
echo.
pause

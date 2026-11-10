@echo off
chcp 65001 >nul
title Descarga Automatica de Imagenes Satelitales Sentinel-2 (GeoTIFF)
color 0A

echo ==============================================================================
echo   DESCARGADOR SATELITAL AUTOMATICO DE UN CLIC - COPERNICUS SENTINEL-2 L2A
echo   Centroide: 8.899050, -79.766716  ^|  Radio: 5 km
echo   Años: 2016, 2021, 2022, 2023, 2024, 2025
echo   Indices: NDVI, NDBI, MNDWI y RGB (Color Natural) a 10m de resolucion
echo ==============================================================================
echo.

cd /d "%~dp0"

echo [1/2] Verificando entorno de ejecucion de Python...
py -3 --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python detectado via lanzador 'py'. Iniciando descarga...
    echo.
    py scripts\descargar_tiffs_satelitales.py
    goto FIN
)

"C:\Program Files\Python313\python.exe" --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python 3.13 detectado en Program Files. Iniciando descarga...
    echo.
    "C:\Program Files\Python313\python.exe" scripts\descargar_tiffs_satelitales.py
    goto FIN
)

python --version >nul 2>&1
if %errorlevel% equ 0 (
    echo [OK] Python detectado en PATH. Iniciando descarga...
    echo.
    python scripts\descargar_tiffs_satelitales.py
    goto FIN
)

echo [ERROR] No se pudo encontrar un ejecutable de Python valido en el sistema.
pause
exit /b 1

:FIN
echo.
echo ==============================================================================
echo   Proceso finalizado. Los archivos se encuentran en la carpeta:
echo   %~dp0resultados_tiff
echo ==============================================================================
echo.
pause

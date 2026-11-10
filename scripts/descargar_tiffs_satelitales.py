#!/usr/bin/env python3
"""
Descargador automatizado de imágenes satelitales GeoTIFF y cálculo de índices espectrales
Autor: Andres Barrionuevo
Objetivo:
  - Centroide: Lat 8.899050, Lon -79.766716
  - Radio de cobertura: 5 km (área total ~78.5 km²)
  - Años: 2016, 2021, 2022, 2023, 2024, 2025
  - Calidad: Máxima resolución nativa (10 m / pixel) de Copernicus Sentinel-2 L2A
  - Índices calculados: NDVI, NDBI, MNDWI y composición RGB en color natural
  - Destino: Carpeta 'resultados_tiff/'
"""
from __future__ import annotations

import json
import math
import sys
import time
from pathlib import Path

try:
    import numpy as np
    import rasterio
    from rasterio.enums import Resampling
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds
    import requests
except ImportError as err:
    print(f"[ERROR] Falta una librería requerida: {err}", file=sys.stderr)
    print("Ejecuta: pip install rasterio numpy requests", file=sys.stderr)
    sys.exit(1)


# Configuración del Centroide y Parámetros
CENTROIDE_LAT = 8.899050
CENTROIDE_LON = -79.766716
RADIO_KM = 5.0
ANOS_OBJETIVO = [2016, 2021, 2022, 2023, 2024, 2025]

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "resultados_tiff"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def calcular_bbox(lat: float, lon: float, radio_km: float) -> list[float]:
    """Calcula el Bounding Box [min_lon, min_lat, max_lon, max_lat] para un radio en km."""
    delta_lat = radio_km / 111.139
    delta_lon = radio_km / (111.139 * math.cos(math.radians(lat)))
    return [
        round(lon - delta_lon, 6),
        round(lat - delta_lat, 6),
        round(lon + delta_lon, 6),
        round(lat + delta_lat, 6),
    ]


def obtener_token_mpc() -> str:
    """Obtiene token SAS para acceso directo a los Cloud-Optimized GeoTIFFs de Microsoft Planetary Computer."""
    try:
        r = requests.get("https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel-2-l2a", timeout=15)
        if r.status_code == 200:
            return r.json().get("token", "")
    except Exception as exc:
        print(f"[AVISO] No se pudo obtener token SAS directo: {exc}")
    return ""


def buscar_mejor_escena(year: int, bbox: list[float]) -> dict | None:
    """Busca la escena Sentinel-2 L2A con la menor nubosidad para el año dado."""
    stac_url = "https://planetarycomputer.microsoft.com/api/stac/v1/search"
    # Temporada seca y despejada en la región de Panamá suele darse entre diciembre y abril
    # Buscamos en todo el año para garantizar la escena con menor nubosidad absoluta
    payload = {
        "collections": ["sentinel-2-l2a"],
        "bbox": bbox,
        "datetime": f"{year}-01-01T00:00:00Z/{year}-12-31T23:59:59Z",
        "query": {"eo:cloud_cover": {"lt": 40}},
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
        "limit": 5,
    }

    try:
        r = requests.post(stac_url, json=payload, timeout=20)
        if r.status_code == 200:
            feats = r.json().get("features", [])
            if feats:
                return feats[0]
    except Exception as exc:
        print(f"[{year}] Error en consulta STAC: {exc}")

    # Reintento con umbral más permisivo si el año fue particularmente nublado
    payload["query"] = {"eo:cloud_cover": {"lt": 75}}
    try:
        r = requests.post(stac_url, json=payload, timeout=20)
        feats = r.json().get("features", [])
        return feats[0] if feats else None
    except Exception:
        return None


def calcular_indice_seguro(banda_a: np.ndarray, banda_b: np.ndarray) -> np.ndarray:
    """Calcula (A - B) / (A + B) de forma numéricamente estable sin divisiones por cero."""
    a = banda_a.astype(np.float32)
    b = banda_b.astype(np.float32)
    denom = a + b
    num = a - b
    res = np.zeros_like(a, dtype=np.float32)
    mask = denom != 0
    res[mask] = num[mask] / denom[mask]
    # Limitar rango matemático [-1, 1]
    return np.clip(res, -1.0, 1.0)


def procesar_ano(year: int, bbox: list[float], token: str) -> dict | None:
    """Descarga las bandas de la ventana geográfica y computa los índices en GeoTIFF."""
    print(f"\n========================================================")
    print(f"[*] Buscando la mejor escena satelital para el año {year}...")
    
    scene = buscar_mejor_escena(year, bbox)
    if not scene:
        print(f"[!] No se encontró ninguna escena satelital válida para el año {year}.")
        return None

    scene_id = scene["id"]
    fecha_adquisicion = scene["properties"]["datetime"]
    nubosidad = scene["properties"].get("eo:cloud_cover", 0.0)
    assets = scene["assets"]

    print(f"[+] Escena seleccionada: {scene_id}")
    print(f"    Fecha: {fecha_adquisicion[:10]} | Nubosidad en escena: {nubosidad:.2f}%")

    auth_param = f"?{token}" if token else ""

    # Enlaces de bandas en resolución 10m y 20m
    url_b04 = assets["B04"]["href"] + auth_param  # Rojo (10m)
    url_b08 = assets["B08"]["href"] + auth_param  # Infrarrojo Cercano (NIR, 10m)
    url_b03 = assets["B03"]["href"] + auth_param  # Verde (10m)
    url_b02 = assets["B02"]["href"] + auth_param  # Azul (10m)
    url_b11 = assets["B11"]["href"] + auth_param  # Infrarrojo Onda Corta (SWIR, 20m)
    has_visual = "visual" in assets
    url_visual = (assets["visual"]["href"] + auth_param) if has_visual else None

    print(f"[*] Extrayendo recorte espacial de 5 km en alta resolución (10m/pixel)...")

    # 1. Leer Banda 4 (Rojo) y determinar ventana espacial
    with rasterio.open(url_b04) as src_ref:
        crs = src_ref.crs
        left, bottom, right, top = transform_bounds("EPSG:4326", crs, bbox[0], bbox[1], bbox[2], bbox[3])
        win_10m = from_bounds(left, bottom, right, top, src_ref.transform)
        win_10m = win_10m.round_offsets().round_shape()
        
        b04 = src_ref.read(1, window=win_10m)
        out_shape = b04.shape
        out_transform = src_ref.window_transform(win_10m)
        height, width = out_shape

    # 2. Leer Banda 8 (NIR - 10m)
    with rasterio.open(url_b08) as src:
        b08 = src.read(1, window=win_10m, out_shape=out_shape)

    # 3. Leer Banda 3 (Verde - 10m)
    with rasterio.open(url_b03) as src:
        b03 = src.read(1, window=win_10m, out_shape=out_shape)

    # 4. Leer Banda 2 (Azul - 10m)
    with rasterio.open(url_b02) as src:
        b02 = src.read(1, window=win_10m, out_shape=out_shape)

    # 5. Leer Banda 11 (SWIR - 20m) reescalada bilinealmente a 10m
    with rasterio.open(url_b11) as src:
        win_20m = from_bounds(left, bottom, right, top, src.transform)
        b11 = src.read(1, window=win_20m, out_shape=out_shape, resampling=Resampling.bilinear)

    print(f"    Recorte leído con éxito: {width}x{height} píxeles (Resolución nativa 10 metros).")

    # 6. Cálculo de Índices Espectrales
    print(f"[*] Calculando índices espectrales:")
    print(f"    - NDVI (Vegetación y Áreas Verdes) = (B08 - B04) / (B08 + B04)")
    ndvi = calcular_indice_seguro(b08, b04)

    print(f"    - NDBI (Edificación y Expansión Urbana) = (B11 - B08) / (B11 + B08)")
    ndbi = calcular_indice_seguro(b11, b08)

    print(f"    - MNDWI (Cuerpos de Agua e Inundación) = (B03 - B11) / (B03 + B11)")
    mndwi = calcular_indice_seguro(b03, b11)

    # 7. Escritura de GeoTIFFs
    meta_float = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": out_transform,
        "compress": "lzw",
        "nodata": -9999.0,
    }

    # Guardar NDVI
    path_ndvi = OUT_DIR / f"sentinel2_{year}_NDVI.tif"
    with rasterio.open(path_ndvi, "w", **meta_float) as dst:
        dst.write(ndvi, 1)
        dst.set_band_description(1, f"NDVI Sentinel-2 {year}")
    print(f"    -> Guardado: {path_ndvi.name}")

    # Guardar NDBI
    path_ndbi = OUT_DIR / f"sentinel2_{year}_NDBI.tif"
    with rasterio.open(path_ndbi, "w", **meta_float) as dst:
        dst.write(ndbi, 1)
        dst.set_band_description(1, f"NDBI Sentinel-2 {year}")
    print(f"    -> Guardado: {path_ndbi.name}")

    # Guardar MNDWI
    path_mndwi = OUT_DIR / f"sentinel2_{year}_MNDWI.tif"
    with rasterio.open(path_mndwi, "w", **meta_float) as dst:
        dst.write(mndwi, 1)
        dst.set_band_description(1, f"MNDWI Sentinel-2 {year}")
    print(f"    -> Guardado: {path_mndwi.name}")

    # Guardar GeoTIFF Multibanda (NDVI, NDBI, MNDWI)
    meta_multi = meta_float.copy()
    meta_multi["count"] = 3
    path_multi = OUT_DIR / f"sentinel2_{year}_INDICES_MULTIBANDA.tif"
    with rasterio.open(path_multi, "w", **meta_multi) as dst:
        dst.write(ndvi, 1)
        dst.set_band_description(1, "NDVI (Vegetacion)")
        dst.write(ndbi, 2)
        dst.set_band_description(2, "NDBI (Edificacion/Urbano)")
        dst.write(mndwi, 3)
        dst.set_band_description(3, "MNDWI (Agua)")
    print(f"    -> Guardado: {path_multi.name}")

    # Guardar Imagen RGB Color Natural
    path_rgb = OUT_DIR / f"sentinel2_{year}_RGB_COLOR_NATURAL.tif"
    if url_visual:
        try:
            with rasterio.open(url_visual) as src:
                win_vis = from_bounds(left, bottom, right, top, src.transform)
                rgb = src.read([1, 2, 3], window=win_vis, out_shape=(3, height, width))
                meta_rgb = {
                    "driver": "GTiff",
                    "height": height,
                    "width": width,
                    "count": 3,
                    "dtype": "uint8",
                    "crs": crs,
                    "transform": out_transform,
                    "compress": "lzw",
                }
                with rasterio.open(path_rgb, "w", **meta_rgb) as dst:
                    dst.write(rgb)
                    dst.set_band_description(1, "Rojo (Red)")
                    dst.set_band_description(2, "Verde (Green)")
                    dst.set_band_description(3, "Azul (Blue)")
            print(f"    -> Guardado: {path_rgb.name}")
        except Exception as e_rgb:
            print(f"    [!] No se pudo descargar visual RGB directo: {e_rgb}")

    return {
        "year": year,
        "scene_id": scene_id,
        "date": fecha_adquisicion,
        "cloud_cover_percent": nubosidad,
        "pixels_width": width,
        "pixels_height": height,
        "resolution_meters": 10.0,
        "crs": str(crs),
        "files": [
            path_ndvi.name,
            path_ndbi.name,
            path_mndwi.name,
            path_multi.name,
            path_rgb.name if path_rgb.exists() else None,
        ],
    }


def main():
    print("==========================================================================")
    print("  DESCARGA AUTOMÁTICA DE IMÁGENES SATELITALES Y CÁLCULO DE ÍNDICES GEOTIFF")
    print("  Copernicus Sentinel-2 L2A (10 metros de resolución espacial)")
    print("==========================================================================")
    print(f"Centroide: Latitud {CENTROIDE_LAT}, Longitud {CENTROIDE_LON}")
    print(f"Radio de análisis: {RADIO_KM} km")
    print(f"Años a procesar: {ANOS_OBJETIVO}")
    print(f"Directorio de salida: {OUT_DIR.resolve()}\n")

    bbox = calcular_bbox(CENTROIDE_LAT, CENTROIDE_LON, RADIO_KM)
    print(f"Bounding Box calculado (WGS84): {bbox}")

    print("[*] Obteniendo credenciales de acceso satelital...")
    token = obtener_token_mpc()

    resumen = []
    t_inicio = time.time()

    for year in ANOS_OBJETIVO:
        info = procesar_ano(year, bbox, token)
        if info:
            resumen.append(info)

    # Guardar reporte JSON de trazabilidad
    reporte_path = OUT_DIR / "informe_descargas.json"
    with open(reporte_path, "w", encoding="utf-8") as f:
        json.dump(
            {
                "generado_el": time.strftime("%Y-%m-%d %H:%M:%S"),
                "centroide": {"lat": CENTROIDE_LAT, "lon": CENTROIDE_LON},
                "radio_km": RADIO_KM,
                "bbox_wgs84": bbox,
                "total_anos_procesados": len(resumen),
                "resultados": resumen,
            },
            f,
            indent=2,
            ensure_ascii=False,
        )

    t_total = time.time() - t_inicio
    print("\n==========================================================================")
    print(f"[OK] PROCESO COMPLETADO EXITOSAMENTE en {t_total:.1f} segundos.")
    print(f"[OK] Archivos GeoTIFF generados en: {OUT_DIR.resolve()}")
    print(f"[OK] Informe de trazabilidad guardado en: {reporte_path.name}")
    print("==========================================================================")


if __name__ == "__main__":
    main()

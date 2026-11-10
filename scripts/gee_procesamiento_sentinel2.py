#!/usr/bin/env python3
"""
Script reproducible de procesamiento en Google Earth Engine (GEE)
Iniciativa: urbano-gt-salud-metropolitana (Región Metropolitana de Guatemala)
Autor: Andres Barrionuevo

Parámetros metodológicos verificados:
  - Colección: Sentinel-2 L2A Harmonized (COPERNICUS/S2_SR_HARMONIZED)
  - Umbral máximo de nubosidad: 20%
  - Enmascaramiento SCL: Clases 4 (Vegetación), 5 (Suelo no vegetado) y 6 (Agua)
  - Región de interés (ROI): Región metropolitana de Guatemala (Área ~2,253 km²)
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def get_ee_session(project_id: str | None = None):
    """Inicializa la sesión de Google Earth Engine con autenticación segura."""
    try:
        import ee
    except ImportError:
        print("[ERROR] earthengine-api no está instalado. Ejecuta: pip install earthengine-api", file=sys.stderr)
        sys.exit(1)

    try:
        if project_id:
            ee.Initialize(project=project_id)
        else:
            ee.Initialize()
        print("[OK] Sesión de Google Earth Engine inicializada correctamente.")
        return ee
    except Exception as exc:
        print(f"[AVISO] Requiere autenticación previa: {exc}")
        print("Iniciando flujo interactivo de autenticación...")
        try:
            ee.Authenticate()
            if project_id:
                ee.Initialize(project=project_id)
            else:
                ee.Initialize()
            print("[OK] Autenticación completada con éxito.")
            return ee
        except Exception as auth_err:
            print(f"[ERROR] No se pudo autenticar en Google Earth Engine: {auth_err}", file=sys.stderr)
            sys.exit(1)


def mask_scl_sentinel2(image, ee):
    """Aplica enmascaramiento por Scene Classification Layer (SCL).
    
    Conserva únicamente:
      - Clase 4: Vegetación
      - Clase 5: Suelo desnudo / no vegetado
      - Clase 6: Agua
    Enmascara sombras de nubes (3), nubes medias/altas (8, 9), cirros (10) y defectos.
    """
    scl = image.select("SCL")
    valid_mask = scl.eq(4).Or(scl.eq(5)).Or(scl.eq(6))
    return image.updateMask(valid_mask).divide(10000).copyProperties(image, ["system:time_start"])


def build_analysis_pipeline(
    ee,
    start_date: str = "2026-01-01",
    end_date: str = "2026-11-10",
    cloud_threshold: float = 20.0,
):
    """Construye el pipeline de procesamiento multiespectral para la Región Metropolitana."""
    # Coordenadas declaradas: 14°37'16.48"N 90°20'51.03"W -> 14.621244, -90.347508
    centroide_lon = -90.347508
    centroide_lat = 14.621244
    punto_central = ee.Geometry.Point([centroide_lon, centroide_lat])

    # Área aproximada de 2,253 km² -> radio buffer aprox. 26,800 metros
    roi = punto_central.buffer(26800).bounds()

    # Colección Sentinel-2 L2A Armonizada
    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filterDate(start_date, end_date)
        .filter(ee.Filter.lte("CLOUDY_PIXEL_PERCENTAGE", cloud_threshold))
        .map(lambda img: mask_scl_sentinel2(img, ee))
    )

    # Composición de mediana temporal (libre de nubes)
    composite = collection.median().clip(roi)

    # Índice de Vegetación de Diferencia Normalizada (NDVI) -> Exposición a espacios verdes
    ndvi = composite.normalizedDifference(["B8", "B4"]).rename("NDVI")

    # Índice de Edificación de Diferencia Normalizada (NDBI) -> Expansión urbana y calor
    ndbi = composite.normalizedDifference(["B11", "B8"]).rename("NDBI")

    # Índice de Agua Modificado (MNDWI) -> Cuerpos de agua y zonas propensas a inundación
    mndwi = composite.normalizedDifference(["B3", "B11"]).rename("MNDWI")

    # Imagen multidimensional con índices integrados
    resultado = composite.addBands([ndvi, ndbi, mndwi])

    return {
        "roi": roi,
        "image": resultado,
        "collection_count": collection.size(),
        "centroide": [centroide_lon, centroide_lat],
    }


def main():
    parser = argparse.ArgumentParser(
        description="Pipeline Google Earth Engine - Prevención de Riesgos de Salud (Región Metropolitana Guatemala)"
    )
    parser.add_argument("--project", type=str, default=None, help="ID del proyecto de Google Cloud con Earth Engine habilitado")
    parser.add_argument("--start-date", type=str, default="2026-01-01", help="Fecha inicial (YYYY-MM-DD)")
    parser.add_argument("--end-date", type=str, default="2026-11-10", help="Fecha final (YYYY-MM-DD)")
    parser.add_argument("--cloud-threshold", type=float, default=20.0, help="Umbral máximo de nubosidad (porcentaje)")
    parser.add_argument("--check-only", action="store_true", help="Verifica la conexión sin exportar datos")

    args = parser.parse_args()

    ee = get_ee_session(args.project)
    pipeline = build_analysis_pipeline(
        ee,
        start_date=args.start_date,
        end_date=args.end_date,
        cloud_threshold=args.cloud_threshold,
    )

    conteo = pipeline["collection_count"].getInfo()
    print(f"[OK] Imágenes Sentinel-2 L2A encontradas con nubosidad <= {args.cloud_threshold}%: {conteo}")
    print(f"[OK] Centroide de análisis: Lat {pipeline['centroide'][1]}, Lon {pipeline['centroide'][0]}")
    print("[OK] Bandas generadas: B4, B3, B2, B8, B11, NDVI, NDBI, MNDWI con enmascaramiento SCL.")


if __name__ == "__main__":
    main()

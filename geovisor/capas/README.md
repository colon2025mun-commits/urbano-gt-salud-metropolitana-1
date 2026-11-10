# Carpeta de capas para el Geovisor (`geovisor/capas/`)

Sube en esta carpeta los archivos geoespaciales generados por el equipo para que aparezcan automáticamente en la opción **«Cargar desde carpeta»** (`Carpeta repo`) del Geovisor de la iniciativa.

## Formatos compatibles con GeoLibre soportados

- **Vectoriales directos en el visor integrado y en GeoLibre:**
  - `.geojson` / `.json` (recomendado en `EPSG:4326` / WGS84 para capas ligeras e indicadores agregados).
  - `.kml` (convertido automáticamente en el navegador).
- **Proyectos completos de GeoLibre:**
  - `.geolibre.json` (configuración completa de fuentes, estilos y cámara para GeoLibre Web).
- **Formatos cloud-native para GeoLibre Studio (`web.geolibre.app`):**
  - `.pmtiles` (teselas vectoriales o ráster optimizadas para la nube).
  - `.fgb` (FlatGeobuf).
  - `.tif` / `.tiff` (Cloud-Optimized GeoTIFF — COG).
  - `.parquet` / `.geoparquet`.

## Reglas antes de subir una capa

1. Verifica que esté proyectada en **`EPSG:4326` (WGS84)** y con geometrías válidas.
2. **No subas datos personales, contactos ni catastros prediales restringidos**; publica únicamente agregaciones o capas con autorización institucional.
3. Si el archivo supera los límites razonables de GitHub (~25–50 MB), alójalo en un servidor OGC / bucket con CORS habilitado y regístralo por URL `https://` en `geovisor/layers.json`.

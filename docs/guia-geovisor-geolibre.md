# Guía del Geovisor basado en GeoLibre (`gt-salud-metropolitana`)

Cada sitio de iniciativa incluye en `/aplicacion/` un geovisor interactivo diseñado sobre dos niveles complementarios:

1. **Motor integrado MapLibre GL JS:** Funciona de inmediato en desarrollo local (`http://localhost:8000`), en vistas previas de forks y en GitHub Pages, leyendo `geovisor/layers.json`. Incluye selector de mapas base libres, control de opacidad, inspección de atributos y un **cargador temporal de archivos `.geojson` locales** en el navegador.
2. **Proyecto compatible con GeoLibre (`geovisor/proyecto.geolibre.json`):** Generado automáticamente por `scripts/build_site.py`. Cuando el sitio está publicado bajo HTTPS en GitHub Pages (con soporte CORS), puede incrustarse directamente mediante `https://web.geolibre.app/?url=<URL_SITIO>/geovisor/proyecto.geolibre.json&maponly` o abrirse en pantalla completa en **GeoLibre Studio** para análisis avanzado con COG, PMTiles, GeoParquet, STAC y DuckDB-WASM.

## Pasos para publicar una capa generada por el equipo

1. Verifica que el archivo esté en coordenadas geográficas `EPSG:4326` (WGS84), con topología revisada y sin información personal o sensible.
2. Coloca archivos `.geojson` ligeros en `geovisor/data/` (los rásters pesados tipo COG o servicios WMS/XYZ deben alojarse en servidores geoespaciales o repositorios de datos adecuados y referenciarse por URL `https://`).
3. Edita `geovisor/layers.json`:
   - Actualiza `"source_path": "geovisor/data/mi_capa.geojson"` (o la URL `https://`).
   - Actualiza `"status"` de `"en_preparacion"` a `"en_revision"` o `"publicado"`.
   - Revisa la nota metodológica en `"caveat"`.
4. Ejecuta `python3 scripts/validate.py --source && python3 scripts/build_site.py --output site && python3 scripts/validate.py --site site`.

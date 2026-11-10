# Prevención de Riesgos

> **Identificador estable de iniciativa:** `gt-salud-metropolitana` · Parte del ecosistema **Comunidad Urbana Copernicus Centroamérica**.

La iniciativa propone actualizar información de expansión urbana y exposición a inundaciones, deslizamientos y calor para apoyar la prevención de riesgos a la salud y la coordinación entre MSPAS y municipalidades.

## Estructura del repositorio

| Ruta | Función |
|---|---|
| `project.json` | Manifiesto estructurado canónico de la iniciativa (`schemas/project.schema.json`). |
| `content/` | Contenido editorial público (`project.md`, `metodologia.md`, `pmv.md`, `continuidad.md`). |
| `geovisor/` | Configuración del **Geovisor basado en GeoLibre / MapLibre GL JS** (`layers.json`, `proyecto.geolibre.json` y carpeta `data/`). |
| `atlas/products/` | Metadatos de contribuciones al **Atlas Urbano Regional** (`schemas/atlas-product.schema.json`). |
| `src/` | Espacio para scripts reproducibles (Google Earth Engine, Python, openEO, QGIS). |
| `web/` | Estilos institucionales y controladores JS del sitio y geovisor. |
| `scripts/` | Generador estático (`build_site.py`) y validador de contratos/enlaces (`validate.py`). |
| `.github/` | Workflow de GitHub Pages (`pages.yml`), formularios de Issues y plantilla de PR. |

## Ejecución y validación local

Instala la dependencia mínima reproducible y ejecuta los tres comandos oficiales:

```bash
python3 -m pip install -r requirements.txt
python3 scripts/validate.py --source
python3 scripts/build_site.py --output site
python3 scripts/validate.py --site site
```

Servir vista previa local en `http://localhost:8000`:

```bash
python3 -m http.server 8000 --directory site
```

## Publicación en GitHub Pages

1. En **Settings → Pages → Build and deployment**, elegir **Source: GitHub Actions**.
2. Definir la variable de repositorio `PAGES_ENABLED=true` y, únicamente en el repositorio canónico verificado, `PAGES_SITE_MODE=canonical` (en forks personales usar `preview`).
3. Al publicar, registrar las URLs efectivas en `project.json` y en el registro del portal `clusterurbano`.

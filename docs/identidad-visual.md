# Guía de Identidad Visual Institucional y Logos del Proyecto

**Versión del tema común:** `2.0.0-copernicus-2026`  
**Referencia gráfica principal:** `PPT PLANTILLA COPERNICUS_2026.pptx` (Clúster de Asentamientos Humanos · Comunidad Urbana Copernicus Centroamérica)

Esta guía documenta el sistema visual compartido entre el portal regional (`copernicuscentroamerica/clusterurbano`), la plantilla común (`clusterurbano-proyecto-template`) y los ocho repositorios de proyectos (`urbano-{id}`), así como el procedimiento para que cada equipo añada o actualice los logos de sus instituciones participantes sin perderlos cuando se actualiza el tema común.

---

## 1. Paleta cromática y pila tipográfica institucional

### 1.1. Colores institucionales (`PPT PLANTILLA COPERNICUS_2026.pptx`)

Los colores del sistema proceden directamente de la composición visual de la plantilla institucional de presentaciones 2026:

| Variable CSS | Valor Hex | Uso en el sistema web |
| :--- | :--- | :--- |
| `--c-brand-blue` | `#000A62` | Azul institucional principal (cabecera de navegación, títulos, tarjetas institucionales, texto sobre acento amarillo). |
| `--c-cover-blue` | `#0C1659` | Azul oscuro de portada (franja superior de identidad, base de los encabezados `.hero` y barra del geovisor). |
| `--c-mesh-blue` | `#172070` | Azul de la trama cartográfica (superposición discreta de red urbana en cabeceras y bordes de énfasis). |
| `--c-accent-yellow` | `#FFC800` | Amarillo de acento (botones primarios `.btn-primary`, indicadores de navegación activa, foco de teclado y ondas de partículas). **Regla de contraste:** siempre se combina con texto oscuro `#000A62` / `#0C1659` (relación de contraste > 11:1, nivel WCAG AAA). |
| `--c-white` / `--c-surface` | `#FFFFFF` | Blanco puro para fondos de lectura (`.prose`, `.card`), contenedores de tablas y banda institucional regional. |

> **Separación frente a estados y simbología cartográfica:** las insignias de estado (`declarado`, `propuesta`, `pendiente`, `en_revision`, `validado`) y las rampas de color analíticas del geovisor mantienen su propia codificación semántica para que la identidad institucional nunca altere el significado de una capa o de su grado de validación.

### 1.2. Pila tipográfica web documentada

El archivo `ppt/theme/theme1.xml` de la plantilla institucional define **Calibri Light** para títulos (`majorFont`) y **Calibri** para cuerpo de texto (`minorFont`), con usos complementarios de **Poppins** en composiciones de diapositiva. Para garantizar legibilidad y disponibilidad en Windows, macOS, Linux y dispositivos móviles sin depender de fuentes propietarias externas, se utiliza la siguiente pila tipográfica:

```css
--font-heading: "Calibri Light", "Calibri", "Carlito", "Segoe UI Variable Display", "Segoe UI", "Poppins", system-ui, -apple-system, sans-serif;
--font-sans: "Calibri", "Carlito", "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, "Helvetica Neue", Arial, sans-serif;
--font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
```

- **Windows:** emplea directamente `Calibri Light` y `Calibri` instaladas en el sistema.
- **Linux:** emplea `Carlito` (métrica idéntica a Calibri) o la fuente del sistema.
- **macOS / iOS / Android:** emplea `Calibri` (si Office está instalado) o cae limpiamente a `system-ui` / `-apple-system`.

---

## 2. Identidad institucional regional común

Todos los sitios comparten dos bloques institucionales extraídos fielmente de `PPT PLANTILLA COPERNICUS_2026.pptx` (almacenados en `web/assets/img/brand/`):

1. **Identidad superior (sobre fondo azul oscuro `#0C1659`):**
   - **Global Gateway** (`logo-global-gateway.png`).
   - **Emblema de la Unión Europea** (`logo-union-europea.png`).
2. **Banda institucional regional (sobre fondo blanco `#FFFFFF`):**
   - **Implementado por:**
     1. **CCVAH** (`logo-ccvah.png`) — Consejo Centroamericano de Vivienda y Asentamientos Humanos.
     2. **SISCA** (`logo-sisca.png`) — Secretaría de la Integración Social Centroamericana.
     3. **SICA** (`logo-sica.png`) — Sistema de la Integración Centroamericana.
   - **Con el apoyo técnico de:**
     4. **Cooperación Alemana** (`logo-cooperacion-alemana.png`) — *cooperación alemana · DEUTSCHE ZUSAMMENARBEIT*.
     5. **GIZ** (`logo-giz.png`) — *Deutsche Gesellschaft für Internationale Zusammenarbeit (GIZ) GmbH*.
     6. **Copernicus LAC Chile** (`logo-copernicus-lac-chile.png`).

En la página del **Geovisor (`/aplicacion/`)**, la cabecera adopta un formato compacto (`.hero-compact`) y las bandas institucionales se sitúan debajo del área de trabajo del mapa para preservar el máximo espacio vertical al lienzo cartográfico y sus controles.

---

## 3. Identidad propia de cada proyecto (`Instituciones participantes del proyecto`)

Cada repositorio dispone de una zona específica denominada **«Instituciones participantes del proyecto»**, diferenciada de la banda regional y gobernada por dos elementos que pertenecen exclusivamente al equipo de la iniciativa:

- `branding/project-branding.json`: archivo de configuración de la identidad local.
- `branding/logos/`: carpeta donde se alojan los archivos gráficos (`.svg` o `.png`) del proyecto y de sus instituciones participantes.
- `schemas/project-branding.schema.json`: esquema JSON Schema Draft 2020-12 que valida la estructura.

### 3.1. Formato de `branding/project-branding.json`

```json
{
  "schema_version": "1.0.0",
  "project_id": "pa-panama-oeste",
  "theme_version": "2.0.0-copernicus-2026",
  "updated_at": "2026-11-10",
  "notes": "Identidad local de las instituciones participantes en la iniciativa.",
  "project_logo": null,
  "institutions": [
    {
      "id": "miviot",
      "name": "Ministerio de Vivienda y Ordenamiento Territorial",
      "acronym": "MIVIOT",
      "role": "Institución principal declarada en el perfil",
      "logo_path": "branding/logos/logo-miviot.png",
      "alt_text": "Logo del Ministerio de Vivienda y Ordenamiento Territorial (MIVIOT) de Panamá",
      "url": "https://www.miviot.gob.pa/",
      "order": 1,
      "aspect_hint": "horizontal"
    }
  ]
}
```

### 3.2. Reglas de representación y calidad gráfica

- **Formatos admitidos:**
  - Preferido: **SVG original** (`branding/logos/nombre.svg`) con curvas convertidas o texto trazado y `viewBox` definido.
  - Alternativa recomendada: **PNG con transparencia** (`branding/logos/nombre.png`), ancho recomendado entre `300 px` y `1200 px`, peso máximo `2 MB`.
  - Se aceptan también `.webp` o `.jpg`/`.jpeg` cuando el emblema original tenga fondo blanco sólido, siempre que se respete un margen blanco uniforme y no supere `2 MB`.
- **Orientaciones (`aspect_hint`):**
  - `"horizontal"`: marcas apaisadas (relación ancho/alto > 1.4).
  - `"vertical"`: escudos o emblemas altos (relación ancho/alto < 0.85).
  - `"square"` o `"auto"`: marcas cuadradas o circulares.
  - El contenedor aplica `object-fit: contain` y espacio de protección para evitar recortes o deformaciones.
- **Instituciones sin archivo de logo (`"logo_path": null`):**
  - Si una institución aún no ha entregado su archivo gráfico, deja `"logo_path": null`.
  - El generador mostrará su sigla, nombre oficial y rol de forma legible en una tarjeta institucional limpia. **Nunca generes logos con IA ni utilices escudos aproximados.**

---

## 4. Procedimiento paso a paso para añadir o actualizar un logo

1. **Abrir el repositorio de la iniciativa:** trabaja en tu copia local clonada desde tu fork personal (o directamente en una rama si tienes permisos en el repositorio del proyecto).
2. **Incorporar el archivo gráfico:** copia el archivo `.svg` o `.png` dentro de la carpeta `branding/logos/` (por ejemplo, `branding/logos/logo-institucion.png`).
3. **Registrar los metadatos en `branding/project-branding.json`:** añade o actualiza la entrada en la lista `institutions` indicando `id`, `name`, `acronym`, `role`, `logo_path`, `alt_text`, `url` (opcional, con `https://`) y `order`.
4. **Validar y comprobar la vista previa local:**
   ```bash
   python3 scripts/validate.py --source
   python3 scripts/build_site.py --output site
   python3 scripts/validate.py --site site
   python3 -m http.server 8000 --directory site
   ```
5. **Enviar rama y Pull Request:**
   ```bash
   git switch -c feat/logos-institucionales
   git add branding/
   git commit -m "Añade logo institucional en branding/logos/"
   git push -u origin feat/logos-institucionales
   ```
   Abre el Pull Request hacia la rama `main` del repositorio canónico de tu iniciativa.
6. **Publicación tras revisión:** al integrarse el Pull Request en `main`, GitHub Actions reconstruye el sitio oficial del proyecto y el sincronizador del portal regional (`sync_catalog.py`) incorpora la identidad aprobada en la ficha del proyecto dentro de `clusterurbano`.

### Prompt rápido para pedir ayuda a Antigravity

Puedes copiar y pegar este prompt en Antigravity después de colocar tus archivos en la carpeta del proyecto:

> «He copiado los archivos de logos institucionales en la carpeta `branding/logos/` de este repositorio. Por favor:
> 1. Inspecciona los archivos nuevos en `branding/logos/` (verifica formato, dimensiones y que no superen 2 MB).
> 2. Actualiza `branding/project-branding.json` manteniendo intacto `project_id` y añadiendo o vinculando cada archivo en `institutions` con su `name`, `acronym`, `role`, `alt_text` descriptivo, `aspect_hint` (`horizontal`, `vertical` o `square`) y `order`.
> 3. Ejecuta `python scripts/validate.py --source`, `python scripts/build_site.py --output site` y `python scripts/validate.py --site site` para confirmar que no hay errores.
> 4. Muéstrame el resumen de cambios (`git status` y `git diff branding/project-branding.json`) listo para crear una rama y enviar un Pull Request.»

---

## 5. Mantenimiento del tema común y actualización sin perder logos locales

### 5.1. Separación entre componentes del tema común e identidad local

| Archivos del tema común (se actualizan desde `clusterurbano-proyecto-template`) | Archivos de identidad y contenido local (se conservan en cada proyecto) |
| :--- | :--- |
| `web/assets/css/styles.css` | `branding/project-branding.json` |
| `web/assets/js/ui.js`, `web/assets/js/geovisor.js` | `branding/logos/*` |
| `web/assets/img/brand/*` (logos regionales y ondas/trama) | `project.json`, `repo.config.json` |
| `scripts/site_common.py`, `scripts/build_site.py`, `scripts/validate.py` | `content/*.md`, `geovisor/layers.json`, `geovisor/capas/*`, `atlas/products/*` |
| `schemas/*.schema.json`, `docs/identidad-visual.md` | |

### 5.2. Cómo aplicar una actualización del tema común a los proyectos existentes

1. En el repositorio de la iniciativa, crea una rama de mantenimiento:
   ```bash
   git switch -c chore/actualiza-tema-comun main
   ```
2. Copia únicamente los archivos del tema común desde `clusterurbano-proyecto-template` (`web/assets/css/styles.css`, `web/assets/img/brand/`, `scripts/site_common.py`, `scripts/build_site.py`, `scripts/validate.py`, `schemas/project-branding.schema.json`, `docs/identidad-visual.md`). **No sobrescribas** `branding/project-branding.json` ni `branding/logos/`.
3. Revisa las diferencias antes de confirmar:
   ```bash
   git status --short
   git diff branding/
   ```
   *(El comando `git diff branding/` debe estar vacío si solo estás actualizando el tema común).*
4. Ejecuta la validación y reconstrucción completa:
   ```bash
   python3 scripts/validate.py --source
   python3 scripts/build_site.py --output site
   python3 scripts/validate.py --site site
   ```

### 5.3. Cómo volver a una versión anterior (Rollback)

Si una actualización del tema común presenta algún inconveniente visual o funcional:

```bash
# Opción A: descartar cambios locales antes de hacer commit
git checkout -- web/ scripts/ schemas/

# Opción B: revertir un commit de actualización ya integrado manteniendo el historial limpio
git revert <SHA_DEL_COMMIT_DE_TEMA>
python3 scripts/build_site.py --output site
```

---

## 6. Archivos institucionales vectoriales recomendados para mejora continua

Los logos regionales comunes incluidos en `web/assets/img/brand/` fueron extraídos a alta resolución (`4800 × 2700 px` y capas RGBA de las presentaciones oficiales del programa) sin alteración ni recreación artificial. Para alcanzar la máxima nitidez en pantallas 4K/Retina y reducir aún más el peso de transferencia, se recomienda solicitar a las contrapartes de comunicación los siguientes originales independientes en formato vectorial (`.svg` o `.eps`/`.ai`):

1. **Global Gateway** y **Emblema de la Unión Europea** en versión vectorial blanca/color sobre fondo oscuro (`#0C1659`).
2. **CCVAH**, **SISCA** y **SICA** en versión vectorial oficial para fondo claro (`#FFFFFF`).
3. **Cooperación Alemana (`DEUTSCHE ZUSAMMENARBEIT`)**, **GIZ** y **Copernicus LAC Chile** en versión vectorial `.svg`.
4. **Logos vectoriales propios de las instituciones nacionales y municipales** de cada uno de los 8 proyectos (por ejemplo: MIVIOT en Panamá; OPAMSS en San Salvador; MARN y MOPT en La Unión; CONRED y Municipalidad de Guatemala en Bethania; MSPAS en Guatemala; Ayuntamiento de Santiago y MEPyD en República Dominicana; AMDC, UNAH y SEGOB en Distrito Central) para ir sustituyendo las tarjetas textuales (`"logo_path": null`) conforme cada institución valide y entregue su archivo oficial en `branding/logos/`.

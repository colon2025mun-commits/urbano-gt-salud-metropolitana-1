## Alcance técnico y metodológico declarado en el perfil

Los siguientes campos reproducen la información declarada por el equipo en el documento principal del perfil (identificado en el inventario documental como `S23`; consulta la lista completa de archivos al final de esta página). Representan la formulación técnica del perfil y se actualizan conforme avanza la validación del proyecto.

### Territorio y escala

**Ciudad, sector o territorio.** Región metropolitana de Guatemala

**Escala principal de análisis.** Área metropolitana / conurbación

**Superficie aproximada.** 2,253 Km2

**Centroide (lat, lon).** 14°37'16.48"N 90°20'51.03"W

**¿Cuenta con archivos geoespaciales?.** Si

**Archivo cargado.** No especificado

**Descripción de los archivos.** 

### Instrumentos y productos

**Instrumento de planificación o gestión al que aportaría.** Plan de ordenamiento territorial / plan de desarrollo urbano

Plan de gestión de riesgo

Plan de acción climática

**Tipo de producto o entregable.** Capa geoespacial

Indicador urbano

Script reproducible

Reporte o informe automatizado

Dashboard / tablero

Visor web

Aplicación

Formulario de campo

Base de datos

Protocolo operativo

**Descripción del producto.** Mapa con dashboard/visor web, de la región metropolitana de Guatemala

**Avance mínimo esperado en la jornada presencial.** Protocolo operativo, Scrip Reproducible, Mapa con dashboard automatizado

### Datos

**Datos satelitales o productos geoespaciales útiles.** Sentinel-2 / óptico multiespectral

Sentinel-1 / radar SAR

Landsat térmico / temperatura superficial (LST)

Imágenes de muy alta resolución / ortofotos

LiDAR / modelos digitales de superficie

Copernicus DEM / elevación

Cobertura del suelo global (ESA WorldCover, Dynamic World)

Huellas de edificaciones (Google/Microsoft Open Buildings)

OpenStreetMap (vías, edificaciones, equipamientos)

Límites institucionales o administrativos

**Datos locales, institucionales o de campo disponibles.** Límites municipales, departamentales y nacionales, capas de  inundación y deslizamientos (desactualizados), censos de población año 2018 de la region metropolitana de Guatemala

**Datos que hacen falta.** Datos actualizados

**Enlaces relacionados.** No especificado

### Método y herramientas

**Métodos o pasos previstos.** Detección de cambios / expansión urbana entre fechas (Sentinel 2)

Extracción de edificaciones (segmentación / deep learning)

Series temporales

Análisis multicriterio / aptitud del suelo

Modelación de crecimiento urbano / escenarios

Análisis sociodemográfico

Visualización en dashboard, visor o app

**Flujo de trabajo preliminar.** Recopilación de datos a diferentes escalas, actualización, aplicación y producto final para los usuarios propuestos

**Índices, algoritmos o herramientas.** No especificado

### Operación y acompañamiento

**Frecuencia de actualización o análisis.** Anual

Después de un evento específico

**Nivel(es) de acceso.** Uso institucional

Público

Comunitario

**Componentes para usar o desplegar.** Google Earth Engine App

Dashboard / tablero

GeoServer / servicio geoespacial

Integración con IDE o geoportal

**Uso previsto por otras personas.** Decisiones basadas en datos desde la escala municipal a regional y nacional

**¿Requiere actualización periódica?.** Sí

**Actualización requerida.** Lo realizaría el MSPAS, actualización anual

**Pregunta principal.** ¿Qué herramientas y metodologías recomiendan para actualizar los datos y que la información esté disponible para el usuario municipal y nacional?

**Áreas en las que necesita asesoría.** Datos disponibles y datos necesarios

Metodología y análisis geoespacial

Scrips de automatización

Validación de resultados

Producto esperado y visualización

Despliegue digital

## Referencias documentales del expediente

- `S23` — `0. Perfiles de Proyectos/Grupo 7_Guatemala_Prevencion riesgos salud/Ficha_07_Guatemala_MSPAS_Prevencion_Riesgos_Salud.docx`.

### Parámetros de corrida verificados

El equipo utilizará un umbral máximo de nubosidad del 20 % y enmascaramiento SCL (clases 4, 5 y 6) sobre Sentinel-2 L2A.


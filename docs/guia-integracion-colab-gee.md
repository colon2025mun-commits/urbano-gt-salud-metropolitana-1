# Guía de Integración: Google Colab, Google Earth Engine y Antigravity

**Iniciativa:** Prevención de Riesgos de Salud · Región Metropolitana de Guatemala (`gt-salud-metropolitana`)  
**Creador del proyecto:** Andres Barrionuevo  
**Repositorio:** [copernicuscentroamerica/urbano-gt-salud-metropolitana](https://github.com/copernicuscentroamerica/urbano-gt-salud-metropolitana)

---

## 1. Arquitectura de Integración

Este proyecto cuenta con un entorno integrado de tres niveles:

```
┌─────────────────────────────────┐
│     Google Earth Engine (GEE)   │  Catálogo satelital Sentinel-2 L2A, Landsat LST, DEM
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│   Google Colab & Scripts Python │  scripts/gee_procesamiento_sentinel2.py
│   (Procesamiento y Modelos)     │  notebooks/analisis_sentinel2_salud_metropolitana.ipynb
└────────────────┬────────────────┘
                 │ (Capas GeoJSON / GeoTIFF / MBTiles)
                 ▼
┌─────────────────────────────────┐
│   Geovisor Integrado GeoLibre   │  MapLibre GL JS + geovisor/proyecto.geolibre.json
│   (Visualización y Publicación) │  Servidor local HTTP (localhost:8000)
└─────────────────────────────────┘
```

---

## 2. Parámetros Metodológicos Verificados en GEE

Para garantizar la coherencia técnica del proyecto, todos los scripts y notebooks aplican los siguientes filtros:

* **Colección satelital:** `COPERNICUS/S2_SR_HARMONIZED`
* **Umbral de nubes:** `CLOUDY_PIXEL_PERCENTAGE <= 20`
* **Enmascaramiento SCL (Scene Classification Layer):**
  * Conservar:
    * Clase 4: Vegetación
    * Clase 5: Suelo desnudo / no vegetado
    * Clase 6: Agua
  * Descartar: Clases 1, 2, 3 (sombras), 7, 8, 9 (nubes) y 10 (cirros).
* **Región de Interés (ROI):** Centroide `14°37'16.48"N, 90°20'51.03"W` (`14.621244, -90.347508`) con un radio buffer de 26.8 km (~2,253 km²).

---

## 3. Banco de Memoria: Errores Comunes y Soluciones Verificadas

Para simplificar futuras situaciones de desarrollo en este equipo y máquina:

### 1. Bloqueo de Git en Push (espera de credenciales / ventana colgada)
* **Causa:** Git estándar en Windows intenta abrir una ventana GUI de autenticación o se bloquea esperando un token.
* **Solución permanente:**
  ```powershell
  gh auth setup-git
  ```
  Esto vincula directamente Git con las credenciales activas de GitHub CLI (`gh`), permitiendo `git push` y `git fetch` fluidos sin contraseñas ni bloqueos.

### 2. Error de Administrador / Permisos al ejecutar Python en Windows
* **Causa:** En equipos institucionales o corporativos, el comando `python` puede invocar el alias de WindowsApps (`AppData\Local\Microsoft\WindowsApps\python.exe`), el cual intenta abrir la tienda Microsoft Store y es bloqueado por políticas de TI.
* **Solución permanente:**
  No es necesario elevar privilegios a Administrador. Ejecuta Python estándar directamente:
  ```powershell
  py scripts/build_site.py --output site
  # o con ruta absoluta
  & "C:\Program Files\Python313\python.exe" scripts/build_site.py --output site
  ```

### 3. Aislamiento de Red en Sandbox
* **Causa:** Al instalar librerías (`pip install ...`) o interactuar con APIs externas (`gh repo fork`, `earthengine authenticate`), el entorno aislado no tiene acceso a internet.
* **Solución:** Ejecutar comandos de red directamente en la terminal del sistema.

---

## 4. Codex de Prompts para Antigravity (Generación de Modelos Complejos)

Utiliza estos prompts estructurados para solicitarle a Antigravity nuevas funcionalidades avanzadas:

### Prompt A: Expansión Urbana y Temperatura Superficial (LST)
```text
Actuando como especialista geoespacial para urbano-gt-salud-metropolitana:
Genera un script en Python para Google Earth Engine que integre Landsat 8/9 (TIRS)
para estimar la Temperatura Superficial del Suelo (LST) en la Región Metropolitana de Guatemala.
Relaciona el LST con el índice NDBI y exporta una capa ráster para ser integrada
en geovisor/capas/ de este repositorio.
```

### Prompt B: Análisis de Vulnerabilidad a Inundación Multicriterio
```text
Genera un modelo multicriterio en Google Earth Engine combinando:
1. Copernicus DEM (pendientes < 5%)
2. MNDWI de Sentinel-2 L2A (SCL 4, 5, 6, nubes < 20%)
3. Distancia a drenajes principales
Exporta el resultado reclasificado en 3 categorías de riesgo a la salud (Bajo, Medio, Alto)
siguiendo los criterios documentados en project.json.
```

---

## 5. Persistencia y Aprendizaje

Para indicarle a Antigravity que persista y recuerde estas reglas de trabajo en cualquier conversación futura, puedes usar en el chat el comando:
```text
/learn
```
El agente registrará las configuraciones y lecciones aprendidas en su memoria de largo plazo.

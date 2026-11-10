# Reglas del Proyecto Copernicus Urbano (gt-salud-metropolitana)

## Contexto del Proyecto
- **ID:** `gt-salud-metropolitana`
- **Creador:** Andres Barrionuevo
- **Organización / Repositorio Canónico:** `copernicuscentroamerica/urbano-gt-salud-metropolitana`
- **Área Territorial:** Región Metropolitana de Guatemala (Centroide 14°37'16.48"N, 90°20'51.03"W; Área ~2,253 km²)

## Parámetros Metodológicos Invariables
- Colección satelital: Sentinel-2 L2A Armonizada (`COPERNICUS/S2_SR_HARMONIZED`).
- Umbral máximo de nubes: 20%.
- Enmascaramiento SCL: Clases 4 (Vegetación), 5 (Suelo desnudo/no vegetado) y 6 (Agua).
- Índices requeridos: NDVI, NDBI, MNDWI y análisis térmico LST.

## Buenas Prácticas del Entorno Local (Windows)
1. **Git Credentials:** Siempre usar `gh auth setup-git` antes de operaciones remotas de git para evitar bloqueos por ventanas emergentes de credenciales.
2. **Python:** Nunca requerir privilegios de Administrador. Invocar Python mediante `py` o `& "C:\Program Files\Python313\python.exe"` para evitar el alias de WindowsApps.
3. **Validaciones obligatorias antes de commit:**
   - `python scripts/build_site.py --output site`
   - `python scripts/validate.py --source`
   - `python scripts/validate.py --site site`
4. **Punteros JSON en project.json:** Toda modificación de campos debe contar con su correspondiente entrada en `provenance.statements`.

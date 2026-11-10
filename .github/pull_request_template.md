## Propósito del cambio

Describe brevemente qué actualiza esta Pull Request (metodología, ficha, capas del geovisor GeoLibre, código o contribución al Atlas).

## Issue o compromiso relacionado

- Relacionado con: #

## Evidencia y procedencia

- [ ] Distingue claramente datos `declarado`, `propuesta` y `por_confirmar`.
- [ ] No incorpora datos personales, contactos no autorizados ni geometrías/resultados ficticios.
- [ ] Si publica o actualiza una capa en `geovisor/`, documenta CRS (`EPSG:4326`), fuente, fecha y limitaciones.

## Comprobaciones ejecutadas localmente

- [ ] `python3 scripts/validate.py --source`
- [ ] `python3 scripts/build_site.py --output site`
- [ ] `python3 scripts/validate.py --site site`

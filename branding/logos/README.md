# Carpeta de logos del proyecto (`branding/logos/`)

Coloca en esta carpeta los archivos gráficos oficiales de las instituciones participantes del proyecto y, si existe, el identificador gráfico propio de la iniciativa.

## Reglas de formato y nomenclatura

- **Formatos admitidos:** `.svg` (preferido), `.png` (con fondo transparente), `.webp`.
- **Nombres de archivo:** en minúsculas, sin espacios ni tildes, usando guiones (`logo-institucion.svg` o `logo-institucion.png`).
- **Peso máximo:** `2 MB` por archivo (`< 300 KB` recomendado).
- **Integridad:** utiliza únicamente archivos oficiales proporcionados por cada institución; no generes ni aproximes logotipos con IA.

Tras añadir un archivo en esta carpeta, regístralo en `../project-branding.json` y ejecuta:

```bash
python scripts/validate.py --source
python scripts/build_site.py --output site
python scripts/validate.py --site site
```

#!/usr/bin/env python3
"""
Validador oficial de fuentes (--source) y artefacto estático (--site)
para repositorios de iniciativa (urbano-{id}) y plantilla (clusterurbano-proyecto-template).
"""
from __future__ import annotations

import argparse
import html.parser
import json
import re
import sys
import urllib.parse
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from site_common import make_format_checker, resolve_json_pointer

ROOT = Path(__file__).resolve().parent.parent
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


class LinkAndMetaCollector(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.has_noindex = False
        self.has_work_banner = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() == "a" and "href" in attr_map:
            self.links.append(("href", attr_map["href"]))
        elif tag.lower() in ("link", "script", "img", "iframe"):
            for key in ("href", "src"):
                if key in attr_map and attr_map[key]:
                    self.links.append((key, attr_map[key]))
        if tag.lower() == "meta" and attr_map.get("name", "").lower() == "robots":
            if "noindex" in attr_map.get("content", "").lower():
                self.has_noindex = True
        if "work-banner" in attr_map.get("class", ""):
            self.has_work_banner = True


def check_no_private_data(text: str, label: str, errors: list[str]) -> None:
    found_emails = EMAIL_RE.findall(text)
    if found_emails:
        errors.append(f"[{label}] Contiene direcciones de correo no autorizadas: {found_emails}")


def validate_source() -> list[str]:
    errors: list[str] = []

    cfg_path = ROOT / "repo.config.json"
    hub_registry_path = ROOT / "data" / "projects.registry.json"
    if hub_registry_path.exists():
        errors.append(
            "Configuración ambigua: se encontraron simultáneamente repo.config.json de iniciativa y data/projects.registry.json del hub."
        )
        return errors

    if not cfg_path.exists():
        errors.append("Falta repo.config.json en la raíz del repositorio.")
        return errors

    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    repo_kind = cfg.get("repo_kind")
    if repo_kind not in ("project", "template"):
        errors.append(f"repo.config.json tiene repo_kind inválido: {repo_kind}")
        return errors

    checker = make_format_checker()

    # 1. Validar esquemas JSON Schema Draft 2020-12
    proj_schema_path = ROOT / "schemas" / "project.schema.json"
    atlas_schema_path = ROOT / "schemas" / "atlas-product.schema.json"
    for sp in (proj_schema_path, atlas_schema_path):
        if not sp.exists():
            errors.append(f"Falta esquema requerido: {sp.relative_to(ROOT)}")
        else:
            schema_obj = json.loads(sp.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema_obj)

    if errors:
        return errors

    proj_schema = json.loads(proj_schema_path.read_text(encoding="utf-8"))
    atlas_schema = json.loads(atlas_schema_path.read_text(encoding="utf-8"))
    proj_validator = Draft202012Validator(proj_schema, format_checker=checker)
    atlas_validator = Draft202012Validator(atlas_schema, format_checker=checker)

    # 2. Validar project.json
    manifest_path = ROOT / "project.json"
    if not manifest_path.exists():
        errors.append("Falta project.json en la raíz.")
        return errors

    raw_manifest = manifest_path.read_text(encoding="utf-8")
    check_no_private_data(raw_manifest, "project.json", errors)
    manifest = json.loads(raw_manifest)

    for verr in proj_validator.iter_errors(manifest):
        loc = "/".join(str(p) for p in verr.absolute_path) or "<raíz>"
        errors.append(f"[project.json -> {loc}] {verr.message}")

    pid = manifest.get("id", "")
    if repo_kind == "project":
        expected_id = cfg.get("expected_project_id")
        if pid != expected_id:
            errors.append(f"project.json id '{pid}' no coincide con expected_project_id '{expected_id}'.")
        if "Título de demostración del contrato" in manifest.get("title", "") or "PLANTILLA" in manifest.get("title", ""):
            errors.append("project.json conserva texto de ejemplo o plantilla sin personalizar.")

    # Comprobar punteros de procedencia y source_ids
    sources_defined = {s["id"] for s in manifest.get("provenance", {}).get("sources", [])}
    for st in manifest.get("provenance", {}).get("statements", []):
        ptr = st.get("pointer", "")
        try:
            resolve_json_pointer(manifest, ptr)
        except Exception as exc:
            errors.append(f"[project.json provenance] Puntero inválido '{ptr}': {exc}")
        for sid in st.get("source_ids", []):
            if sid not in sources_defined:
                errors.append(f"[project.json provenance] source_id '{sid}' no existe en provenance.sources.")

    # 3. Validar productos del Atlas
    atlas_dir = ROOT / "atlas" / "products"
    if atlas_dir.exists():
        for ap_file in sorted(atlas_dir.glob("*.json")):
            ap_raw = ap_file.read_text(encoding="utf-8")
            check_no_private_data(ap_raw, str(ap_file.relative_to(ROOT)), errors)
            ap_obj = json.loads(ap_raw)
            for verr in atlas_validator.iter_errors(ap_obj):
                loc = "/".join(str(p) for p in verr.absolute_path) or "<raíz>"
                errors.append(f"[{ap_file.name} -> {loc}] {verr.message}")
            if ap_obj.get("project_id") != pid:
                errors.append(
                    f"[{ap_file.name}] project_id '{ap_obj.get('project_id')}' no coincide con '{pid}'."
                )
            ap_sources = {s["id"] for s in ap_obj.get("provenance", {}).get("sources", [])}
            for st in ap_obj.get("provenance", {}).get("statements", []):
                try:
                    resolve_json_pointer(ap_obj, st.get("pointer", ""))
                except Exception as exc:
                    errors.append(f"[{ap_file.name} provenance] Puntero inválido: {exc}")
                for sid in st.get("source_ids", []):
                    if sid not in ap_sources:
                        errors.append(f"[{ap_file.name} provenance] source_id '{sid}' inexistente.")

    # 4. Validar configuración del Geovisor GeoLibre
    layers_path = ROOT / "geovisor" / "layers.json"
    geolibre_path = ROOT / "geovisor" / "proyecto.geolibre.json"
    if not layers_path.exists() or not geolibre_path.exists():
        errors.append("Faltan archivos requeridos en geovisor/ (layers.json o proyecto.geolibre.json).")
    else:
        layers_cfg = json.loads(layers_path.read_text(encoding="utf-8"))
        if layers_cfg.get("project_id") != pid:
            errors.append(f"[geovisor/layers.json] project_id '{layers_cfg.get('project_id')}' != '{pid}'.")
        center = layers_cfg.get("map_view", {}).get("center", [])
        if (
            not isinstance(center, list)
            or len(center) != 2
            or not (-180 <= float(center[0]) <= 180)
            or not (-90 <= float(center[1]) <= 90)
        ):
            errors.append(f"[geovisor/layers.json] Coordenadas de centro inválidas: {center}")
        for lyr in layers_cfg.get("layers", []):
            sp = lyr.get("source_path")
            st = lyr.get("status")
            if st in ("publicado", "en_revision") and not sp:
                errors.append(f"[geovisor/layers.json] Capa '{lyr.get('id')}' en estado '{st}' requiere source_path.")
            if sp and not str(sp).startswith("https://"):
                local_target = ROOT / str(sp)
                if not local_target.exists():
                    errors.append(f"[geovisor/layers.json] No existe archivo local de capa: {sp}")

    # 5. Validar archivos editoriales Markdown
    required_md = [
        ROOT / "content" / "project.md",
        ROOT / "content" / "metodologia.md",
        ROOT / "content" / "pmv.md",
        ROOT / "content" / "continuidad.md",
    ]
    for md_file in required_md:
        if not md_file.exists():
            errors.append(f"Falta contenido requerido: {md_file.relative_to(ROOT)}")
            continue
        txt = md_file.read_text(encoding="utf-8")
        if not txt.strip():
            errors.append(f"El archivo está vacío: {md_file.relative_to(ROOT)}")
        check_no_private_data(txt, str(md_file.relative_to(ROOT)), errors)
        if "../fuentes/" in txt or "](fuentes/" in txt:
            errors.append(f"[{md_file.relative_to(ROOT)}] Contiene enlace relativo prohibido hacia carpeta privada fuentes/.")
        if repo_kind == "project" and "TEXTO_PLANTILLA_POR_REEMPLAZAR" in txt:
            errors.append(f"[{md_file.relative_to(ROOT)}] Conserva marcadores de plantilla sin reemplazar.")

    # Prohibir carpeta fuentes/ dentro del repositorio público
    if (ROOT / "fuentes").exists():
        errors.append("La carpeta privada 'fuentes/' no debe existir dentro del repositorio público.")

    return errors


def resolve_internal_target(site_dir: Path, base_path: str, current_html: Path, ref: str) -> Path | None:
    parsed = urllib.parse.urlsplit(ref)
    if parsed.scheme or parsed.netloc:
        return None
    path_part = parsed.path
    if not path_part:
        return current_html

    norm_base = base_path if base_path.endswith("/") else base_path + "/"
    if path_part.startswith("/"):
        if norm_base != "/" and path_part.startswith(norm_base):
            rel = path_part[len(norm_base) :]
        elif norm_base == "/":
            rel = path_part.lstrip("/")
        else:
            # Ruta absoluta fuera del prefijo base configurado -> error!
            return site_dir / "__FUERA_DE_BASE_PATH__" / path_part.lstrip("/")
        target = site_dir / rel
    else:
        target = (current_html.parent / path_part).resolve()

    if target.is_dir() or str(path_part).endswith("/"):
        return target / "index.html"
    return target


def validate_site(site_dir: Path) -> list[str]:
    errors: list[str] = []
    if not site_dir.exists():
        return [f"No existe el directorio de salida: {site_dir}"]

    required_outputs = [
        "index.html",
        "404.html",
        "proyecto/index.html",
        "aplicacion/index.html",
        "metodologia/index.html",
        "resultados/index.html",
        "colaborar/index.html",
        "geovisor/layers.json",
        "geovisor/proyecto.geolibre.json",
        "data/project.json",
        "data/build-meta.json",
        "assets/css/styles.css",
        "assets/js/ui.js",
        "assets/js/geovisor.js",
    ]
    for rel in required_outputs:
        if not (site_dir / rel).exists():
            errors.append(f"[site] Falta archivo generado requerido: {rel}")

    if (site_dir / "CNAME").exists():
        errors.append("[site] No debe heredarse ni generarse un archivo CNAME sin configuración expresa.")
    if (site_dir / "fuentes").exists():
        errors.append("[site] La carpeta fuentes/ no puede publicarse en site/.")

    if errors:
        return errors

    build_meta = json.loads((site_dir / "data" / "build-meta.json").read_text(encoding="utf-8"))
    base_path = build_meta.get("base_path", "/")
    effective_mode = build_meta.get("effective_mode", "preview")
    manifest = json.loads((ROOT / "project.json").read_text(encoding="utf-8"))

    html_files = sorted(site_dir.rglob("*.html"))
    for hf in html_files:
        content = hf.read_text(encoding="utf-8")
        check_no_private_data(content, str(hf.relative_to(site_dir)), errors)
        collector = LinkAndMetaCollector()
        collector.feed(content)

        if effective_mode == "preview" and hf.name != "404.html":
            if not collector.has_noindex:
                errors.append(f"[{hf.relative_to(site_dir)}] Vista preview requiere meta robots noindex.")
            if not collector.has_work_banner:
                errors.append(f"[{hf.relative_to(site_dir)}] Vista preview requiere franja 'Vista de trabajo'.")

        for attr_kind, href in collector.links:
            h = href.strip()
            if h == "#":
                errors.append(f"[{hf.relative_to(site_dir)}] Enlace vacío prohibido href='#'.")
                continue
            if h.lower().startswith(("javascript:", "data:", "vbscript:")):
                errors.append(f"[{hf.relative_to(site_dir)}] Esquema ejecutable prohibido: {h}")
                continue
            if "fuentes/" in h.lower():
                errors.append(f"[{hf.relative_to(site_dir)}] Enlace hacia carpeta privada fuentes/: {h}")
                continue
            if h.startswith("http://"):
                errors.append(f"[{hf.relative_to(site_dir)}] Recurso externo sin HTTPS: {h}")
                continue
            if h.startswith("https://") or h.startswith("#"):
                continue

            target = resolve_internal_target(site_dir, base_path, hf, h)
            if target is not None and not target.exists():
                errors.append(
                    f"[{hf.relative_to(site_dir)}] Enlace interno roto ({attr_kind}='{h}') -> no existe {target}"
                )

    index_txt = (site_dir / "index.html").read_text(encoding="utf-8")
    if manifest["id"] not in index_txt:
        errors.append("[site/index.html] No conserva visible el identificador estable del proyecto.")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida fuentes o artefacto construido del proyecto.")
    parser.add_argument("--source", action="store_true", help="Valida esquemas, manifiesto y contenidos fuente.")
    parser.add_argument("--site", type=str, default=None, help="Directorio del sitio construido a validar (ej. site).")
    args = parser.parse_args()

    if not args.source and not args.site:
        parser.error("Indica --source y/o --site <directorio>.")

    all_errors: list[str] = []
    if args.source:
        errs = validate_source()
        if errs:
            all_errors.extend(errs)
        else:
            print("[OK] Validación de fuentes (--source) superada sin errores.")

    if args.site:
        errs = validate_site(ROOT / args.site)
        if errs:
            all_errors.extend(errs)
        else:
            print(f"[OK] Validación de sitio construido (--site {args.site}) superada sin errores.")

    if all_errors:
        print("Se encontraron errores de validación:", file=sys.stderr)
        for e in all_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

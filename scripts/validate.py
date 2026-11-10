#!/usr/bin/env python3
"""
Validador oficial de fuentes (--source) y artefacto estático (--site)
para repositorios de iniciativa (urbano-{id}) y plantilla (clusterurbano-proyecto-template).
Incluye validación de identidad visual común y local (branding/project-branding.json).
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

from site_common import THEME_VERSION, make_format_checker, resolve_json_pointer

ROOT = Path(__file__).resolve().parent.parent
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
MAX_LOGO_BYTES = 2 * 1024 * 1024
ALLOWED_LOGO_EXTS = {".svg", ".png", ".webp", ".jpg", ".jpeg"}
REQUIRED_BRAND_ASSETS = [
    "logo-global-gateway.png",
    "logo-union-europea.png",
    "logo-ccvah.png",
    "logo-sisca.png",
    "logo-sica.png",
    "logo-cooperacion-alemana.png",
    "logo-giz.png",
    "logo-copernicus-lac-chile.png",
    "bg-trama-cartografica.png",
    "onda-puntos-amarilla.png",
]


class LinkAndMetaCollector(html.parser.HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.images_missing_alt: list[str] = []
        self.has_noindex = False
        self.has_work_banner = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        t = tag.lower()
        if t == "a" and "href" in attr_map:
            self.links.append(("href", attr_map["href"]))
        elif t in ("link", "script", "img", "iframe"):
            for key in ("href", "src"):
                if key in attr_map and attr_map[key]:
                    self.links.append((key, attr_map[key]))
            if t == "img":
                alt_val = attr_map.get("alt", "").strip()
                if not alt_val:
                    self.images_missing_alt.append(attr_map.get("src", "<sin-src>"))
        if t == "meta" and attr_map.get("name", "").lower() == "robots":
            if "noindex" in attr_map.get("content", "").lower():
                self.has_noindex = True
        if "work-banner" in attr_map.get("class", ""):
            self.has_work_banner = True


def validate_geolibre_project_obj(gl_obj: Any, label: str, errors: list[str]) -> None:
    if not isinstance(gl_obj, dict):
        errors.append(f"[{label}] El archivo .geolibre.json debe ser un objeto JSON.")
        return
    for req_key in ("version", "name", "mapView", "basemapStyleUrl", "layers", "styles"):
        if req_key not in gl_obj or gl_obj[req_key] is None:
            errors.append(f"[{label}] Falta campo obligatorio de GeoLibre Studio: '{req_key}'.")
    mv = gl_obj.get("mapView")
    if isinstance(mv, dict):
        c = mv.get("center")
        if not isinstance(c, list) or len(c) != 2 or not (-180 <= float(c[0]) <= 180) or not (-90 <= float(c[1]) <= 90):
            errors.append(f"[{label}] mapView.center inválido: {c}")
        if not isinstance(mv.get("zoom"), (int, float)):
            errors.append(f"[{label}] mapView.zoom inválido: {mv.get('zoom')}")
    layers = gl_obj.get("layers")
    if isinstance(layers, list):
        for lyr in layers:
            if not isinstance(lyr, dict):
                errors.append(f"[{label}] Capa inválida en layers.")
                continue
            for lreq in ("id", "name", "type", "source", "style", "metadata"):
                if lreq not in lyr:
                    errors.append(f"[{label}] Capa '{lyr.get('id')}' sin campo requerido '{lreq}'.")
            if isinstance(lyr.get("style"), dict):
                for sreq in ("fillColor", "strokeColor", "strokeWidth", "fillOpacity", "vectorStyleMode"):
                    if sreq not in lyr["style"]:
                        errors.append(f"[{label}] Estilo de capa '{lyr.get('id')}' sin '{sreq}'.")


def check_no_private_data(text: str, label: str, errors: list[str]) -> None:
    found_emails = EMAIL_RE.findall(text)
    if found_emails:
        errors.append(f"[{label}] Contiene direcciones de correo no autorizadas: {found_emails}")


def validate_logo_file(rel_path: str, label: str, errors: list[str]) -> None:
    if not rel_path.startswith("branding/logos/"):
        errors.append(f"[{label}] Ruta de logo fuera de branding/logos/: '{rel_path}'")
        return
    target = (ROOT / rel_path).resolve()
    logos_root = (ROOT / "branding" / "logos").resolve()
    if logos_root not in target.parents:
        errors.append(f"[{label}] Ruta de logo inválida: '{rel_path}'")
        return
    if not target.exists() or not target.is_file():
        errors.append(f"[{label}] No existe el archivo de logo referenciado: '{rel_path}'")
        return
    ext = target.suffix.lower()
    if ext not in ALLOWED_LOGO_EXTS:
        errors.append(f"[{label}] Formato de logo no permitido ('{ext}') en '{rel_path}'.")
        return
    sz = target.stat().st_size
    if sz == 0:
        errors.append(f"[{label}] El archivo de logo está vacío: '{rel_path}'.")
    elif sz > MAX_LOGO_BYTES:
        errors.append(f"[{label}] El archivo de logo supera 2 MB ({sz} bytes): '{rel_path}'.")
    if ext == ".svg":
        svg_txt = target.read_text(encoding="utf-8", errors="ignore").lower()
        if "<svg" not in svg_txt:
            errors.append(f"[{label}] Archivo SVG inválido (sin etiqueta <svg>): '{rel_path}'.")
        if "<script" in svg_txt or "onload=" in svg_txt or "javascript:" in svg_txt:
            errors.append(f"[{label}] Archivo SVG contiene código ejecutable prohibido: '{rel_path}'.")


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
    branding_schema_path = ROOT / "schemas" / "project-branding.schema.json"
    for sp in (proj_schema_path, atlas_schema_path, branding_schema_path):
        if not sp.exists():
            errors.append(f"Falta esquema requerido: {sp.relative_to(ROOT)}")
        else:
            schema_obj = json.loads(sp.read_text(encoding="utf-8"))
            Draft202012Validator.check_schema(schema_obj)

    if errors:
        return errors

    proj_schema = json.loads(proj_schema_path.read_text(encoding="utf-8"))
    atlas_schema = json.loads(atlas_schema_path.read_text(encoding="utf-8"))
    branding_schema = json.loads(branding_schema_path.read_text(encoding="utf-8"))
    proj_validator = Draft202012Validator(proj_schema, format_checker=checker)
    atlas_validator = Draft202012Validator(atlas_schema, format_checker=checker)
    branding_validator = Draft202012Validator(branding_schema, format_checker=checker)

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

    # 2b. Validar identidad visual local (branding/project-branding.json) y recursos comunes
    branding_path = ROOT / "branding" / "project-branding.json"
    if not branding_path.exists():
        errors.append("Falta branding/project-branding.json.")
    else:
        raw_branding = branding_path.read_text(encoding="utf-8")
        check_no_private_data(raw_branding, "branding/project-branding.json", errors)
        branding = json.loads(raw_branding)
        for verr in branding_validator.iter_errors(branding):
            loc = "/".join(str(p) for p in verr.absolute_path) or "<raíz>"
            errors.append(f"[branding/project-branding.json -> {loc}] {verr.message}")
        if branding.get("project_id") != pid:
            errors.append(
                f"[branding/project-branding.json] project_id '{branding.get('project_id')}' no coincide con project.json id '{pid}'."
            )
        if branding.get("theme_version") != THEME_VERSION:
            errors.append(
                f"[branding/project-branding.json] theme_version '{branding.get('theme_version')}' != '{THEME_VERSION}'."
            )
        pl = branding.get("project_logo")
        if isinstance(pl, dict) and pl.get("logo_path"):
            validate_logo_file(str(pl["logo_path"]), "branding.project_logo", errors)

        seen_orders: set[int] = set()
        seen_inst_ids: set[str] = set()
        for inst in branding.get("institutions", []):
            if not isinstance(inst, dict):
                continue
            iid = str(inst.get("id") or "")
            if iid in seen_inst_ids:
                errors.append(f"[branding/project-branding.json] ID de institución duplicado: '{iid}'.")
            seen_inst_ids.add(iid)
            ord_val = inst.get("order")
            if isinstance(ord_val, int):
                if ord_val in seen_orders:
                    errors.append(f"[branding/project-branding.json] Orden de presentación duplicado ({ord_val}) en '{iid}'.")
                seen_orders.add(ord_val)
            lpath = inst.get("logo_path")
            if lpath:
                validate_logo_file(str(lpath), f"branding.institutions[{iid}]", errors)

    brand_assets_dir = ROOT / "web" / "assets" / "img" / "brand"
    for req_asset in REQUIRED_BRAND_ASSETS:
        if not (brand_assets_dir / req_asset).exists():
            errors.append(f"[web/assets/img/brand] Falta recurso gráfico institucional común: {req_asset}")

    doc_visual = ROOT / "docs" / "identidad-visual.md"
    if not doc_visual.exists() or not doc_visual.read_text(encoding="utf-8").strip():
        errors.append("Falta guía requerida docs/identidad-visual.md o está vacía.")

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
        gl_src = json.loads(geolibre_path.read_text(encoding="utf-8"))
        validate_geolibre_project_obj(gl_src, "geovisor/proyecto.geolibre.json", errors)

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
        "geovisor/capas/index.json",
        "data/project.json",
        "data/project-branding.json",
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
    branding = json.loads((site_dir / "data" / "project-branding.json").read_text(encoding="utf-8"))

    # Verificar que todos los logos locales configurados fueron copiados a site/branding/logos/
    pl = branding.get("project_logo")
    if isinstance(pl, dict) and pl.get("logo_path"):
        if not (site_dir / str(pl["logo_path"])).exists():
            errors.append(f"[site] Falta archivo de logo de proyecto en salida: {pl['logo_path']}")
    for inst in branding.get("institutions", []):
        if isinstance(inst, dict) and inst.get("logo_path"):
            if not (site_dir / str(inst["logo_path"])).exists():
                errors.append(f"[site] Falta archivo de logo institucional en salida: {inst['logo_path']}")

    html_files = sorted(site_dir.rglob("*.html"))
    for hf in html_files:
        content = hf.read_text(encoding="utf-8")
        check_no_private_data(content, str(hf.relative_to(site_dir)), errors)
        collector = LinkAndMetaCollector()
        collector.feed(content)

        if collector.images_missing_alt:
            errors.append(
                f"[{hf.relative_to(site_dir)}] Imágenes sin atributo alt accesible: {collector.images_missing_alt}"
            )

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

    gl_site_obj = json.loads((site_dir / "geovisor" / "proyecto.geolibre.json").read_text(encoding="utf-8"))
    validate_geolibre_project_obj(gl_site_obj, "site/geovisor/proyecto.geolibre.json", errors)

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description="Valida fuentes o artefacto construido del proyecto.")
    parser.add_argument("--source", action="store_true", help="Valida esquemas, manifiesto y contenidos fuente.")
    parser.add_argument("--site", type=str, default=None, help="Valida el directorio del sitio generado.")
    args = parser.parse_args()

    if not args.source and not args.site:
        parser.error("Especifica --source y/o --site <directorio>.")

    all_errors: list[str] = []
    if args.source:
        src_errs = validate_source()
        all_errors.extend(src_errs)
        if not src_errs:
            print("[OK] Validación de fuentes (--source) superada sin errores.")

    if args.site:
        site_errs = validate_site((ROOT / args.site).resolve())
        all_errors.extend(site_errs)
        if not site_errs:
            print(f"[OK] Validación de sitio construido (--site {args.site}) superada sin errores.")

    if all_errors:
        print("\nSe encontraron errores de validación:", file=sys.stderr)
        for e in all_errors:
            print(f"  - {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

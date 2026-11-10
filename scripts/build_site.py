#!/usr/bin/env python3
"""
Generador estático determinista (scripts/build_site.py) para cada repositorio de iniciativa
(urbano-{id}) y para la plantilla común (clusterurbano-proyecto-template).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import shutil
import sys
import urllib.parse
from pathlib import Path
from typing import Any

from markdown_lite import render_markdown
from site_common import (
    TEMPLATE_VERSION,
    THEME_VERSION,
    SiteContext,
    badge_html,
    compute_site_context,
    esc,
    format_spanish_date,
    render_project_institutions_band,
    render_regional_institutional_band,
    render_upper_institutional_bar,
)

ROOT = Path(__file__).resolve().parent.parent


def render_link_or_pending(url: str | None, active_label: str, pending_label: str, btn_class: str = "btn btn-outline", declared_only: bool = False) -> str:
    if url and url.startswith("https://"):
        suffix = " (referencia declarada)" if declared_only else " ↗"
        return (
            f'<a class="{btn_class}" href="{html.escape(url, quote=True)}" '
            f'target="_blank" rel="noopener noreferrer">{html.escape(active_label + suffix)}</a>'
        )
    return f'<span class="btn-disabled" role="status">{html.escape(pending_label)}</span>'


def render_status_strip(manifest: dict[str, Any]) -> str:
    st = manifest["status"]
    pmv = manifest["pmv"]
    tr = st["technical_review"]
    iv = st["institutional_validation"]
    ad = st["adoption"]
    return f"""
    <section class="status-strip" aria-label="Estados independientes de la iniciativa">
      <div class="status-cell">
        <div class="status-cell-label">Alcance del PMV</div>
        <div>{badge_html(pmv.get("scope_status"))}</div>
      </div>
      <div class="status-cell">
        <div class="status-cell-label">Desarrollo</div>
        <div>{badge_html(st.get("development"))}</div>
      </div>
      <div class="status-cell">
        <div class="status-cell-label">Demostración</div>
        <div>{badge_html(st.get("demo"))}</div>
      </div>
      <div class="status-cell">
        <div class="status-cell-label">Revisión técnica</div>
        <div>{badge_html(tr.get("state"))}</div>
      </div>
      <div class="status-cell">
        <div class="status-cell-label">Validación institucional</div>
        <div>{badge_html(iv.get("state"))}</div>
      </div>
      <div class="status-cell">
        <div class="status-cell-label">Adopción</div>
        <div>{badge_html(ad.get("state"))}</div>
      </div>
    </section>
    """


def render_shell(
    *,
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    page_title: str,
    active_nav: str,
    hero_html: str,
    body_html: str,
    include_maplibre: bool = False,
) -> str:
    pid = manifest["id"]
    short_title = repo_cfg.get("short_title") or manifest["title"]
    country_name = manifest["country"]["name"]
    country_code = manifest["country"]["code"]

    robots_meta = (
        '<meta name="robots" content="noindex, nofollow">'
        if ctx.effective_mode != "canonical"
        else '<meta name="robots" content="index, follow">'
    )

    canonical_link_note = ""
    if manifest["links"].get("website"):
        w = html.escape(manifest["links"]["website"], quote=True)
        canonical_link_note = f' · <a href="{w}">Ir a la versión canónica publicada</a>'
    elif manifest["links"].get("repository"):
        r = html.escape(manifest["links"]["repository"], quote=True)
        canonical_link_note = f' · <a href="{r}" target="_blank" rel="noopener noreferrer">Repositorio canónico</a>'

    work_banner_html = ""
    if ctx.effective_mode != "canonical":
        mode_reason = (
            f" Vista generada desde {html.escape(ctx.github_repository)}."
            if ctx.github_repository
            else " Previsualización local o repositorio canónico pendiente de verificación."
        )
        work_banner_html = f"""
        <div class="work-banner" role="region" aria-label="Aviso de versión de trabajo">
          <div class="container">
            <span>Vista de trabajo (versión no canónica) · ID estable: <code>{esc(pid)}</code>.{mode_reason}</span>
            <span>Solo el repositorio canónico publica la referencia compartida del equipo{canonical_link_note}</span>
          </div>
        </div>
        """

    hub_link_html = (
        f'<a href="{html.escape(ctx.hub_url, quote=True)}">← Volver al Portal de la Comunidad Urbana</a>'
        if ctx.hub_url and ctx.hub_url.startswith("https://")
        else '<span>Portal regional: <code>clusterurbano</code> (enlace activo al publicar el hub)</span>'
    )

    upper_bar_html = render_upper_institutional_bar(
        ctx,
        hub_link_html,
        f"Comunidad Urbana Copernicus Centroamérica · <strong>{esc(country_name)} ({esc(country_code)})</strong> · ID: <code>{esc(pid)}</code>",
    )

    # La banda institucional regional se ubica al final de todas las páginas, justo encima del pie
    bottom_regional_band_html = render_regional_institutional_band(ctx, extra_class="is-footer-band")

    nav_items = [
        ("inicio", "Inicio", ctx.site_url("")),
        ("proyecto", "Proyecto", ctx.site_url("proyecto/")),
        ("aplicacion", "Geovisor (GeoLibre)", ctx.site_url("aplicacion/")),
        ("metodologia", "Metodología", ctx.site_url("metodologia/")),
        ("resultados", "Resultados y Atlas", ctx.site_url("resultados/")),
        ("colaborar", "Colaborar", ctx.site_url("colaborar/")),
    ]
    nav_lis = []
    for key, label, href in nav_items:
        cur = ' aria-current="page"' if key == active_nav else ""
        nav_lis.append(f'<li><a href="{html.escape(href, quote=True)}"{cur}>{html.escape(label)}</a></li>')

    maplibre_head = ""
    maplibre_scripts = ""
    if include_maplibre:
        maplibre_head = (
            '<link rel="stylesheet" href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" crossorigin="anonymous">'
        )
        maplibre_scripts = (
            '<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js" crossorigin="anonymous"></script>\n'
            f'  <script src="{html.escape(ctx.site_url("assets/js/geovisor.js"), quote=True)}?v=2.0.2"></script>'
        )

    updated_raw = manifest["governance"].get("content_updated_at")
    updated_label = format_spanish_date(updated_raw, "Fecha de actualización no informada")

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(page_title)} · {esc(short_title)}</title>
  <meta name="description" content="{esc(manifest['summary'])}">
  {robots_meta}
  <link rel="stylesheet" href="{html.escape(ctx.site_url('assets/css/styles.css'), quote=True)}?v=2.0.2">
  {maplibre_head}
</head>
<body>
  <a class="skip-link" href="#contenido-principal">Saltar al contenido principal</a>
  {work_banner_html}
  {upper_bar_html}
  <header class="site-header">
    <div class="container header-inner">
      <a class="brand" href="{html.escape(ctx.site_url(''), quote=True)}">
        <span class="brand-mark" aria-hidden="true">{esc(country_code)}</span>
        <span class="brand-text">
          <span class="brand-title">{esc(short_title)}</span>
          <span class="brand-subtitle">Clúster de Asentamientos Humanos · Fase II</span>
        </span>
      </a>
      <button class="nav-toggle" type="button" data-nav-toggle aria-expanded="false" aria-controls="menu-proyecto">
        Menú ☰
      </button>
      <nav id="menu-proyecto" class="site-nav" data-site-nav aria-label="Navegación de la iniciativa">
        <ul>
          {"".join(nav_lis)}
        </ul>
      </nav>
    </div>
  </header>

  {hero_html}

  <main id="contenido-principal">
    <div class="container">
      {body_html}
    </div>
  </main>

  {bottom_regional_band_html}
  <footer class="site-footer">
    <div class="container footer-grid">
      <div>
        <p class="footer-title">{esc(manifest['title'])}</p>
        <p>Identificador estable: <code>{esc(pid)}</code> · Grupos de origen: {esc(", ".join(str(g) for g in manifest["source_groups"]))} · Tema común: <code>{esc(THEME_VERSION)}</code>.</p>
        <p>Última actualización del contenido por el equipo: <strong>{esc(updated_label)}</strong>.</p>
      </div>
      <div>
        <p class="footer-title">Navegación rápida</p>
        <p>
          <a href="{html.escape(ctx.site_url('proyecto/'), quote=True)}">Ficha completa</a> ·
          <a href="{html.escape(ctx.site_url('aplicacion/'), quote=True)}">Geovisor GeoLibre</a> ·
          <a href="{html.escape(ctx.site_url('metodologia/'), quote=True)}">Metodología</a> ·
          <a href="{html.escape(ctx.site_url('resultados/'), quote=True)}">Resultados y Atlas</a> ·
          <a href="{html.escape(ctx.site_url('colaborar/'), quote=True)}">Colaborar y Logos</a>
        </p>
      </div>
      <div>
        <p class="footer-title">Transparencia documental</p>
        <p>Este sitio distingue afirmaciones declaradas en el perfil, propuestas técnicas de trabajo y datos pendientes de confirmar. Una página publicada no equivale por sí sola a validación institucional.</p>
      </div>
    </div>
  </footer>

  <script src="{html.escape(ctx.site_url('assets/js/ui.js'), quote=True)}?v=2.0.2"></script>
  {maplibre_scripts}
</body>
</html>
"""


def make_geolibre_layer_style(raw_style: dict[str, Any] | None) -> dict[str, Any]:
    s = raw_style or {}
    fill_color = str(s.get("fillColor") or "#0d9488")
    stroke_color = str(s.get("lineColor") or s.get("strokeColor") or "#115e59")
    stroke_width = float(s.get("lineWidth") or s.get("strokeWidth") or 2)
    fill_opacity = float(s.get("fillOpacity") if s.get("fillOpacity") is not None else 0.35)
    circle_radius = float(s.get("circleRadius") or 6)
    circle_color = str(s.get("circleColor") or fill_color)
    return {
        "minZoom": 0,
        "maxZoom": 24,
        "fillColor": fill_color,
        "strokeColor": stroke_color,
        "strokeWidth": stroke_width,
        "strokeWidthUnit": "pixels",
        "strokeOpacity": 1,
        "strokeDash": [],
        "strokeBlur": 0,
        "fillOpacity": fill_opacity,
        "circleRadius": circle_radius,
        "textColor": "#111827",
        "textHaloColor": "#ffffff",
        "textHaloWidth": 2,
        "textSize": 14,
        "labels": {
            "enabled": False,
            "field": "",
            "expression": "",
            "placement": "point",
            "size": 12,
            "color": "#111827",
            "haloColor": "#ffffff",
            "haloWidth": 1.5,
            "minZoom": 0,
            "maxZoom": 24,
            "allowOverlap": False,
            "anchor": "center",
            "offsetX": 0,
            "offsetY": 0,
            "rotation": 0,
            "maxWidth": 10,
            "transform": "none",
            "numberFormatEnabled": False,
            "numberDecimals": 0,
            "numberLocale": "",
            "dedupe": "off",
            "sizeExpression": "",
            "colorExpression": "",
            "opacityExpression": "",
            "visibilityExpression": "",
            "priorityExpression": "",
        },
        "extrusionEnabled": False,
        "extrusionColor": fill_color,
        "extrusionOpacity": 0.8,
        "extrusionHeightProperty": "height",
        "extrusionHeightScale": 1,
        "extrusionBase": 0,
        "extrusionBaseProperty": "",
        "extrusionBaseScale": 1,
        "extrusionFloorHeight": 0,
        "extrusionAdvancedStyleEnabled": False,
        "extrusionColorExpression": "",
        "extrusionHeightExpression": "",
        "extrusionBaseExpression": "",
        "elevation3dEnabled": False,
        "elevation3dVerticalScale": 1,
        "elevation3dOffset": 0,
        "vectorStyleMode": "single",
        "vectorStyleProperty": "",
        "vectorStyleClassCount": 5,
        "vectorStyleColorRamp": "viridis",
        "vectorStyleClassificationScheme": "equal-interval",
        "vectorStyleStops": [
            {"value": 0, "color": "#dbeafe"},
            {"value": 1, "color": fill_color},
        ],
        "vectorStyleExpression": "",
        "vectorRules": [],
        "proportionalSizeEnabled": False,
        "proportionalSizeProperty": "",
        "proportionalSizeMinValue": 0,
        "proportionalSizeMaxValue": 100,
        "proportionalSizeMinRadius": 4,
        "proportionalSizeMaxRadius": 24,
        "fillPattern": "none",
        "fillPatternColor": stroke_color,
        "fillPatternSvg": "",
        "markerEnabled": False,
        "markerShape": "circle",
        "markerColor": circle_color,
        "markerSize": 18,
        "markerSvg": "",
        "simpleStyleEnabled": False,
        "diagramType": "none",
        "diagramFields": [],
        "diagramSizeMode": "fixed",
        "diagramSize": 30,
        "diagramSizeProperty": "",
        "diagramMinZoom": 0,
        "diagramDeclutter": False,
        "pointRenderer": "single",
        "heatmapRadius": 30,
        "heatmapIntensity": 1,
        "heatmapColorRamp": "turbo",
        "heatmapWeightProperty": "",
        "clusterRadius": 50,
        "clusterMaxZoom": 14,
        "invertedFillEnabled": False,
        "lineDecoration": "none",
        "lineDecorationColor": "",
        "lineDecorationSize": 12,
        "lineDecorationSpacing": 80,
        "geometryGenerator": "none",
        "geometryGeneratorBufferDistance": 1000,
        "geometryGeneratorBufferProperty": "",
        "geometryGeneratorFillColor": "#f59e0b",
        "geometryGeneratorStrokeColor": "#b45309",
        "geometryGeneratorStrokeWidth": 2,
        "geometryGeneratorOpacity": 0.4,
        "geometryGeneratorCircleRadius": 5,
        "geometryGeneratorSizeProperty": "",
        "geometryGeneratorSizeMinValue": 0,
        "geometryGeneratorSizeMaxValue": 100,
        "geometryGeneratorSizeMinRadius": 4,
        "geometryGeneratorSizeMaxRadius": 24,
        "rasterBrightnessMin": 0,
        "rasterBrightnessMax": 1,
        "rasterSaturation": 0,
        "rasterContrast": 0,
        "rasterHueRotate": 0,
        "blendMode": "normal",
    }


def build_geolibre_project_json(
    layers_cfg: dict[str, Any],
    manifest: dict[str, Any],
    ctx: SiteContext,
) -> dict[str, Any]:
    pid = manifest["id"]
    active_layers: list[dict[str, Any]] = []
    styles_map: dict[str, Any] = {}
    legend_order: list[str] = []

    for lyr in layers_cfg.get("layers", []):
        sp = lyr.get("source_path")
        st = lyr.get("status")
        if not sp or st not in ("publicado", "en_revision"):
            continue
        lid = lyr["id"]
        resolved = sp if str(sp).startswith("https://") else ctx.full_url(str(sp))
        fmt = str(lyr.get("format") or "geojson").lower()
        layer_type = "geojson" if fmt in ("geojson", "json", "kml") else ("cog" if fmt in ("tif", "tiff", "cog") else ("pmtiles" if fmt == "pmtiles" else "raster"))
        full_style = make_geolibre_layer_style(lyr.get("style"))
        styles_map[lid] = full_style
        legend_order.append(lid)

        embedded_geojson = None
        if not str(sp).startswith("https://") and fmt in ("geojson", "json"):
            local_file = ROOT / str(sp)
            if local_file.exists() and local_file.stat().st_size <= 5 * 1024 * 1024:
                try:
                    parsed_gj = json.loads(local_file.read_text(encoding="utf-8"))
                    if isinstance(parsed_gj, dict) and parsed_gj.get("type") == "FeatureCollection":
                        embedded_geojson = parsed_gj
                except Exception:
                    embedded_geojson = None

        layer_entry: dict[str, Any] = {
            "id": lid,
            "name": lyr["title"],
            "type": layer_type,
            "source": {
                "type": "geojson" if layer_type == "geojson" else "raster",
                "url": resolved,
                "data": resolved if layer_type == "geojson" else None,
            },
            "visible": True,
            "opacity": 1,
            "style": full_style,
            "metadata": {
                "sourceUrl": resolved,
                "status": st,
                "resolution": lyr.get("resolution"),
                "caveat": lyr.get("caveat"),
            },
        }
        if embedded_geojson is not None:
            layer_entry["geojson"] = embedded_geojson
        active_layers.append(layer_entry)

    mv = layers_cfg.get("map_view", {})
    center = mv.get("center", [-84.0, 13.5])
    zoom = float(mv.get("zoom", 10))
    map_view_obj: dict[str, Any] = {
        "center": [float(center[0]), float(center[1])],
        "zoom": zoom,
        "bearing": 0,
        "pitch": 0,
    }
    if mv.get("bbox") and isinstance(mv["bbox"], list) and len(mv["bbox"]) == 4:
        map_view_obj["bbox"] = [float(x) for x in mv["bbox"]]

    return {
        "id": f"geolibre-{pid}",
        "version": "0.2.0",
        "name": f"{manifest['country']['name']} · {layers_cfg.get('title', manifest['title'])}",
        "mapView": map_view_obj,
        "basemapStyleUrl": "https://tiles.openfreemap.org/styles/positron",
        "basemapVisible": True,
        "basemapOpacity": 1,
        "blankBackgroundColor": None,
        "primaryRenderer": "maplibre",
        "layers": active_layers,
        "selectedLayerId": active_layers[0]["id"] if active_layers else None,
        "layerGroups": [],
        "styles": styles_map,
        "preferences": {
            "map": {
                "restrictBounds": False,
                "bounds": [-180, -85, 180, 85],
                "minZoom": 0,
                "maxZoom": 24,
                "maxPitch": 85,
                "renderWorldCopies": True,
                "projection": "mercator",
                "ellipsoidId": "earth",
                "scaleUnit": "metric",
                "showPointerElevation": False,
                "terrainEnabled": False,
                "coordinateFormat": "dd",
                "zoomToNewLayers": True,
            },
            "environmentVariables": [],
            "geocoding": {
                "providerId": "nominatim",
                "apiKeys": {},
            },
        },
        "legend": {
            "title": "Capas del proyecto",
            "groupByLayer": True,
            "order": legend_order,
            "overrides": {},
        },
        "comments": [],
        "metadata": {
            "project_id": pid,
            "description": manifest["summary"],
            "schema_version": manifest["schema_version"],
            "community": "Comunidad Urbana Copernicus Centroamérica",
            "referential_frame_only": len(active_layers) == 0,
            "note": mv.get("reference_note"),
            "planned_layers": [
                {
                    "id": lyr["id"],
                    "title": lyr["title"],
                    "status": lyr["status"],
                    "expected_file_hint": lyr.get("expected_file_hint"),
                    "caveat": lyr.get("caveat"),
                }
                for lyr in layers_cfg.get("layers", [])
            ],
        },
    }


def has_declared_demo_statement(manifest: dict[str, Any]) -> bool:
    for st in manifest.get("provenance", {}).get("statements", []):
        if st.get("pointer") == "/links/demo" and st.get("status") == "declarado":
            return True
    return False


def build_home_page(
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    layers_cfg: dict[str, Any],
    branding: dict[str, Any],
) -> str:
    iu = manifest["institutional_use"]
    institutions_li = "".join(f"<li>{esc(inst)}</li>" for inst in iu.get("institutions", [])) or "<li>Institución por confirmar</li>"
    limitations_li = "".join(f"<li>{esc(lim)}</li>" for lim in manifest.get("limitations", [])[:5])
    tags_spans = "".join(f'<span class="tag">{esc(t)}</span>' for t in manifest.get("tags", []))

    demo_declared_only = has_declared_demo_statement(manifest) and manifest["status"].get("demo") != "disponible"
    repo_btn = render_link_or_pending(
        manifest["links"].get("repository"),
        "Ver repositorio canónico",
        "Repositorio canónico en preparación",
        "btn btn-outline-light",
    )
    demo_btn = ""
    if manifest["links"].get("demo"):
        demo_btn = render_link_or_pending(
            manifest["links"].get("demo"),
            "Ver demostrador externo",
            "",
            "btn btn-outline-light",
            declared_only=demo_declared_only,
        )

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">{esc(manifest['country']['name'])} · {esc(manifest['territory']['label'])}</span>
          <span class="badge badge-country">Grupos de origen: {esc(', '.join(str(g) for g in manifest['source_groups']))}</span>
          {badge_html(manifest['pmv']['scope_status'], 'Alcance PMV')}
        </div>
        <h1>{esc(manifest['title'])}</h1>
        <p class="hero-lead">{esc(manifest['summary'])}</p>
        <div class="hero-actions">
          <a class="btn btn-primary" href="{html.escape(ctx.site_url('aplicacion/'), quote=True)}">Abrir Geovisor (GeoLibre)</a>
          <a class="btn btn-teal" href="{html.escape(ctx.site_url('proyecto/'), quote=True)}">Leer ficha completa</a>
          <a class="btn btn-outline-light" href="{html.escape(ctx.site_url('colaborar/'), quote=True)}">Colaborar (Fork / PR)</a>
          {repo_btn}
          {demo_btn}
        </div>
      </div>
    </section>
    """

    mv = layers_cfg.get("map_view", {})
    repo_url = (manifest["links"].get("repository") or "").rstrip("/")
    hub_base = (ctx.hub_url or "https://copernicuscentroamerica.github.io/clusterurbano/").rstrip("/")
    ejercicio_url = f"{hub_base}/ejercicio/"
    new_task_url = f"{repo_url}/issues/new?template=01-tarea-pmv.yml" if repo_url else ctx.site_url("colaborar/")
    support_url = f"{repo_url}/issues/new?template=02-bloqueo-apoyo.yml" if repo_url else ctx.site_url("colaborar/")
    pulls_url = f"{repo_url}/pulls" if repo_url else ctx.site_url("colaborar/")
    colaborar_logos_href = ctx.site_url("colaborar/") + "#anadir-actualizar-logos"

    body = f"""
    {render_status_strip(manifest)}

    <section class="section">
      <div class="card" style="border-left:4px solid var(--c-brand-blue);">
        <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:0.75rem;">
          <div>
            <span class="badge badge-ok">Trabajar en este proyecto</span>
            <h2 style="margin:0.35rem 0 0.25rem;font-size:1.2rem;">Accesos directos para participantes e instituciones</h2>
            <p style="margin:0;font-size:0.9rem;color:var(--c-text-muted);">Usa estos enlaces para incorporar avances, actualizar logos institucionales, ejecutar el ejercicio práctico (Google Colab o Google Earth Engine con la misma cuenta de Google que uses en Antigravity), registrar tareas o solicitar apoyo técnico.</p>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:0.5rem;">
            {f'<a class="btn btn-outline btn-xs" href="{html.escape(repo_url, quote=True)}" target="_blank" rel="noopener noreferrer">Repositorio oficial ↗</a>' if repo_url else ''}
            <a class="btn btn-teal btn-xs" href="{html.escape(ctx.site_url('colaborar/'), quote=True)}">Guía de incorporación</a>
            <a class="btn btn-outline btn-xs" href="{html.escape(colaborar_logos_href, quote=True)}">Añadir o actualizar logos</a>
            <a class="btn btn-primary btn-xs" href="{html.escape(ejercicio_url, quote=True)}">Ejercicio Colab / GEE ↗</a>
            <a class="btn btn-outline btn-xs" href="{html.escape(new_task_url, quote=True)}" target="_blank" rel="noopener noreferrer">Crear tarea ↗</a>
            <a class="btn btn-outline btn-xs" href="{html.escape(support_url, quote=True)}" target="_blank" rel="noopener noreferrer">Solicitar apoyo ↗</a>
            <a class="btn btn-outline btn-xs" href="{html.escape(pulls_url, quote=True)}" target="_blank" rel="noopener noreferrer">Enviar o revisar PR ↗</a>
          </div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="section-header">
        <h2>Contexto institucional y territorial</h2>
        <div class="tag-list">{tags_spans}</div>
      </div>
      <div class="grid-3">
        <article class="card">
          <span class="badge badge-declarado">Según el perfil</span>
          <h3>Problema que aborda</h3>
          <p>{esc(iu.get('problem'))}</p>
          <p><strong>Territorio:</strong> {esc(manifest['territory']['label'])}</p>
        </article>
        <article class="card">
          <span class="badge badge-declarado">Según el perfil</span>
          <h3>Instituciones y usuario principal</h3>
          <ul>{institutions_li}</ul>
          <p><strong>Usuario directo:</strong> {esc(iu.get('primary_user'), 'No indicado en el perfil')}</p>
        </article>
        <article class="card">
          <span class="badge badge-declarado">Según el perfil</span>
          <h3>Decisión pública que apoya</h3>
          <p>{esc(iu.get('decision_supported'), 'No indicado en el perfil')}</p>
          <p><strong>Beneficio esperado:</strong> {esc(iu.get('expected_benefit'), 'No indicado en el perfil')}</p>
        </article>
      </div>
    </section>

    <section class="section">
      <div class="grid-2">
        <article class="card">
          <span class="badge badge-propuesta">Alcance de trabajo</span>
          <h3>Producto Mínimo Viable (PMV) previsto</h3>
          <p>{esc(manifest['pmv'].get('description'), 'Alcance pendiente de confirmar con el equipo.')}</p>
          <div class="callout callout-muted">
            <strong>Ámbito espacial documentado</strong>
            <span>{esc(mv.get('area_declared', manifest['territory']['label']))}</span>
          </div>
          <div class="card-footer">
            <a class="btn btn-teal" href="{html.escape(ctx.site_url('proyecto/'), quote=True)}">Ver criterios de aceptación ({len(manifest['pmv'].get('acceptance_criteria', []))})</a>
            <a class="btn btn-outline" href="{html.escape(ctx.site_url('metodologia/'), quote=True)}">Ver datos y método</a>
          </div>
        </article>

        <article class="card">
          <span class="badge badge-warn">Geovisor basado en GeoLibre</span>
          <h3>Espacio de visualización geoespacial</h3>
          <p>Este repositorio incorpora un visor integrado basado en <strong>MapLibre GL JS</strong> y exporta un proyecto estándar <code>geovisor/proyecto.geolibre.json</code> (v0.2.0) compatible con <strong>GeoLibre Studio</strong> para desplegar las capas en <code>geovisor/capas/</code>.</p>
          <p><strong>Capas preconfiguradas en catálogo:</strong> {len(layers_cfg.get('layers', []))} capas previstas ({sum(1 for l in layers_cfg.get('layers', []) if l.get('status') in ('publicado', 'en_revision'))} publicadas/en revisión actualmente).</p>
          <div class="card-footer">
            <a class="btn btn-primary" href="{html.escape(ctx.site_url('aplicacion/'), quote=True)}">Explorar Geovisor →</a>
            <a class="btn btn-outline" href="{html.escape(ctx.site_url('resultados/'), quote=True)}">Contribución al Atlas</a>
          </div>
        </article>
      </div>
    </section>

    <section class="section">
      <div class="callout callout-warn">
        <strong>Limitaciones, discrepancias y cautelas documentadas</strong>
        <ul>{limitations_li}</ul>
      </div>
    </section>

    {render_project_institutions_band(ctx, branding, manifest, colaborar_href=colaborar_logos_href)}
    """

    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="Inicio",
        active_nav="inicio",
        hero_html=hero,
        body_html=body,
    )


def build_proyecto_page(
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    project_md: str,
    pmv_md: str,
    branding: dict[str, Any],
) -> str:
    ac_rows = []
    for ac in manifest["pmv"].get("acceptance_criteria", []):
        ac_rows.append(
            f"<tr><td><code>{esc(ac['id'])}</code></td>"
            f"<td>{esc(ac['description'])}</td>"
            f"<td>{badge_html(ac['status'])}</td>"
            f"<td>{esc(ac.get('evidence_required'))}</td></tr>"
        )
    ac_table = (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>ID</th><th>Criterio de aceptación</th><th>Procedencia</th><th>Evidencia requerida</th>"
        "</tr></thead><tbody>" + "".join(ac_rows) + "</tbody></table></div>"
        if ac_rows
        else "<p>Criterios de aceptación pendientes de definir.</p>"
    )

    src_map = {s["id"]: s["label"] for s in manifest["provenance"]["sources"]}
    src_rows = []
    for s in manifest["provenance"]["sources"]:
        url_cell = (
            f'<a href="{html.escape(s["url"], quote=True)}" target="_blank" rel="noopener noreferrer">Abrir referencia externa ↗</a>'
            if s.get("url")
            else "Documento del expediente técnico de la cartera"
        )
        src_rows.append(
            f"<tr><td><strong>{esc(s['label'])}</strong><br><small style='color:var(--c-text-muted);'>Código interno de trazabilidad: <code>{esc(s['id'])}</code></small></td><td>{url_cell}</td></tr>"
        )

    stmt_rows = []
    for st in manifest["provenance"]["statements"]:
        ptr = st["pointer"] or "/ (raíz)"
        sids = ", ".join(f"{sid} ({src_map.get(sid, sid)})" for sid in st.get("source_ids", [])) or "—"
        stmt_rows.append(
            f"<tr><td><code>{esc(ptr)}</code></td><td>{badge_html(st['status'])}</td>"
            f"<td>{esc(sids)}</td><td>{esc(st.get('note'), '—')}</td></tr>"
        )

    gov = manifest.get("governance", {})
    updated_label = format_spanish_date(gov.get("content_updated_at"), "Pendiente de informar")
    repo_url = (manifest["links"].get("repository") or "").rstrip("/")
    support_url = f"{repo_url}/issues/new?template=02-bloqueo-apoyo.yml" if repo_url else ctx.site_url("colaborar/")
    colaborar_logos_href = ctx.site_url("colaborar/") + "#anadir-actualizar-logos"

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">Ficha completa del proyecto</span>
          <span class="badge badge-country">{esc(manifest['id'])}</span>
        </div>
        <h1>{esc(manifest['title'])}</h1>
        <p class="hero-lead">Alcance territorial en {esc(manifest['territory']['label'])}, criterios del PMV, instituciones participantes y trazabilidad documental desde <code>project.json</code>.</p>
      </div>
    </section>
    """

    body = f"""
    {render_status_strip(manifest)}

    <section class="section">
      <div class="card">
        <h3>Gobernanza, coordinación operativa y fechas clave</h3>
        <div class="grid-3">
          <div>
            <p><strong>Instituciones participantes:</strong><br>{esc(", ".join(manifest["institutional_use"].get("institutions", [])), "Por confirmar")}</p>
            <p><strong>Responsabilidad funcional:</strong><br>Equipo técnico de la iniciativa ({esc(manifest['country']['name'])}) · Coordinación regional del Clúster Urbano.</p>
          </div>
          <div>
            <p><strong>Próximo entregable previsto:</strong><br>Capas de salida del PMV en <code>geovisor/capas/</code> y validación de criterios de aceptación.</p>
            <p><strong>Última actualización del contenido por el equipo:</strong><br><code>governance.content_updated_at</code>: <strong>{esc(updated_label)}</strong></p>
          </div>
          <div>
            <p><strong>Canal de soporte y atención técnica:</strong><br>Formulario estructurado de bloqueos e incidencias del repositorio con atención de la facilitación del clúster.</p>
            <p><a class="btn btn-teal btn-xs" href="{html.escape(support_url, quote=True)}" target="_blank" rel="noopener noreferrer">Solicitar apoyo técnico ↗</a></p>
          </div>
        </div>
      </div>
    </section>

    <section class="section">
      <div class="prose">
        {render_markdown(project_md)}
      </div>
    </section>

    <section class="section">
      <h2>Criterios de aceptación propuestos para el PMV</h2>
      <p>Estos criterios convierten el perfil en resultados verificables durante y después de la jornada; requieren acuerdo del equipo y evidencia para darse por validados.</p>
      {ac_table}
    </section>

    <section class="section">
      <div class="prose">
        {render_markdown(pmv_md)}
      </div>
    </section>

    <section class="section">
      <h2>Fuentes documentales de referencia</h2>
      <p>Documentos e insumos a partir de los cuales se estructuró el perfil inicial de la iniciativa:</p>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Documento o insumo de origen</th><th>Referencia / disponibilidad</th></tr></thead>
          <tbody>{"".join(src_rows)}</tbody>
        </table>
      </div>
      <details class="card" style="margin-top:1rem;">
        <summary style="cursor:pointer;font-weight:700;color:var(--c-brand-blue);">Ver registro técnico de procedencia por campo (JSON Pointer y códigos internos de auditoría)</summary>
        <div class="table-wrap" style="margin-top:0.85rem;">
          <table>
            <thead><tr><th>Campo (JSON Pointer)</th><th>Estado</th><th>Fuentes asociadas</th><th>Nota metodológica</th></tr></thead>
            <tbody>{"".join(stmt_rows)}</tbody>
          </table>
        </div>
      </details>
    </section>

    {render_project_institutions_band(ctx, branding, manifest, colaborar_href=colaborar_logos_href)}
    """

    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="Ficha del proyecto",
        active_nav="proyecto",
        hero_html=hero,
        body_html=body,
    )


def build_aplicacion_page(
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    layers_cfg: dict[str, Any],
    branding: dict[str, Any],
) -> str:
    pid = manifest["id"]
    mv = layers_cfg.get("map_view", {})
    grouped: dict[str, list[dict[str, Any]]] = {}
    for lyr in layers_cfg.get("layers", []):
        grp = lyr.get("group", "Capas del proyecto")
        grouped.setdefault(grp, []).append(lyr)

    groups_html: list[str] = []
    for grp_name, items in grouped.items():
        items_html: list[str] = []
        for lyr in items:
            lid = lyr["id"]
            is_ready = bool(lyr.get("source_path")) and lyr.get("status") in ("publicado", "en_revision")
            disabled_attr = "" if is_ready else " disabled"
            checked_attr = " checked" if is_ready else ""
            hint_html = (
                f'<div class="layer-item-meta">Ruta esperada para activar: <code>{esc(lyr.get("expected_file_hint"))}</code></div>'
                if not is_ready and lyr.get("expected_file_hint")
                else ""
            )
            caveat_html = (
                f'<div class="layer-item-caveat">{esc(lyr.get("caveat"))}</div>'
                if lyr.get("caveat")
                else ""
            )
            items_html.append(
                f"""
                <div class="layer-item">
                  <div class="layer-item-head">
                    <label class="layer-item-title">
                      <input type="checkbox" data-layer-toggle="{esc(lid)}"{checked_attr}{disabled_attr}>
                      <span>{esc(lyr['title'])}</span>
                    </label>
                    {badge_html(lyr.get('status', 'en_preparacion'))}
                  </div>
                  <div class="layer-item-meta">Formato: <code>{esc(lyr.get('format'))}</code> · Escala/resolución: {esc(lyr.get('resolution'), 'Por documentar')}</div>
                  {hint_html}
                  <div class="layer-item-meta" style="display:flex;align-items:center;gap:0.5rem;margin-top:0.35rem;">
                    <label for="op-{esc(lid)}">Opacidad:</label>
                    <input id="op-{esc(lid)}" type="range" min="0.1" max="1" step="0.05" value="0.55" data-layer-opacity="{esc(lid)}"{disabled_attr}>
                  </div>
                  {caveat_html}
                </div>
                """
            )
        groups_html.append(f'<div class="layer-group-title">{esc(grp_name)}</div>' + "".join(items_html))

    controls_li = "".join(f"<li>{esc(c)}</li>" for c in layers_cfg.get("planned_controls", []))
    ext_refs_html = ""
    if layers_cfg.get("external_references"):
        ext_cards = []
        for ref in layers_cfg["external_references"]:
            badge_k = "declarado" if ref.get("kind") == "referencia_declarada" else "propuesta"
            ext_cards.append(
                f"""
                <div class="card">
                  <div>{badge_html(badge_k)}</div>
                  <h3>{esc(ref['label'])}</h3>
                  <p>{esc(ref.get('note', ''))}</p>
                  <div class="card-footer">
                    <a class="btn btn-outline" href="{html.escape(ref['url'], quote=True)}" target="_blank" rel="noopener noreferrer">Abrir enlace externo ↗</a>
                  </div>
                </div>
                """
            )
        ext_refs_html = f"""
        <section class="section">
          <h2>Referencias técnicas y demostradores externos documentados</h2>
          <div class="grid-2">{"".join(ext_cards)}</div>
        </section>
        """

    effective_repo_slug = (
        ctx.github_repository
        if ctx.github_repository
        else (ctx.canonical_repository if ctx.effective_mode == "canonical" else None)
    )
    runtime_cfg = dict(layers_cfg)
    runtime_cfg["site_base_url"] = ctx.site_url("")
    runtime_cfg["repository_slug"] = effective_repo_slug
    runtime_cfg["canonical_repository_slug"] = ctx.canonical_repository
    runtime_cfg["effective_mode"] = ctx.effective_mode
    runtime_cfg["repository_branch"] = "main"
    safe_json_cfg = json.dumps(runtime_cfg, ensure_ascii=False).replace("</", "<\\/")

    repo_capas_gh_btn = ""
    target_gh_slug = effective_repo_slug or ctx.canonical_repository
    if target_gh_slug:
        gh_capas_url = f"https://github.com/{target_gh_slug}/tree/main/geovisor/capas"
        repo_capas_gh_btn = (
            f'<a class="btn btn-outline btn-xs" href="{html.escape(gh_capas_url, quote=True)}" '
            f'target="_blank" rel="noopener noreferrer">Abrir geovisor/capas/ en GitHub ↗</a>'
        )

    hero = f"""
    <section class="hero hero-compact">
      <div class="container">
        <div class="hero-eyebrow" style="margin-bottom:0.45rem;">
          <span class="badge badge-lime">Geovisor basado en GeoLibre</span>
          <span class="badge badge-country">{esc(pid)} · {esc(manifest['territory']['label'])}</span>
          {badge_html(manifest['status']['demo'], 'Estado Demo')}
        </div>
        <h1>Geovisor del proyecto y espacio de integración de capas</h1>
        <p class="hero-lead">Visor integrado sobre MapLibre GL JS y proyecto exportable <code>geovisor/proyecto.geolibre.json</code> (v0.2.0) compatible con GeoLibre Studio.</p>
      </div>
    </section>
    """

    geolibre_json_href = html.escape(ctx.site_url("geovisor/proyecto.geolibre.json"), quote=True)
    geolibre_full_url = ctx.full_url("geovisor/proyecto.geolibre.json")
    studio_open_href = (
        f"https://web.geolibre.app/?url={urllib.parse.quote(geolibre_full_url, safe='')}"
        if geolibre_full_url.startswith("https://")
        else "https://web.geolibre.app/"
    )
    colaborar_logos_href = ctx.site_url("colaborar/") + "#anadir-actualizar-logos"

    body = f"""
    <div class="callout" style="margin-top:0;margin-bottom:1rem;padding:0.75rem 1rem;">
      <strong>Nota de integridad cartográfica ({esc(mv.get('scale_label', 'Escala del perfil'))})</strong>
      <span>{esc(mv.get('reference_note'))} Los límites administrativos procedentes de fuentes abiertas (OpenStreetMap ODbL) se muestran con carácter referencial hasta su homologación institucional.</span>
    </div>

    <section class="section" id="geovisor-app">
      <div class="geovisor-shell">
        <aside class="geovisor-sidebar" aria-label="Controles y capas del geovisor">
          <div class="geovisor-tabs" role="tablist">
            <button type="button" class="geovisor-tab is-active" data-gv-tab="layers">Capas ({len(layers_cfg.get('layers', []))})</button>
            <button type="button" class="geovisor-tab" data-gv-tab="repo-folder">Carpeta repo</button>
            <button type="button" class="geovisor-tab" data-gv-tab="local">Archivo local</button>
            <button type="button" class="geovisor-tab" data-gv-tab="embed">GeoLibre</button>
          </div>

          <div class="geovisor-panel is-active" data-gv-panel="layers">
            <div class="filter-field" style="margin-bottom:0.75rem;">
              <label for="gv-basemap-select">Mapa base de referencia</label>
              <select id="gv-basemap-select">
                <option value="carto-positron">Mapa Claro Vectorial (OpenFreeMap)</option>
                <option value="osm-standard">OpenStreetMap Estándar</option>
                <option value="carto-dark">Modo Oscuro Vectorial (OpenFreeMap)</option>
                <option value="esri-imagery">Imagen Satelital (Referencia visual)</option>
              </select>
            </div>
            <label style="display:flex;align-items:center;gap:0.45rem;font-size:0.83rem;font-weight:600;margin-bottom:0.6rem;">
              <input type="checkbox" id="gv-toggle-ref-marker" checked>
              <span>Mostrar marcador de centroide referencial</span>
            </label>
            {"".join(groups_html)}
          </div>

          <div class="geovisor-panel" data-gv-panel="repo-folder">
            <h3 style="margin-top:0;font-size:1rem;color:var(--c-brand-blue);">Cargar capa desde carpeta del repositorio</h3>
            <p style="font-size:0.82rem;">Lee los archivos publicados en <code>geovisor/capas/</code> de <strong>esta vista</strong> (en una copia personal o fork lee exclusivamente tu repositorio para no mezclar capas con el repositorio oficial).</p>
            <div style="display:flex;flex-wrap:wrap;gap:0.45rem;margin-bottom:0.75rem;">
              <button type="button" id="gv-refresh-repo-folder" class="btn btn-teal btn-xs">Leer / Refrescar carpeta</button>
              {repo_capas_gh_btn}
            </div>
            <p id="gv-repo-folder-status" style="font-size:0.8rem;color:var(--c-brand-blue);font-weight:600;margin-bottom:0.6rem;">Consultando carpeta geovisor/capas/...</p>
            <div id="gv-repo-folder-list"></div>
          </div>

          <div class="geovisor-panel" data-gv-panel="local">
            <h3 style="margin-top:0;font-size:1rem;color:var(--c-brand-blue);">Inspeccionar archivo desde tu equipo (Archivo local)</h3>
            <p style="font-size:0.84rem;">Arrastra o selecciona un archivo <code>.geojson</code> o <code>.kml</code> desde tu computadora para verificar su geometría y atributos antes de subirlo a <code>geovisor/capas/</code>.</p>
            <div class="dropzone" id="gv-dropzone" tabindex="0" role="button" aria-label="Seleccionar archivo GeoJSON o KML local">
              <strong>Haz clic o arrastra aquí un .geojson / .kml</strong>
              <div style="font-size:0.78rem;margin-top:0.25rem;">WGS84 (EPSG:4326) recomendado</div>
            </div>
            <input type="file" id="gv-local-geojson-input" accept=".geojson,.json,.kml,application/geo+json,application/json" class="hidden">
            <p id="gv-local-status" style="font-size:0.82rem;color:var(--c-brand-blue);font-weight:600;">Ningún archivo temporal cargado.</p>
            <button type="button" id="gv-clear-local" class="btn btn-outline btn-xs hidden">Quitar capa temporal</button>
          </div>

          <div class="geovisor-panel" data-gv-panel="embed">
            <h3 style="margin-top:0;font-size:1rem;color:var(--c-brand-blue);">Integración con GeoLibre Studio</h3>
            <p id="geolibre-embed-notice" style="font-size:0.83rem;">Este sitio combina dos piezas complementarias: el <strong>visor integrado (MapLibre GL JS)</strong> para consulta rápida de vectores y el archivo de proyecto <code>geovisor/proyecto.geolibre.json</code> (esquema oficial v0.2.0 con <code>mapView</code>, <code>layers</code> y <code>styles</code>) para abrir la iniciativa completa en <strong>GeoLibre Studio</strong>.</p>
            <div style="display:flex;flex-direction:column;gap:0.55rem;margin-top:0.85rem;">
              <a class="btn btn-primary" href="{html.escape(studio_open_href, quote=True)}" target="_blank" rel="noopener noreferrer">Abrir proyecto en GeoLibre Studio ↗</a>
              <a class="btn btn-teal" href="{geolibre_json_href}" download="proyecto-{esc(pid)}.geolibre.json">Descargar proyecto.geolibre.json</a>
            </div>
          </div>
        </aside>

        <div class="geovisor-stage">
          <div class="geovisor-toolbar">
            <div><strong>{esc(layers_cfg.get('title', manifest['title']))}</strong> · Motor MapLibre / GeoLibre</div>
            <div class="geovisor-toolbar-actions">
              <button type="button" id="gv-open-folder-tab" class="btn btn-outline-light btn-xs">Cargar desde carpeta</button>
              <button type="button" id="gv-reset-view" class="btn btn-outline-light btn-xs">Encuadre inicial</button>
              <a class="btn btn-outline-light btn-xs" href="{geolibre_json_href}">JSON GeoLibre</a>
              <a id="btn-open-geolibre-studio" class="btn btn-primary btn-xs" href="{html.escape(studio_open_href, quote=True)}" target="_blank" rel="noopener noreferrer">Abrir en GeoLibre Studio ↗</a>
            </div>
          </div>
          <div id="geovisor-map-canvas" class="geovisor-canvas" role="region" aria-label="Mapa interactivo del proyecto"></div>
          <iframe id="geolibre-embed-iframe" class="geovisor-iframe" title="Visor GeoLibre embebido" allowfullscreen loading="lazy"></iframe>
          <div class="geovisor-statusbar">
            <span id="gv-coords-readout">Encuadre referencial inicial: Lat {mv.get('center', [0, 0])[1]:.4f} · Lon {mv.get('center', [0, 0])[0]:.4f}</span>
            <span>Ubicación referencial según perfil · Colores analíticos independientes de la marca</span>
          </div>
        </div>
      </div>
      <script id="geovisor-config-data" type="application/json">{safe_json_cfg}</script>
    </section>

    <section class="section">
      <div class="grid-2">
        <div class="card">
          <span class="badge badge-declarado">Comportamiento por tipo de archivo</span>
          <h2>Formatos admitidos en <code>geovisor/capas/</code></h2>
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>Formato</th><th>Dónde se abre</th><th>Pasos necesarios</th></tr>
              </thead>
              <tbody>
                <tr>
                  <td><code>.geojson</code>, <code>.json</code>, <code>.kml</code></td>
                  <td>Visor integrado del sitio (MapLibre) y GeoLibre Studio</td>
                  <td>Pulsar <strong>Cargar en mapa</strong> en la pestaña <em>Carpeta repo</em> (o arrastrar en <em>Archivo local</em>).</td>
                </tr>
                <tr>
                  <td><code>.geolibre.json</code></td>
                  <td>GeoLibre Studio (<code>web.geolibre.app/?url=...</code>)</td>
                  <td>Pulsar <strong>Abrir en GeoLibre Studio</strong> para restaurar encuadre (<code>mapView</code>), capas y estilos.</td>
                </tr>
                <tr>
                  <td><code>.tif</code> / <code>.tiff</code> (COG), <code>.pmtiles</code>, <code>.fgb</code>, <code>.geoparquet</code></td>
                  <td>GeoLibre Studio (<code>web.geolibre.app/?data=...</code>)</td>
                  <td>Pulsar <strong>Abrir capa en GeoLibre Studio</strong> en la pestaña <em>Carpeta repo</em> (transfiere la URL pública mediante <code>?data=</code>).</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <span class="badge badge-propuesta">Módulos funcionales previstos para el PMV</span>
          <h2>Controles y análisis especificados por el perfil</h2>
          <p>Conforme al expediente de la iniciativa, los siguientes módulos y selectores se habilitan progresivamente conforme el equipo incorpora las salidas verificadas en el repositorio:</p>
          <ul>{controls_li}</ul>
        </div>
      </div>
    </section>

    {ext_refs_html}

    {render_project_institutions_band(ctx, branding, manifest, colaborar_href=colaborar_logos_href)}
    """

    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="Geovisor GeoLibre y Aplicación",
        active_nav="aplicacion",
        hero_html=hero,
        body_html=body,
        include_maplibre=True,
    )


def build_metodologia_page(
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    metodologia_md: str,
    branding: dict[str, Any],
) -> str:
    ds_rows = []
    for ds in manifest.get("data_sources", []):
        url_part = (
            f'<br><a href="{html.escape(ds["url"], quote=True)}" target="_blank" rel="noopener noreferrer">{esc(ds["url"])}</a>'
            if ds.get("url")
            else ""
        )
        ds_rows.append(
            f"<tr><td><strong>{esc(ds['title'])}</strong>{url_part}</td>"
            f"<td>{esc(ds.get('provider'), 'Por confirmar')}</td>"
            f"<td><code>{esc(ds.get('access'))}</code></td>"
            f"<td>{badge_html(ds.get('status'))}</td>"
            f"<td>{esc(ds.get('description'), '—')}</td></tr>"
        )
    ds_table = (
        '<div class="table-wrap"><table><thead><tr>'
        "<th>Fuente o producto</th><th>Proveedor</th><th>Acceso</th><th>Procedencia</th><th>Notas</th>"
        "</tr></thead><tbody>" + "".join(ds_rows) + "</tbody></table></div>"
        if ds_rows
        else "<p>Fuentes de datos en proceso de documentación.</p>"
    )

    lim_li = "".join(f"<li>{esc(l)}</li>" for l in manifest.get("limitations", [])) or "<li>Sin limitaciones adicionales registradas.</li>"
    colaborar_logos_href = ctx.site_url("colaborar/") + "#anadir-actualizar-logos"

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">Datos, flujo técnico y cautelas</span>
          <span class="badge badge-country">{esc(manifest['id'])}</span>
        </div>
        <h1>Metodología, fuentes de datos y limitaciones</h1>
        <p class="hero-lead">Fuentes satelitales Copernicus, registros locales declarados en {esc(manifest['territory']['label'])}, secuencia metodológica y condiciones de interpretación.</p>
      </div>
    </section>
    """

    body = f"""
    <section class="section">
      <h2>Fuentes de datos estructuradas en el manifiesto</h2>
      {ds_table}
    </section>

    <section class="section">
      <div class="prose">
        {render_markdown(metodologia_md)}
      </div>
    </section>

    <section class="section">
      <div class="callout callout-warn">
        <strong>Supuestos, discrepancias y limitaciones documentadas</strong>
        <ul>{lim_li}</ul>
      </div>
    </section>

    {render_project_institutions_band(ctx, branding, manifest, colaborar_href=colaborar_logos_href)}
    """

    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="Metodología y datos",
        active_nav="metodologia",
        hero_html=hero,
        body_html=body,
    )


def build_resultados_page(
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    atlas_products: list[dict[str, Any]],
    continuidad_md: str,
    branding: dict[str, Any],
) -> str:
    outputs_li = "".join(f"<li>{esc(o)}</li>" for o in manifest.get("expected_outputs", [])) or "<li>Productos esperados por detallar.</li>"

    atlas_cards = []
    for ap in atlas_products:
        ind = ap.get("indicator", {})
        cov = ap.get("coverage", {})
        outs = ap.get("outputs", {})
        viewer_btn = render_link_or_pending(outs.get("viewer_url"), "Abrir visor del producto", "Visor del producto aún no publicado")
        dl_btn = render_link_or_pending(outs.get("download_url"), "Descargar datos", "Descarga pendiente de publicación")
        atlas_cards.append(
            f"""
            <article class="card">
              <div style="display:flex;flex-wrap:wrap;gap:0.4rem;">
                {badge_html(ap.get('publication_status'), 'Publicación')}
                {badge_html(ap.get('validation', {}).get('state'), 'Validación')}
                <span class="badge badge-country">Tipo: {esc(ap.get('product_type'))}</span>
              </div>
              <h3>{esc(ap['title'])}</h3>
              <p>{esc(ap['summary'])}</p>
              <div class="table-wrap">
                <table>
                  <tbody>
                    <tr><th>ID de producto Atlas</th><td><code>{esc(ap['id'])}</code></td></tr>
                    <tr><th>Cobertura y resolución</th><td>{esc(cov.get('label'))} · Resolución: {esc(cov.get('spatial_resolution'), 'Por confirmar')}</td></tr>
                    <tr><th>Indicador y unidad</th><td>{esc(ind.get('name'), 'Por definir')} ({esc(ind.get('unit'), 'unidad por definir')})</td></tr>
                    <tr><th>Definición y agregación</th><td>{esc(ind.get('definition'), '—')} · Agregación: {esc(ind.get('aggregation'), '—')}</td></tr>
                    <tr><th>Institución custodia</th><td>{esc(ap.get('governance', {}).get('institution'), 'Por confirmar')}</td></tr>
                    <tr><th>Condición de reutilización</th><td>{esc(ap.get('license', {}).get('reuse_note'), 'Condiciones de reutilización por confirmar')}</td></tr>
                  </tbody>
                </table>
              </div>
              <div class="card-footer">
                {viewer_btn}
                {dl_btn}
              </div>
            </article>
            """
        )

    colaborar_logos_href = ctx.site_url("colaborar/") + "#anadir-actualizar-logos"

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">Evidencias y Atlas Urbano Regional</span>
          <span class="badge badge-country">{esc(manifest['id'])}</span>
        </div>
        <h1>Resultados disponibles, productos esperados y aporte al Atlas</h1>
        <p class="hero-lead">Separación explícita entre insumos/evidencias documentales existentes y productos comprometidos como meta del PMV en {esc(manifest['territory']['label'])}.</p>
      </div>
    </section>
    """

    body = f"""
    {render_status_strip(manifest)}

    <section class="section">
      <div class="grid-2">
        <article class="card">
          <span class="badge badge-declarado">Según el perfil</span>
          <h3>Productos y entregables esperados</h3>
          <ul>{outputs_li}</ul>
        </article>
        <article class="card">
          <span class="badge badge-pendiente">Verificación independiente</span>
          <h3>Estado de evidencias operativas</h3>
          <p><strong>Revisión técnica:</strong> {esc(manifest['status']['technical_review']['state'])} (revisor: {esc(manifest['status']['technical_review'].get('reviewer'), 'pendiente')}).</p>
          <p><strong>Validación institucional:</strong> {esc(manifest['status']['institutional_validation']['state'])} (referente: {esc(manifest['status']['institutional_validation'].get('reviewer'), 'pendiente')}).</p>
          <p><strong>Adopción institucional:</strong> {esc(manifest['status']['adoption']['state'])}.</p>
          <p style="font-size:0.86rem;color:var(--c-text-muted);">Para cambiar cualquiera de estos estados a <em>validado</em> o <em>uso documentado</em>, el esquema exige registrar fecha, persona revisora y URL HTTPS de evidencia verificable.</p>
        </article>
      </div>
    </section>

    <section class="section">
      <h2>Contribución prevista al Atlas Urbano Regional</h2>
      <p>Metadatos estructurados en <code>atlas/products/</code> conforme a <code>atlas-product.schema.json</code>:</p>
      {"".join(atlas_cards) if atlas_cards else "<p>Sin fichas de Atlas registradas todavía.</p>"}
    </section>

    <section class="section">
      <div class="prose">
        {render_markdown(continuidad_md)}
      </div>
    </section>

    {render_project_institutions_band(ctx, branding, manifest, colaborar_href=colaborar_logos_href)}
    """

    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="Resultados y Atlas",
        active_nav="resultados",
        hero_html=hero,
        body_html=body,
    )


def build_colaborar_page(
    ctx: SiteContext,
    manifest: dict[str, Any],
    repo_cfg: dict[str, Any],
    branding: dict[str, Any],
) -> str:
    pid = manifest["id"]
    proposed_owner = repo_cfg.get("proposed_owner", "copernicuscentroamerica")
    proposed_repo = repo_cfg.get("proposed_repository", f"urbano-{pid}")
    confirmed_repo_url = manifest["links"].get("repository")
    canonical_slug = (
        ctx.canonical_repository
        if ctx.canonical_repository
        else f"{proposed_owner}/{proposed_repo}"
    )
    effective_slug = ctx.github_repository or canonical_slug
    repo_status_note = (
        f"Repositorio canónico verificado: <code>{esc(canonical_slug)}</code>."
        if confirmed_repo_url
        else f"Nombre propuesto sujeto a aprovisionamiento: <code>{esc(canonical_slug)}</code> (sustituye el propietario si se aloja en otra organización)."
    )

    issue_btn = render_link_or_pending(
        manifest["links"].get("issue_tracker"),
        "Abrir Issues del repositorio",
        "Formularios listos en .github/ISSUE_TEMPLATE/ (se activan al publicar el repo)",
        "btn btn-teal",
    )

    fork_cmds = f"""# 1. Crear fork personal en tu cuenta de GitHub y clonarlo localmente
gh repo fork {canonical_slug} --clone=false
git clone https://github.com/TU_USUARIO_GITHUB/{proposed_repo}.git
cd {proposed_repo}

# 2. Registrar el repositorio canónico como upstream (NO usar el portal general como upstream)
git remote add upstream https://github.com/{canonical_slug}.git
git remote -v
git fetch upstream
git switch -c feat/nueva-capa-geovisor upstream/main"""

    validate_cmds = f"""# 3. Validar fuentes, construir el sitio y comprobar enlaces internos
python3 scripts/validate.py --source
python3 scripts/build_site.py --output site
python3 scripts/validate.py --site site

# 4. Previsualizar localmente en http://localhost:8000
python3 -m http.server 8000 --directory site"""

    pr_cmds = f"""# 5. Confirmar solo los archivos modificados y enviar Pull Request al canónico
git status --short
git add project.json content/ geovisor/ branding/
git commit -m "Actualiza avances y recursos verificados de {pid}"
git push -u origin feat/nueva-capa-geovisor

gh pr create --repo {canonical_slug} --base main --head TU_USUARIO_GITHUB:feat/nueva-capa-geovisor --title "Actualiza geovisor, logos o documentación ({pid})" --body-file pr-body.md"""

    antigravity_logo_prompt = f"""He copiado los archivos de logos de las instituciones participantes del proyecto {pid} ({manifest['title']}) en la carpeta branding/logos/ de este repositorio.
Por favor:
1. Inspecciona los archivos nuevos dentro de branding/logos/ (comprueba que sean .svg o .png con proporciones naturales y peso menor a 2 MB).
2. Actualiza branding/project-branding.json conservando intacto "project_id": "{pid}" y "theme_version": "{THEME_VERSION}", y registrando cada institución en la lista "institutions" con su "id", "name", "acronym", "role", "logo_path", "alt_text" descriptivo, "url" (si aplica con https://), "order" y "aspect_hint" ("horizontal", "vertical" o "square").
3. Ejecuta python scripts/validate.py --source, python scripts/build_site.py --output site y python scripts/validate.py --site site para confirmar que toda la validación pasa sin errores.
4. Muéstrame git status y git diff branding/project-branding.json y deja lista una rama feat/logos-institucionales para enviar el Pull Request al repositorio {canonical_slug}."""

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">Colaboración GitHub, Logos y GeoLibre</span>
          <span class="badge badge-country">{esc(pid)}</span>
        </div>
        <h1>Cómo colaborar en esta iniciativa (Fork, Capas, Logos y PR)</h1>
        <p class="hero-lead">Cada iniciativa evoluciona en su propio repositorio independiente. Las personas participantes trabajan en ramas de su fork personal y proponen mejoras, capas geoespaciales o logos institucionales mediante Pull Request.</p>
        <div class="hero-actions">
          <a class="btn btn-primary" href="#anadir-actualizar-logos">Añadir o actualizar logos</a>
          <a class="btn btn-outline-light" href="#ejercicio-practico">Ejercicio práctico Colab / GEE</a>
        </div>
      </div>
    </section>
    """

    hub_base = (ctx.hub_url or "https://copernicuscentroamerica.github.io/clusterurbano/").rstrip("/")
    ejercicio_url = f"{hub_base}/ejercicio/"
    repo_url = (confirmed_repo_url or f"https://github.com/{canonical_slug}").rstrip("/")
    effective_repo_url = f"https://github.com/{effective_slug}"
    gh_logos_dir_url = f"{effective_repo_url}/tree/main/branding/logos"
    gh_branding_json_url = f"{effective_repo_url}/blob/main/branding/project-branding.json"
    gh_guide_doc_url = f"{effective_repo_url}/blob/main/docs/identidad-visual.md"

    body = f"""
    <div class="callout">
      <strong>Identidad del repositorio de esta iniciativa</strong>
      <span>{repo_status_note} El identificador <code>{esc(pid)}</code> debe permanecer intacto en <code>project.json</code> y en <code>branding/project-branding.json</code> incluso cuando trabajes en un fork personal.</span>
    </div>

    <section class="section" id="anadir-actualizar-logos">
      <article class="card" style="border-top:4px solid var(--c-accent-yellow);">
        <div style="display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;gap:0.75rem;">
          <div>
            <span class="badge badge-lime">Identidad local del proyecto</span>
            <h2 style="margin:0.35rem 0 0.2rem;color:var(--c-brand-blue);">Añadir o actualizar logos</h2>
            <p style="margin:0;font-size:0.92rem;color:var(--c-text-muted);">Procedimiento oficial para incorporar el logo del proyecto y los logos de las instituciones participantes en <code>{esc(pid)}</code> sin alterar el tema común.</p>
          </div>
          <div style="display:flex;flex-wrap:wrap;gap:0.5rem;">
            <a class="btn btn-teal btn-xs" href="{html.escape(gh_logos_dir_url, quote=True)}" target="_blank" rel="noopener noreferrer">Abrir carpeta branding/logos/ ↗</a>
            <a class="btn btn-outline btn-xs" href="{html.escape(gh_branding_json_url, quote=True)}" target="_blank" rel="noopener noreferrer">Editar branding/project-branding.json ↗</a>
            <a class="btn btn-outline btn-xs" href="{html.escape(gh_guide_doc_url, quote=True)}" target="_blank" rel="noopener noreferrer">Guía docs/identidad-visual.md ↗</a>
          </div>
        </div>

        <div class="grid-2" style="margin-top:0.85rem;">
          <div>
            <h3>Pasos para el equipo de la iniciativa</h3>
            <ol style="padding-left:1.25rem;line-height:1.65;">
              <li><strong>Abre el repositorio de tu iniciativa:</strong> trabaja sobre tu copia local clonada desde tu fork personal o abre el repositorio en GitHub.</li>
              <li><strong>Añade el archivo del logo a <code>branding/logos/</code>:</strong> prefiere formato <code>.svg</code> original o <code>.png</code> con fondo transparente (máximo 2 MB), conservando colores y proporciones oficiales.</li>
              <li><strong>Completa los datos en <code>branding/project-branding.json</code>:</strong> registra el nombre oficial (<code>name</code>), sigla (<code>acronym</code>), rol documentado (<code>role</code>), ruta (<code>logo_path</code>), texto alternativo (<code>alt_text</code>), enlace opcional (<code>url</code> con <code>https://</code>) y orden (<code>order</code>). Si una institución aún no tiene archivo de logo, deja <code>"logo_path": null</code> (nunca inventes logos con IA).</li>
              <li><strong>Comprueba la vista previa local:</strong> ejecuta <code>python3 scripts/validate.py --source</code> y <code>python3 scripts/build_site.py --output site</code>.</li>
              <li><strong>Presenta el cambio mediante una rama y un Pull Request:</strong> sube tu rama (por ejemplo, <code>feat/logos-institucionales</code>) y abre el Pull Request hacia <code>{esc(canonical_slug)}</code>.</li>
              <li><strong>Publicación tras revisión:</strong> al integrarse el PR, el sitio reconstruido de la iniciativa y la ficha del proyecto en el portal regional muestran los logos aprobados.</li>
            </ol>
          </div>

          <div>
            <h3>Prompt para Antigravity (sin editar JSON manualmente)</h3>
            <p style="font-size:0.88rem;color:var(--c-text-muted);">Coloca tus archivos de imagen en <code>branding/logos/</code> y pega esta instrucción en el chat de Antigravity para que prepare y valide toda la configuración automáticamente:</p>
            <pre id="prompt-antigravity-logos" class="code-block"><code>{html.escape(antigravity_logo_prompt)}</code></pre>
            <div style="margin-top:0.65rem;">
              <button type="button" class="btn btn-primary btn-xs" data-copy-target="prompt-antigravity-logos">Copiar prompt para Antigravity</button>
            </div>
          </div>
        </div>

        <div class="card" style="margin-top:1rem;background:#F8FAFF;" data-logo-preview-helper>
          <h3 style="margin-top:0;">Previsualizador local de logo y asistente de configuración JSON</h3>
          <div class="callout callout-warn" style="margin:0.25rem 0 0.85rem;">
            <strong>Importante sobre el funcionamiento de esta previsualización en el navegador</strong>
            <ul style="margin:0.35rem 0 0;padding-left:1.2rem;font-size:0.85rem;">
              <li><strong>Seleccionar y previsualizar un archivo local aquí no significa que ya esté publicado</strong> en el sitio oficial ni en GitHub.</li>
              <li>Esta herramienta permite comprobar las proporciones del logo en su tarjeta y <strong>descargar o copiar el bloque JSON preparado</strong> para incorporarlo en <code>branding/project-branding.json</code>.</li>
              <li>La publicación permanente debe seguir siempre el mecanismo de escritura autenticado y revisión del repositorio (commit en rama + Pull Request).</li>
              <li>Este sitio público es estático y <strong>no contiene ni solicita credenciales de escritura</strong>.</li>
            </ul>
          </div>

          <div class="grid-2">
            <div style="display:flex;flex-direction:column;gap:0.65rem;">
              <div class="filter-field">
                <label for="logo-file-inp">1. Seleccionar archivo local (.svg o .png) para previsualizar</label>
                <input id="logo-file-inp" type="file" accept=".svg,.png,.webp,.jpg,.jpeg,image/svg+xml,image/png" data-logo-file-input>
              </div>
              <div class="filter-field">
                <label for="logo-inst-name">2. Nombre oficial de la institución</label>
                <input id="logo-inst-name" type="text" placeholder="Ej. Ministerio de Vivienda y Ordenamiento Territorial" value="{esc((manifest['institutional_use'].get('institutions') or ['Institución participante'])[0])}" data-logo-inst-name>
              </div>
              <div style="display:grid;grid-template-columns:1fr 1fr;gap:0.65rem;">
                <div class="filter-field">
                  <label for="logo-inst-acr">Sigla (opcional)</label>
                  <input id="logo-inst-acr" type="text" placeholder="Ej. MIVIOT" data-logo-inst-acronym>
                </div>
                <div class="filter-field">
                  <label for="logo-inst-ord">Orden de presentación</label>
                  <input id="logo-inst-ord" type="number" min="1" max="50" value="1" data-logo-inst-order>
                </div>
              </div>
              <div class="filter-field">
                <label for="logo-inst-role">Rol o agrupación documentada</label>
                <input id="logo-inst-role" type="text" value="Institución participante del proyecto" data-logo-inst-role>
              </div>
              <div class="filter-field">
                <label for="logo-inst-url">Enlace institucional opcional (https://...)</label>
                <input id="logo-inst-url" type="url" placeholder="https://..." data-logo-inst-url>
              </div>
            </div>

            <div style="display:flex;flex-direction:column;gap:0.75rem;">
              <div>
                <strong style="font-size:0.82rem;color:var(--c-brand-blue);display:block;margin-bottom:0.35rem;">Vista previa local de la tarjeta institucional:</strong>
                <div class="inst-proyecto-card" style="display:flex;align-items:center;gap:0.75rem;padding:0.65rem 0.85rem;background:#F9FAFE;border:1px solid #D5DDF0;border-radius:8px;">
                  <div class="inst-proyecto-logo-box is-horizontal" data-logo-preview-box style="height:48px;min-width:72px;max-width:130px;display:flex;align-items:center;justify-content:center;padding:0.25rem 0.5rem;background:#FFFFFF;border:1px solid #E4EAF7;border-radius:6px;flex-shrink:0;">
                    <img src="{html.escape(ctx.site_url('assets/img/brand/logo-copernicus-lac-chile.png'), quote=True)}" alt="Previsualización local del logo seleccionado" height="36" style="max-height:36px;max-width:118px;width:auto;height:auto;object-fit:contain;display:block;" data-logo-preview-img>
                  </div>
                  <div style="min-width:0;">
                    <div class="inst-proyecto-text-head" style="margin-bottom:0.2rem;">
                      <span class="inst-proyecto-acronym hidden" data-logo-preview-acronym>SIGLA</span>
                    </div>
                    <p class="inst-proyecto-name" data-logo-preview-name>{esc((manifest['institutional_use'].get('institutions') or ['Institución participante'])[0])}</p>
                    <p class="inst-proyecto-role" data-logo-preview-role>Institución participante del proyecto</p>
                  </div>
                </div>
              </div>

              <div>
                <strong style="font-size:0.82rem;color:var(--c-brand-blue);display:block;margin-bottom:0.35rem;">Entrada generada para <code>branding/project-branding.json</code>:</strong>
                <pre id="logo-json-snippet" class="code-block" style="margin:0;"><code data-logo-json-output></code></pre>
                <div style="display:flex;flex-wrap:wrap;gap:0.5rem;margin-top:0.55rem;">
                  <button type="button" class="btn btn-outline btn-xs" data-copy-target="logo-json-snippet">Copiar bloque JSON</button>
                  <button type="button" class="btn btn-teal btn-xs" data-logo-download-json>Descargar bloque (.json)</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </article>
    </section>

    <section class="section" id="ejercicio-practico">
      <article class="card" style="border-left:4px solid var(--c-brand-blue);">
        <span class="badge badge-ok">Ejercicio guiado de extremo a extremo</span>
        <h2>Ejercicio práctico: Mancha Urbana con Sentinel-2 (Google Colab + Google Earth Engine + Antigravity)</h2>
        <p>¿Es tu primera vez contribuyendo al proyecto? En el portal regional dispones de un ejercicio completo paso a paso para clasificar el área construida (<em>built-up</em>) con imágenes <strong>Copernicus Sentinel-2 L2A</strong> y un modelo <strong>Random Forest</strong> entrenado con etiquetas automáticas de edificios y red vial, usando la <strong>misma cuenta de Google</strong> que utilizas en Antigravity:</p>
        <ul>
          <li><strong>Guía A — Google Colab:</strong> ejecuta el cuaderno interactivo <code>mancha_urbana_sentinel2_vmod01.ipynb</code> en la nube sin instalar paquetes locales y descarga <code>probabilidad.tif</code>, <code>construido.tif</code>, <code>resumen.csv</code> y el polígono vectorial <code>.geojson</code>.</li>
          <li><strong>Guía B — Google Earth Engine (GEE):</strong> replica el flujo equivalente sobre el catálogo <code>COPERNICUS/S2_SR_HARMONIZED</code> y <code>ee.Classifier.smileRandomForest</code> para escalar a series multianuales y exportar directamente a <code>EPSG:4326</code>.</li>
          <li><strong>Integración con Antigravity:</strong> coloca los productos resultantes en <code>geovisor/capas/</code>, actualiza la narrativa en <code>content/</code> y envía tu Pull Request para revisión del equipo.</li>
        </ul>
        <div class="card-footer">
          <a class="btn btn-primary" href="{html.escape(ejercicio_url, quote=True)}">Ir al ejercicio guiado (Colab + GEE + Antigravity) →</a>
          <a class="btn btn-teal" href="{html.escape(ctx.site_url('aplicacion/'), quote=True)}">Abrir Geovisor de {esc(pid)}</a>
          <a class="btn btn-outline" href="{html.escape(repo_url + '/pulls', quote=True)}" target="_blank" rel="noopener noreferrer">Ver Pull Requests del proyecto ↗</a>
        </div>
      </article>
    </section>

    <section class="section">
      <div class="grid-2">
        <article class="card">
          <span class="badge badge-propuesta">Flujo A · Recomendado para participantes</span>
          <h3>1. Fork personal, clonación y rama descriptiva</h3>
          <p>Crea o reutiliza el fork en tu cuenta personal, configura <code>origin</code> (tu fork) y <code>upstream</code> (el repositorio canónico del equipo), y crea una rama con nombre descriptivo de tu tarea:</p>
          <pre id="cmd-fork" class="code-block"><code>{html.escape(fork_cmds)}</code></pre>
          <div class="card-footer">
            <button type="button" class="btn btn-outline btn-xs" data-copy-target="cmd-fork">Copiar comandos</button>
          </div>
        </article>

        <article class="card">
          <span class="badge badge-ok">Verificación local reproducible</span>
          <h3>2. Validar y previsualizar antes de subir cambios</h3>
          <p>Ejecuta siempre los tres comandos comunes antes de confirmar tu rama:</p>
          <pre id="cmd-val" class="code-block"><code>{html.escape(validate_cmds)}</code></pre>
          <div class="card-footer">
            <button type="button" class="btn btn-outline btn-xs" data-copy-target="cmd-val">Copiar comandos</button>
          </div>
        </article>
      </div>
    </section>

    <section class="section">
      <article class="card">
        <span class="badge badge-declarado">Despliegue de capas en el Geovisor GeoLibre</span>
        <h3>Cómo publicar una nueva capa geoespacial del equipo</h3>
        <ol>
          <li>Verifica que la capa tenga CRS <code>EPSG:4326</code> (WGS84), topología limpia, tabla de atributos documentada, autorización de publicación y ausencia de datos personales o prediales restringidos (puedes inspeccionarla antes en la pestaña <strong>Archivo local</strong> del geovisor).</li>
          <li>Coloca el archivo en <code>geovisor/capas/</code>:
            <ul>
              <li><code>.geojson</code>, <code>.json</code> y <code>.kml</code> se cargan directamente en el <strong>visor integrado (MapLibre)</strong> desde la pestaña <strong>Carpeta repo</strong>.</li>
              <li><code>.geolibre.json</code> abre el proyecto completo con estilos en <strong>GeoLibre Studio</strong> (<code>?url=...</code>).</li>
              <li><code>.tif</code> (COG), <code>.pmtiles</code>, <code>.fgb</code> y <code>.geoparquet</code> transfieren automáticamente su URL a <strong>GeoLibre Studio</strong> mediante <code>?data=...</code>.</li>
            </ul>
          </li>
          <li>Para dejar una capa activa por defecto al abrir el visor, edita <code>geovisor/layers.json</code>: coloca <code>geovisor/capas/tu_capa.geojson</code> en <code>source_path</code> y cambia <code>status</code> a <code>"en_revision"</code> o <code>"publicado"</code>.</li>
          <li>Ejecuta <code>python3 scripts/build_site.py --output site</code>: el generador actualizará automáticamente <code>site/geovisor/proyecto.geolibre.json</code> (v0.2.0) y activará el control en el Geovisor.</li>
        </ol>
      </article>
    </section>

    <section class="section">
      <div class="grid-2">
        <article class="card">
          <h3>3. Enviar Pull Request y dar seguimiento a la revisión</h3>
          <pre id="cmd-pr" class="code-block"><code>{html.escape(pr_cmds)}</code></pre>
          <p style="font-size:0.84rem;color:var(--c-text-muted);margin-top:0.65rem;">Tras abrir el Pull Request, GitHub Actions ejecuta automáticamente el validador. Si un chequeo aparece en rojo o la persona revisora solicita ajustes, corrige en tu misma rama y ejecuta <code>git push</code>: el PR se actualizará sin crear uno nuevo.</p>
          <div class="card-footer">
            <button type="button" class="btn btn-outline btn-xs" data-copy-target="cmd-pr">Copiar comandos</button>
          </div>
        </article>

        <article class="card">
          <h3>4. Registro de tareas, bloqueos y revisiones</h3>
          <p>Este repositorio incluye cuatro formularios estructurados en <code>.github/ISSUE_TEMPLATE/</code>:</p>
          <ul>
            <li><strong>Tarea del PMV:</strong> resultado concreto, criterio de aceptación y fecha objetivo propuesta.</li>
            <li><strong>Bloqueo o solicitud de apoyo:</strong> dificultad técnica o de datos y ayuda requerida (atendido por la facilitación técnica del clúster).</li>
            <li><strong>Solicitud de revisión:</strong> enlace a evidencia para revisión técnica o validación.</li>
            <li><strong>Contribución al Atlas:</strong> revisión de metadatos antes de pasar a publicado.</li>
          </ul>
          <div class="card-footer">
            {issue_btn}
          </div>
        </article>
      </div>
    </section>

    {render_project_institutions_band(ctx, branding, manifest)}
    """

    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="Colaborar",
        active_nav="colaborar",
        hero_html=hero,
        body_html=body,
    )


def build_404_page(ctx: SiteContext, manifest: dict[str, Any], repo_cfg: dict[str, Any]) -> str:
    hero = f"""
    <section class="hero">
      <div class="container">
        <h1>Página no encontrada (404)</h1>
        <p class="hero-lead">La ruta solicitada no existe dentro del sitio de <strong>{esc(manifest['title'])}</strong>.</p>
        <div class="hero-actions">
          <a class="btn btn-primary" href="{html.escape(ctx.site_url(''), quote=True)}">Volver a la portada de la iniciativa</a>
          <a class="btn btn-outline-light" href="{html.escape(ctx.site_url('aplicacion/'), quote=True)}">Ir al Geovisor GeoLibre</a>
        </div>
      </div>
    </section>
    """
    body = """
    <section class="section">
      <p>Comprueba la dirección o utiliza el menú superior para recorrer la ficha del proyecto, la metodología, los resultados o la guía de colaboración.</p>
    </section>
    """
    return render_shell(
        ctx=ctx,
        manifest=manifest,
        repo_cfg=repo_cfg,
        page_title="404 Página no encontrada",
        active_nav="",
        hero_html=hero,
        body_html=body,
    )


def write_deterministic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Construye el sitio estático de la iniciativa.")
    parser.add_argument("--output", type=str, default="site", help="Directorio de salida (por defecto: site).")
    parser.add_argument("--base-path", type=str, default=None, help="Prefijo explícito de ruta base (ej. / o /prueba-fork/).")
    parser.add_argument("--origin", type=str, default=None, help="Origen explícito HTTPS para generación de URLs absolutas.")
    args = parser.parse_args()

    if (ROOT / "data" / "projects.registry.json").exists():
        print("Error: directorio ambiguo (contiene data/projects.registry.json).", file=sys.stderr)
        return 1

    repo_cfg = json.loads((ROOT / "repo.config.json").read_text(encoding="utf-8"))
    manifest = json.loads((ROOT / "project.json").read_text(encoding="utf-8"))
    layers_cfg = json.loads((ROOT / "geovisor" / "layers.json").read_text(encoding="utf-8"))
    branding_path = ROOT / "branding" / "project-branding.json"
    if branding_path.exists():
        branding = json.loads(branding_path.read_text(encoding="utf-8"))
    else:
        branding = {
            "schema_version": "1.0.0",
            "project_id": manifest["id"],
            "theme_version": THEME_VERSION,
            "updated_at": "2026-11-10",
            "project_logo": None,
            "institutions": [
                {
                    "id": f"inst-{idx}",
                    "name": nm,
                    "acronym": None,
                    "role": "Institución declarada en el perfil",
                    "logo_path": None,
                    "alt_text": f"Institución participante: {nm}",
                    "url": None,
                    "order": idx,
                    "aspect_hint": "auto",
                }
                for idx, nm in enumerate(manifest.get("institutional_use", {}).get("institutions", []), start=1)
            ],
        }

    project_md = (ROOT / "content" / "project.md").read_text(encoding="utf-8")
    metodologia_md = (ROOT / "content" / "metodologia.md").read_text(encoding="utf-8")
    pmv_md = (ROOT / "content" / "pmv.md").read_text(encoding="utf-8")
    continuidad_md = (ROOT / "content" / "continuidad.md").read_text(encoding="utf-8")

    atlas_products: list[dict[str, Any]] = []
    atlas_dir = ROOT / "atlas" / "products"
    if atlas_dir.exists():
        for ap_file in sorted(atlas_dir.glob("*.json")):
            atlas_products.append(json.loads(ap_file.read_text(encoding="utf-8")))

    explicit_bp = args.base_path if args.base_path is not None else os.environ.get("SITE_BASE_PATH")
    ctx = compute_site_context(
        canonical_repo_url_or_slug=manifest["links"].get("repository"),
        explicit_base_path=explicit_bp,
        explicit_origin=args.origin,
        hub_url=repo_cfg.get("hub_url"),
    )

    out_dir = (ROOT / args.output).resolve()
    if out_dir == ROOT:
        print("Error: --output no puede ser la raíz del repositorio.", file=sys.stderr)
        return 1
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Copiar recursos estáticos del tema común
    shutil.copytree(ROOT / "web" / "assets", out_dir / "assets")

    # Copiar logos propios de la iniciativa desde branding/logos/ hacia site/branding/logos/
    logos_src_dir = ROOT / "branding" / "logos"
    logos_out_dir = out_dir / "branding" / "logos"
    logos_out_dir.mkdir(parents=True, exist_ok=True)
    allowed_logo_exts = {".svg", ".png", ".webp", ".jpg", ".jpeg"}
    if logos_src_dir.exists():
        for lf in sorted(logos_src_dir.iterdir()):
            if lf.is_file() and lf.suffix.lower() in allowed_logo_exts:
                shutil.copy2(lf, logos_out_dir / lf.name)

    # Generar proyecto.geolibre.json actualizado y copiar capas públicas si existen
    geolibre_obj = build_geolibre_project_json(layers_cfg, manifest, ctx)
    write_deterministic(
        out_dir / "geovisor" / "layers.json",
        json.dumps(layers_cfg, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    write_deterministic(
        out_dir / "geovisor" / "proyecto.geolibre.json",
        json.dumps(geolibre_obj, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    data_layers_dir = ROOT / "geovisor" / "data"
    if data_layers_dir.exists():
        (out_dir / "geovisor" / "data").mkdir(parents=True, exist_ok=True)
        for f in sorted(data_layers_dir.iterdir()):
            if f.is_file() and f.name != ".gitkeep":
                shutil.copy2(f, out_dir / "geovisor" / "data" / f.name)

    # Indexar y publicar la carpeta geovisor/capas/ (formatos compatibles con GeoLibre)
    geolibre_exts = {".geojson", ".json", ".kml", ".pmtiles", ".fgb", ".tif", ".tiff", ".parquet", ".geoparquet"}
    capas_src_dir = ROOT / "geovisor" / "capas"
    capas_out_dir = out_dir / "geovisor" / "capas"
    capas_out_dir.mkdir(parents=True, exist_ok=True)
    indexed_files: list[dict[str, Any]] = []
    if capas_src_dir.exists():
        for f in sorted(capas_src_dir.iterdir()):
            if not f.is_file() or f.name in (".gitkeep", "README.md", "index.json"):
                continue
            if f.suffix.lower() in geolibre_exts or f.name.lower().endswith(".geolibre.json"):
                shutil.copy2(f, capas_out_dir / f.name)
                indexed_files.append(
                    {
                        "name": f.name,
                        "path": f"geovisor/capas/{f.name}",
                        "format": "geolibre" if f.name.lower().endswith(".geolibre.json") else f.suffix.lower().lstrip("."),
                        "size_bytes": f.stat().st_size,
                    }
                )
    effective_repo_slug = (
        ctx.github_repository
        if ctx.github_repository
        else (ctx.canonical_repository if ctx.effective_mode == "canonical" else None)
    )
    write_deterministic(
        capas_out_dir / "index.json",
        json.dumps(
            {
                "folder": "geovisor/capas",
                "project_id": manifest["id"],
                "repository": effective_repo_slug,
                "canonical_repository": ctx.canonical_repository,
                "effective_mode": ctx.effective_mode,
                "files": indexed_files,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
    )

    # Exportar JSONs públicos seleccionados
    write_deterministic(
        out_dir / "data" / "project.json",
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    write_deterministic(
        out_dir / "data" / "project-branding.json",
        json.dumps(branding, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    write_deterministic(
        out_dir / "data" / "atlas-products.json",
        json.dumps(atlas_products, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    build_meta = {
        "project_id": manifest["id"],
        "schema_version": manifest["schema_version"],
        "template_version": TEMPLATE_VERSION,
        "theme_version": THEME_VERSION,
        "repo_kind": repo_cfg.get("repo_kind"),
        "base_path": ctx.base_path,
        "origin": ctx.origin,
        "effective_mode": ctx.effective_mode,
        "canonical_repository": ctx.canonical_repository,
    }
    write_deterministic(
        out_dir / "data" / "build-meta.json",
        json.dumps(build_meta, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )

    # Generar páginas HTML estáticas
    write_deterministic(out_dir / "index.html", build_home_page(ctx, manifest, repo_cfg, layers_cfg, branding))
    write_deterministic(out_dir / "proyecto" / "index.html", build_proyecto_page(ctx, manifest, repo_cfg, project_md, pmv_md, branding))
    write_deterministic(out_dir / "aplicacion" / "index.html", build_aplicacion_page(ctx, manifest, repo_cfg, layers_cfg, branding))
    write_deterministic(out_dir / "metodologia" / "index.html", build_metodologia_page(ctx, manifest, repo_cfg, metodologia_md, branding))
    write_deterministic(out_dir / "resultados" / "index.html", build_resultados_page(ctx, manifest, repo_cfg, atlas_products, continuidad_md, branding))
    write_deterministic(out_dir / "colaborar" / "index.html", build_colaborar_page(ctx, manifest, repo_cfg, branding))
    write_deterministic(out_dir / "404.html", build_404_page(ctx, manifest, repo_cfg))

    print(
        f"[OK] Sitio construido para '{manifest['id']}' en {out_dir} "
        f"(base_path='{ctx.base_path}', modo='{ctx.effective_mode}', tema='{THEME_VERSION}')."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

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
from pathlib import Path
from typing import Any

from markdown_lite import render_markdown
from site_common import (
    TEMPLATE_VERSION,
    SiteContext,
    badge_html,
    compute_site_context,
    esc,
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
            f'  <script src="{html.escape(ctx.site_url("assets/js/geovisor.js"), quote=True)}"></script>'
        )

    updated_label = manifest["governance"].get("content_updated_at") or "Fecha de actualización no informada"

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(page_title)} · {esc(short_title)}</title>
  <meta name="description" content="{esc(manifest['summary'])}">
  {robots_meta}
  <link rel="stylesheet" href="{html.escape(ctx.site_url('assets/css/styles.css'), quote=True)}">
  {maplibre_head}
</head>
<body>
  <a class="skip-link" href="#contenido-principal">Saltar al contenido principal</a>
  {work_banner_html}
  <div class="topbar">
    <div class="container">
      <div>{hub_link_html}</div>
      <div>Comunidad Urbana Copernicus Centroamérica · <strong>{esc(country_name)} ({esc(country_code)})</strong> · ID: <code>{esc(pid)}</code></div>
    </div>
  </div>
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

  <footer class="site-footer">
    <div class="container footer-grid">
      <div>
        <p class="footer-title">{esc(manifest['title'])}</p>
        <p>Identificador estable: <code>{esc(pid)}</code> · Grupos de origen: {esc(", ".join(str(g) for g in manifest["source_groups"]))}.</p>
        <p>Estado de actualización del contenido: {esc(updated_label)}.</p>
      </div>
      <div>
        <p class="footer-title">Navegación rápida</p>
        <p>
          <a href="{html.escape(ctx.site_url('proyecto/'), quote=True)}">Ficha completa</a> ·
          <a href="{html.escape(ctx.site_url('aplicacion/'), quote=True)}">Geovisor GeoLibre</a> ·
          <a href="{html.escape(ctx.site_url('metodologia/'), quote=True)}">Metodología</a> ·
          <a href="{html.escape(ctx.site_url('resultados/'), quote=True)}">Resultados y Atlas</a> ·
          <a href="{html.escape(ctx.site_url('colaborar/'), quote=True)}">Colaborar (Fork/PR)</a>
        </p>
      </div>
      <div>
        <p class="footer-title">Transparencia documental</p>
        <p>Este sitio distingue afirmaciones declaradas en el perfil, propuestas técnicas de trabajo y datos pendientes de confirmar. Una página publicada no equivale por sí sola a validación institucional.</p>
      </div>
    </div>
  </footer>

  <script src="{html.escape(ctx.site_url('assets/js/ui.js'), quote=True)}"></script>
  {maplibre_scripts}
</body>
</html>
"""


def build_geolibre_project_json(
    layers_cfg: dict[str, Any],
    manifest: dict[str, Any],
    ctx: SiteContext,
) -> dict[str, Any]:
    pid = manifest["id"]
    sources: dict[str, Any] = {}
    active_layers: list[dict[str, Any]] = []

    for lyr in layers_cfg.get("layers", []):
        sp = lyr.get("source_path")
        st = lyr.get("status")
        if not sp or st not in ("publicado", "en_revision"):
            continue
        lid = lyr["id"]
        resolved = sp if str(sp).startswith("https://") else ctx.full_url(str(sp))
        sources[lid] = {
            "type": "geojson" if lyr.get("format") == "geojson" else "raster",
            "url": resolved,
        }
        active_layers.append(
            {
                "id": lid,
                "name": lyr["title"],
                "source": lid,
                "status": st,
                "visible": True,
                "style": lyr.get("style", {}),
            }
        )

    return {
        "version": "1.0.0",
        "id": f"geolibre-{pid}",
        "name": f"{manifest['country']['name']} · {layers_cfg.get('title', manifest['title'])}",
        "description": manifest["summary"],
        "metadata": {
            "project_id": pid,
            "schema_version": manifest["schema_version"],
            "community": "Comunidad Urbana Copernicus Centroamérica",
            "referential_frame_only": len(active_layers) == 0,
            "note": layers_cfg.get("map_view", {}).get("reference_note"),
        },
        "map": {
            "engine": "maplibre",
            "center": layers_cfg.get("map_view", {}).get("center", [-84.0, 13.5]),
            "zoom": layers_cfg.get("map_view", {}).get("zoom", 10),
            "bearing": 0,
            "pitch": 0,
            "basemap": "carto-positron",
        },
        "sources": sources,
        "layers": active_layers,
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
    }


def has_declared_demo_statement(manifest: dict[str, Any]) -> bool:
    for st in manifest.get("provenance", {}).get("statements", []):
        if st.get("pointer") == "/links/demo" and st.get("status") == "declarado":
            return True
    return False


def build_home_page(ctx: SiteContext, manifest: dict[str, Any], repo_cfg: dict[str, Any], layers_cfg: dict[str, Any]) -> str:
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
          <span class="badge badge-lime">{esc(manifest['country']['name'])}</span>
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
    body = f"""
    {render_status_strip(manifest)}

    <section class="section">
      <div class="section-header">
        <h2> Contexto institucional y territorial</h2>
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
          <p>Este repositorio incorpora un geovisor interactivo basado en <strong>GeoLibre / MapLibre GL JS</strong> configurado en <code>geovisor/proyecto.geolibre.json</code> y <code>geovisor/layers.json</code> para desplegar las capas generadas por el equipo.</p>
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


def build_proyecto_page(ctx: SiteContext, manifest: dict[str, Any], repo_cfg: dict[str, Any], project_md: str, pmv_md: str) -> str:
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

    src_rows = []
    for s in manifest["provenance"]["sources"]:
        url_cell = (
            f'<a href="{html.escape(s["url"], quote=True)}" target="_blank" rel="noopener noreferrer">Enlace externo ↗</a>'
            if s.get("url")
            else "Documento del expediente interno"
        )
        src_rows.append(
            f"<tr><td><code>{esc(s['id'])}</code></td><td>{esc(s['label'])}</td><td>{url_cell}</td></tr>"
        )

    stmt_rows = []
    for st in manifest["provenance"]["statements"]:
        ptr = st["pointer"] or "/ (raíz)"
        sids = ", ".join(st.get("source_ids", [])) or "—"
        stmt_rows.append(
            f"<tr><td><code>{esc(ptr)}</code></td><td>{badge_html(st['status'])}</td>"
            f"<td><code>{esc(sids)}</code></td><td>{esc(st.get('note'), '—')}</td></tr>"
        )

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">Ficha completa del proyecto</span>
          <span class="badge badge-country">{esc(manifest['id'])}</span>
        </div>
        <h1>Alcance, criterios del PMV y trazabilidad documental</h1>
        <p class="hero-lead">Información pública estructurada desde el perfil de la iniciativa y su manifiesto canónico <code>project.json</code>.</p>
      </div>
    </section>
    """

    body = f"""
    {render_status_strip(manifest)}

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
      <h2>Fuentes documentales y registro de procedencia</h2>
      <div class="grid-2">
        <div>
          <h3>Fuentes registradas</h3>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Código</th><th>Documento original</th><th>Referencia</th></tr></thead>
              <tbody>{"".join(src_rows)}</tbody>
            </table>
          </div>
        </div>
        <div>
          <h3>Declaraciones de procedencia por campo</h3>
          <div class="table-wrap">
            <table>
              <thead><tr><th>Campo</th><th>Estado</th><th>Fuentes</th><th>Nota</th></tr></thead>
              <tbody>{"".join(stmt_rows)}</tbody>
            </table>
          </div>
        </div>
      </div>
    </section>
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


def build_aplicacion_page(ctx: SiteContext, manifest: dict[str, Any], repo_cfg: dict[str, Any], layers_cfg: dict[str, Any]) -> str:
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

    runtime_cfg = dict(layers_cfg)
    runtime_cfg["site_base_url"] = ctx.site_url("")
    safe_json_cfg = json.dumps(runtime_cfg, ensure_ascii=False).replace("</", "<\\/")

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">Geovisor basado en GeoLibre</span>
          <span class="badge badge-country">{esc(pid)}</span>
          {badge_html(manifest['status']['demo'], 'Estado Demo')}
        </div>
        <h1>Geovisor del proyecto y espacio de integración de capas</h1>
        <p class="hero-lead">Visualizador construido sobre MapLibre GL JS y sincronizado con el archivo de proyecto <code>geovisor/proyecto.geolibre.json</code> para desplegar las capas generadas por la iniciativa sin simular resultados inexistentes.</p>
      </div>
    </section>
    """

    geolibre_json_href = html.escape(ctx.site_url("geovisor/proyecto.geolibre.json"), quote=True)

    body = f"""
    <div class="callout">
      <strong>Nota de integridad cartográfica ({esc(mv.get('scale_label', 'Escala del perfil'))})</strong>
      <span>{esc(mv.get('reference_note'))} Mientras una capa permanezca <em>En preparación</em>, su interruptor se mantiene desactivado y no se dibujan geometrías ficticias.</span>
    </div>

    <section class="section" id="geovisor-app">
      <div class="geovisor-shell">
        <aside class="geovisor-sidebar" aria-label="Controles y capas del geovisor">
          <div class="geovisor-tabs" role="tablist">
            <button type="button" class="geovisor-tab is-active" data-gv-tab="layers">Capas ({len(layers_cfg.get('layers', []))})</button>
            <button type="button" class="geovisor-tab" data-gv-tab="local">Probar GeoJSON</button>
            <button type="button" class="geovisor-tab" data-gv-tab="embed">GeoLibre App</button>
          </div>

          <div class="geovisor-panel is-active" data-gv-panel="layers">
            <div class="filter-field" style="margin-bottom:0.75rem;">
              <label for="gv-basemap-select">Mapa base de referencia</label>
              <select id="gv-basemap-select">
                <option value="carto-positron">Carto Claro (Positron)</option>
                <option value="osm-standard">OpenStreetMap Estándar</option>
                <option value="carto-dark">Carto Oscuro (Contraste)</option>
                <option value="esri-imagery">Imagen Satelital (Referencia visual)</option>
              </select>
            </div>
            <label style="display:flex;align-items:center;gap:0.45rem;font-size:0.83rem;font-weight:600;margin-bottom:0.6rem;">
              <input type="checkbox" id="gv-toggle-ref-marker" checked>
              <span>Mostrar marcador de centroide referencial</span>
            </label>
            {"".join(groups_html)}
          </div>

          <div class="geovisor-panel" data-gv-panel="local">
            <h3 style="margin-top:0;font-size:1rem;color:var(--c-navy);">Inspeccionar capa local (.geojson)</h3>
            <p style="font-size:0.84rem;">Durante los laboratorios puedes arrastrar o seleccionar un archivo <code>.geojson</code> exportado desde QGIS o Google Earth Engine para verificar su posición y atributos sobre el mapa base. Los datos no salen de tu navegador.</p>
            <div class="dropzone" id="gv-dropzone" tabindex="0" role="button" aria-label="Seleccionar archivo GeoJSON local">
              <strong>Haz clic o arrastra aquí un archivo .geojson</strong>
              <div style="font-size:0.78rem;margin-top:0.25rem;">WGS84 (EPSG:4326) recomendado</div>
            </div>
            <input type="file" id="gv-local-geojson-input" accept=".geojson,.json,application/geo+json,application/json" class="hidden">
            <p id="gv-local-status" style="font-size:0.82rem;color:var(--c-teal-dark);font-weight:600;">Ningún archivo temporal cargado.</p>
            <button type="button" id="gv-clear-local" class="btn btn-outline btn-xs hidden">Quitar capa temporal</button>
            <hr style="border:none;border-top:1px solid var(--c-border);margin:1rem 0;">
            <p style="font-size:0.8rem;margin:0;"><strong>¿Cómo publicarla para todo el equipo?</strong><br>1) Copia el archivo validado en <code>geovisor/data/</code>.<br>2) En <code>geovisor/layers.json</code> asigna su <code>source_path</code> y cambia <code>status</code> a <code>"en_revision"</code> o <code>"publicado"</code>.<br>3) Ejecuta <code>build_site.py</code> y abre una PR.</p>
          </div>

          <div class="geovisor-panel" data-gv-panel="embed">
            <h3 style="margin-top:0;font-size:1rem;color:var(--c-navy);">Integración nativa con GeoLibre</h3>
            <p id="geolibre-embed-notice" style="font-size:0.84rem;">GeoLibre permite abrir o incrustar el archivo versionado <code>geovisor/proyecto.geolibre.json</code> con soporte para COG, PMTiles, GeoParquet, STAC, comparador swipe y consultas DuckDB-WASM.</p>
            <div style="display:flex;flex-direction:column;gap:0.55rem;margin-top:0.85rem;">
              <a class="btn btn-teal" href="{geolibre_json_href}" download="proyecto-{esc(pid)}.geolibre.json">Descargar proyecto.geolibre.json</a>
              <a class="btn btn-outline" href="https://web.geolibre.app/" target="_blank" rel="noopener noreferrer">Abrir web.geolibre.app ↗</a>
            </div>
          </div>
        </aside>

        <div class="geovisor-stage">
          <div class="geovisor-toolbar">
            <div><strong>{esc(layers_cfg.get('title', manifest['title']))}</strong> · Motor MapLibre / GeoLibre</div>
            <div class="geovisor-toolbar-actions">
              <button type="button" id="gv-reset-view" class="btn btn-outline-light btn-xs">Encuadre inicial</button>
              <a class="btn btn-outline-light btn-xs" href="{geolibre_json_href}">JSON GeoLibre</a>
              <a id="btn-open-geolibre-studio" class="btn btn-primary btn-xs" href="https://web.geolibre.app/" target="_blank" rel="noopener noreferrer">Abrir en GeoLibre Studio ↗</a>
            </div>
          </div>
          <div id="geovisor-map-canvas" class="geovisor-canvas" role="region" aria-label="Mapa interactivo del proyecto"></div>
          <iframe id="geolibre-embed-iframe" class="geovisor-iframe" title="Visor GeoLibre embebido" allowfullscreen loading="lazy"></iframe>
          <div class="geovisor-statusbar">
            <span id="gv-coords-readout">Encuadre referencial inicial: Lat {mv.get('center', [0, 0])[1]:.4f} · Lon {mv.get('center', [0, 0])[0]:.4f}</span>
            <span>Ubicación referencial según perfil · Sin resultados simulados</span>
          </div>
        </div>
      </div>
      <script id="geovisor-config-data" type="application/json">{safe_json_cfg}</script>
    </section>

    <section class="section">
      <div class="card">
        <span class="badge badge-propuesta">Módulos funcionales previstos para el PMV</span>
        <h2>Controles y análisis especificados por el perfil</h2>
        <p>Conforme al expediente de la iniciativa, los siguientes módulos y selectores se habilitan progresivamente conforme el equipo incorpora las salidas verificadas en el repositorio:</p>
        <ul>{controls_li}</ul>
      </div>
    </section>

    {ext_refs_html}
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


def build_metodologia_page(ctx: SiteContext, manifest: dict[str, Any], repo_cfg: dict[str, Any], metodologia_md: str) -> str:
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

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">Datos, flujo técnico y cautelas</span>
          <span class="badge badge-country">{esc(manifest['id'])}</span>
        </div>
        <h1>Metodología, fuentes de datos y limitaciones</h1>
        <p class="hero-lead">Fuentes satelitales Copernicus, registros locales declarados, secuencia metodológica y condiciones de interpretación.</p>
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

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">Evidencias y Atlas Urbano Regional</span>
          <span class="badge badge-country">{esc(manifest['id'])}</span>
        </div>
        <h1>Resultados disponibles, productos esperados y aporte al Atlas</h1>
        <p class="hero-lead">Separación explícita entre insumos/evidencias documentales existentes y productos comprometidos como meta del PMV.</p>
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


def build_colaborar_page(ctx: SiteContext, manifest: dict[str, Any], repo_cfg: dict[str, Any]) -> str:
    pid = manifest["id"]
    proposed_owner = repo_cfg.get("proposed_owner", "copernicuscentroamerica")
    proposed_repo = repo_cfg.get("proposed_repository", f"urbano-{pid}")
    confirmed_repo_url = manifest["links"].get("repository")
    canonical_slug = (
        ctx.canonical_repository
        if ctx.canonical_repository
        else f"{proposed_owner}/{proposed_repo}"
    )
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
git add project.json content/ geovisor/
git commit -m "Incorpora capa validada al geovisor de {pid}"
git push -u origin feat/nueva-capa-geovisor

gh pr create --repo {canonical_slug} --base main --head TU_USUARIO_GITHUB:feat/nueva-capa-geovisor --title "Actualiza geovisor y documentación ({pid})" --body-file pr-body.md"""

    hero = f"""
    <section class="hero">
      <div class="container">
        <div class="hero-eyebrow">
          <span class="badge badge-lime">Colaboración GitHub y GeoLibre</span>
          <span class="badge badge-country">{esc(pid)}</span>
        </div>
        <h1>Cómo colaborar en esta iniciativa (Fork, Clone, Capas y PR)</h1>
        <p class="hero-lead">Cada iniciativa evoluciona en su propio repositorio independiente. Las personas participantes trabajan en ramas de su fork personal y proponen mejoras mediante Pull Request.</p>
      </div>
    </section>
    """

    body = f"""
    <div class="callout">
      <strong>Identidad del repositorio de esta iniciativa</strong>
      <span>{repo_status_note} El identificador <code>{esc(pid)}</code> debe permanecer intacto en <code>project.json</code> incluso cuando trabajes en un fork personal.</span>
    </div>

    <section class="section">
      <div class="grid-2">
        <article class="card">
          <span class="badge badge-propuesta">Flujo A · Recomendado para participantes</span>
          <h3>1. Fork personal, clonación y rama</h3>
          <p>Crea o reutiliza el fork en tu cuenta personal, configura <code>origin</code> (tu fork) y <code>upstream</code> (el repositorio canónico del equipo):</p>
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
          <li>Verifica que la capa tenga CRS <code>EPSG:4326</code> (WGS84), topología limpia, autorización de publicación y ausencia de datos personales o prediales restringidos.</li>
          <li>Si es un archivo vectorial ligero (ej. <code>.geojson</code>), guárdalo en <code>geovisor/data/</code>. Si es un ráster pesado (COG, XYZ tiles de GEE o WMS/WFS OGC), alójalo en el servicio correspondiente y usa su URL <code>https://</code>.</li>
          <li>Edita la entrada correspondiente en <code>geovisor/layers.json</code>: coloca la ruta en <code>source_path</code> y cambia <code>status</code> a <code>"en_revision"</code> o <code>"publicado"</code>.</li>
          <li>Ejecuta <code>python3 scripts/build_site.py --output site</code>: el generador actualizará automáticamente <code>site/geovisor/proyecto.geolibre.json</code> y activará el control en el Geovisor.</li>
        </ol>
      </article>
    </section>

    <section class="section">
      <div class="grid-2">
        <article class="card">
          <h3>3. Enviar Pull Request al repositorio canónico</h3>
          <pre id="cmd-pr" class="code-block"><code>{html.escape(pr_cmds)}</code></pre>
          <div class="card-footer">
            <button type="button" class="btn btn-outline btn-xs" data-copy-target="cmd-pr">Copiar comandos</button>
          </div>
        </article>

        <article class="card">
          <h3>4. Registro de tareas, bloqueos y revisiones</h3>
          <p>Este repositorio incluye cuatro formularios estructurados en <code>.github/ISSUE_TEMPLATE/</code>:</p>
          <ul>
            <li><strong>Tarea del PMV:</strong> resultado concreto, criterio de aceptación y fecha objetivo propuesta.</li>
            <li><strong>Bloqueo o solicitud de apoyo:</strong> dificultad técnica o de datos y ayuda requerida.</li>
            <li><strong>Solicitud de revisión:</strong> enlace a evidencia para revisión técnica o validación.</li>
            <li><strong>Contribución al Atlas:</strong> revisión de metadatos antes de pasar a publicado.</li>
          </ul>
          <div class="card-footer">
            {issue_btn}
          </div>
        </article>
      </div>
    </section>
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

    # Copiar recursos estáticos
    shutil.copytree(ROOT / "web" / "assets", out_dir / "assets")

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

    # Exportar JSONs públicos seleccionados
    write_deterministic(
        out_dir / "data" / "project.json",
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    write_deterministic(
        out_dir / "data" / "atlas-products.json",
        json.dumps(atlas_products, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    build_meta = {
        "project_id": manifest["id"],
        "schema_version": manifest["schema_version"],
        "template_version": TEMPLATE_VERSION,
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
    write_deterministic(out_dir / "index.html", build_home_page(ctx, manifest, repo_cfg, layers_cfg))
    write_deterministic(out_dir / "proyecto" / "index.html", build_proyecto_page(ctx, manifest, repo_cfg, project_md, pmv_md))
    write_deterministic(out_dir / "aplicacion" / "index.html", build_aplicacion_page(ctx, manifest, repo_cfg, layers_cfg))
    write_deterministic(out_dir / "metodologia" / "index.html", build_metodologia_page(ctx, manifest, repo_cfg, metodologia_md))
    write_deterministic(out_dir / "resultados" / "index.html", build_resultados_page(ctx, manifest, repo_cfg, atlas_products, continuidad_md))
    write_deterministic(out_dir / "colaborar" / "index.html", build_colaborar_page(ctx, manifest, repo_cfg))
    write_deterministic(out_dir / "404.html", build_404_page(ctx, manifest, repo_cfg))

    print(
        f"[OK] Sitio construido para '{manifest['id']}' en {out_dir} "
        f"(base_path='{ctx.base_path}', modo='{ctx.effective_mode}')."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())

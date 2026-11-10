#!/usr/bin/env python3
"""
Utilidades comunes de validación, cálculo de base path, identidad canónica vs. preview,
sistema de identidad visual institucional (2.0.0-copernicus-2026) y saneamiento
para el Portal Comunitario y los repositorios de iniciativas.
"""
from __future__ import annotations

import datetime as dt
import html
import os
import re
import urllib.parse
from dataclasses import dataclass
from typing import Any

from jsonschema import FormatChecker

TEMPLATE_VERSION = "1.1.0"
THEME_VERSION = "2.0.0-copernicus-2026"

STATUS_LABELS = {
    "declarado": ("Según el perfil", "badge-declarado"),
    "propuesta": ("Propuesto", "badge-propuesta"),
    "por_confirmar": ("Pendiente de confirmar", "badge-pendiente"),
    "definicion": ("En definición", "badge-pendiente"),
    "en_desarrollo": ("En desarrollo", "badge-warn"),
    "demostrable": ("Demostrable", "badge-ok"),
    "en_mantenimiento": ("En mantenimiento", "badge-ok"),
    "no_disponible": ("No disponible aún", "badge-pendiente"),
    "disponible": ("Disponible", "badge-ok"),
    "pendiente": ("Pendiente", "badge-pendiente"),
    "en_revision": ("En revisión", "badge-warn"),
    "validado": ("Validado", "badge-ok"),
    "con_observaciones": ("Con observaciones", "badge-warn"),
    "no_validado": ("No validado", "badge-danger"),
    "no_documentada": ("No documentada", "badge-pendiente"),
    "piloto": ("En piloto", "badge-warn"),
    "uso_documentado": ("Uso documentado", "badge-ok"),
    "propuesto": ("Propuesto", "badge-propuesta"),
    "en_preparacion": ("En preparación", "badge-warn"),
    "publicado": ("Publicado", "badge-ok"),
    "retirado": ("Retirado", "badge-danger"),
}


def make_format_checker() -> FormatChecker:
    checker = FormatChecker()

    @checker.checks("date", ValueError)
    def _check_date(value: object) -> bool:
        if not isinstance(value, str):
            return True
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", value):
            raise ValueError(f"Fecha ISO inválida: {value}")
        dt.date.fromisoformat(value)
        return True

    @checker.checks("date-time", ValueError)
    def _check_datetime(value: object) -> bool:
        if not isinstance(value, str):
            return True
        if "T" not in value:
            raise ValueError(f"Fecha-hora ISO inválida: {value}")
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError(f"Falta zona horaria en date-time: {value}")
        return True

    @checker.checks("uri", ValueError)
    def _check_uri(value: object) -> bool:
        if not isinstance(value, str):
            return True
        parts = urllib.parse.urlsplit(value)
        if not parts.scheme or not parts.netloc:
            raise ValueError(f"URI inválida: {value}")
        return True

    return checker


def resolve_json_pointer(doc: Any, pointer: str) -> Any:
    if pointer == "":
        return doc
    if not pointer.startswith("/"):
        raise KeyError(f"JSON Pointer inválido: {pointer}")
    cur = doc
    for raw_token in pointer.lstrip("/").split("/"):
        token = raw_token.replace("~1", "/").replace("~0", "~")
        if isinstance(cur, list):
            cur = cur[int(token)]
        elif isinstance(cur, dict):
            if token not in cur:
                raise KeyError(f"Ruta inexistente {pointer} ('{token}')")
            cur = cur[token]
        else:
            raise KeyError(f"No navegable '{token}' en {pointer}")
    return cur


def normalize_github_repo_url(url: str | None) -> str | None:
    if not url or not isinstance(url, str):
        return None
    m = re.match(r"^https://github\.com/([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$", url.strip())
    if not m:
        return None
    return f"{m.group(1)}/{m.group(2)}"


@dataclass(frozen=True)
class SiteContext:
    origin: str
    base_path: str
    github_repository: str | None
    canonical_repository: str | None
    effective_mode: str  # "canonical" | "preview"
    hub_url: str | None

    def site_url(self, rel_path: str = "") -> str:
        clean = rel_path.lstrip("/")
        base = self.base_path
        if not base.startswith("/"):
            base = "/" + base
        if not base.endswith("/"):
            base = base + "/"
        return f"{base}{clean}"

    def full_url(self, rel_path: str = "") -> str:
        if not self.origin:
            return self.site_url(rel_path)
        return f"{self.origin.rstrip('/')}{self.site_url(rel_path)}"


def compute_site_context(
    *,
    canonical_repo_url_or_slug: str | None,
    explicit_base_path: str | None = None,
    explicit_origin: str | None = None,
    hub_url: str | None = None,
) -> SiteContext:
    gh_repo = os.environ.get("GITHUB_REPOSITORY", "").strip() or None
    requested_mode = os.environ.get("PAGES_SITE_MODE", "preview").strip().lower()

    canonical_slug: str | None = None
    if canonical_repo_url_or_slug:
        if "/" in canonical_repo_url_or_slug and not canonical_repo_url_or_slug.startswith("http"):
            canonical_slug = canonical_repo_url_or_slug.strip()
        else:
            canonical_slug = normalize_github_repo_url(canonical_repo_url_or_slug)

    if explicit_base_path is not None:
        bp = explicit_base_path.strip()
        if not bp.startswith("/"):
            bp = "/" + bp
        if not bp.endswith("/"):
            bp = bp + "/"
        origin = (explicit_origin or "").rstrip("/")
    elif gh_repo and "/" in gh_repo:
        owner, repo = gh_repo.split("/", 1)
        origin = (explicit_origin or f"https://{owner}.github.io").rstrip("/")
        if repo.lower() == f"{owner.lower()}.github.io":
            bp = "/"
        else:
            bp = f"/{repo}/"
    else:
        bp = "/"
        origin = (explicit_origin or "").rstrip("/")

    is_canonical = (
        bool(canonical_slug)
        and bool(gh_repo)
        and gh_repo.lower() == canonical_slug.lower()
        and requested_mode == "canonical"
    )
    effective_mode = "canonical" if is_canonical else "preview"

    return SiteContext(
        origin=origin,
        base_path=bp,
        github_repository=gh_repo,
        canonical_repository=canonical_slug,
        effective_mode=effective_mode,
        hub_url=hub_url,
    )


def badge_html(status_key: str | None, prefix: str = "") -> str:
    key = status_key or "por_confirmar"
    label, cls = STATUS_LABELS.get(key, (key, "badge-pendiente"))
    text = f"{prefix}: {label}" if prefix else label
    return f'<span class="badge {cls}">{html.escape(text)}</span>'


def esc(val: object, fallback: str = "Pendiente de confirmar") -> str:
    if val is None or val == "":
        return html.escape(fallback)
    return html.escape(str(val))


SPANISH_MONTHS_SHORT = {
    1: "ene",
    2: "feb",
    3: "mar",
    4: "abr",
    5: "may",
    6: "jun",
    7: "jul",
    8: "ago",
    9: "sep",
    10: "oct",
    11: "nov",
    12: "dic",
}


def format_spanish_date(val: str | None, fallback: str = "Pendiente de confirmar") -> str:
    if not val or not isinstance(val, str):
        return fallback
    s = val.strip()
    m_dt = re.match(r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})", s)
    if m_dt:
        yr, mo, dy, hh, mm = int(m_dt.group(1)), int(m_dt.group(2)), int(m_dt.group(3)), m_dt.group(4), m_dt.group(5)
        m_name = SPANISH_MONTHS_SHORT.get(mo, str(mo))
        return f"{dy} {m_name} {yr} · {hh}:{mm} UTC"
    m_d = re.match(r"^(\d{4})-(\d{2})-(\d{2})$", s)
    if m_d:
        yr, mo, dy = int(m_d.group(1)), int(m_d.group(2)), int(m_d.group(3))
        m_name = SPANISH_MONTHS_SHORT.get(mo, str(mo))
        return f"{dy} {m_name} {yr}"
    return s


def render_upper_institutional_bar(
    ctx: SiteContext,
    left_context_html: str,
    right_context_html: str,
) -> str:
    """
    Renderiza la barra superior de contexto sobre fondo azul oscuro (#0C1659).
    Los logotipos institucionales comunes y propios del proyecto se ubican en el
    bloque inferior de la página para mantener despejada la cabecera.
    """
    return f"""
  <div class="topbar" role="region" aria-label="Contexto institucional superior">
    <div class="container">
      <div class="topbar-brand-left">
        <div class="topbar-context">{left_context_html}</div>
      </div>
      <div class="topbar-brand-right">
        <div class="topbar-context">{right_context_html}</div>
      </div>
    </div>
  </div>"""


def render_regional_institutional_band(
    ctx: SiteContext,
    extra_class: str = "is-footer-band",
) -> str:
    """
    Renderiza la banda institucional regional común al pie de la página sobre fondo blanco (#FFFFFF),
    conservando los logos, nombres, orden y agrupaciones de PPT PLANTILLA COPERNICUS_2026.pptx:
      - Marco Global Gateway y Unión Europea.
      - Implementado por: CCVAH, SISCA, SICA.
      - Con el apoyo técnico de: Cooperación Alemana, GIZ, Copernicus LAC Chile.
    Incluye atributos HTML e inline styles de respaldo para impedir desconfiguración por caché.
    """
    cls_attr = f"banda-institucional-regional {extra_class}".strip()
    gg_src = html.escape(ctx.site_url("assets/img/brand/logo-global-gateway.png"), quote=True)
    eu_src = html.escape(ctx.site_url("assets/img/brand/logo-union-europea.png"), quote=True)
    ccvah_src = html.escape(ctx.site_url("assets/img/brand/logo-ccvah.png"), quote=True)
    sisca_src = html.escape(ctx.site_url("assets/img/brand/logo-sisca.png"), quote=True)
    sica_src = html.escape(ctx.site_url("assets/img/brand/logo-sica.png"), quote=True)
    coop_src = html.escape(ctx.site_url("assets/img/brand/logo-cooperacion-alemana.png"), quote=True)
    giz_src = html.escape(ctx.site_url("assets/img/brand/logo-giz.png"), quote=True)
    cop_src = html.escape(ctx.site_url("assets/img/brand/logo-copernicus-lac-chile.png"), quote=True)

    return f"""
  <section class="{cls_attr}" aria-label="Banda institucional regional" style="background:#FFFFFF;border-top:3px solid #FFC800;border-bottom:1px solid #D5DDF0;padding:1.1rem 0;">
    <div class="container banda-regional-inner" style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:1.25rem 2rem;">
      <div class="banda-regional-grupo" style="display:flex;flex-direction:column;gap:0.4rem;">
        <span class="banda-regional-label" style="font-size:0.75rem;font-weight:700;color:#000A62;text-transform:uppercase;letter-spacing:0.03em;">Iniciativa Global Gateway · Unión Europea:</span>
        <div class="banda-regional-logos" style="display:flex;flex-wrap:wrap;align-items:center;gap:0.85rem;">
          <span class="banda-regional-item logo-gg-pill" style="display:inline-flex;align-items:center;justify-content:center;background:#0C1659;padding:0.35rem 0.65rem;border-radius:6px;">
            <img src="{gg_src}" alt="Global Gateway" height="28" style="height:28px;width:auto;max-width:110px;object-fit:contain;display:block;" loading="lazy">
          </span>
          <span class="banda-regional-item logo-eu" style="display:inline-flex;align-items:center;justify-content:center;">
            <img src="{eu_src}" alt="Emblema de la Unión Europea" height="32" style="height:32px;width:auto;max-width:90px;object-fit:contain;display:block;" loading="lazy">
          </span>
        </div>
      </div>
      <div class="banda-regional-grupo" style="display:flex;flex-direction:column;gap:0.4rem;">
        <span class="banda-regional-label" style="font-size:0.75rem;font-weight:700;color:#000A62;text-transform:uppercase;letter-spacing:0.03em;">Implementado por:</span>
        <div class="banda-regional-logos" style="display:flex;flex-wrap:wrap;align-items:center;gap:1.1rem;">
          <span class="banda-regional-item logo-ccvah" style="display:inline-flex;align-items:center;justify-content:center;">
            <img src="{ccvah_src}" alt="CCVAH — Consejo Centroamericano de Vivienda y Asentamientos Humanos" height="38" style="height:38px;width:auto;max-width:90px;object-fit:contain;display:block;" loading="lazy">
          </span>
          <span class="banda-regional-item logo-sisca" style="display:inline-flex;align-items:center;justify-content:center;">
            <img src="{sisca_src}" alt="SISCA — Secretaría de la Integración Social Centroamericana" height="36" style="height:36px;width:auto;max-width:115px;object-fit:contain;display:block;" loading="lazy">
          </span>
          <span class="banda-regional-item logo-sica" style="display:inline-flex;align-items:center;justify-content:center;">
            <img src="{sica_src}" alt="SICA — Sistema de la Integración Centroamericana" height="36" style="height:36px;width:auto;max-width:115px;object-fit:contain;display:block;" loading="lazy">
          </span>
        </div>
      </div>
      <div class="banda-regional-grupo" style="display:flex;flex-direction:column;gap:0.4rem;">
        <span class="banda-regional-label" style="font-size:0.75rem;font-weight:700;color:#000A62;text-transform:uppercase;letter-spacing:0.03em;">Con el apoyo técnico de:</span>
        <div class="banda-regional-logos" style="display:flex;flex-wrap:wrap;align-items:center;gap:1.1rem;">
          <span class="banda-regional-item logo-cooperacion" style="display:inline-flex;align-items:center;justify-content:center;">
            <img src="{coop_src}" alt="Cooperación Alemana — Deutsche Zusammenarbeit" height="38" style="height:38px;width:auto;max-width:115px;object-fit:contain;display:block;" loading="lazy">
          </span>
          <span class="banda-regional-item logo-giz" style="display:inline-flex;align-items:center;justify-content:center;">
            <img src="{giz_src}" alt="GIZ — Deutsche Gesellschaft für Internationale Zusammenarbeit (GIZ) GmbH" height="30" style="height:30px;width:auto;max-width:115px;object-fit:contain;display:block;" loading="lazy">
          </span>
          <span class="banda-regional-item logo-copernicus" style="display:inline-flex;align-items:center;justify-content:center;">
            <img src="{cop_src}" alt="Copernicus LAC Chile" height="32" style="height:32px;width:auto;max-width:120px;object-fit:contain;display:block;" loading="lazy">
          </span>
        </div>
      </div>
    </div>
  </section>"""


def render_project_institutions_band(
    ctx: SiteContext,
    branding: dict[str, Any] | None,
    manifest: dict[str, Any],
    colaborar_href: str | None = None,
    logo_url_prefix: str = "",
) -> str:
    """
    Renderiza la zona «Instituciones participantes del proyecto» al final de la página,
    diferenciada de la banda regional común. Incluye estilos inline de respaldo para
    garantizar proporciones compactas y legibles en cualquier navegador.
    """
    cards_html: list[str] = []

    if branding and isinstance(branding.get("project_logo"), dict):
        pl = branding["project_logo"]
        pl_path = pl.get("logo_path")
        if pl_path:
            resolved_pl = ctx.site_url(f"{logo_url_prefix}{pl_path}".lstrip("/"))
            aspect_cls = f"is-{pl.get('aspect_hint', 'horizontal')}"
            pl_name = esc(pl.get("name") or manifest.get("title"))
            pl_alt = esc(pl.get("alt_text") or pl_name)
            pl_url = pl.get("url")
            name_node = (
                f'<a href="{html.escape(pl_url, quote=True)}" target="_blank" rel="noopener noreferrer">{pl_name} ↗</a>'
                if pl_url and str(pl_url).startswith("https://")
                else pl_name
            )
            cards_html.append(
                f"""
                <div class="inst-proyecto-card is-project-emblem" style="display:flex;align-items:center;gap:0.75rem;padding:0.65rem 0.85rem;background:#F9FAFE;border:1px solid #D5DDF0;border-radius:8px;">
                  <div class="inst-proyecto-logo-box {aspect_cls}" style="height:48px;min-width:72px;max-width:130px;display:flex;align-items:center;justify-content:center;padding:0.25rem 0.5rem;background:#FFFFFF;border:1px solid #E4EAF7;border-radius:6px;flex-shrink:0;">
                    <img src="{html.escape(resolved_pl, quote=True)}" alt="{pl_alt}" height="38" style="max-height:38px;max-width:118px;width:auto;height:auto;object-fit:contain;display:block;" loading="lazy">
                  </div>
                  <div style="min-width:0;">
                    <span class="badge badge-lime" style="margin-bottom:0.2rem;font-size:0.7rem;">Marca de la iniciativa</span>
                    <p class="inst-proyecto-name" style="margin:0;font-size:0.86rem;font-weight:700;color:#000A62;">{name_node}</p>
                  </div>
                </div>
                """
            )

    institutions: list[dict[str, Any]] = []
    if branding and isinstance(branding.get("institutions"), list) and branding["institutions"]:
        institutions = sorted(
            branding["institutions"],
            key=lambda x: (int(x.get("order", 99)), str(x.get("id", ""))),
        )
    else:
        for idx, raw_name in enumerate(manifest.get("institutional_use", {}).get("institutions", []), start=1):
            institutions.append(
                {
                    "id": f"inst-{idx}",
                    "name": raw_name,
                    "acronym": None,
                    "role": "Institución declarada en el perfil",
                    "logo_path": None,
                    "alt_text": f"Institución participante: {raw_name}",
                    "url": None,
                    "order": idx,
                    "aspect_hint": "auto",
                }
            )

    for inst in institutions:
        nm = esc(inst.get("name"))
        acr = inst.get("acronym")
        role = inst.get("role")
        lpath = inst.get("logo_path")
        alt = esc(inst.get("alt_text") or inst.get("name"))
        url = inst.get("url")
        aspect = inst.get("aspect_hint") or "horizontal"

        name_html = (
            f'<a href="{html.escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{nm} ↗</a>'
            if url and str(url).startswith("https://")
            else nm
        )
        acr_badge = f'<span class="inst-proyecto-acronym" style="display:inline-block;background:#000A62;color:#FFFFFF;font-size:0.7rem;font-weight:700;padding:0.1rem 0.45rem;border-radius:4px;">{esc(acr)}</span>' if acr else ""
        role_html = f'<p class="inst-proyecto-role" style="margin:0.15rem 0 0;font-size:0.76rem;color:#3B4668;">{esc(role)}</p>' if role else ""

        if lpath:
            resolved_src = ctx.site_url(f"{logo_url_prefix}{lpath}".lstrip("/"))
            cards_html.append(
                f"""
                <div class="inst-proyecto-card" style="display:flex;align-items:center;gap:0.75rem;padding:0.65rem 0.85rem;background:#F9FAFE;border:1px solid #D5DDF0;border-radius:8px;">
                  <div class="inst-proyecto-logo-box is-{html.escape(aspect)}" style="height:48px;min-width:72px;max-width:130px;display:flex;align-items:center;justify-content:center;padding:0.25rem 0.5rem;background:#FFFFFF;border:1px solid #E4EAF7;border-radius:6px;flex-shrink:0;">
                    <img src="{html.escape(resolved_src, quote=True)}" alt="{alt}" height="38" style="max-height:38px;max-width:118px;width:auto;height:auto;object-fit:contain;display:block;" loading="lazy">
                  </div>
                  <div style="min-width:0;">
                    <div class="inst-proyecto-text-head" style="margin-bottom:0.15rem;">
                      {acr_badge}
                    </div>
                    <p class="inst-proyecto-name" style="margin:0;font-size:0.85rem;font-weight:700;color:#000A62;line-height:1.25;">{name_html}</p>
                    {role_html}
                  </div>
                </div>
                """
            )
        else:
            cards_html.append(
                f"""
                <div class="inst-proyecto-card is-text-only" style="display:flex;flex-direction:column;justify-content:center;padding:0.65rem 0.85rem;background:#F9FAFE;border:1px solid #D5DDF0;border-left:4px solid #000A62;border-radius:8px;">
                  <div class="inst-proyecto-text-head" style="display:flex;flex-wrap:wrap;align-items:center;gap:0.35rem;margin-bottom:0.2rem;">
                    {acr_badge}
                    <span class="inst-proyecto-no-logo-note" style="font-size:0.7rem;color:#52607A;background:#EEF2FA;padding:0.08rem 0.4rem;border-radius:4px;">Institución participante</span>
                  </div>
                  <div>
                    <p class="inst-proyecto-name" style="margin:0;font-size:0.85rem;font-weight:700;color:#000A62;line-height:1.25;">{name_html}</p>
                    {role_html}
                  </div>
                </div>
                """
            )

    action_link = ""
    if colaborar_href:
        action_link = (
            f'<a class="btn btn-outline btn-xs" href="{html.escape(colaborar_href, quote=True)}">'
            f'Añadir o actualizar logos →</a>'
        )

    return f"""
    <section id="instituciones-participantes" class="banda-instituciones-proyecto" aria-label="Instituciones participantes del proyecto" style="background:#FFFFFF;border:1px solid #D5DDF0;border-top:3px solid #000A62;border-radius:10px;padding:1rem 1.15rem;margin:1.5rem 0 0.5rem;">
      <div class="banda-proyecto-header" style="display:flex;flex-wrap:wrap;align-items:center;justify-content:space-between;gap:0.65rem;margin-bottom:0.8rem;padding-bottom:0.55rem;border-bottom:1px solid #E4EAF7;">
        <div class="banda-proyecto-title-wrap" style="display:flex;flex-wrap:wrap;align-items:center;gap:0.5rem;">
          <span class="badge badge-country">Identidad local del proyecto</span>
          <h2 class="banda-proyecto-title" style="margin:0;font-size:1.02rem;color:#000A62;">Instituciones participantes del proyecto</h2>
        </div>
        {action_link}
      </div>
      <div class="banda-proyecto-grid" style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:0.75rem;align-items:stretch;">
        {"".join(cards_html)}
      </div>
    </section>
    """

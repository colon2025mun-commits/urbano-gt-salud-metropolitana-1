#!/usr/bin/env python3
"""
Utilidades comunes de validación, cálculo de base path, identidad canónica vs. preview
y saneamiento para el Portal Comunitario y los repositorios de iniciativas.
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

TEMPLATE_VERSION = "1.0.0"

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

    # Regla estricta de 03_GITHUB_PAGES_Y_AUTOMATIZACION.md:
    # Un sitio solo se identifica como canonical si coincide con el repositorio canónico confirmado
    # y PAGES_SITE_MODE == 'canonical'.
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


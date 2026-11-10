#!/usr/bin/env python3
"""
Conversor Markdown -> HTML seguro con lista blanca explícita de elementos.
- Escapa todo HTML crudo de entrada.
- Admite únicamente enlaces https://, mailto: institucionales explícitos si se aprobaran (desactivado por defecto)
  o rutas relativas seguras sin traversal hacia fuentes privadas.
- Envuelve tablas en <div class="table-wrap"> para consulta móvil accesible.
"""
from __future__ import annotations

import html
import re
import urllib.parse


def is_safe_href(url: str) -> bool:
    u = url.strip()
    if not u or u == "#":
        return False
    lower = u.lower()
    if lower.startswith(("javascript:", "data:", "vbscript:", "file:")):
        return False
    if "fuentes/" in lower:
        return False
    parsed = urllib.parse.urlsplit(u)
    if parsed.scheme:
        return parsed.scheme == "https" and bool(parsed.netloc)
    # Relative path inside site
    if u.startswith("//"):
        return False
    return True


def render_inline(text: str) -> str:
    escaped = html.escape(text, quote=True)

    # Extract inline code spans first to protect their content
    code_tokens: list[str] = []

    def _save_code(match: re.Match[str]) -> str:
        idx = len(code_tokens)
        code_tokens.append(f"<code>{match.group(1)}</code>")
        return f"\x00CODE{idx}\x00"

    escaped = re.sub(r"`([^`]+)`", _save_code, escaped)

    # Links: [label](url)
    def _replace_link(match: re.Match[str]) -> str:
        label = match.group(1)
        raw_url = html.unescape(match.group(2)).strip()
        if is_safe_href(raw_url):
            safe_url = html.escape(raw_url, quote=True)
            ext_attrs = ' target="_blank" rel="noopener noreferrer"' if raw_url.startswith("https://") else ""
            return f'<a href="{safe_url}"{ext_attrs}>{label}</a>'
        return f"{label} <code>({html.escape(raw_url)})</code>"

    escaped = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _replace_link, escaped)

    # Strong & emphasis
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", escaped)

    for idx, token_html in enumerate(code_tokens):
        escaped = escaped.replace(f"\x00CODE{idx}\x00", token_html)

    return escaped


def render_markdown(md_text: str) -> str:
    if not md_text:
        return ""

    lines = md_text.replace("\r\n", "\n").split("\n")
    out: list[str] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # Skip HTML comments cleanly
        if stripped.startswith("<!--") and stripped.endswith("-->"):
            i += 1
            continue

        # Blank line
        if not stripped:
            i += 1
            continue

        # Fenced code block
        if stripped.startswith("```"):
            lang = re.sub(r"[^a-zA-Z0-9_-]", "", stripped[3:].strip())
            i += 1
            code_lines: list[str] = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(html.escape(lines[i], quote=False))
                i += 1
            if i < n:
                i += 1
            cls = f' class="language-{lang}"' if lang else ""
            out.append(f'<pre class="code-block"><code{cls}>' + "\n".join(code_lines) + "</code></pre>")
            continue

        # Headings (# to ####)
        hm = re.match(r"^(#{1,4})\s+(.*)$", stripped)
        if hm:
            level = len(hm.group(1))
            content = render_inline(hm.group(2).strip())
            out.append(f"<h{level}>{content}</h{level}>")
            i += 1
            continue

        # Markdown table
        if "|" in stripped and i + 1 < n and re.match(r"^\|?[\s:-]+\|[\s|:-]+$", lines[i + 1].strip()):
            header_cells = [c.strip() for c in stripped.strip("|").split("|")]
            i += 2  # skip header + separator
            rows_html: list[str] = []
            while i < n and "|" in lines[i] and lines[i].strip():
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                # Pad or trim to header length
                if len(cells) < len(header_cells):
                    cells.extend([""] * (len(header_cells) - len(cells)))
                td_html = "".join(f"<td>{render_inline(c)}</td>" for c in cells[: len(header_cells)])
                rows_html.append(f"<tr>{td_html}</tr>")
                i += 1
            th_html = "".join(f'<th scope="col">{render_inline(h)}</th>' for h in header_cells)
            out.append(
                '<div class="table-wrap"><table><thead><tr>'
                + th_html
                + "</tr></thead><tbody>"
                + "".join(rows_html)
                + "</tbody></table></div>"
            )
            continue

        # Unordered list
        if re.match(r"^[-*]\s+", stripped):
            items: list[str] = []
            while i < n and re.match(r"^\s*[-*]\s+", lines[i]):
                item_txt = re.sub(r"^\s*[-*]\s+", "", lines[i]).strip()
                items.append(f"<li>{render_inline(item_txt)}</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue

        # Ordered list
        if re.match(r"^\d+\.\s+", stripped):
            items = []
            while i < n and re.match(r"^\s*\d+\.\s+", lines[i]):
                item_txt = re.sub(r"^\s*\d+\.\s+", "", lines[i]).strip()
                items.append(f"<li>{render_inline(item_txt)}</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue

        # Paragraph (accumulate contiguous normal lines)
        para_lines: list[str] = []
        while (
            i < n
            and lines[i].strip()
            and not lines[i].strip().startswith(("```", "#", "<!--"))
            and not re.match(r"^\s*[-*]\s+", lines[i])
            and not re.match(r"^\s*\d+\.\s+", lines[i])
            and not (
                "|" in lines[i]
                and i + 1 < n
                and re.match(r"^\|?[\s:-]+\|[\s|:-]+$", lines[i + 1].strip())
            )
        ):
            para_lines.append(lines[i].strip())
            i += 1
        if para_lines:
            out.append(f"<p>{render_inline(' '.join(para_lines))}</p>")

    return "\n".join(out)

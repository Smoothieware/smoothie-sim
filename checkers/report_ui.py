"""Shared UI kit for the smoothie-sim HTML report: inline icons, design tokens, CSS, JS and small HTML builders.

Everything is self-contained (no external requests): the report stays one file.

Icons: path data from Tabler Icons (https://tabler.io/icons), outline style, version 3.46.0.
    MIT License, Copyright (c) 2020-2026 Paweł Kuna. Permission is hereby granted, free of charge, to any person
    obtaining a copy of the icons and associated files, to deal in them without restriction, subject to this
    copyright and permission notice being included in copies or substantial portions. The icons are provided
    "as is", without warranty of any kind. Full text: https://github.com/tabler/tabler-icons/blob/main/LICENSE
    Note: Tabler has no "memory" icon; the name "memory" maps to its "database" icon.

Public API (all builders return HTML strings, escape their text arguments and never raise):
    icon, set_source_base, file_link, status_badge, chip, stat_card, drawer, nav, CSS, JS
Additions beyond the agreed contract (optional helpers):
    drawer_parts (button and panel separately, for table detail rows), HEAD_JS (tiny script for <head>: applies the remembered theme before first paint), copy_button, code_block,
    kv_grid, progress_bar, callout, section_head, hero

Markup conventions the CSS/JS understand:
    <div class="page"> wraps the whole report body below the nav. A plain <section> is styled as a card.
    <table data-sortable data-filterable>: header click sorts, a filter box + status chips are injected above.
        A cell may carry data-sort="123" to sort on a different value than its text. A <tr data-status="fail">
        feeds the status chips. A <tr class="detail-row"> belongs to the row before it (sorted/filtered together).
    <button class="copy-btn" data-copy="text">, <details>, [data-tip="tooltip text"] (give it tabindex=0).
    Nav buttons: [data-action="theme" | "expand-all" | "collapse-all"].
"""
from __future__ import annotations

import html as _html
import json as _json
import re as _re
from functools import wraps as _wraps
from urllib.parse import quote as _quote

# ---------------------------------------------------------------------------------------------------------------------
# Icons
# ---------------------------------------------------------------------------------------------------------------------

_ICONS = {
    "check": '<path d="M5 12l5 5l10 -10"/>',
    "x": '<path d="M18 6l-12 12"/> <path d="M6 6l12 12"/>',
    "alert-triangle": '<path d="M12 9v4"/> <path d="M10.363 3.591l-8.106 13.534a1.914 1.914 0 0 0 1.636 2.871h16.214a1.914 1.914 0 0 0 1.636 -2.87l-8.106 -13.536a1.914 1.914 0 0 0 -3.274 0"/> <path d="M12 16h.01"/>',
    "info-circle": '<path d="M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0"/> <path d="M12 9h.01"/> <path d="M11 12h1v4h1"/>',
    "chevron-down": '<path d="M6 9l6 6l6 -6"/>',
    "chevron-right": '<path d="M9 6l6 6l-6 6"/>',
    "file-code": '<path d="M14 3v4a1 1 0 0 0 1 1h4"/> <path d="M17 21h-10a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2"/> <path d="M10 13l-1 2l1 2"/> <path d="M14 13l1 2l-1 2"/>',
    "folder": '<path d="M5 4h4l3 3h7a2 2 0 0 1 2 2v8a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-11a2 2 0 0 1 2 -2"/>',
    "external-link": '<path d="M12 6h-6a2 2 0 0 0 -2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2 -2v-6"/> <path d="M11 13l9 -9"/> <path d="M15 4h5v5"/>',
    "link": '<path d="M9 15l6 -6"/> <path d="M11 6l.463 -.536a5 5 0 0 1 7.071 7.072l-.534 .464"/> <path d="M13 18l-.397 .534a5.068 5.068 0 0 1 -7.127 0a4.972 4.972 0 0 1 0 -7.071l.524 -.463"/>',
    "copy": '<path d="M7 9.667a2.667 2.667 0 0 1 2.667 -2.667h8.666a2.667 2.667 0 0 1 2.667 2.667v8.666a2.667 2.667 0 0 1 -2.667 2.667h-8.666a2.667 2.667 0 0 1 -2.667 -2.667l0 -8.666"/> <path d="M4.012 16.737a2.005 2.005 0 0 1 -1.012 -1.737v-10c0 -1.1 .9 -2 2 -2h10c.75 0 1.158 .385 1.5 1"/>',
    "clock": '<path d="M3 12a9 9 0 1 0 18 0a9 9 0 0 0 -18 0"/> <path d="M12 7v5l3 3"/>',
    "cpu": '<path d="M5 6a1 1 0 0 1 1 -1h12a1 1 0 0 1 1 1v12a1 1 0 0 1 -1 1h-12a1 1 0 0 1 -1 -1l0 -12"/> <path d="M9 9h6v6h-6l0 -6"/> <path d="M3 10h2"/> <path d="M3 14h2"/> <path d="M10 3v2"/> <path d="M14 3v2"/> <path d="M21 10h-2"/> <path d="M21 14h-2"/> <path d="M14 21v-2"/> <path d="M10 21v-2"/>',
    "bolt": '<path d="M13 3l0 7l6 0l-8 11l0 -7l-6 0l8 -11"/>',
    "player-play": '<path d="M7 4v16l13 -8l-13 -8"/>',
    "player-pause": '<path d="M6 6a1 1 0 0 1 1 -1h2a1 1 0 0 1 1 1v12a1 1 0 0 1 -1 1h-2a1 1 0 0 1 -1 -1l0 -12"/> <path d="M14 6a1 1 0 0 1 1 -1h2a1 1 0 0 1 1 1v12a1 1 0 0 1 -1 1h-2a1 1 0 0 1 -1 -1l0 -12"/>',
    "chart-line": '<path d="M4 19l16 0"/> <path d="M4 15l4 -6l4 2l4 -5l4 4"/>',
    "route": '<path d="M3 19a2 2 0 1 0 4 0a2 2 0 0 0 -4 0"/> <path d="M19 7a2 2 0 1 0 0 -4a2 2 0 0 0 0 4"/> <path d="M11 19h5.5a3.5 3.5 0 0 0 0 -7h-8a3.5 3.5 0 0 1 0 -7h4.5"/>',
    "ruler": '<path d="M5 4h14a1 1 0 0 1 1 1v5a1 1 0 0 1 -1 1h-7a1 1 0 0 0 -1 1v7a1 1 0 0 1 -1 1h-5a1 1 0 0 1 -1 -1v-14a1 1 0 0 1 1 -1"/> <path d="M4 8l2 0"/> <path d="M4 12l3 0"/> <path d="M4 16l2 0"/> <path d="M8 4l0 2"/> <path d="M12 4l0 3"/> <path d="M16 4l0 2"/>',
    "adjustments": '<path d="M4 10a2 2 0 1 0 4 0a2 2 0 0 0 -4 0"/> <path d="M6 4v4"/> <path d="M6 12v8"/> <path d="M10 16a2 2 0 1 0 4 0a2 2 0 0 0 -4 0"/> <path d="M12 4v10"/> <path d="M12 18v2"/> <path d="M16 7a2 2 0 1 0 4 0a2 2 0 0 0 -4 0"/> <path d="M18 4v1"/> <path d="M18 9v11"/>',
    "layers-subtract": '<path d="M8 6a2 2 0 0 1 2 -2h8a2 2 0 0 1 2 2v8a2 2 0 0 1 -2 2h-8a2 2 0 0 1 -2 -2l0 -8"/> <path d="M16 16v2a2 2 0 0 1 -2 2h-8a2 2 0 0 1 -2 -2v-8a2 2 0 0 1 2 -2h2"/>',
    "memory": '<path d="M4 6a8 3 0 1 0 16 0a8 3 0 1 0 -16 0"/> <path d="M4 6v6a8 3 0 0 0 16 0v-6"/> <path d="M4 12v6a8 3 0 0 0 16 0v-6"/>',
    "git-branch": '<path d="M5 18a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/> <path d="M5 6a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/> <path d="M15 6a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/> <path d="M7 8l0 8"/> <path d="M9 18h6a2 2 0 0 0 2 -2v-5"/> <path d="M14 14l3 -3l3 3"/>',
    "git-pull-request": '<path d="M4 18a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/> <path d="M4 6a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/> <path d="M16 18a2 2 0 1 0 4 0a2 2 0 1 0 -4 0"/> <path d="M6 8l0 8"/> <path d="M11 6h5a2 2 0 0 1 2 2v8"/> <path d="M14 9l-3 -3l3 -3"/>',
    "search": '<path d="M3 10a7 7 0 1 0 14 0a7 7 0 1 0 -14 0"/> <path d="M21 21l-6 -6"/>',
    "filter": '<path d="M4 4h16v2.172a2 2 0 0 1 -.586 1.414l-4.414 4.414v7l-6 2v-8.5l-4.48 -4.928a2 2 0 0 1 -.52 -1.345v-2.227"/>',
    "eye": '<path d="M10 12a2 2 0 1 0 4 0a2 2 0 0 0 -4 0"/> <path d="M21 12c-2.4 4 -5.4 6 -9 6c-3.6 0 -6.6 -2 -9 -6c2.4 -4 5.4 -6 9 -6c3.6 0 6.6 2 9 6"/>',
    "eye-off": '<path d="M10.585 10.587a2 2 0 0 0 2.829 2.828"/> <path d="M16.681 16.673a8.717 8.717 0 0 1 -4.681 1.327c-3.6 0 -6.6 -2 -9 -6c1.272 -2.12 2.712 -3.678 4.32 -4.674m2.86 -1.146a9.055 9.055 0 0 1 1.82 -.18c3.6 0 6.6 2 9 6c-.666 1.11 -1.379 2.067 -2.138 2.87"/> <path d="M3 3l18 18"/>',
    "list-details": '<path d="M13 5h8"/> <path d="M13 9h5"/> <path d="M13 15h8"/> <path d="M13 19h5"/> <path d="M3 5a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v4a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1l0 -4"/> <path d="M3 15a1 1 0 0 1 1 -1h4a1 1 0 0 1 1 1v4a1 1 0 0 1 -1 1h-4a1 1 0 0 1 -1 -1l0 -4"/>',
    "code": '<path d="M7 8l-4 4l4 4"/> <path d="M17 8l4 4l-4 4"/> <path d="M14 4l-4 16"/>',
    "bug": '<path d="M9 9v-1a3 3 0 0 1 6 0v1"/> <path d="M8 9h8a6 6 0 0 1 1 3v3a5 5 0 0 1 -10 0v-3a6 6 0 0 1 1 -3"/> <path d="M3 13l4 0"/> <path d="M17 13l4 0"/> <path d="M12 20l0 -6"/> <path d="M4 19l3.35 -2"/> <path d="M20 19l-3.35 -2"/> <path d="M4 7l3.75 2.4"/> <path d="M20 7l-3.75 2.4"/>',
    "shield-check": '<path d="M11.46 20.846a12 12 0 0 1 -7.96 -14.846a12 12 0 0 0 8.5 -3a12 12 0 0 0 8.5 3a12 12 0 0 1 -.09 7.06"/> <path d="M15 19l2 2l4 -4"/>',
    "hourglass": '<path d="M6.5 7h11"/> <path d="M6.5 17h11"/> <path d="M6 20v-2a6 6 0 1 1 12 0v2a1 1 0 0 1 -1 1h-10a1 1 0 0 1 -1 -1"/> <path d="M6 4v2a6 6 0 1 0 12 0v-2a1 1 0 0 0 -1 -1h-10a1 1 0 0 0 -1 1"/>',
    "flame": '<path d="M12 10.941c2.333 -3.308 .167 -7.823 -1 -8.941c0 3.395 -2.235 5.299 -3.667 6.706c-1.43 1.408 -2.333 3.294 -2.333 5.588c0 3.704 3.134 6.706 7 6.706c3.866 0 7 -3.002 7 -6.706c0 -1.712 -1.232 -4.403 -2.333 -5.588c-2.084 3.353 -3.257 3.353 -4.667 2.235"/>',
    "sun": '<path d="M8 12a4 4 0 1 0 8 0a4 4 0 1 0 -8 0"/> <path d="M3 12h1m8 -9v1m8 8h1m-9 8v1m-6.4 -15.4l.7 .7m12.1 -.7l-.7 .7m0 11.4l.7 .7m-12.1 -.7l-.7 .7"/>',
    "moon": '<path d="M12 3c.132 0 .263 0 .393 0a7.5 7.5 0 0 0 7.92 12.446a9 9 0 1 1 -8.313 -12.454l0 .008"/>',
    "arrow-up": '<path d="M12 5l0 14"/> <path d="M18 11l-6 -6"/> <path d="M6 11l6 -6"/>',
    "arrow-down": '<path d="M12 5l0 14"/> <path d="M18 13l-6 6"/> <path d="M6 13l6 6"/>',
    "arrows-sort": '<path d="M3 9l4 -4l4 4m-4 -4v14"/> <path d="M21 15l-4 4l-4 -4m4 4v-14"/>',
    "settings": '<path d="M10.325 4.317c.426 -1.756 2.924 -1.756 3.35 0a1.724 1.724 0 0 0 2.573 1.066c1.543 -.94 3.31 .826 2.37 2.37a1.724 1.724 0 0 0 1.065 2.572c1.756 .426 1.756 2.924 0 3.35a1.724 1.724 0 0 0 -1.066 2.573c.94 1.543 -.826 3.31 -2.37 2.37a1.724 1.724 0 0 0 -2.572 1.065c-.426 1.756 -2.924 1.756 -3.35 0a1.724 1.724 0 0 0 -2.573 -1.066c-1.543 .94 -3.31 -.826 -2.37 -2.37a1.724 1.724 0 0 0 -1.065 -2.572c-1.756 -.426 -1.756 -2.924 0 -3.35a1.724 1.724 0 0 0 1.066 -2.573c-.94 -1.543 .826 -3.31 2.37 -2.37c1 .608 2.296 .07 2.572 -1.065"/> <path d="M9 12a3 3 0 1 0 6 0a3 3 0 0 0 -6 0"/>',
    "package": '<path d="M12 3l8 4.5l0 9l-8 4.5l-8 -4.5l0 -9l8 -4.5"/> <path d="M12 12l8 -4.5"/> <path d="M12 12l0 9"/> <path d="M12 12l-8 -4.5"/> <path d="M16 5.25l-8 4.5"/>',
    "terminal-2": '<path d="M8 9l3 3l-3 3"/> <path d="M13 15l3 0"/> <path d="M3 6a2 2 0 0 1 2 -2h14a2 2 0 0 1 2 2v12a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2l0 -12"/>',
    "circle-check": '<path d="M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0"/> <path d="M9 12l2 2l4 -4"/>',
    "circle-x": '<path d="M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0"/> <path d="M10 10l4 4m0 -4l-4 4"/>',
    "circle-dashed": '<path d="M8.56 3.69a9 9 0 0 0 -2.92 1.95"/> <path d="M3.69 8.56a9 9 0 0 0 -.69 3.44"/> <path d="M3.69 15.44a9 9 0 0 0 1.95 2.92"/> <path d="M8.56 20.31a9 9 0 0 0 3.44 .69"/> <path d="M15.44 20.31a9 9 0 0 0 2.92 -1.95"/> <path d="M20.31 15.44a9 9 0 0 0 .69 -3.44"/> <path d="M20.31 8.56a9 9 0 0 0 -1.95 -2.92"/> <path d="M15.44 3.69a9 9 0 0 0 -3.44 -.69"/>',
    "plug": '<path d="M9.785 6l8.215 8.215l-2.054 2.054a5.81 5.81 0 1 1 -8.215 -8.215l2.054 -2.054"/> <path d="M4 20l3.5 -3.5"/> <path d="M15 4l-3.5 3.5"/> <path d="M20 9l-3.5 3.5"/>',
    "sparkles": '<path d="M16 18a2 2 0 0 1 2 2a2 2 0 0 1 2 -2a2 2 0 0 1 -2 -2a2 2 0 0 1 -2 2m0 -12a2 2 0 0 1 2 2a2 2 0 0 1 2 -2a2 2 0 0 1 -2 -2a2 2 0 0 1 -2 2m-7 12a6 6 0 0 1 6 -6a6 6 0 0 1 -6 -6a6 6 0 0 1 -6 6a6 6 0 0 1 6 6"/>',
}
_ICONS_JSON_NAMES = ("search", "x", "chevron-down", "check", "copy")


def _e(value) -> str:
    """HTML-escape any value (None becomes an empty string)."""
    if value is None:
        return ""
    return _html.escape(str(value), quote=True)


def _slug(value, default: str = "x") -> str:
    s = _re.sub(r"[^A-Za-z0-9_-]+", "-", str(value if value is not None else "")).strip("-")
    return s or default


def _kind(value) -> str:
    return _slug(str(value or "").lower(), "") if value else ""


def _safe(default: str = ""):
    """Decorator: a builder must never raise on odd input, it returns `default` instead."""
    def deco(fn):
        @_wraps(fn)
        def inner(*a, **k):
            try:
                return fn(*a, **k)
            except Exception:  # noqa: BLE001 - robustness is the contract
                return default
        return inner
    return deco


@_safe()
def icon(name: str, size: int = 16, cls: str = "") -> str:
    """Inline Tabler outline icon (currentColor). Unknown names give an empty string."""
    body = _ICONS.get(str(name or "").strip().lower())
    if body is None:
        return ""
    try:
        px = max(6, min(128, int(size)))
    except (TypeError, ValueError):
        px = 16
    extra = (" " + _e(cls).strip()) if cls else ""
    return (f'<svg class="ic ic-{_slug(name)}{extra}" xmlns="http://www.w3.org/2000/svg" width="{px}" height="{px}" '
            f'viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" '
            f'stroke-linejoin="round" aria-hidden="true" focusable="false">{body}</svg>')


# ---------------------------------------------------------------------------------------------------------------------
# Source links
# ---------------------------------------------------------------------------------------------------------------------

_source_base = ""


def set_source_base(url_template: str) -> None:
    """Template such as https://github.com/Smoothieware/Smoothieware/blob/<rev>/{path}; empty disables links."""
    global _source_base
    try:
        t = str(url_template or "").strip()
    except Exception:  # noqa: BLE001
        t = ""
    if _re.match(r"^\s*(javascript|data|vbscript):", t, _re.I):
        t = ""
    _source_base = t


@_safe()
def file_link(path: str, line: int | None = None, label: str | None = None) -> str:
    """File name as a link to the source on GitHub (plain styled text when no base is set)."""
    p = str(path if path is not None else "").strip()
    ln = None
    try:
        if line is not None and int(line) > 0:
            ln = int(line)
    except (TypeError, ValueError):
        ln = None
    text = label if label else (p + (f":{ln}" if ln else ""))
    if not p and not label:
        return ""
    shown = _e(text).replace("/", "/<wbr>")  # lets long paths wrap at directory boundaries on phones
    inner = f'{icon("file-code", 14, "flink-ic")}<span class="flink-text">{shown}</span>'
    rel = p.replace("\\", "/").lstrip("/")
    while rel.startswith("./"):
        rel = rel[2:]
    if not _source_base or not rel:
        return f'<span class="flink" title="{_e(p)}">{inner}</span>'
    if "{path}" in _source_base:
        url = _source_base.replace("{path}", _quote(rel, safe="/"))
    else:
        url = _source_base.rstrip("/") + "/" + _quote(rel, safe="/")
    if ln:
        url += f"#L{ln}"
    title = f"Open {p}{(' at line ' + str(ln)) if ln else ''} on GitHub"
    return (f'<a class="flink" href="{_e(url)}" target="_blank" rel="noopener noreferrer" title="{_e(title)}">'
            f'{inner}{icon("external-link", 12, "flink-ext")}</a>')


# ---------------------------------------------------------------------------------------------------------------------
# Small components
# ---------------------------------------------------------------------------------------------------------------------

_STATUS = {
    "pass": ("pass", "circle-check", "Pass"),
    "fail": ("fail", "circle-x", "Fail"),
    "warn": ("warn", "alert-triangle", "Warning"),
    "info": ("info", "info-circle", "Info"),
    "exercised": ("pass", "circle-check", "Exercised"),
    "partial": ("warn", "circle-dashed", "Partial"),
    "loaded-not-run": ("warn", "player-pause", "Loaded, not run"),
    "excluded": ("fail", "circle-x", "Excluded"),
}


@_safe()
def status_badge(status: str) -> str:
    """Coloured pill with icon and text for a result or coverage state."""
    key = str(status or "").strip().lower()
    tone, ic, text = _STATUS.get(key, ("info", "info-circle", str(status) if status else "Unknown"))
    return f'<span class="badge badge-{tone}" data-status="{_e(key)}">{icon(ic, 14)}<span>{_e(text)}</span></span>'


@_safe()
def chip(text: str, kind: str = "", icon_name: str = "") -> str:
    k = _kind(kind)
    ic = icon(icon_name, 12) if icon_name else ""
    return f'<span class="chip{(" chip-" + k) if k else ""}">{ic}<span>{_e(text)}</span></span>'


@_safe()
def stat_card(label: str, value: str, kind: str = "", icon_name: str = "") -> str:
    """Headline number tile. `value` is plain text (escaped)."""
    k = _kind(kind)
    ic = f'<span class="stat-ic">{icon(icon_name, 20)}</span>' if icon_name else ""
    return (f'<div class="stat{(" stat-" + k) if k else ""}">{ic}<div class="stat-body">'
            f'<div class="stat-label">{_e(label)}</div><div class="stat-value">{_e(value)}</div></div></div>')


@_safe()
def copy_button(text: str, label: str = "") -> str:
    """Copy-to-clipboard button; `label` is optional visible text."""
    lab = f'<span class="copy-label" data-idle="{_e(label)}">{_e(label)}</span>' if label else ""
    return (f'<button type="button" class="copy-btn" data-copy="{_e(text)}" aria-label="Copy {_e(label or "to clipboard")}" '
            f'title="Copy"><span class="ic-copy">{icon("copy", 14)}</span><span class="ic-done">{icon("check", 14)}</span>{lab}</button>')


@_safe()
def progress_bar(value, total, kind: str = "") -> str:
    """Thin proportion bar (value of total) with a screen-reader text."""
    try:
        v, t = float(value), float(total)
        pct = 0.0 if t <= 0 else max(0.0, min(100.0, v / t * 100.0))
    except (TypeError, ValueError):
        v, t, pct = 0.0, 0.0, 0.0
    k = _kind(kind)
    return (f'<span class="bar{(" bar-" + k) if k else ""}" role="progressbar" aria-valuemin="0" aria-valuemax="100" '
            f'aria-valuenow="{pct:.0f}" aria-label="{pct:.0f} percent"><span style="width:{pct:.1f}%"></span></span>')


@_safe()
def callout(body_html: str, kind: str = "info", icon_name: str = "") -> str:
    """Highlighted note. `body_html` is trusted HTML."""
    k = _kind(kind) or "info"
    default_ic = {"pass": "circle-check", "fail": "circle-x", "warn": "alert-triangle", "info": "info-circle"}.get(k, "info-circle")
    return f'<div class="callout callout-{k}">{icon(icon_name or default_ic, 18)}<div>{body_html or ""}</div></div>'


@_safe()
def kv_grid(pairs) -> str:
    """Definition grid from (key, value_html) pairs; keys are escaped, values are trusted HTML. None values show a dash."""
    items = pairs.items() if isinstance(pairs, dict) else (pairs or [])
    out = []
    for item in items:
        try:
            k, v = item
        except (TypeError, ValueError):
            continue
        out.append(f'<div class="kv-row"><dt>{_e(k)}</dt><dd>{"&ndash;" if v is None or v == "" else v}</dd></div>')
    return f'<dl class="kv">{"".join(out)}</dl>'


@_safe()
def section_head(title: str, icon_name: str = "", badge_html: str = "", sub: str = "") -> str:
    ic = f'<span class="sec-ic">{icon(icon_name, 20)}</span>' if icon_name else ""
    subtitle = f'<p class="sec-sub">{_e(sub)}</p>' if sub else ""
    badge = f'<span class="sec-badge">{badge_html}</span>' if badge_html else ""
    return f'<div class="sec-head">{ic}<div class="sec-title"><h2>{_e(title)}</h2>{subtitle}</div>{badge}</div>'


@_safe()
def hero(title: str, subtitle: str = "", badge_html: str = "", stats_html: str = "") -> str:
    sub = f'<p class="hero-sub">{_e(subtitle)}</p>' if subtitle else ""
    stats = f'<div class="stats">{stats_html}</div>' if stats_html else ""
    return (f'<header class="hero"><div class="hero-top"><h1>{_e(title)}</h1>{badge_html or ""}</div>{sub}{stats}</header>')


def _drawer_ids(drawer_id) -> str:
    return _slug(drawer_id, "drawer")


@_safe(("", ""))
def drawer_parts(button_label: str, body_html: str, drawer_id: str, open_by_default: bool = False) -> tuple[str, str]:
    """The drawer split in two: (toggle button HTML, collapsible panel HTML).

    The two may live in different places, for example the button in a table cell and the panel in a following
    <tr class="detail-row"><td colspan="N">...</td></tr> so the card can use the full table width."""
    did = _drawer_ids(drawer_id)
    opened = bool(open_by_default)
    button = (f'<button type="button" class="drawer-btn" id="{did}-btn" data-drawer-toggle aria-expanded="{"true" if opened else "false"}" aria-controls="{did}">'
              f'{icon("info-circle", 16, "drawer-ic")}<span class="drawer-label">{_e(button_label)}</span>{icon("chevron-down", 14, "drawer-chev")}</button>')
    panel = (f'<div class="drawer{" is-open" if opened else ""}" id="{did}" role="region" aria-labelledby="{did}-btn">'
             f'<div class="drawer-inner"><div class="drawer-card">{body_html or ""}</div></div></div>')
    return button, panel


@_safe()
def drawer(button_label: str, body_html: str, drawer_id: str, open_by_default: bool = False) -> str:
    """Icon button that toggles a smoothly animated card directly below it (aria-expanded / aria-controls)."""
    button, panel = drawer_parts(button_label, body_html, drawer_id, open_by_default)
    return f'<div class="drawer-wrap">{button}{panel}</div>'


@_safe()
def nav(items, brand: str = "", tools: bool = True) -> str:
    """Sticky top navigation. items: (anchor_id, label, icon_name). Includes theme and expand/collapse buttons."""
    links = []
    for it in items or []:
        try:
            anchor, label, ic = (list(it) + ["", "", ""])[:3]
        except TypeError:
            continue
        links.append(f'<a href="#{_slug(anchor)}" data-spy title="{_e(label)}">{icon(ic, 16) if ic else ""}<span class="nav-label">{_e(label)}</span></a>')
    brand_html = f'<a class="nav-brand" href="#top" title="Back to top">{icon("sparkles", 16)}<span>{_e(brand)}</span></a>' if brand else ""
    tool_html = ""
    if tools:
        tool_html = ('<div class="topnav-tools">'
                     f'<button type="button" class="icon-btn" data-action="expand-all" aria-label="Expand all details" title="Expand all details">{icon("chevron-down", 16)}</button>'
                     f'<button type="button" class="icon-btn" data-action="collapse-all" aria-label="Collapse all details" title="Collapse all details">{icon("chevron-down", 16, "flip")}</button>'
                     f'<button type="button" class="icon-btn" data-action="theme" aria-label="Switch theme" title="Switch theme">'
                     f'<span class="ic-to-light">{icon("sun", 16)}</span><span class="ic-to-dark">{icon("moon", 16)}</span></button></div>')
    return (f'<header class="topnav" id="top"><nav aria-label="Report sections"><div class="topnav-inner">{brand_html}'
            f'<div class="topnav-links">{"".join(links)}</div>{tool_html}</div></nav></header>')


# ---------------------------------------------------------------------------------------------------------------------
# Code block with a small C/C++ highlighter
# ---------------------------------------------------------------------------------------------------------------------

_KEYWORDS = ("alignas alignof asm auto bool break case catch char class const constexpr continue default delete do double "
             "else enum explicit extern false float for friend goto if inline int long mutable namespace new noexcept "
             "nullptr operator override private protected public register return short signed sizeof static struct switch "
             "template this throw true try typedef typename union unsigned using virtual void volatile while "
             "uint8_t uint16_t uint32_t uint64_t int8_t int16_t int32_t int64_t size_t").split()
_TOKEN_RE = _re.compile(
    r"(?P<c>//[^\n]*|/\*.*?\*/)"
    r"|(?P<s>\"(?:\\.|[^\"\\\n])*\"|'(?:\\.|[^'\\\n])*')"
    r"|(?P<p>^[ \t]*\#[ \t]*\w+)"
    r"|(?P<n>\b0[xX][0-9a-fA-F]+[uUlL]*\b|\b\d+(?:\.\d+)?(?:[eE][+-]?\d+)?[fFuUlL]*\b)"
    r"|(?P<k>\b(?:" + "|".join(_KEYWORDS) + r")\b)",
    _re.S | _re.M)


def _highlight_lines(code: str, lang: str) -> list[str]:
    segs: list[tuple[str, str]] = []
    if str(lang).lower() in ("c", "cpp", "c++", "cc", "h", "hpp", "cxx"):
        pos = 0
        for m in _TOKEN_RE.finditer(code):
            if m.start() > pos:
                segs.append(("", code[pos:m.start()]))
            segs.append((m.lastgroup or "", m.group(0)))
            pos = m.end()
        if pos < len(code):
            segs.append(("", code[pos:]))
    else:
        segs.append(("", code))
    lines: list[list[tuple[str, str]]] = [[]]
    for cls, text in segs:
        for i, part in enumerate(text.split("\n")):
            if i:
                lines.append([])
            if part:
                lines[-1].append((cls, part))
    return ["".join(f'<span class="tk-{c}">{_e(t)}</span>' if c else _e(t) for c, t in ln) for ln in lines]


@_safe()
def code_block(code: str, lang: str = "", path: str | None = None, start_line: int = 1, highlight=None, copy: bool = True) -> str:
    """Numbered, highlighted, copyable code listing. `highlight` is a line number or iterable of absolute line numbers."""
    text = str(code if code is not None else "").replace("\r\n", "\n").rstrip("\n")
    try:
        first = int(start_line)
    except (TypeError, ValueError):
        first = 1
    hl: set[int] = set()
    try:
        if highlight is not None:
            hl = {int(highlight)} if isinstance(highlight, (int, str)) else {int(x) for x in highlight}
    except (TypeError, ValueError):
        hl = set()
    rendered = _highlight_lines(text, lang)
    rows = "".join(f'<span class="cl{" hl" if first + i in hl else ""}" data-n="{first + i}">{r or " "}</span>' for i, r in enumerate(rendered))
    head_left = file_link(path, first if first > 1 or hl else None) if path else ""
    lang_chip = f'<span class="code-lang">{_e(lang)}</span>' if lang else ""
    return (f'<figure class="codebox"><figcaption class="code-head"><span class="code-title">{head_left}{lang_chip}</span>'
            f'{copy_button(text) if copy else ""}</figcaption><pre class="code" tabindex="0"><code>{rows}</code></pre></figure>')


# ---------------------------------------------------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------------------------------------------------

_DARK_TOKENS = """color-scheme:dark;
--bg:#0d1117;--glow:radial-gradient(900px 420px at 8% -8%,rgba(88,166,255,.13),transparent 62%),radial-gradient(760px 380px at 100% 0,rgba(163,113,247,.10),transparent 58%);
--surface:#151b23;--surface-2:#1a212b;--surface-3:#232c38;--border:#2d3640;--border-strong:#414d5c;
--fg:#e6edf3;--fg-2:#c3ccd6;--mut:#8f9bab;
--accent:#58a6ff;--accent-2:#a371f7;--accent-bg:rgba(88,166,255,.13);--accent-bd:rgba(88,166,255,.38);
--pass:#3fb950;--pass-tx:#56d364;--pass-bg:rgba(63,185,80,.14);--pass-bd:rgba(63,185,80,.40);
--fail:#f85149;--fail-tx:#ff7b72;--fail-bg:rgba(248,81,73,.14);--fail-bd:rgba(248,81,73,.42);
--warn:#d29922;--warn-tx:#e3b341;--warn-bg:rgba(210,153,34,.15);--warn-bd:rgba(210,153,34,.42);
--info:#58a6ff;--info-tx:#79c0ff;--info-bg:rgba(88,166,255,.13);--info-bd:rgba(88,166,255,.38);
--nav-bg:rgba(13,17,23,.80);--shadow:0 1px 0 rgba(255,255,255,.03) inset,0 10px 28px rgba(0,0,0,.32);--shadow-sm:0 2px 8px rgba(0,0,0,.30);
--code-bg:#0f141b;--hl-bg:rgba(88,166,255,.16);
--tk-c:#8b949e;--tk-s:#a5d6ff;--tk-k:#ff7b72;--tk-n:#79c0ff;--tk-p:#d2a8ff;--focus:#79c0ff;"""

_LIGHT_TOKENS = """color-scheme:light;
--bg:#f6f8fa;--glow:radial-gradient(900px 420px at 8% -8%,rgba(9,105,218,.08),transparent 62%),radial-gradient(760px 380px at 100% 0,rgba(130,80,223,.07),transparent 58%);
--surface:#ffffff;--surface-2:#f6f8fa;--surface-3:#eaeef2;--border:#d0d7de;--border-strong:#afb8c1;
--fg:#1f2328;--fg-2:#35404b;--mut:#596370;
--accent:#0969da;--accent-2:#8250df;--accent-bg:rgba(9,105,218,.09);--accent-bd:rgba(9,105,218,.35);
--pass:#1a7f37;--pass-tx:#1a7f37;--pass-bg:rgba(26,127,55,.10);--pass-bd:rgba(26,127,55,.35);
--fail:#cf222e;--fail-tx:#cf222e;--fail-bg:rgba(207,34,46,.09);--fail-bd:rgba(207,34,46,.35);
--warn:#9a6700;--warn-tx:#8a5a00;--warn-bg:rgba(154,103,0,.11);--warn-bd:rgba(154,103,0,.38);
--info:#0969da;--info-tx:#0550ae;--info-bg:rgba(9,105,218,.09);--info-bd:rgba(9,105,218,.35);
--nav-bg:rgba(246,248,250,.84);--shadow:0 1px 2px rgba(31,35,40,.06),0 8px 22px rgba(31,35,40,.08);--shadow-sm:0 1px 3px rgba(31,35,40,.10);
--code-bg:#f6f8fa;--hl-bg:rgba(9,105,218,.12);
--tk-c:#59636e;--tk-s:#0a3069;--tk-k:#cf222e;--tk-n:#0550ae;--tk-p:#8250df;--focus:#0969da;"""

_CSS_BODY = r"""
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%;scroll-behavior:smooth;--r:12px;--r-sm:8px;
 --font:-apple-system,BlinkMacSystemFont,"Segoe UI Variable","Segoe UI",system-ui,"Helvetica Neue",Arial,sans-serif;
 --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace}
body{margin:0;background:var(--bg);background-image:var(--glow);background-repeat:no-repeat;color:var(--fg);
 font:15px/1.55 var(--font);font-variant-numeric:tabular-nums;min-height:100vh;overflow-wrap:break-word;-webkit-font-smoothing:antialiased}
.page{max-width:1100px;margin:0 auto;padding:20px 16px 56px}
[id]{scroll-margin-top:72px}
[hidden]{display:none!important}
.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
a{color:var(--accent);text-decoration-thickness:1px;text-underline-offset:2px}
a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--focus);outline-offset:2px;border-radius:6px}
h1,h2,h3,h4{line-height:1.25;margin:0;letter-spacing:-.01em}
h1{font-size:clamp(1.55rem,4.4vw,2.15rem);font-weight:700;letter-spacing:-.025em}
h2{font-size:1.2rem;font-weight:650}
h3{font-size:1rem;font-weight:650;margin:22px 0 10px;color:var(--fg)}
p{margin:.5em 0}
code,kbd,samp,pre{font-family:var(--mono)}
:not(pre)>code{font-size:.9em;background:var(--surface-3);border:1px solid var(--border);border-radius:6px;padding:.05em .4em}
svg:not(.ic){max-width:100%;height:auto}
svg.ic{display:inline-block;flex:none;vertical-align:-.18em;max-width:none}
.mut{color:var(--mut)}.num{font-variant-numeric:tabular-nums;text-align:right;white-space:nowrap}
.pass{color:var(--pass-tx)}.fail{color:var(--fail-tx)}.warn{color:var(--warn-tx)}.info{color:var(--info-tx)}
.s{font-weight:700;white-space:nowrap}
.flip{transform:rotate(180deg)}

/* top navigation */
.topnav{position:sticky;top:0;z-index:50;background:var(--nav-bg);-webkit-backdrop-filter:saturate(170%) blur(14px);backdrop-filter:saturate(170%) blur(14px);border-bottom:1px solid var(--border)}
.topnav-inner{max-width:1100px;margin:0 auto;padding:7px 16px;display:flex;align-items:center;gap:10px}
.topnav-links{display:flex;gap:2px;min-width:0;flex:1;overflow-x:auto;scrollbar-width:none;-ms-overflow-style:none}
.topnav-links::-webkit-scrollbar{display:none}
.topnav-links a,.nav-brand{display:inline-flex;align-items:center;gap:7px;padding:7px 11px;border-radius:9px;color:var(--mut);font-size:13.5px;font-weight:560;text-decoration:none;white-space:nowrap;transition:background .18s,color .18s}
.nav-brand{color:var(--fg);font-weight:700;padding-left:6px}.nav-brand .ic{color:var(--accent)}
.topnav-links a:hover{background:var(--surface-3);color:var(--fg);text-decoration:none}
.topnav-links a[aria-current="true"]{color:var(--fg);background:var(--accent-bg);box-shadow:inset 0 -2px 0 var(--accent)}
.topnav-tools{display:flex;gap:6px;flex:none}
.icon-btn{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;border:1px solid var(--border);background:var(--surface-2);color:var(--fg-2);border-radius:var(--r-sm);cursor:pointer;padding:0;transition:border-color .18s,background .18s,color .18s,transform .18s}
.icon-btn:hover{border-color:var(--border-strong);background:var(--surface-3);color:var(--fg)}
.icon-btn:active{transform:scale(.95)}
.ic-to-dark{display:none}
.ic-to-light,.ic-to-dark{display:inline-flex}
:root[data-theme="light"] .ic-to-light{display:none}:root[data-theme="light"] .ic-to-dark{display:inline-flex}
:root[data-theme="dark"] .ic-to-dark{display:none}
@media (prefers-color-scheme:light){:root:not([data-theme="dark"]) .ic-to-light{display:none}:root:not([data-theme="dark"]) .ic-to-dark{display:inline-flex}}

/* hero, cards, sections */
.hero{position:relative;border:1px solid var(--border);border-radius:16px;padding:22px 22px 20px;margin:0 0 18px;overflow:hidden;
 background:linear-gradient(135deg,var(--accent-bg),transparent 55%),var(--surface);box-shadow:var(--shadow)}
.hero::before{content:"";position:absolute;inset:0 0 auto 0;height:3px;background:linear-gradient(90deg,var(--accent),var(--accent-2))}
.hero-top{display:flex;flex-wrap:wrap;align-items:center;gap:10px 14px;justify-content:space-between}
.hero-sub{color:var(--mut);margin:.45em 0 0;max-width:80ch}
.hero .stats{margin-top:16px}
section,.card{background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:18px 20px;margin:18px 0;box-shadow:var(--shadow)}
section>h2:first-child,.sec-head h2{display:flex;align-items:center;flex-wrap:wrap;gap:8px 10px}
.sec-head{display:flex;align-items:flex-start;gap:12px;margin-bottom:12px}
.sec-ic{display:inline-flex;align-items:center;justify-content:center;width:36px;height:36px;flex:none;border-radius:10px;background:var(--accent-bg);color:var(--accent);border:1px solid var(--accent-bd)}
.sec-title{flex:1;min-width:0}.sec-sub{margin:.2em 0 0;color:var(--mut);font-size:13.5px}.sec-badge{flex:none}
details{margin:.9em 0;background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-sm);padding:.15em .9em;transition:border-color .18s}
details[open]{padding-bottom:.7em;border-color:var(--border-strong)}
summary{cursor:pointer;color:var(--fg-2);padding:.55em 0;font-weight:560;list-style:none;display:flex;align-items:center;gap:9px}
summary::-webkit-details-marker{display:none}
summary::before{content:"";flex:none;width:7px;height:7px;border-right:2px solid var(--mut);border-bottom:2px solid var(--mut);transform:rotate(-45deg);transition:transform .2s}
details[open]>summary::before{transform:rotate(45deg)}
summary:hover{color:var(--fg)}

/* stat cards */
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:12px 0}
.stat{position:relative;display:flex;align-items:center;gap:12px;min-width:0;background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r);padding:12px 14px;overflow:hidden;transition:transform .18s,border-color .18s}
.stat:hover{transform:translateY(-1px);border-color:var(--border-strong)}
.stat::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--border-strong)}
.stat-ic{display:inline-flex;align-items:center;justify-content:center;width:38px;height:38px;flex:none;border-radius:10px;background:var(--surface-3);color:var(--fg-2)}
.stat-body{min-width:0}
.stat-label{font-size:11.5px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--mut)}
.stat-value{font-size:1.5rem;font-weight:700;line-height:1.2;letter-spacing:-.02em;overflow-wrap:anywhere}
.stat-pass::before{background:var(--pass)}.stat-pass .stat-ic{background:var(--pass-bg);color:var(--pass-tx)}
.stat-fail::before{background:var(--fail)}.stat-fail .stat-ic{background:var(--fail-bg);color:var(--fail-tx)}
.stat-warn::before{background:var(--warn)}.stat-warn .stat-ic{background:var(--warn-bg);color:var(--warn-tx)}
.stat-info::before,.stat-accent::before{background:var(--accent)}.stat-info .stat-ic,.stat-accent .stat-ic{background:var(--info-bg);color:var(--info-tx)}

/* badges and chips */
.badge,.chip{display:inline-flex;align-items:center;gap:5px;max-width:100%;border-radius:999px;border:1px solid var(--border);font-size:12px;font-weight:600;line-height:1.3;white-space:nowrap}
@media(max-width:640px){.chip{white-space:normal;overflow-wrap:anywhere;border-radius:12px}}
.badge{padding:2px 10px 2px 7px}
.chip{padding:1px 9px;background:var(--surface-3);color:var(--fg-2);font-weight:560}
.badge-pass,.chip-pass{background:var(--pass-bg);border-color:var(--pass-bd);color:var(--pass-tx)}
.badge-fail,.chip-fail{background:var(--fail-bg);border-color:var(--fail-bd);color:var(--fail-tx)}
.badge-warn,.chip-warn{background:var(--warn-bg);border-color:var(--warn-bd);color:var(--warn-tx)}
.badge-info,.chip-info,.chip-accent{background:var(--info-bg);border-color:var(--info-bd);color:var(--info-tx)}
.chip-mono{font-family:var(--mono);font-size:11.5px}

/* file links */
.flink{display:inline;font-family:var(--mono);font-size:.9em;color:var(--accent);text-decoration:none;border-radius:6px;padding:1px 3px;margin:0 -3px;transition:background .15s}
a.flink:hover{background:var(--accent-bg);text-decoration:none}
a.flink:hover .flink-text{text-decoration:underline;text-underline-offset:3px}
span.flink{color:var(--fg-2)}
.flink-text{overflow-wrap:anywhere}
.flink-ic{margin-right:4px;opacity:.85}
.flink-ext{margin-left:4px;opacity:.55}
a.flink:hover .flink-ext{opacity:1}

/* tables */
.tbl-scroll{overflow-x:auto;border:1px solid var(--border);border-radius:var(--r-sm);background:var(--surface);margin:10px 0;-webkit-overflow-scrolling:touch}
table{border-collapse:separate;border-spacing:0;width:100%;font-size:13px}
.tbl-scroll>table{margin:0}
th,td{padding:8px 12px;text-align:left;vertical-align:top;overflow-wrap:anywhere;border-bottom:1px solid var(--border)}
th{position:relative;font-size:11.5px;font-weight:650;letter-spacing:.04em;text-transform:uppercase;color:var(--mut);background:var(--surface-2);white-space:nowrap;border-bottom-color:var(--border-strong)}
tbody tr:last-child>td{border-bottom:0}
tbody tr:hover>td{background:var(--surface-2)}
tr.detail-row>td{background:var(--surface)!important;padding:0 12px;border-bottom:1px solid var(--border)}
tr.detail-row:has(.drawer.is-open)>td{padding:0 12px 12px}
tr:has(+tr.detail-row)>td{border-bottom:0}
tr.detail-row .drawer-inner{position:sticky;left:12px;width:var(--scroll-w,auto)}  /* keeps the card inside the visible part of a horizontally scrolling table */
table[data-sortable] th:not(.nosort){cursor:pointer;user-select:none;padding-right:26px}
table[data-sortable] th:not(.nosort):hover{color:var(--fg)}
table[data-sortable] th:not(.nosort)::after{content:"";position:absolute;right:10px;top:50%;width:8px;height:8px;margin-top:-5px;opacity:.35;
 border-right:2px solid currentColor;border-bottom:2px solid currentColor;transform:rotate(45deg) scale(.7);transition:transform .2s,opacity .2s}
th[aria-sort="ascending"]{color:var(--accent)}th[aria-sort="descending"]{color:var(--accent)}
th[aria-sort="ascending"]::after{opacity:1!important;transform:rotate(225deg) scale(.7)!important;margin-top:-2px!important}
th[aria-sort="descending"]::after{opacity:1!important;transform:rotate(45deg) scale(.7)!important}
.tbl-tools{display:flex;flex-wrap:wrap;align-items:center;gap:8px 10px;margin:14px 0 0}
.tbl-search{display:flex;align-items:center;gap:8px;flex:1 1 200px;max-width:340px;background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r-sm);padding:0 10px;color:var(--mut);transition:border-color .18s,box-shadow .18s}
.tbl-search:focus-within{border-color:var(--accent);box-shadow:0 0 0 3px var(--accent-bg);color:var(--accent)}
.tbl-search input{flex:1;min-width:0;height:34px;border:0;outline:0;background:transparent;color:var(--fg);font:inherit;font-size:13.5px}
.tbl-search input::placeholder{color:var(--mut)}
.tbl-chips{display:flex;flex-wrap:wrap;gap:6px}
.tbl-chip{border:1px solid var(--border);background:var(--surface-2);color:var(--fg-2);border-radius:999px;padding:3px 11px;font:inherit;font-size:12.5px;font-weight:560;cursor:pointer;transition:background .15s,border-color .15s}
.tbl-chip:hover{border-color:var(--border-strong)}
.tbl-chip[aria-pressed="true"]{background:var(--accent-bg);border-color:var(--accent-bd);color:var(--accent)}
.tbl-count{margin-left:auto;font-size:12.5px;color:var(--mut)}

/* drawer */
.drawer-wrap{display:block;margin:8px 0}
.drawer-btn{overflow-wrap:normal;word-break:normal;white-space:nowrap;display:inline-flex;align-items:center;gap:8px;max-width:100%;padding:6px 12px 6px 10px;border-radius:999px;border:1px solid var(--accent-bd);background:var(--accent-bg);color:var(--accent);
 font:inherit;font-size:13px;font-weight:620;cursor:pointer;transition:background .18s,border-color .18s,transform .18s,box-shadow .18s}
.drawer-btn:hover{border-color:var(--accent);box-shadow:var(--shadow-sm)}
.drawer-btn:active{transform:scale(.98)}
.drawer-label{text-align:left;overflow:hidden;text-overflow:ellipsis}
.drawer-chev{transition:transform .3s cubic-bezier(.2,.8,.2,1)}
.drawer-btn[aria-expanded="true"] .drawer-chev{transform:rotate(180deg)}
.drawer{display:grid;grid-template-rows:0fr;opacity:0;visibility:hidden;transition:grid-template-rows .34s cubic-bezier(.2,.8,.2,1),opacity .25s ease,visibility 0s linear .34s}
.drawer.is-open{grid-template-rows:1fr;opacity:1;visibility:visible;transition-delay:0s}
.drawer-inner{min-height:0;overflow:hidden;padding:0 3px}
.drawer.is-open .drawer-inner{padding:10px 3px 4px}
.drawer-card{position:relative;background:var(--surface-2);border:1px solid var(--border);border-radius:var(--r);padding:16px 18px;box-shadow:var(--shadow-sm);overflow:hidden}
.drawer-card::before{content:"";position:absolute;inset:0 0 auto 0;height:2px;background:linear-gradient(90deg,var(--accent),var(--accent-2))}
.drawer-card h4{display:flex;align-items:center;gap:7px;margin:16px 0 8px;font-size:11.5px;font-weight:700;letter-spacing:.07em;text-transform:uppercase;color:var(--mut)}
.drawer-card h4:first-child{margin-top:0}
.drawer-card h4 .ic{color:var(--accent)}
.drawer-card p{margin:.4em 0}
.drawer-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px 20px}
.drawer-card .tbl-scroll{background:var(--surface)}

/* key-value grid, callouts, bars */
.kv{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:8px 18px;margin:0}
.kv-row{min-width:0;padding:8px 0;border-bottom:1px dashed var(--border)}
.kv dt{font-size:11.5px;font-weight:600;letter-spacing:.05em;text-transform:uppercase;color:var(--mut)}
.kv dd{margin:2px 0 0;overflow-wrap:anywhere}
.callout{display:flex;gap:10px;align-items:flex-start;padding:10px 14px;margin:10px 0;border-radius:var(--r-sm);border:1px solid var(--info-bd);background:var(--info-bg);color:var(--fg)}
.callout>.ic{margin-top:3px}.callout>div{min-width:0}
.callout-info>.ic{color:var(--info-tx)}.callout-pass{border-color:var(--pass-bd);background:var(--pass-bg)}.callout-pass>.ic{color:var(--pass-tx)}
.callout-warn{border-color:var(--warn-bd);background:var(--warn-bg)}.callout-warn>.ic{color:var(--warn-tx)}
.callout-fail{border-color:var(--fail-bd);background:var(--fail-bg)}.callout-fail>.ic{color:var(--fail-tx)}
.bar{display:inline-block;vertical-align:middle;width:100%;max-width:140px;height:6px;border-radius:99px;background:var(--surface-3);overflow:hidden}
.bar>span{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,var(--accent),var(--accent-2))}
.bar-pass>span{background:var(--pass)}.bar-fail>span{background:var(--fail)}.bar-warn>span{background:var(--warn)}

/* code */
.codebox{margin:10px 0;border:1px solid var(--border);border-radius:var(--r-sm);overflow:hidden;background:var(--code-bg)}
.code-head{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:6px 8px 6px 12px;background:var(--surface-3);border-bottom:1px solid var(--border);font-size:12.5px;min-width:0}
.code-title{display:flex;align-items:center;flex-wrap:wrap;gap:4px 10px;min-width:0}
.code-lang{font-family:var(--mono);font-size:11px;color:var(--mut);text-transform:uppercase;letter-spacing:.05em}
pre.code{margin:0;padding:10px 0;overflow-x:auto;font-size:12.5px;line-height:1.6;tab-size:4;-moz-tab-size:4}
pre.code code{display:block;min-width:max-content;font-family:var(--mono)}
.cl{display:block;padding:0 14px 0 0;white-space:pre}
.cl::before{content:attr(data-n);display:inline-block;width:3.6em;margin-right:12px;padding-right:10px;text-align:right;color:var(--mut);border-right:1px solid var(--border);user-select:none;-webkit-user-select:none}
.cl.hl{background:var(--hl-bg);box-shadow:inset 3px 0 0 var(--accent)}
.tk-c{color:var(--tk-c);font-style:italic}.tk-s{color:var(--tk-s)}.tk-k{color:var(--tk-k)}.tk-n{color:var(--tk-n)}.tk-p{color:var(--tk-p)}

/* copy button */
.copy-btn{display:inline-flex;align-items:center;gap:6px;border:1px solid var(--border);background:var(--surface-2);color:var(--fg-2);border-radius:7px;padding:3px 8px;font:inherit;font-size:12px;font-weight:560;cursor:pointer;flex:none;transition:background .15s,border-color .15s,color .15s}
.copy-btn:hover{border-color:var(--border-strong);color:var(--fg)}
.copy-btn .ic-done{display:none}.copy-btn.copied .ic-copy{display:none}.copy-btn.copied .ic-done{display:inline-flex}
.copy-btn.copied{color:var(--pass-tx);border-color:var(--pass-bd);background:var(--pass-bg)}
.copy-btn.copy-failed{color:var(--fail-tx);border-color:var(--fail-bd)}

/* tooltips: <span class="tip" data-tip="text" tabindex="0"> */
[data-tip]{position:relative;cursor:help;text-decoration:underline dotted var(--mut);text-underline-offset:3px}
[data-tip]::after{content:attr(data-tip);position:absolute;left:50%;bottom:calc(100% + 8px);transform:translate(-50%,4px);width:max-content;max-width:min(280px,78vw);
 padding:6px 10px;border-radius:8px;background:var(--surface-3);border:1px solid var(--border-strong);color:var(--fg);font:500 12.5px/1.4 var(--font);text-transform:none;letter-spacing:0;white-space:normal;text-align:left;
 box-shadow:var(--shadow);opacity:0;visibility:hidden;pointer-events:none;transition:opacity .15s,transform .15s;z-index:60}
[data-tip]:hover::after,[data-tip]:focus-visible::after{opacity:1;visibility:visible;transform:translate(-50%,0)}

/* small screens */
@media (max-width:640px){
 body{font-size:14.5px}
 .page{padding:14px 12px 44px}
 section,.card{padding:14px 12px;margin:14px 0}
 .hero{padding:16px 14px}
 .topnav-inner{padding:6px 10px;gap:6px}
 .nav-label{display:none}
 .topnav-links a[aria-current="true"] .nav-label{display:inline}
 .nav-brand span{display:none}
 .topnav-links a{padding:8px 10px}
 .stats{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
 .stat{padding:10px;gap:9px}.stat-ic{width:32px;height:32px}.stat-value{font-size:1.25rem}
 th,td{padding:7px 8px}
 table{font-size:12.5px}
 .drawer-card{padding:14px 12px}
 .tbl-search{max-width:none}
 .tbl-count{margin-left:0;width:100%}
 .kv{grid-template-columns:1fr}
}
@media (max-width:380px){.topnav-tools .icon-btn:first-child,.topnav-tools .icon-btn:nth-child(2){display:none}}
@media (prefers-reduced-motion:reduce){
 html{scroll-behavior:auto}
 *,*::before,*::after{transition-duration:.001ms!important;animation-duration:.001ms!important}
}
@media print{
 body{background:#fff!important;background-image:none!important}
 .topnav,.tbl-tools,.copy-btn,.icon-btn,.drawer-chev{display:none!important}
 section,.card,.hero,.stat,.drawer-card{box-shadow:none!important;break-inside:avoid-page}
 .drawer{grid-template-rows:1fr!important;opacity:1!important;visibility:visible!important}
 .drawer-inner{padding:6px 3px!important}
 .tbl-scroll{overflow:visible}
 a.flink::after{content:none}
}
"""


def _build_css() -> str:
    light = _LIGHT_TOKENS
    return (":root{" + _DARK_TOKENS + "}\n"
            "@media (prefers-color-scheme:light){:root:not([data-theme=\"dark\"]){" + light + "}}\n"
            ":root[data-theme=\"light\"]{" + light + "}\n"
            ":root[data-theme=\"dark\"]{" + _DARK_TOKENS + "}\n"
            "@media print{:root{" + light + "}}\n" + _CSS_BODY)


CSS: str = _build_css()

# ---------------------------------------------------------------------------------------------------------------------
# JavaScript
# ---------------------------------------------------------------------------------------------------------------------

HEAD_JS: str = ("(function(){try{var t=localStorage.getItem('smoothie-sim-report-theme');"
                "if(t==='light'||t==='dark')document.documentElement.setAttribute('data-theme',t);}catch(e){}})();")

_JS_TEMPLATE = r"""
(function () {
  'use strict';
  var D = document, W = window, ICONS = %%ICONS%%;
  var THEME_KEY = 'smoothie-sim-report-theme';

  function log(n, e) { try { console.warn('[report-ui] ' + n, e); } catch (_) {} }
  function safe(n, f) { try { f(); } catch (e) { log(n, e); } }
  function $(s, r) { return (r || D).querySelector(s); }
  function $$(s, r) { return Array.prototype.slice.call((r || D).querySelectorAll(s)); }
  function up(el, sel) { return el && el.closest ? el.closest(sel) : null; }

  /* ---------- theme ---------- */
  function storedTheme() { try { var v = localStorage.getItem(THEME_KEY); return v === 'light' || v === 'dark' ? v : null; } catch (e) { return null; } }
  function storeTheme(v) { try { localStorage.setItem(THEME_KEY, v); } catch (e) {} }
  function systemTheme() { try { return W.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'; } catch (e) { return 'dark'; } }
  function theme() { return D.documentElement.getAttribute('data-theme') || systemTheme(); }
  function syncThemeButtons() {
    var t = theme(), next = t === 'light' ? 'dark' : 'light';
    $$('[data-action="theme"]').forEach(function (b) {
      b.setAttribute('aria-pressed', t === 'light' ? 'true' : 'false');
      b.setAttribute('aria-label', 'Switch to ' + next + ' theme');
      b.setAttribute('title', 'Switch to ' + next + ' theme');
    });
  }
  function applyTheme(t) { D.documentElement.setAttribute('data-theme', t); storeTheme(t); syncThemeButtons(); }

  /* ---------- drawers ---------- */
  function setDrawer(btn, open) {
    var d = D.getElementById(btn.getAttribute('aria-controls'));
    if (!d) return;
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
    d.classList.toggle('is-open', !!open);
  }
  function openFor(el) {
    var d = up(el, '.drawer'), any = false;
    while (d) {
      var b = D.getElementById(d.id + '-btn') || $('[aria-controls="' + d.id + '"]');
      if (b) { setDrawer(b, true); any = true; }
      d = up(d.parentNode, '.drawer');
    }
    var det = up(el, 'details');
    while (det) { det.open = true; det = up(det.parentNode, 'details'); }
    return any;
  }
  function openHash() {
    var id = decodeURIComponent((W.location.hash || '').slice(1));
    if (!id) return;
    var el = D.getElementById(id);
    if (!el) return;
    openFor(el);
    setTimeout(function () { try { el.scrollIntoView({ block: 'start' }); } catch (e) {} }, 380);
  }

  /* ---------- copy ---------- */
  function copyText(text) {
    function fallback() {
      return new Promise(function (res, rej) {
        var ta = D.createElement('textarea');
        ta.value = text; ta.setAttribute('readonly', '');
        ta.style.cssText = 'position:fixed;top:0;left:-9999px;opacity:0';
        D.body.appendChild(ta); ta.select();
        var ok = false; try { ok = D.execCommand('copy'); } catch (e) {}
        D.body.removeChild(ta);
        ok ? res() : rej(new Error('copy failed'));
      });
    }
    try {
      if (navigator.clipboard && navigator.clipboard.writeText) return navigator.clipboard.writeText(text).catch(fallback);
    } catch (e) {}
    return fallback();
  }
  function onCopy(btn) {
    var text = btn.getAttribute('data-copy') || '';
    var label = $('.copy-label', btn), idle = label ? label.getAttribute('data-idle') : '';
    copyText(text).then(function () {
      btn.classList.add('copied'); btn.classList.remove('copy-failed');
      if (label) label.textContent = 'Copied';
    }, function () {
      btn.classList.add('copy-failed'); if (label) label.textContent = 'Copy failed';
    }).then(function () {
      setTimeout(function () { btn.classList.remove('copied', 'copy-failed'); if (label) label.textContent = idle || ''; }, 1600);
    });
  }

  /* ---------- tables: wrap, sort, filter ---------- */
  function wrapTables() {
    $$('table').forEach(function (t) {
      if (up(t.parentNode, '.tbl-scroll')) return;
      var w = D.createElement('div'); w.className = 'tbl-scroll';
      t.parentNode.insertBefore(w, t); w.appendChild(t);
    });
  }
  function rowGroups(tbody) {
    var groups = [];
    Array.prototype.forEach.call(tbody.rows, function (tr) {
      if (tr.classList.contains('detail-row') && groups.length) { groups[groups.length - 1].rows.push(tr); return; }
      if (tr.__ridx === undefined) tr.__ridx = tbody.__count = (tbody.__count || 0) + 1;  // remembered original position
      groups.push({ rows: [tr], idx: tr.__ridx });
    });
    return groups;
  }
  var NUM_RE = /^[+\-−]?\d[\d,]*(?:\.\d+)?/;
  function cellValue(tr, col) {
    var td = tr.cells[col]; if (!td) return '';
    var v = td.getAttribute('data-sort'); if (v === null) v = td.textContent;
    return String(v).trim();
  }
  function sortTable(table, th, dir) {
    var col = th.cellIndex;
    Array.prototype.forEach.call(table.tBodies, function (tb) {
      var groups = rowGroups(tb);
      if (dir === 'none') groups.sort(function (a, b) { return a.idx - b.idx; });
      else {
        var vals = groups.map(function (g) { return cellValue(g.rows[0], col); });
        var numeric = vals.every(function (v) { return v === '' || NUM_RE.test(v); }) && vals.some(function (v) { return v !== ''; });
        var key = function (g) {
          var v = cellValue(g.rows[0], col);
          if (numeric) { var m = NUM_RE.exec(v); return m ? parseFloat(m[0].replace(/,/g, '').replace('−', '-')) : -Infinity; }
          return v;
        };
        var sign = dir === 'ascending' ? 1 : -1;
        groups.sort(function (a, b) {
          var x = key(a), y = key(b), c;
          c = numeric ? (x < y ? -1 : x > y ? 1 : 0) : String(x).localeCompare(String(y), undefined, { numeric: true, sensitivity: 'base' });
          return c * sign || a.idx - b.idx;
        });
      }
      groups.forEach(function (g) { g.rows.forEach(function (r) { tb.appendChild(r); }); });
    });
  }
  function initSortable(table) {
    var head = table.tHead && table.tHead.rows[table.tHead.rows.length - 1];
    if (!head) return;
    Array.prototype.forEach.call(table.tBodies, rowGroups);
    Array.prototype.forEach.call(head.cells, function (th) {
      if (th.classList.contains('nosort')) return;
      th.setAttribute('tabindex', '0'); th.setAttribute('role', 'columnheader');
      var go = function () {
        var cur = th.getAttribute('aria-sort');
        var next = cur === 'ascending' ? 'descending' : cur === 'descending' ? 'none' : 'ascending';
        Array.prototype.forEach.call(head.cells, function (o) { o.removeAttribute('aria-sort'); });
        if (next !== 'none') th.setAttribute('aria-sort', next);
        sortTable(table, th, next);
      };
      th.addEventListener('click', go);
      th.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
    });
  }
  function initFilterable(table) {
    var bodies = Array.prototype.slice.call(table.tBodies);
    var all = [];
    bodies.forEach(function (tb) { rowGroups(tb).forEach(function (g) { all.push(g); }); });
    var statuses = [];
    all.forEach(function (g) { var s = g.rows[0].getAttribute('data-status'); if (s && statuses.indexOf(s) < 0) statuses.push(s); });
    var tools = D.createElement('div'); tools.className = 'tbl-tools';
    tools.innerHTML = '<label class="tbl-search">' + ICONS.search + '<input type="search" placeholder="Filter rows" aria-label="Filter table rows" autocomplete="off" spellcheck="false"></label>' +
      '<span class="tbl-chips" role="group" aria-label="Filter by status"></span><span class="tbl-count" aria-live="polite"></span>';
    var anchor = up(table, '.tbl-scroll') || table;
    anchor.parentNode.insertBefore(tools, anchor);
    var input = $('input', tools), chips = $('.tbl-chips', tools), count = $('.tbl-count', tools), active = '';
    statuses.forEach(function (s) {
      var b = D.createElement('button'); b.type = 'button'; b.className = 'tbl-chip'; b.textContent = s; b.setAttribute('aria-pressed', 'false');
      b.addEventListener('click', function () {
        active = active === s ? '' : s;
        $$('.tbl-chip', chips).forEach(function (o) { o.setAttribute('aria-pressed', o.textContent === active ? 'true' : 'false'); });
        apply();
      });
      chips.appendChild(b);
    });
    function apply() {
      var q = input.value.trim().toLowerCase(), shown = 0;
      all.forEach(function (g) {
        var main = g.rows[0];
        var ok = (!q || (main.textContent + ' ' + (main.getAttribute('data-search') || '')).toLowerCase().indexOf(q) >= 0) &&
                 (!active || main.getAttribute('data-status') === active);
        g.rows.forEach(function (r) { r.hidden = !ok; });
        if (ok) shown++;
      });
      count.textContent = (q || active) ? (shown ? shown + ' of ' + all.length + ' rows' : 'No matching rows') : all.length + ' rows';
    }
    input.addEventListener('input', apply);
    input.addEventListener('keydown', function (e) { if (e.key === 'Escape' && input.value) { input.value = ''; apply(); } });
    apply();
  }

  function sizeScrollers() {
    $$('.tbl-scroll').forEach(function (w) { w.style.setProperty('--scroll-w', Math.max(160, w.clientWidth - 24) + 'px'); });
  }
  function initScrollers() {
    sizeScrollers();
    if (W.ResizeObserver) { var ro = new W.ResizeObserver(sizeScrollers); $$('.tbl-scroll').forEach(function (w) { ro.observe(w); }); }
    else W.addEventListener('resize', sizeScrollers);
  }

  /* ---------- scroll spy ---------- */
  function initSpy() {
    var links = $$('a[data-spy]');
    if (!links.length) return;
    var items = links.map(function (a) { return { a: a, el: D.getElementById((a.getAttribute('href') || '').slice(1)) }; }).filter(function (x) { return x.el; });
    if (!items.length) return;
    var ticking = false, current = null;
    function update() {
      ticking = false;
      var pick = items[0], y = 110;
      var atBottom = (W.innerHeight + W.pageYOffset) >= D.documentElement.scrollHeight - 4;
      if (atBottom) pick = items[items.length - 1];
      else items.forEach(function (x) { if (x.el.getBoundingClientRect().top <= y) pick = x; });
      if (pick === current) return;
      current = pick;
      items.forEach(function (x) { if (x === pick) x.a.setAttribute('aria-current', 'true'); else x.a.removeAttribute('aria-current'); });
      var box = pick.a.parentNode;
      if (box && box.scrollWidth > box.clientWidth) {
        var left = pick.a.offsetLeft - (box.clientWidth - pick.a.offsetWidth) / 2;
        try { box.scrollTo({ left: left, behavior: 'smooth' }); } catch (e) { box.scrollLeft = left; }
      }
    }
    function req() { if (!ticking) { ticking = true; W.requestAnimationFrame(update); } }
    W.addEventListener('scroll', req, { passive: true });
    W.addEventListener('resize', req);
    update();
  }

  /* ---------- global click handling ---------- */
  D.addEventListener('click', function (e) {
    safe('click', function () {
      var t = e.target;
      var tog = up(t, '[data-drawer-toggle]');
      if (tog) { setDrawer(tog, tog.getAttribute('aria-expanded') !== 'true'); return; }
      var cp = up(t, '.copy-btn[data-copy]');
      if (cp) { e.preventDefault(); onCopy(cp); return; }
      var act = up(t, '[data-action]');
      if (!act) return;
      var a = act.getAttribute('data-action');
      if (a === 'theme') applyTheme(theme() === 'light' ? 'dark' : 'light');
      else if (a === 'expand-all' || a === 'collapse-all') {
        var open = a === 'expand-all';
        $$('[data-drawer-toggle]').forEach(function (b) { setDrawer(b, open); });
        $$('details').forEach(function (d) { d.open = open; });
      }
    });
  });

  function init() {
    safe('theme', function () { var s = storedTheme(); if (s) D.documentElement.setAttribute('data-theme', s); syncThemeButtons(); });
    safe('tables-wrap', wrapTables);
    safe('tables-sort', function () { $$('table[data-sortable]').forEach(function (t) { safe('sort', function () { initSortable(t); }); }); });
    safe('tables-filter', function () { $$('table[data-filterable]').forEach(function (t) { safe('filter', function () { initFilterable(t); }); }); });
    safe('scrollers', initScrollers);
    safe('spy', initSpy);
    safe('hash', openHash);
    W.addEventListener('hashchange', function () { safe('hash', openHash); });
  }
  if (D.readyState === 'loading') D.addEventListener('DOMContentLoaded', init); else init();
})();
"""


def _build_js() -> str:
    names = _ICONS_JSON_NAMES
    data = {n: icon(n, 16) for n in names}
    payload = _json.dumps(data).replace("</", "<\\/")
    return _JS_TEMPLATE.replace("%%ICONS%%", payload)


JS: str = _build_js()

#!/usr/bin/env python3
"""Builds the HTML report, the Markdown job summary and the short PR comment from the checker result JSON files.

The HTML is one self-contained file: inline CSS, inline JS, inline SVG icons (report_ui.py), no external requests.
Module coverage is rendered by report_coverage.py; the shared look and behaviour (icons, badges, drawers, tables) live in report_ui.py.
"""
import argparse, datetime, html, json, math, os, sys, urllib.parse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from common import block_positions, trapezoid_profile
import report_ui as ui
from report_ui import icon, file_link, status_badge, chip, stat_card, drawer

try:
    from report_coverage import coverage_html
except Exception:  # the report must still build if the coverage renderer is missing or broken
    def coverage_html(d, fw_label=""):
        cov = d.get("coverage", [])
        if not cov:
            return ""
        rows = "".join(f'<tr><td>{file_link(c.get("file", "?"))}</td><td>{status_badge(c.get("state", "info"))}</td>'
                       f'<td>{esc(", ".join(e[3:] for e in c.get("events", [])))}</td><td>{esc(c.get("why", ""))}</td></tr>' for c in cov)
        return (f'<h3>{icon("layers-subtract")} Module coverage</h3><table class="tbl stack" data-sortable><thead><tr><th>Module file</th><th>State</th><th>Events</th><th>Why</th></tr></thead>'
                f'<tbody>{rows}</tbody></table>')

ICON = {"pass": "PASS", "fail": "FAIL", "warn": "WARN", "info": "INFO"}   # plain text for the Markdown outputs
RANK = {"fail": 0, "warn": 1, "info": 2, "pass": 3}
GITHUB_PR = "https://github.com/Smoothieware/Smoothieware/pull/{}"
STATUS_ICON = {"pass": "circle-check", "fail": "circle-x", "warn": "alert-triangle", "info": "info-circle"}
STATUS_WORD = {"pass": "Passed", "fail": "Failed", "warn": "Needs a look", "info": "Info"}


def esc(x):
    return html.escape("" if x is None else str(x))


def num(x, default=0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def fmt_us(us):
    us = num(us)
    if us >= 1e6: return f"{us / 1e6:.2f} s"
    if us >= 1000: return f"{us / 1000:.1f} ms"
    return f"{us:.0f} us"


def nice_ticks(vmax, n=4):
    """Round tick values 0..vmax: step is 1, 2 or 5 times a power of ten."""
    if vmax <= 0:
        return [0]
    raw = vmax / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(m * mag for m in (1, 2, 5, 10) if m * mag >= raw)
    return [i * step for i in range(int(vmax // step) + 1)]


def tick_label(v):
    return f"{v:g}" if abs(v) < 1e5 else f"{v:.2g}"


# ---------------------------------------------------------------- charts (SVG; colours come from CSS variables so light and dark both work)

def chart(title, svg, legend="", note="", icon_name="chart-line"):
    if not svg:
        return ""
    return (f'<figure class="chart"><figcaption>{icon(icon_name, 16)}<span>{esc(title)}</span></figcaption>'
            f'<div class="chart-body">{svg}</div>{f"<div class=legend>{legend}</div>" if legend else ""}'
            f'{f"<p class=note>{note}</p>" if note else ""}</figure>')


def legend_item(swatch_cls, text):
    return f'<span class="lg"><i class="sw {swatch_cls}"></i>{esc(text)}</span>'


def toolpath_svg(sim, w=440, h=440):
    blocks = sim.get("blocks") or []
    if not blocks:
        return ""
    pos = block_positions(blocks, sim["steps_per_mm"])
    xs = [p[0] for p in pos]; ys = [p[1] for p in pos]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    padl, padb, padt, padr = 46, 34, 14, 14
    sc = min(w - padl - padr, h - padb - padt) / max(x1 - x0, y1 - y0, 1e-6)
    P = lambda p: (padl + (p[0] - x0) * sc, h - padb - (p[1] - y0) * sc)
    vmax = max((b.get("nominal_speed", 0) for b in blocks), default=1) or 1
    grid = []
    span = max(x1 - x0, y1 - y0, 1e-6)
    for v in nice_ticks(span, 4):
        gx = padl + v * sc; gy = h - padb - v * sc
        grid.append(f'<line class="grid" x1="{gx:.1f}" y1="{padt}" x2="{gx:.1f}" y2="{h - padb}"/><text class="tick" x="{gx:.1f}" y="{h - padb + 15}" text-anchor="middle">{tick_label(x0 + v)}</text>')
        grid.append(f'<line class="grid" x1="{padl}" y1="{gy:.1f}" x2="{w - padr}" y2="{gy:.1f}"/><text class="tick" x="{padl - 6}" y="{gy + 4:.1f}" text-anchor="end">{tick_label(y0 + v)}</text>')
    grid.append(f'<text class="axis-title" x="{(padl + w - padr) / 2:.0f}" y="{h - 3}" text-anchor="middle">X (mm)</text>')
    grid.append(f'<text class="axis-title" x="11" y="{(padt + h - padb) / 2:.0f}" text-anchor="middle" transform="rotate(-90 11 {(padt + h - padb) / 2:.0f})">Y (mm)</text>')
    segs, dots = [], []
    for i in range(len(pos) - 1):
        a, b = P(pos[i]), P(pos[i + 1])
        v = blocks[i].get("nominal_speed", 0)
        mix = max(0, min(100, round(v / vmax * 100)))
        segs.append(f'<line x1="{a[0]:.1f}" y1="{a[1]:.1f}" x2="{b[0]:.1f}" y2="{b[1]:.1f}" class="seg" style="stroke:color-mix(in srgb,var(--rp-hot) {mix}%,var(--rp-cool))">'
                    f'<title>block {i}, G-code line {blocks[i].get("gcode_line", "?")}, {v:.0f} mm/s</title></line>')
        dots.append(f'<circle class="dot" cx="{b[0]:.1f}" cy="{b[1]:.1f}" r="2.4"/>')
    s, e = P(pos[0]), P(pos[-1])
    marks = (f'<circle class="start" cx="{s[0]:.1f}" cy="{s[1]:.1f}" r="5"><title>start</title></circle>'
             f'<circle class="end" cx="{e[0]:.1f}" cy="{e[1]:.1f}" r="5"><title>end</title></circle>')
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="XY toolpath from planned blocks">{"".join(grid)}{"".join(segs)}{"".join(dots)}{marks}</svg>'


def velocity_svg(sim, w=620, h=240):
    pts, spans, t = [], [], 0.0
    blocks = sim.get("blocks") or []
    for i, b in enumerate(blocks):
        prof = trapezoid_profile(b)
        for dt, v in prof:
            pts.append((t + dt, v))
        spans.append((t, t + prof[-1][0], i))
        t += prof[-1][0]
    if not pts or t <= 0:
        return ""
    vmax = max(v for _, v in pts) or 1
    padl, padr, padt, padb = 44, 12, 12, 30
    X = lambda tt: padl + tt / t * (w - padl - padr)
    Y = lambda v: h - padb - v / vmax * (h - padt - padb)
    line = " ".join(f"{X(tt):.1f},{Y(v):.1f}" for tt, v in pts)
    area = f"{X(0):.1f},{Y(0):.1f} {line} {X(t):.1f},{Y(0):.1f}"
    grid = "".join(f'<line class="grid" x1="{padl}" y1="{Y(v):.1f}" x2="{w - padr}" y2="{Y(v):.1f}"/><text class="tick" x="{padl - 6}" y="{Y(v) + 4:.1f}" text-anchor="end">{tick_label(v)}</text>' for v in nice_ticks(vmax, 4))
    grid += "".join(f'<line class="grid v" x1="{X(v):.1f}" y1="{padt}" x2="{X(v):.1f}" y2="{h - padb}"/><text class="tick" x="{X(v):.1f}" y="{h - padb + 15}" text-anchor="middle">{tick_label(v)}</text>' for v in nice_ticks(t, 5))
    grid += f'<text class="axis-title" x="{(padl + w - padr) / 2:.0f}" y="{h - 2}" text-anchor="middle">time (s)</text>'
    hover = "".join(f'<rect class="hit" x="{X(a):.1f}" y="{padt}" width="{max(X(b) - X(a), 1):.1f}" height="{h - padt - padb}"><title>block {i}, G-code line {blocks[i].get("gcode_line", "?")}: '
                    f'{blocks[i].get("nominal_speed", 0):.0f} mm/s nominal, {b - a:.3f} s</title></rect>' for a, b, i in spans[:4000])
    return (f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="planned speed over time"><defs><linearGradient id="gv" x1="0" y1="0" x2="0" y2="1">'
            f'<stop offset="0" class="gs-ok-a"/><stop offset="1" class="gs-ok-b"/></linearGradient></defs>{grid}'
            f'<polygon points="{area}" fill="url(#gv)"/><polyline class="vline" points="{line}"/>{hover}</svg>')


def steps_bar_svg(sim, w=620, h=200):
    bl = sim.get("blocks") or []
    if not bl:
        return ""
    m = max(b.get("steps_event_count", 0) for b in bl) or 1
    padl, padr, padt, padb = 44, 12, 12, 28
    bw = (w - padl - padr) / len(bl)
    Y = lambda v: h - padb - v / m * (h - padt - padb)
    grid = "".join(f'<line class="grid" x1="{padl}" y1="{Y(v):.1f}" x2="{w - padr}" y2="{Y(v):.1f}"/><text class="tick" x="{padl - 6}" y="{Y(v) + 4:.1f}" text-anchor="end">{tick_label(v)}</text>' for v in nice_ticks(m, 4))
    xt = nice_ticks(len(bl), 6)
    grid += "".join(f'<text class="tick" x="{padl + v * bw:.1f}" y="{h - padb + 15}" text-anchor="middle">{tick_label(v)}</text>' for v in xt)
    grid += f'<text class="axis-title" x="{(padl + w - padr) / 2:.0f}" y="{h - 2}" text-anchor="middle">block number</text>'
    bars = "".join(f'<rect class="stp" x="{padl + i * bw:.1f}" y="{Y(b.get("steps_event_count", 0)):.1f}" width="{max(bw - 1, 1):.1f}" height="{(h - padb) - Y(b.get("steps_event_count", 0)):.1f}" rx="1.5">'
                   f'<title>block {i}: {b.get("steps_event_count", 0)} steps</title></rect>' for i, b in enumerate(bl))
    defs = '<defs><linearGradient id="gb" x1="0" y1="1" x2="0" y2="0"><stop offset="0" class="gb-a"/><stop offset="1" class="gb-b"/></linearGradient></defs>'
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="steps per block">{defs}{grid}{bars}</svg>'


def hbars(rows, label_head="", ):
    """Horizontal bar list in HTML so the labels stay readable at phone width. rows: (label_html, value, value_text, bad, title)."""
    if not rows:
        return ""
    m = max(r[1] for r in rows) or 1
    out = []
    for label, v, text, bad, title in rows:
        out.append(f'<li class="hb" title="{esc(title)}"><span class="hb-l">{label}</span><span class="hb-t"><span class="hb-f{" bad" if bad else ""}" style="width:{max(v / m * 100, 1.5):.1f}%"></span></span><span class="hb-v">{esc(text)}</span></li>')
    return f'<ul class="hbars" role="list">{"".join(out)}</ul>'


def handler_chart(d):
    hs = sorted((d.get("handlers") or {}).items(), key=lambda kv: -num(kv[1].get("max_self_us")))[:14]
    if not hs:
        return ""
    rows = [(f'<code>{esc(k)}</code>', num(v.get("max_self_us")), f'{int(num(v.get("max_self_us")))} us', num(v.get("max_self_us")) > 1000,
             f'{k}: {v.get("calls", 0)} calls, {v.get("self_us", 0)} us own time in total, longest single call {v.get("max_self_us", 0)} us') for k, v in hs]
    return chart("Slowest handlers (max own time per call)", hbars(rows),
                 legend_item("ok", "up to 1000 us") + legend_item("bad", "over 1000 us"), "Hover a bar for the call count and total own time.", "flame")


def wait_chart(d):
    ws = d.get("runtime_waits") or []
    if not ws:
        return ""
    rows = [(f'<span class="mut">line {esc(x.get("gcode_line"))}</span> <code>{esc(x.get("module"))}::{esc(str(x.get("event", ""))[3:])}</code>', num(x.get("us")),
             f'{esc(x.get("kind"))} {num(x.get("us")) / 1000:.1f} ms', True, f'{x.get("module")}::{x.get("event")} {x.get("kind")} {x.get("us")} us') for x in ws]
    return chart("Blocking time per G-code line (workload timeline)", hbars(rows), icon_name="hourglass")


# ---------------------------------------------------------------- tables

def table(head, rows, cls="", filterable=False, statuses=None):
    """head: list of (label, kind) with kind 'num' for numeric columns; rows: lists of cells, a cell is html or (html, sort_value).
    statuses: optional per-row status word (fills data-status, which the status filter chips of a filterable table use)."""
    ths = "".join(f'<th scope="col"{" class=num" if t == "num" else ""}>{h}</th>' for h, t in head)
    trs = []
    for n, r in enumerate(rows):
        tds = []
        for (h, t), cell in zip(head, r):
            html_, key = cell if isinstance(cell, tuple) else (cell, None)
            sort_attr = "" if key is None else f' data-sort="{esc(key)}"'
            tds.append(f'<td data-label="{esc(h)}"{" class=num" if t == "num" else ""}{sort_attr}>{html_}</td>')
        st = f' data-status="{esc(statuses[n])}"' if statuses and statuses[n] else ""
        trs.append(f'<tr{st}>{"".join(tds)}</tr>')
    flt = " data-filterable" if filterable else ""
    return f'<table class="tbl stack {cls}" data-sortable{flt}><thead><tr>{ths}</tr></thead><tbody>{"".join(trs)}</tbody></table>'


def copy_btn(text, label="Copy"):
    return ui.copy_button(text, "").replace('aria-label="Copy to clipboard"', f'aria-label="{esc(label)}"')


def checks_table(res):
    cs = res.get("checks", [])
    rows = [[(status_badge(c.get("status", "info")), RANK.get(c.get("status"), 2)), esc(c.get("check")), esc(c.get("detail"))] for c in cs]
    return table([("Result", ""), ("Check", ""), ("Detail", "")], rows, "checks", filterable=len(rows) > 8, statuses=[c.get("status") for c in cs])


def static_table(hits):
    rows, sts = [], []
    for x in hits:
        sev = x.get("severity") if x.get("severity") in ("fail", "warn") else "pass"
        where = f'{x.get("file", "?")}:{x.get("line", "?")}'
        snippet = f'<div class="snip"><code>{esc(x["text"])}</code>{copy_btn(x["text"], "Copy source line")}</div>' if x.get("text") else ""
        rows.append([(f'{file_link(x.get("file", "?"), x.get("line"))}{copy_btn(where, "Copy file:line")}', where),
                     f'<code class="call">{esc(x.get("call"))}</code>{snippet}',
                     f'<code>{esc(x.get("function") or "?")}</code> {chip(x.get("context") or "?")}',
                     (f'{status_badge(sev)} {chip(x.get("rule", ""), "mono") if x.get("rule") else ""}', RANK[sev]),
                     esc(x.get("why"))])
        sts.append(sev)
    return table([("Where", ""), ("Call", ""), ("Function (context)", ""), ("Rule: status", ""), ("Reason", "")], rows, "hits", filterable=True, statuses=sts)


def waits_table(ws):
    m = max((num(x.get("us")) for x in ws), default=1) or 1
    rows = [[f'<code>{esc(x.get("module"))}::{esc(x.get("event"))}</code>', chip(x.get("kind", ""), "mono"),
             (f'<span class="inline-bar"><i style="width:{max(num(x.get("us")) / m * 100, 2):.0f}%"></i></span> {num(x.get("us")) / 1000:.1f} ms', num(x.get("us"))),
             (f'line {esc(x.get("gcode_line"))}', num(x.get("gcode_line"))),
             (f'{chip(x.get("rule", ""), "mono") if x.get("rule") else ""} {esc(x.get("reason", ""))}')] for x in ws]
    return table([("Handler", ""), ("Kind", ""), ("Duration", "num"), ("G-code line", "num"), ("Rule and reason", "")], rows, "waits", filterable=len(rows) > 8)


def long_handlers_table(hs):
    rows = [[f'<code>{esc(h.get("name"))}</code>', (f'{fmt_us(h.get("max_self_us"))}', num(h.get("max_self_us"))), (f'{num(h.get("calls")):,.0f}', num(h.get("calls"))),
             (fmt_us(h.get("self_us")), num(h.get("self_us"))), esc(h.get("allowed") or "not on the allow list")] for h in hs]
    return table([("Handler", ""), ("Longest call", "num"), ("Calls", "num"), ("Total own time", "num"), ("Allowed because", "")], rows, "longh", filterable=len(rows) > 8)


def accepted_waits_table(ws):
    agg = {}
    for x in ws:
        k = (x.get("module"), x.get("event"), x.get("kind"), x.get("rule"))
        a = agg.setdefault(k, [0, 0.0, 0.0]); a[0] += 1; a[1] += num(x.get("us")); a[2] = max(a[2], num(x.get("us")))
    rows = [[f'<code>{esc(k[0])}::{esc(k[1])}</code>', chip(k[2] or "", "mono"), (f"{a[0]:,}", a[0]), (fmt_us(a[1]), a[1]), (fmt_us(a[2]), a[2]), chip(k[3] or "", "mono") if k[3] else ""]
            for k, a in sorted(agg.items(), key=lambda kv: -kv[1][1])]
    return table([("Handler", ""), ("Kind", ""), ("Times seen", "num"), ("Total time", "num"), ("Longest", "num"), ("Rule", "")], rows, "acc", filterable=len(rows) > 8)


def replay_html(rows):
    def cell(n, must):
        if n is None:
            return f'{status_badge("warn")} <span class="mut">no result (build failed)</span>'
        if n:
            return f'{chip(f"{n} flagged", "pass")}'
        return chip("0 flagged", "fail") if must else chip("0 flagged")
    body = []
    for r in rows:
        exp = r.get("expected") or {}
        pr = esc(r.get("pr"))
        prl = f'<a class="flink" href="{esc(GITHUB_PR.format(r.get("pr")))}" target="_blank" rel="noopener noreferrer">{icon("git-pull-request", 14)}PR {pr}{icon("external-link", 12)}</a>'
        probs = "; ".join(r.get("problems") or [])
        body.append([(prl, num(r.get("pr"))), (cell(r.get("static"), exp.get("static")), num(r.get("static"), -1)), (cell(r.get("runtime"), exp.get("runtime")), num(r.get("runtime"), -1)),
                     "must be flagged" if exp.get("runtime") else "not runtime-capable: " + esc(exp.get("runtime_note", "")),
                     (f'{status_badge("fail")} {esc(probs)}' if probs else status_badge("pass") + " ok", 0 if probs else 1)])
    bad = sum(1 for r in rows if r.get("problems"))
    st = "fail" if bad else "pass"
    return section("replay", "route", "Old PR replay (regression test)", st,
                   '<p class="lead">Each PR the maintainer rejected for blocking waits is rebuilt into its own simulator and run through the wait checker; the test fails if one is no longer flagged.</p>'
                   + table([("PR", "num"), ("Static scan", "num"), ("Runtime", "num"), ("Expectation", ""), ("Result", "num")], body, "replay"),
                   meta=f'{len(rows)} PRs, {bad} failing')


def memory_html(d):
    rows = []
    for label, key, pool in (("Main SRAM heap", "main_sram", "heap"), ("AHB0 SRAM pool", "ahb0", "pool")):
        m = d[key]
        rows.append([label] + [(f'{num(m.get(k)):,.0f}', num(m.get(k))) for k in ("peak_live_bytes", "live_bytes_at_end", "largest_free_block", "fragmented_free_bytes", "failed_allocations")]
                    + [(f'{num(m.get("margin_to_stack_bytes")):,.0f}', num(m.get("margin_to_stack_bytes"))) if key == "main_sram" else ("", 0)])
    return (table([("Pool", ""), ("Peak live (B)", "num"), ("Live at end (B)", "num"), ("Largest free block (B)", "num"), ("Free but split (B)", "num"), ("Failed allocations", "num"), ("Room below stack (B)", "num")], rows, "memory")
            + f'<p class="note">{int(num(d.get("allocations"))):,} allocations replayed on the LPC1768 layout of an ARM build; {int(num(d.get("size_inexact"))):,} keep their host size because no ARM class size matched, so the figures are estimates.</p>')


def size_html(sz):
    rows_in = sz.get("rows") or []
    cards = "".join(stat_card(str(r.get("memory", "")), f'{num(r.get("delta")):+,.0f} B', "fail" if num(r.get("delta")) > 0 else "pass", "memory") for r in rows_in)
    rows = []
    for r in rows_in:
        pct = "" if r.get("percent") is None else "%+.2f %%" % r["percent"]
        grew = num(r.get("delta")) > 0
        rows.append([esc(r.get("memory")), (f'{num(r.get("reference")):,.0f}', num(r.get("reference"))), (f'{num(r.get("candidate")):,.0f}', num(r.get("candidate"))),
                     (f'<span class="{"fail" if grew else "pass"}">{icon("arrow-up" if grew else "arrow-down", 14)} {num(r.get("delta")):+,.0f} B</span>', num(r.get("delta"))), (pct, num(r.get("percent")))])
    top = [[f'<code>{esc(str(c.get("symbol", ""))[:90])}</code>', (f'{num(c.get("reference")):,.0f}', num(c.get("reference"))), (f'{num(c.get("candidate")):,.0f}', num(c.get("candidate"))),
            (f'{num(c.get("delta")):+,.0f}', num(c.get("delta")))] for c in sz.get("top_symbol_changes", [])]
    probs = "".join(f'<li>{icon("alert-triangle", 14)} {esc(p)}</li>' for p in sz.get("problems", []))
    lim = sz.get("limits") or {}
    limtxt = ", ".join(f"{k} +{v} B" for k, v in lim.items() if v is not None)
    body = (f'<div class="stats">{cards}</div>'
            + (f'<ul class="problems">{probs}</ul>' if probs else "")
            + table([("Memory", ""), ("Reference (bytes)", "num"), ("This build (bytes)", "num"), ("Change", "num"), ("%", "num")], rows, "size")
            + f'<h3>{icon("arrows-sort")} Largest symbol changes</h3>'
            + table([("Symbol", ""), ("Reference", "num"), ("This build", "num"), ("Change", "num")], top, "symbols", filterable=len(top) > 8)
            + (f'<p class="note">Limits applied: {esc(limtxt)}.</p>' if limtxt else ""))
    return section("size", "memory", "RAM and flash", sz.get("status", "info"), body, meta=esc(sz.get("summary", "")))


# ---------------------------------------------------------------- layout

def section(sid, icon_name, title, status, body, meta=""):
    return (f'<section id="{sid}" class="rp-sec">{ui.section_head(title, icon_name, status_badge(status) if status else "", meta)}{body}</section>')


def stacked_bar(c):
    p, w, f, i = (int(num(c.get(k))) for k in ("pass", "warn", "fail", "info"))
    tot = (p + w + f + i) or 1
    seg = "".join(f'<i class="{k}" style="flex:{n}" title="{n} {k}"></i>' for k, n in (("fail", f), ("warn", w), ("info", i), ("pass", p)) if n)
    return f'<span class="sbar" role="img" aria-label="{p} passed, {f} failed, {w} warnings of {tot}">{seg}</span>'


def overview(allr, R):
    rows = []
    for r in allr:
        c = r.get("counts") or {}
        name = f'<a href="#{r.get("anchor", "")}">{icon(r.get("icon", "list-details"), 16)} {esc(r.get("title"))}</a>'
        det = (f'{stacked_bar(c)}<span class="mut">{int(num(c.get("pass")))} passed, {int(num(c.get("fail")))} failed, {int(num(c.get("warn")))} warnings</span>'
               if c else f'<span class="mut">{esc(r.get("summary", ""))}</span>')
        rows.append([(name, r.get("title", "")), (status_badge(r.get("status", "info")), RANK.get(r.get("status"), 2)), det])
    att = [(r, c) for r in R for c in r.get("checks", []) if c.get("status") in ("fail", "warn")]
    att.sort(key=lambda rc: RANK[rc[1]["status"]])
    attention = ""
    if att:
        items = "".join(f'<li class="{c["status"]}">{status_badge(c["status"])}<div><a href="#{r["anchor"]}"><b>{esc(r["title"])}</b></a>: {esc(c.get("check"))}<div class="mut">{esc(str(c.get("detail", ""))[:400])}</div></div></li>' for r, c in att)
        attention = f'<h3>{icon("alert-triangle")} Needs attention <span class="count">{len(att)}</span></h3><ul class="attention">{items}</ul>'
    else:
        attention = ui.callout("Every check passed. Nothing needs attention.", "pass")
    return section("overview", "sparkles", "Summary", None, table([("Checker", ""), ("Result", ""), ("Breakdown", "")], rows, "summary", statuses=None) + attention)


def hero(title, subject, subject_link, overall, run_url, allr, R, stamp):
    subj = esc(subject)
    if subject and subject_link:
        subj = f'<a href="{esc(subject_link)}" target="_blank" rel="noopener noreferrer">{subj} {icon("external-link", 13)}</a>'
    tot = {k: sum(int(num((r.get("counts") or {}).get(k))) for r in R) for k in ("pass", "fail", "warn", "info")}
    n_checks = sum(len(r.get("checks", [])) for r in R)
    chips = [chip(stamp, "", "clock"), chip(f"{len(allr)} checkers, {n_checks} checks", "", "list-details")]
    if run_url:
        chips.append(f'<a class="chip chip-info" href="{esc(run_url)}" target="_blank" rel="noopener noreferrer">{icon("terminal-2", 12)}<span>CI run</span>{icon("external-link", 12)}</a>')
    cards = (stat_card("Checkers", str(len(allr)), "", "plug") + stat_card("Checks passed", str(tot["pass"]), "pass", "circle-check")
             + stat_card("Checks failed", str(tot["fail"]), "fail" if tot["fail"] else "pass", "circle-x") + stat_card("Warnings", str(tot["warn"]), "warn" if tot["warn"] else "pass", "alert-triangle"))
    per = "".join(stat_card(r["title"], f'{int(num(r["counts"].get("pass")))} / {int(num(r["counts"].get("warn")))} / {int(num(r["counts"].get("fail")))}',
                            r["status"], r.get("icon", "")) for r in R if r.get("counts"))
    words = {"pass": "All checks passed", "warn": "Passed with warnings", "fail": "At least one check failed"}
    return (f'<header class="hero rp-hero {overall}"><div class="hero-top"><div class="rp-title"><span class="rp-orb">{icon(STATUS_ICON[overall], 34)}</span>'
            f'<div><p class="eyebrow">{ui.logo(16)} smoothie-sim</p><h1>{esc(title)}</h1></div></div>'
            f'<span class="rp-verdict">{status_badge(overall)}<span>{words[overall]}</span></span></div>'
            f'{f"<p class=hero-sub>{subj}</p>" if subject else ""}<div class="chips">{"".join(chips)}</div>'
            f'<div class="stats">{cards}</div><h3 class="rp-h3">{icon("list-details", 16)} Per checker <span class="mut rp-legend">passed / warnings / failed</span></h3><div class="stats">{per}</div></header>')


REPORT_CSS = """
:root{--rp-ok:var(--pass-tx);--rp-bad:var(--fail-tx);--rp-warn:var(--warn-tx);--rp-info:var(--accent);--rp-hot:var(--warn);--rp-cool:var(--accent);--rp-grid:var(--border);--rp-axis:var(--mut)}
.rp-hero.pass::before{background:linear-gradient(90deg,var(--pass),var(--accent))}.rp-hero.warn::before{background:linear-gradient(90deg,var(--warn),var(--accent-2))}.rp-hero.fail::before{background:linear-gradient(90deg,var(--fail),var(--warn))}
.rp-hero.pass{background:linear-gradient(135deg,var(--pass-bg),transparent 55%),var(--surface)}.rp-hero.warn{background:linear-gradient(135deg,var(--warn-bg),transparent 55%),var(--surface)}.rp-hero.fail{background:linear-gradient(135deg,var(--fail-bg),transparent 55%),var(--surface)}
.rp-title{display:flex;gap:14px;align-items:center;min-width:0}.rp-title h1{overflow-wrap:anywhere}.rp-title>div{min-width:0}
.rp-orb{display:inline-grid;place-items:center;flex:none;width:60px;height:60px;border-radius:50%;border:1px solid currentColor;background:color-mix(in srgb,currentColor 14%,transparent)}
.rp-hero.pass .rp-orb{color:var(--pass-tx)}.rp-hero.warn .rp-orb{color:var(--warn-tx)}.rp-hero.fail .rp-orb{color:var(--fail-tx)}
.eyebrow{margin:0 0 2px;display:flex;gap:6px;align-items:center;color:var(--mut);font-size:12px;font-weight:650;letter-spacing:.08em;text-transform:uppercase}
.rp-verdict{display:inline-flex;gap:8px;align-items:center;font-weight:600}
.hero .chips,.chips{display:flex;gap:6px;flex-wrap:wrap;margin-top:12px}.hero .chip{text-decoration:none}
.rp-h3{display:flex;gap:6px;align-items:baseline;flex-wrap:wrap;margin:18px 0 0;color:var(--fg-2);font-size:.92rem}.rp-legend{font-weight:500;font-size:12px}
.rp-hero .stats:first-of-type{margin-top:16px}
.rp-sec h3{display:flex;gap:7px;align-items:center;margin:24px 0 8px}.rp-sec h3 .ic{color:var(--accent)}
.count{font-size:12px;font-weight:600;padding:0 8px;border-radius:99px;border:1px solid var(--border);color:var(--mut);background:var(--surface-2)}
.lead{color:var(--mut);margin:.2em 0 .8em}.note{color:var(--mut);font-size:13px;margin:.5em 0}
.tbl code{overflow-wrap:anywhere}.tbl .num{white-space:nowrap}.snip{display:flex;gap:4px;align-items:flex-start;margin-top:5px;color:var(--mut)}.snip code{background:transparent;border:0;padding:0}
.tbl td .copy-btn{margin-left:4px;padding:2px 5px;vertical-align:middle}
.inline-bar{display:inline-block;width:60px;height:7px;border-radius:4px;background:var(--surface-3);vertical-align:middle;overflow:hidden}.inline-bar i{display:block;height:100%;background:var(--fail)}
.sbar{display:inline-flex;width:120px;height:8px;border-radius:5px;overflow:hidden;vertical-align:middle;background:var(--surface-3);margin-right:8px}
.sbar i{display:block}.sbar .pass{background:var(--pass)}.sbar .warn{background:var(--warn)}.sbar .fail{background:var(--fail)}.sbar .info{background:var(--accent)}
.attention,.problems{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.attention li{display:flex;gap:10px;align-items:flex-start;padding:10px 12px;border-radius:var(--r-sm);border:1px solid var(--border);background:var(--surface-2)}
.attention li.fail{border-color:var(--fail-bd);background:var(--fail-bg)}.attention li.warn{border-color:var(--warn-bd);background:var(--warn-bg)}
.attention li>div{min-width:0;overflow-wrap:anywhere;color:var(--fg)}.attention a{color:inherit}.problems li{display:flex;gap:6px;align-items:center;color:var(--fail-tx)}
.chart{margin:14px 0;padding:14px;border:1px solid var(--border);border-radius:var(--r);background:var(--surface-2)}
.chart figcaption{display:flex;gap:7px;align-items:center;font-weight:650;margin-bottom:8px}.chart figcaption .ic{color:var(--accent)}
.chart-body svg{display:block;width:100%;height:auto;max-height:460px}
.chart .legend{display:flex;gap:6px 16px;flex-wrap:wrap;margin-top:8px;color:var(--mut);font-size:12.5px}.lg{display:inline-flex;gap:6px;align-items:center}
.sw{display:inline-block;width:12px;height:12px;border-radius:3px}.sw.ok{background:var(--rp-ok)}.sw.bad{background:var(--rp-bad)}.sw.scale{width:46px;background:linear-gradient(90deg,var(--rp-cool),var(--rp-hot))}
.sw.start{background:var(--rp-ok);border-radius:50%}.sw.end{background:var(--rp-bad);border-radius:50%}.sw.pt{background:var(--rp-warn);border-radius:50%;width:8px;height:8px}
.charts-2{display:grid;grid-template-columns:minmax(0,430px) minmax(0,1fr);gap:14px;align-items:start}@media(max-width:820px){.charts-2{grid-template-columns:minmax(0,1fr)}}
svg .grid{stroke:var(--rp-grid);stroke-width:1;opacity:.7}svg .tick{fill:var(--rp-axis);font-size:11.5px}svg .axis-title{fill:var(--rp-axis);font-size:12px}
svg .seg{stroke-width:2.4;stroke-linecap:round}svg .seg:hover{stroke-width:4.5}svg .dot{fill:var(--rp-warn)}svg .start{fill:var(--rp-ok);stroke:var(--surface-2);stroke-width:2}svg .end{fill:var(--rp-bad);stroke:var(--surface-2);stroke-width:2}
svg .vline{fill:none;stroke:var(--rp-ok);stroke-width:1.8;stroke-linejoin:round}.gs-ok-a{stop-color:var(--rp-ok);stop-opacity:.42}.gs-ok-b{stop-color:var(--rp-ok);stop-opacity:.02}
svg .hit{fill:transparent}svg .hit:hover{fill:var(--accent-bg)}svg .stp{fill:url(#gb)}svg .stp:hover{fill:var(--rp-warn)}.gb-a{stop-color:var(--rp-cool)}.gb-b{stop-color:var(--rp-hot)}
.hbars{list-style:none;margin:0;padding:0;display:grid;gap:8px}.hb{display:grid;grid-template-columns:minmax(120px,38%) 1fr auto;gap:10px;align-items:center;font-size:13px}
.hb-l{overflow-wrap:anywhere}.hb-t{height:10px;border-radius:6px;background:var(--surface-3);overflow:hidden}.hb-f{display:block;height:100%;border-radius:6px;background:linear-gradient(90deg,var(--accent-bg),var(--accent))}
.hb-f.bad{background:linear-gradient(90deg,var(--fail-bg),var(--fail))}.hb-v{color:var(--mut);white-space:nowrap}
.rp-wait-head{display:flex;gap:6px;flex-wrap:wrap;margin:14px 0 4px}
.group-h{margin:22px 0 4px;color:var(--mut);font-size:13px;display:flex;gap:6px;align-items:center}
.rp-sec .cov-stats,.rp-sec .cov-stats-s{grid-template-columns:repeat(auto-fit,minmax(168px,1fr))}.stat-label{overflow-wrap:normal;word-break:normal;hyphens:none}
.foot,.foot *{overflow-wrap:anywhere;min-width:0}.foot{margin:28px 0 0;padding:16px 0;border-top:1px solid var(--border);color:var(--mut);font-size:13px;display:flex;gap:8px;flex-wrap:wrap;align-items:center}
@media(max-width:640px){
 .rp-orb{width:46px;height:46px}.rp-orb svg{width:26px;height:26px}
 .hb{grid-template-columns:1fr auto}.hb-l{grid-column:1/-1}.hb-t{grid-column:1}
 .tbl.stack thead{display:none}.tbl.stack,.tbl.stack tbody,.tbl.stack tr,.tbl.stack td{display:block;width:100%}
 .tbl.stack tr{border-bottom:1px solid var(--border-strong);padding:6px 10px}.tbl.stack tbody tr:last-child{border-bottom:0}
 .tbl.stack td,.tbl.stack tbody tr:hover>td{border:0;padding:3px 0;background:transparent}.tbl.stack td::before{content:attr(data-label);display:block;font-size:11px;letter-spacing:.05em;text-transform:uppercase;color:var(--mut)}
 .tbl.stack td.num{text-align:left}.tbl.stack td:empty{display:none}}
"""


def build_modules(r, fw_label):
    d = r.get("data") or {}
    h = []
    acc = d.get("accepted_runtime_waits") or []
    if acc:
        tot_us = sum(num(x.get("us")) for x in acc)
        h.append(f'<div class="chips">{chip(f"{len(acc):,} short waits accepted by the rules ({fmt_us(tot_us)} in total)", "info")}'
                 + "".join(chip(f'{x.get("file")}: {x.get("blocks")} blocks, identical with and without the modules' if x.get("ok") else f'{x.get("file")}: differs when the modules are loaded', "pass" if x.get("ok") else "fail") for x in d.get("interference", []))
                 + "</div>")
    h.append(f'{wait_chart(d)}{handler_chart(d)}')
    h.append(coverage_html(d, fw_label) or "")
    has_base = "new_static_hits" in d
    hits = d["new_static_hits"] if has_base else (d.get("static_hits") or [])
    if hits:
        h.append(f'<h3>{icon("bug")} Blocking calls {"added by this change" if has_base else "found in source"} <span class="count">{len(hits)}</span></h3>' + static_table(hits[:80])
                 + (f'<p class="note">Showing the first 80 of {len(hits)}.</p>' if len(hits) > 80 else ""))
    elif has_base:
        h.append(f'{ui.callout("No new blocking calls in the source.", "pass", "shield-check")}')
    if d.get("runtime_waits"):
        new = "existing_runtime_waits" in d
        h.append(f'<h3>{icon("hourglass")} Waits seen while running{" (new)" if new else ""} <span class="count">{len(d["runtime_waits"])}</span></h3>' + waits_table(d["runtime_waits"]))
    if d.get("long_handlers"):
        h.append(f'<h3>{icon("flame")} Handlers over the duration threshold <span class="count">{len(d["long_handlers"])}</span></h3>' + long_handlers_table(d["long_handlers"]))
    dr = []
    ex_hits = d.get("existing_static_hits") or []
    if ex_hits:
        dr.append(drawer(f'{len(ex_hits)} blocking calls in the source that the reference firmware already has (not caused by this change)',
                         static_table(ex_hits[:200]) + (f'<p class="note">Showing the first 200 of {len(ex_hits)}.</p>' if len(ex_hits) > 200 else ""), "dr-existing-static"))
    ex_waits = d.get("existing_runtime_waits") or []
    if ex_waits:
        dr.append(drawer(f'{len(ex_waits)} waits seen while running that the reference firmware also has (not caused by this change)', waits_table(ex_waits), "dr-existing-waits"))
    ex_long = d.get("existing_long_handlers") or []
    if ex_long:
        dr.append(drawer(f'{len(ex_long)} handlers over the duration threshold that the reference firmware also has (not caused by this change)', long_handlers_table(ex_long), "dr-existing-long"))
    if acc:
        dr.append(drawer(f'{len(acc):,} short waits accepted by the rules, grouped by handler', accepted_waits_table(acc), "dr-accepted"))
    if dr:
        h.append(f'<p class="group-h">{icon("info-circle", 14)} Already in the reference firmware, or accepted by the rules</p><div class="drawers">{"".join(dr)}</div>')
    return "".join(h)


CHECKER_ICON = {"gcode_to_blocks": "route", "gcode_to_steps": "bolt", "gcode_to_steps_face": "bolt", "modules": "plug", "size": "memory", "memory": "memory", "faults": "alert-triangle"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", nargs="+", required=True, help="checker result JSON files")
    ap.add_argument("--size"); ap.add_argument("--sim-json", help="simulator blocks JSON for the plots")
    ap.add_argument("--title", default="Smoothieware simulator report"); ap.add_argument("--subject", default="")
    ap.add_argument("--subject-link", default="", help="URL the subject line links to (for example the pull request)")
    ap.add_argument("--source-url", default="", help="URL template for file links, '{path}' is replaced by the repo-relative path, e.g. https://github.com/Smoothieware/Smoothieware/blob/<rev>/{path}")
    ap.add_argument("--fw-label", default="", help="short name of the checked firmware, shown in the module coverage section (default: the subject)")
    ap.add_argument("--html", required=True); ap.add_argument("--summary-md", required=True); ap.add_argument("--comment-md", required=True)
    ap.add_argument("--run-url", default="")
    ap.add_argument("--replay", help="regress.json written by tools/regress_prs.py (old-PR replay results)")
    a = ap.parse_args()
    ui.set_source_base(a.source_url or "")
    R = [json.load(open(p)) for p in a.results]
    sz = json.load(open(a.size)) if a.size else None
    sim = json.load(open(a.sim_json)) if a.sim_json else None
    allr = R + ([{"title": "RAM and flash", "status": sz["status"], "counts": {}, "summary": sz.get("summary", "")}] if sz else [])
    for r in R:
        r["anchor"] = "chk-" + str(r.get("checker", "x")).replace("_", "-")
        r["icon"] = CHECKER_ICON.get(r.get("checker"), "list-details")
    if sz:
        allr[-1]["anchor"] = "size"; allr[-1]["icon"] = "memory"
    overall = "fail" if any(r["status"] == "fail" for r in allr) else ("warn" if any(r["status"] == "warn" for r in allr) else "pass")
    fw_label = a.fw_label or a.subject or "this firmware"
    stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    nav_items = [("overview", "Summary", "sparkles")]
    if sim: nav_items.append(("toolpath", "Plots", "chart-line"))
    nav_items += [(r["anchor"], r["title"], r["icon"]) for r in R]
    if a.replay: nav_items.append(("replay", "PR replay", "route"))
    if sz: nav_items.append(("size", "RAM and flash", "memory"))

    h = [f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>{esc(a.title)}</title>"
         f"<link rel=icon type=image/svg+xml href=\"data:image/svg+xml,{urllib.parse.quote(ui.FAVICON_SVG)}\">"
         f"<script>{ui.HEAD_JS}</script><style>{ui.CSS}\n{REPORT_CSS}</style></head><body>",
         ui.nav(nav_items, brand="smoothie-sim"), '<main class="page">',
         hero(a.title, a.subject, a.subject_link, overall, a.run_url, allr, R, stamp),
         overview(allr, R)]
    if sim:
        tp, vel, stp = toolpath_svg(sim), velocity_svg(sim), steps_bar_svg(sim)
        body = (f'<div class="charts-2">'
                + chart("XY toolpath", tp, legend_item("scale", "slow to fast (nominal speed)") + legend_item("start", "start") + legend_item("end", "end") + legend_item("pt", "block end"), "Hover a segment for its block, G-code line and speed.", "route")
                + f'<div>{chart("Planned speed over time", vel, legend_item("ok", "speed (mm/s)"), "Hover for the block and its nominal speed.", "chart-line")}'
                + f'{chart("Steps per block", stp, legend_item("scale", "steps in the block"), "", "ruler")}</div></div>'
                + '<p class="note">The speed curve is rebuilt from each block\'s planned entry, nominal and exit speed and acceleration; it is a planning view, not a measured trace. Step-pulse timing is simulated at a 10 us tick and is approximate.</p>')
        h.append(section("toolpath", "chart-line", "Toolpath and speed (from the planned blocks)", None, body, meta=f'{len(sim.get("blocks") or [])} blocks'))
    for r in R:
        body = checks_table(r)
        if r.get("checker") == "modules":
            body += build_modules(r, fw_label)
        if r.get("checker") == "memory" and (r.get("data") or {}).get("measured"):
            body += memory_html(r["data"])
        c = r.get("counts") or {}
        h.append(section(r["anchor"], r["icon"], r["title"], r["status"], body,
                         meta=f'{int(num(c.get("pass")))} passed, {int(num(c.get("fail")))} failed, {int(num(c.get("warn")))} warnings'))
    if a.replay:
        h.append(replay_html(json.load(open(a.replay))))
    if sz:
        h.append(size_html(sz))
    src = f' · file links point to <code>{esc(a.source_url)}</code>' if a.source_url else ""
    h.append(f'<footer class="foot">{icon("cpu", 16)}<span>Generated by smoothie-sim on {stamp}{src}. One self-contained file: no external requests.</span></footer>')
    h.append(f"</main><script>{ui.JS}</script></body></html>")
    open(a.html, "w").write("\n".join(h))

    md = [f"## {a.title}", f"{a.subject}", "", f"**Overall: {ICON[overall]}**", "", "| Checker | Result | Detail |", "|---|---|---|"]
    for r in R:
        c = r["counts"]; md.append(f'| {r["title"]} | {ICON[r["status"]]} | {c["pass"]} passed, {c["fail"]} failed, {c["warn"]} warnings |')
    if sz:
        md.append(f'| RAM and flash | {ICON[sz["status"]]} | {sz["summary"]} |')
    full = "\n".join(md)
    fails = [(r["title"], c) for r in R for c in r["checks"] if c["status"] == "fail"]
    if fails:
        full += "\n\n<details><summary>Failed checks</summary>\n\n" + "\n".join(f'- **{t}**: {c["check"]} - {c["detail"][:300]}' for t, c in fails) + "\n\n</details>"
    if sz:
        full += "\n\n| Memory | Reference | This build | Change |\n|---|---|---|---|\n" + "\n".join(f'| {r["memory"]} | {r["reference"]:,} | {r["candidate"]:,} | {r["delta"]:+,} B |' for r in sz["rows"])
    open(a.summary_md, "w").write(full + "\n")
    open(a.comment_md, "w").write("<!-- smoothie-sim-report -->\n" + full + (f"\n\n[Full HTML report]({a.run_url})" if a.run_url else "") + "\n")


if __name__ == "__main__":
    main()

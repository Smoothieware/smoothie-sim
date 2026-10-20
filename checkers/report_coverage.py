"""HTML for the "Module coverage" section of the report: a summary strip, a progress bar, the module table and, under each module
(and for the section as a whole), a "More info" drawer with handlers, call counts, events, advice and source links.
Everything is built on checkers/report_ui.py (icons, pills, file links, drawer); the output is plain HTML plus one small inline
style block and one small inline script (state filter and search), so the report stays one self-contained file."""
import html, math, os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import report_ui as ui

STATES = ("exercised", "partial", "loaded-not-run", "excluded")
STATE_LABEL = {"exercised": "Exercised", "partial": "Partly exercised", "loaded-not-run": "Not run", "excluded": "Excluded from build"}
STATE_KIND = {"exercised": "pass", "partial": "warn", "loaded-not-run": "warn", "excluded": "fail"}

# What each firmware event means, in plain words (shown in the drawers).
EVENT_INFO = {
    "ON_GCODE_RECEIVED": "A G-code or M-code line reached the module; it can act on the codes it knows.",
    "ON_CONSOLE_LINE_RECEIVED": "A text line arrived on the console (serial or USB shell), for example a shell command.",
    "ON_IDLE": "Called again and again whenever the main loop has nothing else to do, so it runs very often.",
    "ON_MAIN_LOOP": "Called once per pass of the main loop, outside interrupts, for work that may take a little time.",
    "ON_SECOND_TICK": "Called once per second by a timer; used for slow housekeeping such as temperature or file-play timeouts.",
    "ON_HALT": "The machine was halted (emergency stop, kill button or an alarm) or the halt was cleared.",
    "ON_GET_PUBLIC_DATA": "Another module asked this one for a value (a temperature, a position, a state).",
    "ON_SET_PUBLIC_DATA": "Another module asked this one to change a setting.",
    "ON_ENABLE": "A request to switch the module or its motors on or off.",
    "ON_MODULE_LOADED": "Called once at start-up, right after the module is created and its configuration is read.",
}
# What to add to the workload so a handler that never ran does run. Keyed by the handler's short name.
HANDLER_HINT = {
    "on_gcode_received": ("Add a G-code or M-code line that this module handles. Search the handler for gcode->has_g / has_m to see which codes it reacts to.", "; <the G/M-code {module} handles>"),
    "on_console_line_received": ("Send a text command through the console. The handler lists the commands it accepts.", ""),
    "on_second_tick": ("This handler fires once per second of simulated time. Make the workload last longer than a second, for example with a dwell.", "G4 P2000 ; wait 2 s so the 1 s tick fires"),
    "on_halt": ("Trigger a halt near the end of the workload so the module sees it.", "M112 ; emergency stop (ends the run, put it last)"),
    "on_get_public_data": ("Another module has to ask this one for data. Use a G-code that makes a module read it, for example a temperature or position report.", "M105 ; report temperatures"),
    "on_set_public_data": ("Another module has to change a setting here. Use a G-code that makes a module write to it.", ""),
    "on_idle": ("Runs on its own once the module is loaded; if it never ran, the module was probably not created (see the configuration).", ""),
    "on_main_loop": ("Runs on its own once the module is loaded; if it never ran, the module was probably not created (see the configuration).", ""),
    "on_module_loaded": ("Runs once at start-up; if it never ran, the module is not created by the test configuration. Enable it in cases/modules/config.txt.", ""),
    "on_enable": ("Needs a motor or module enable/disable request in the workload, for example M17 / M18.", "M17 ; enable motors\nM18 ; disable motors"),
}
HARDWARE_HANDLER = re.compile(r"^on_(pin_|rise|fall|up|down|back|select|click|button|encoder|panel|menu|enter|left|right|refresh)")

STATE_MEANING = {
    "exercised": ("circle-check", "Every handler function of this module was entered at least once while the workload ran, so the runtime checks (blocking waits, long handlers, interference) really saw this code execute."),
    "partial": ("alert-triangle", "The module was loaded and some of its handlers ran, but others were never entered. The runtime checks cannot see inside a handler that never runs, so a blocking call hidden there would only be caught by the static source scan."),
    "loaded-not-run": ("circle-dashed", "The module is compiled into the simulator but none of its handlers ran. Either the test configuration does not create the module, or the workload contains no G-code the module reacts to. The runtime checks learned nothing about it."),
    "excluded": ("circle-x", "The simulator is built without this module because it drives hardware the simulator does not fake. The static source scan still reads the file, but it never runs."),
}
STATE_ACTION = {
    "exercised": "Nothing to do.",
    "partial": "Add the missing inputs to the workload (hints per handler are listed under Handlers).",
    "loaded-not-run": "Enable the module in the test configuration and add a line it reacts to in the workload.",
    "excluded": "Normally leave it excluded. Only if the hardware can be faked, remove the folder from EXCLUDE_DIRS in the simulator Makefile.",
}


def e(x):
    return html.escape(str(x if x is not None else ""), quote=True)


def num(n):
    try:
        return format(int(n), ",")
    except (TypeError, ValueError):
        return "0"


def short_name(fn):
    return re.sub(r"\(.*", "", str(fn or "")).split("::")[-1]


def class_name(fn):
    parts = re.sub(r"\(.*", "", str(fn or "")).split("::")
    return parts[-2] if len(parts) > 1 else ""


def module_name(path):
    return os.path.splitext(os.path.basename(str(path or "")))[0] or "module"


def slug(path):
    return "cov-" + (re.sub(r"[^A-Za-z0-9]+", "-", str(path or "x")).strip("-").lower() or "x")


def event_label(ev):
    ev = str(ev or "")
    return ev[3:] if ev.startswith("ON_") else ev


def pct(a, b):
    return 0.0 if not b else 100.0 * a / b


def bar(value, total, kind="pass", label=""):
    """Thin horizontal meter; the text label sits next to it so colour is never the only signal."""
    w = max(0.0, min(100.0, pct(value, total)))
    return f'<span class="cov-meter cov-m-{e(kind)}" role="img" aria-label="{e(label)}"><i style="width:{w:.1f}%"></i></span>'


def copy_button(text, label="Copy"):
    return f'<button type="button" class="copy-btn cov-copy" data-copy="{e(text)}" aria-label="{e(label)}" title="{e(label)}">{ui.icon("copy", 14)}<span>{e(label)}</span></button>'


def handler_state(h):
    try:
        return int(h.get("calls") or 0) > 0
    except (TypeError, ValueError):
        return False


def stats_of(c):
    hs = [h for h in (c.get("handlers") or []) if isinstance(h, dict)]
    entered = [h for h in hs if handler_state(h)]
    calls = sum(int(h.get("calls") or 0) for h in hs)
    hit = sum(int(h.get("lines_hit") or 0) for h in hs)
    tot = sum(int(h.get("lines_total") or 0) for h in hs)
    return {"hs": hs, "entered": len(entered), "n": len(hs), "calls": calls, "hit": hit, "tot": tot}


def handler_rows(c, s):
    events = [str(x) for x in (c.get("events") or [])]
    ordered = sorted(s["hs"], key=lambda h: (handler_state(h), -int(h.get("calls") or 0), str(h.get("function") or "")))
    maxlog = max([math.log10(int(h.get("calls") or 0) + 1) for h in ordered] + [1.0])
    out = []
    for h in ordered:
        fn = str(h.get("function") or "?")
        sn = short_name(fn)
        ev = "ON_" + sn[3:].upper() if sn.startswith("on_") else ""
        ev_chip = ""
        if ev == "ON_MODULE_LOADED":
            ev_chip = ui.chip("start-up", "info")
        elif ev in events:
            ev_chip = ui.chip(event_label(ev), "info")
        calls = int(h.get("calls") or 0)
        hit, tot = int(h.get("lines_hit") or 0), int(h.get("lines_total") or 0)
        entered = calls > 0
        state = (f'<span class="cov-hs cov-hs-ok">{ui.icon("check", 14)}entered</span>' if entered
                 else f'<span class="cov-hs cov-hs-no">{ui.icon("x", 14)}never entered</span>')
        calls_bar = bar(math.log10(calls + 1), maxlog, "info" if entered else "fail", f"{num(calls)} calls (log scale)")
        lines = (f'<span class="cov-lines">{bar(hit, tot, "pass" if hit == tot else "warn", f"{hit} of {tot} lines")}<span class="cov-num">{hit}/{tot} lines ({pct(hit, tot):.0f}%)</span></span>'
                 if tot else '<span class="mut">no line data</span>')
        src_link = (f'<div class="cov-src">{ui.file_link(c.get("file"), h.get("line"), "line %d" % int(h["line"]))}</div>'
                    if h.get("line") and c.get("file") else "")
        hint = ""
        if not entered:
            key = sn
            if HARDWARE_HANDLER.match(sn):
                text = "Driven by hardware or panel input (a pin edge, a button, an encoder). The simulator does not generate these, so this handler is expected to stay unentered."
            else:
                text = HANDLER_HINT.get(key, ("Add input to the workload that makes the module call this handler.", ""))[0]
            hint = f'<div class="cov-hint">{ui.icon("sparkles", 13)}<span>{e(text)}</span></div>'
        out.append(
            f'<tr class="{"cov-hr-no" if not entered else ""}">'
            f'<td data-label="Handler"><div class="cov-fn" title="{e(fn)}">{e(class_name(fn))}{"::" if class_name(fn) else ""}<b>{e(sn)}</b></div><div class="cov-fnsig">{e(fn)}</div>{src_link}{ev_chip}{hint}</td>'
            f'<td data-label="State">{state}</td>'
            f'<td data-label="Calls" class="cov-calls"><span class="cov-num">{num(calls)}</span>{calls_bar}</td>'
            f'<td data-label="Line coverage">{lines}</td></tr>')
    return "".join(out)


def snippet_for(c, s, state):
    """Copyable text that helps close the gap for this module, or '' when nothing useful can be said."""
    name = module_name(c.get("file"))
    path = str(c.get("file") or "")
    if state == "excluded":
        m = re.search(r"build excludes (\S+)", str(c.get("why") or ""))
        folder = m.group(1) if m else os.path.dirname(path.split("src/", 1)[-1]) + "/"
        return "Makefile", f"# Makefile: delete this line from EXCLUDE_DIRS to compile {name} into the simulator\n{folder}"
    lines = []
    missing = [short_name(h.get("function")) for h in s["hs"] if not handler_state(h)]
    if state == "loaded-not-run" and not s["hs"]:
        lines += [f"# cases/modules/config.txt: make sure the test configuration creates {name}", f"# (copy its section from the firmware's config sample)"]
        missing = ["on_gcode_received"]
    out = []
    for m in missing:
        if HARDWARE_HANDLER.match(m):
            continue
        hint = HANDLER_HINT.get(m)
        if hint and hint[1]:
            out.append(hint[1].replace("{module}", name))
    seen, uniq = set(), []
    for block in out:
        for ln in block.split("\n"):
            if ln not in seen:
                seen.add(ln); uniq.append(ln)
    if not uniq and not lines:
        return "", ""
    head = [f"; cases/modules/workload.gcode: lines that exercise {name}"] if uniq else []
    return "workload.gcode", "\n".join(lines + head + uniq)


def event_block(c):
    evs = [str(x) for x in (c.get("events") or [])]
    if not evs:
        return f'<p class="mut">No events recorded for this module.</p>'
    items = "".join(f'<li>{ui.icon("bolt", 14)}<div><b>{e(event_label(x))}</b><span>{e(EVENT_INFO.get(x, "Event hooked by this module."))}</span></div></li>' for x in evs)
    return f'<ul class="cov-events">{items}</ul>'


def module_drawer_body(c, fw_label):
    state = str(c.get("state") or "")
    s = stats_of(c)
    path = str(c.get("file") or "")
    icon_name, meaning = STATE_MEANING.get(state, ("info-circle", "State not recognised by this report."))
    action = STATE_ACTION.get(state, "")
    kind = STATE_KIND.get(state, "info")
    entered_kind = "pass" if s["n"] and s["entered"] == s["n"] else ("warn" if s["entered"] else ("fail" if s["n"] else "info"))
    stats = (ui.stat_card("Handlers entered", f'{s["entered"]} of {s["n"]}' if s["n"] else "no counters", entered_kind, "plug")
             + ui.stat_card("Handler calls", num(s["calls"]) if s["n"] else "n/a", "info", "player-play")
             + ui.stat_card("Handler lines run", f'{pct(s["hit"], s["tot"]):.0f} %' if s["tot"] else "n/a", "info", "list-details")
             + ui.stat_card("Events hooked", str(len(c.get("events") or [])), "info", "bolt"))
    if s["hs"]:
        htable = (f'<div class="cov-tblwrap"><table class="cov-htbl"><thead><tr><th>Handler</th><th>State</th><th>Calls</th><th>Line coverage</th></tr></thead><tbody>{handler_rows(c, s)}</tbody></table></div>'
                  f'<p class="mut cov-note">Line coverage counts the lines inside each handler function that ran at least once. Calls bar is logarithmic. Idle and main-loop handlers run thousands of times because they fire on every loop pass.</p>')
    else:
        htable = f'<p class="mut">{ui.icon("info-circle", 14)} No per-handler counters for this module: {e(c.get("why"))}. Build the simulator with COVERAGE=1 (the Makefile default) to list each handler with its call count.</p>'
    label, snip = snippet_for(c, s, state)
    snip_html = ""
    if snip:
        snip_html = (f'<div class="cov-snip"><div class="cov-snip-h"><span>{ui.icon("terminal-2", 14)}{e(label)}</span>{copy_button(snip, "Copy snippet")}</div><pre><code>{e(snip)}</code></pre></div>')
    folder = os.path.dirname(path)
    links = (f'<div class="cov-links">{ui.file_link(path, label=os.path.basename(path) or path)}'
             + (f'{ui.file_link(folder, label=folder)}' if folder else "")
             + copy_button(path, "Copy path") + "</div>")
    fw = f' in {e(fw_label)}' if fw_label else ""
    return (
        f'<div class="cov-card">'
        f'<div class="cov-head"><div class="cov-title">{ui.icon("package", 18)}<h4>{e(module_name(path))}</h4>{ui.status_badge(state)}</div>'
        f'<div class="cov-sub-t mut">{e(path)}{fw}</div></div>'
        f'<div class="cov-stats cov-stats-s">{stats}</div>'
        f'<div class="cov-cols">'
        f'<div class="cov-col"><h5>{ui.icon("bolt", 15)}Events it hooks</h5>{event_block(c)}</div>'
        f'<div class="cov-col cov-explain cov-ex-{kind}"><h5>{ui.icon(icon_name, 15)}What this state means</h5><p>{e(meaning)}</p>'
        f'<h5>{ui.icon("route", 15)}What to do</h5><p>{e(action)}</p>{snip_html}</div>'
        f'</div>'
        f'<h5 class="cov-h5">{ui.icon("list-details", 15)}Handlers <span class="mut">({s["entered"]} of {s["n"]} entered)</span></h5>{htable}'
        f'<h5 class="cov-h5">{ui.icon("link", 15)}Source</h5>{links}'
        f'</div>')


def legend_body(counts, total, fw_label):
    rows = "".join(
        f'<li>{ui.status_badge(st)}<div><b>{e(STATE_LABEL[st])}</b> ({counts[st]})<span>{e(STATE_MEANING[st][1])}</span></div></li>' for st in STATES)
    ev = "".join(f'<li>{ui.icon("bolt", 14)}<div><b>{e(event_label(k))}</b><span>{e(v)}</span></div></li>' for k, v in EVENT_INFO.items())
    how = ("# 1. Make the test configuration create the module (cases/modules/config.txt)\n"
           "# 2. Add a G-code line it handles (cases/modules/workload.gcode)\n"
           "# 3. Re-run the checks:  ./run_checks.sh <sim> <firmware tree> fw out")
    return (
        f'<div class="cov-card">'
        f'<div class="cov-head"><div class="cov-title">{ui.icon("search", 18)}<h4>How to read module coverage</h4></div>'
        f'<div class="cov-intro">A module that never runs cannot be checked at runtime. This table shows which ones the workload really reached.</div></div>'
        f'<div class="cov-cols"><div class="cov-col"><h5>{ui.icon("shield-check", 15)}States</h5><ul class="cov-legend">{rows}</ul></div>'
        f'<div class="cov-col"><h5>{ui.icon("bolt", 15)}Events</h5><ul class="cov-events">{ev}</ul></div></div>'
        f'<h5 class="cov-h5">{ui.icon("terminal-2", 15)}Adding a module to the workload</h5>'
        f'<p>Counters come from gcov: a handler counts as entered only when its first line really executed, not when it was merely registered. '
        f'Open a module\'s own More info card for the exact handlers it is missing and a snippet to copy.</p>'
        f'<div class="cov-snip"><div class="cov-snip-h"><span>{ui.icon("terminal-2", 14)}steps</span>{copy_button(how, "Copy steps")}</div><pre><code>{e(how)}</code></pre></div>'
        f'</div>')


def progress_bar(counts, total):
    segs = "".join(
        f'<i class="cov-seg cov-seg-{st}" style="width:{pct(counts[st], total):.2f}%" title="{e(STATE_LABEL[st])}: {counts[st]} of {total}"></i>' for st in STATES if counts[st])
    desc = ", ".join(f'{STATE_LABEL[st]} {counts[st]}' for st in STATES)
    return f'<div class="cov-bar" role="img" aria-label="Module coverage: {e(desc)} of {total} modules">{segs}</div>'


def filter_chips(counts, total):
    out = [f'<button type="button" class="cov-filter" data-f="all" aria-pressed="true">{ui.icon("layers-subtract", 14)}All <span class="cov-fc">{total}</span></button>']
    for st in STATES:
        if counts[st]:
            out.append(f'<button type="button" class="cov-filter cov-f-{st}" data-f="{st}" aria-pressed="false"><i class="cov-dot cov-seg-{st}"></i>{e(STATE_LABEL[st])} <span class="cov-fc">{counts[st]}</span></button>')
    return "".join(out)


def table_rows(cov, fw_label):
    out = []
    for c in cov:
        state = str(c.get("state") or "")
        s = stats_of(c)
        path = str(c.get("file") or "")
        events = [str(x) for x in (c.get("events") or [])]
        text = " ".join([path, state, " ".join(events), str(c.get("why") or "")]).lower()
        mini = (f'<div class="cov-mini">{bar(s["entered"], s["n"], STATE_KIND.get(state, "info"), "%d of %d handlers entered" % (s["entered"], s["n"]))}<span class="cov-num">{s["entered"]}/{s["n"]}</span></div>'
                if s["n"] else "")
        ev = "".join(ui.chip(event_label(x), "") for x in events) or '<span class="mut">none</span>'
        did = slug(path)
        out.append(
            f'<tr class="cov-row cov-r-{e(state)}" data-cov-state="{e(state)}" data-cov-text="{e(text)}">'
            f'<td data-label="Module file" class="cov-file">{ui.file_link(path)}</td>'
            f'<td data-label="State" class="cov-st">{ui.status_badge(state)}{mini}</td>'
            f'<td data-label="Events" class="cov-ev">{ev}</td>'
            f'<td data-label="Why" class="cov-why">{e(c.get("why"))}</td></tr>'
            f'<tr class="cov-sub" data-cov-state="{e(state)}" data-cov-text="{e(text)}"><td colspan="4">'
            f'{ui.drawer("See more info", module_drawer_body(c, fw_label), did)}</td></tr>')
    return "".join(out)


COVERAGE_CSS = """
.cov{--c-pass:#3fb950;--c-warn:#d29922;--c-fail:#f85149;--c-info:#58a6ff;--c-nr:#db6d28;--c-mut:#8b949e;--c-line:color-mix(in srgb,currentColor 16%,transparent);--c-soft:color-mix(in srgb,currentColor 5%,transparent);--c-soft2:color-mix(in srgb,currentColor 9%,transparent);margin:1.2em 0}
@media(prefers-color-scheme:light){:root:not([data-theme=dark]) .cov{--c-pass:#1a7f37;--c-warn:#9a6700;--c-fail:#cf222e;--c-info:#0969da;--c-nr:#bc4c00;--c-mut:#59636e}}
:root[data-theme=light] .cov{--c-pass:#1a7f37;--c-warn:#9a6700;--c-fail:#cf222e;--c-info:#0969da;--c-nr:#bc4c00;--c-mut:#59636e}
.cov *{box-sizing:border-box}
.cov .mut{color:var(--c-mut)}
.cov-h{display:flex;align-items:center;gap:.5em;flex-wrap:wrap;margin:0 0 .3em}
.cov-h h3{margin:0;display:flex;align-items:center;gap:.4em}
.cov-fwl{font-size:12px;display:inline-flex;align-items:center;gap:.3em;padding:2px 8px;border:1px solid var(--c-line);border-radius:99px;color:var(--c-mut)}
.cov-intro{margin:.2em 0 .8em;color:var(--c-mut);font-size:13px}
.cov-stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;margin:.6em 0}
.cov-stats-s{grid-template-columns:repeat(auto-fit,minmax(120px,1fr))}
.cov-bar{display:flex;height:12px;border-radius:99px;overflow:hidden;background:var(--c-soft2);margin:.7em 0 .4em}
.cov-seg{display:block}.cov-seg-exercised{background:var(--c-pass)}.cov-seg-partial{background:var(--c-warn)}.cov-seg-loaded-not-run{background:var(--c-nr)}.cov-seg-excluded{background:var(--c-fail)}
.cov-barnote{font-size:12px;color:var(--c-mut);margin:0 0 .8em}
.cov-tools{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:.6em 0}
.cov-filter{font:inherit;font-size:12.5px;color:inherit;background:var(--c-soft);border:1px solid var(--c-line);border-radius:99px;padding:4px 10px;cursor:pointer;display:inline-flex;align-items:center;gap:.4em;min-height:30px}
.cov-filter:hover{background:var(--c-soft2)}.cov-filter[aria-pressed=true]{border-color:var(--c-info);background:color-mix(in srgb,var(--c-info) 16%,transparent)}
.cov-filter:focus-visible,.cov-search:focus-visible,.cov-btn:focus-visible,.cov-copy:focus-visible{outline:2px solid var(--c-info);outline-offset:2px}
.cov-dot{width:9px;height:9px;border-radius:50%;display:inline-block}.cov-fc{font-variant-numeric:tabular-nums;color:var(--c-mut)}
.cov-search{font:inherit;font-size:13px;color:inherit;background:var(--c-soft);border:1px solid var(--c-line);border-radius:8px;padding:5px 10px;min-height:30px;flex:1 1 160px;min-width:0;max-width:300px}
.cov-btn{font:inherit;font-size:12.5px;color:inherit;background:transparent;border:1px solid var(--c-line);border-radius:8px;padding:4px 10px;cursor:pointer;display:inline-flex;align-items:center;gap:.35em;min-height:30px}
.cov-btn:hover{background:var(--c-soft2)}
.cov-spacer{flex:1}
.cov-tbl{width:100%;border-collapse:separate;border-spacing:0;font-size:13px}
.cov-tbl th{text-align:left;font-size:12px;color:var(--c-mut);font-weight:600;padding:6px 8px;border-bottom:1px solid var(--c-line)}
.cov-tbl td{padding:8px 8px;vertical-align:top;overflow-wrap:anywhere;border-bottom:0}
.cov-row td{border-top:1px solid var(--c-line)}
.cov-sub td{padding:0 8px 8px}
.cov-row[hidden],.cov-sub[hidden],.cov-empty[hidden]{display:none!important}
.cov-row:hover td,.cov-row:hover+.cov-sub td{background:var(--c-soft)}
.cov-file{width:36%;min-width:200px}.cov-st{white-space:nowrap}.cov-mini{display:flex;align-items:center;gap:6px;margin-top:5px;font-size:11.5px}
.cov-ev{display:flex;flex-wrap:wrap;gap:4px}.cov-why{color:var(--c-mut)}
.cov-meter{display:inline-block;height:6px;width:64px;border-radius:99px;background:var(--c-soft2);overflow:hidden;vertical-align:middle;flex:none}
.cov-meter i{display:block;height:100%;border-radius:99px;background:var(--c-info)}
.cov-m-pass i{background:var(--c-pass)}.cov-m-warn i{background:var(--c-warn)}.cov-m-fail i{background:var(--c-fail)}.cov-m-info i{background:var(--c-info)}
.cov-num{font-variant-numeric:tabular-nums}
.cov-card{border:1px solid var(--c-line);border-radius:12px;padding:14px 16px;background:var(--c-soft);margin:.4em 0;overflow-wrap:anywhere;font-size:13px;line-height:1.5}
.cov-head{margin-bottom:.6em}.cov-title{display:flex;align-items:center;gap:.5em;flex-wrap:wrap}.cov-title h4{margin:0;font-size:16px}
.cov-sub-t{font-size:12px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;margin-top:2px}
.cov-card h5{margin:0 0 .4em;font-size:13px;display:flex;align-items:center;gap:.4em}
.cov-h5{margin:1em 0 .4em!important}
.cov-card p{margin:.3em 0 .6em}
.cov-cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:.8em}
.cov-col{min-width:0}
.cov-explain{border-left:3px solid var(--c-info);padding-left:12px}
.cov-ex-pass{border-color:var(--c-pass)}.cov-ex-warn{border-color:var(--c-warn)}.cov-ex-fail{border-color:var(--c-fail)}
.cov-events,.cov-legend{list-style:none;margin:0;padding:0;display:grid;gap:8px}
.cov-events li,.cov-legend li{display:flex;gap:8px;align-items:flex-start}
.cov-events li>svg{flex:none;margin-top:3px;color:var(--c-info)}
.cov-events li div,.cov-legend li div{display:flex;flex-direction:column;min-width:0}
.cov-events li span,.cov-legend li span{color:var(--c-mut);font-size:12.5px}
.cov-legend li>*:first-child{flex:none}
.cov-tblwrap{width:100%}
.cov-htbl{width:100%;border-collapse:collapse;font-size:12.5px}
.cov-htbl th{text-align:left;font-size:11.5px;color:var(--c-mut);font-weight:600;padding:4px 8px;border-bottom:1px solid var(--c-line)}
.cov-htbl td{padding:7px 8px;border-bottom:1px solid var(--c-line);vertical-align:top}
.cov-hr-no td{background:color-mix(in srgb,var(--c-fail) 7%,transparent)}
.cov-fn{font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.cov-fn b{font-weight:700}
.cov-fnsig{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:11px;color:var(--c-mut);margin:1px 0 4px}
.cov-hs{display:inline-flex;align-items:center;gap:.3em;white-space:nowrap;font-weight:600}.cov-hs-ok{color:var(--c-pass)}.cov-hs-no{color:var(--c-fail)}
.cov-calls,.cov-lines{white-space:nowrap}.cov-calls .cov-meter{display:block;margin-top:4px}.cov-lines{display:flex;flex-direction:column;gap:4px}
.cov-hint{display:flex;gap:6px;align-items:flex-start;margin-top:5px;font-size:12px;color:var(--c-mut)}.cov-hint svg{flex:none;margin-top:2px;color:var(--c-warn)}
.cov-note{font-size:12px}
.cov-snip{border:1px solid var(--c-line);border-radius:8px;overflow:hidden;margin:.5em 0;background:color-mix(in srgb,currentColor 4%,transparent)}
.cov-snip-h{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:4px 8px;border-bottom:1px solid var(--c-line);font-size:12px;color:var(--c-mut)}
.cov-snip-h span{display:inline-flex;align-items:center;gap:.4em}
.cov-snip pre{margin:0;padding:8px 10px;overflow-x:auto;font-size:12px;line-height:1.5;white-space:pre}
.cov-copy{font:inherit;font-size:12px;color:inherit;background:transparent;border:1px solid var(--c-line);border-radius:6px;padding:2px 8px;cursor:pointer;display:inline-flex;align-items:center;gap:.3em;min-height:26px}
.cov-copy:hover{background:var(--c-soft2)}.cov-copy.copied{border-color:var(--c-pass);color:var(--c-pass)}
.cov-links{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
.cov-empty{padding:14px;text-align:center;color:var(--c-mut);border:1px dashed var(--c-line);border-radius:8px;margin:.6em 0}
.cov svg{flex:none;vertical-align:-2px}
@media(max-width:640px){
 .cov-tbl thead,.cov-htbl thead{display:none}
 .cov-tbl,.cov-tbl tbody,.cov-htbl,.cov-htbl tbody{display:block;width:100%}
 .cov-row{display:block;border:1px solid var(--c-line);border-radius:10px 10px 0 0;margin-top:10px;padding:6px 4px}
 .cov-row td{display:block;border:0;padding:3px 8px}
 .cov-row td[data-label]::before{content:attr(data-label);display:block;font-size:11px;text-transform:uppercase;letter-spacing:.04em;color:var(--c-mut)}
 .cov-row td.cov-file::before{display:none}
 .cov-sub{display:block;border:1px solid var(--c-line);border-top:0;border-radius:0 0 10px 10px;padding:2px 4px 6px}
 .cov-sub td{display:block;padding:0 6px}
 .cov-card{padding:12px}
 .cov-htbl tr{display:block;border-bottom:1px solid var(--c-line);padding:6px 0}
 .cov-htbl td{display:block;border:0;padding:2px 4px}
 .cov-htbl td[data-label]:not(:first-child)::before{content:attr(data-label)": ";font-size:11px;color:var(--c-mut)}
 .cov-htbl td:not(:first-child){display:flex;align-items:center;gap:6px;flex-wrap:wrap}
 .cov-calls .cov-meter{display:inline-block;margin:0}
 .cov-lines{flex-direction:row;align-items:center}
}
@media print{.cov-tools{display:none}.cov-row[hidden],.cov-sub[hidden]{display:table-row!important}}
@media(prefers-reduced-motion:reduce){.cov *{transition:none!important}}
"""

COVERAGE_JS = """(function(){try{
var root=document.getElementById('module-coverage');if(!root)return;
var rows=[].slice.call(root.querySelectorAll('tr[data-cov-state]'));
var q=root.querySelector('.cov-search'),cur='all',live=root.querySelector('.cov-live'),empty=root.querySelector('.cov-empty');
function apply(){try{var t=((q&&q.value)||'').toLowerCase().trim(),n=0,tot=0;
rows.forEach(function(r){var main=r.classList.contains('cov-row');var ok=(cur==='all'||r.getAttribute('data-cov-state')===cur)&&(!t||(r.getAttribute('data-cov-text')||'').indexOf(t)>-1);r.hidden=!ok;if(main){tot++;if(ok)n++;}});
if(live)live.textContent='Showing '+n+' of '+tot+' modules';if(empty)empty.hidden=n!==0;}catch(e){}}
[].forEach.call(root.querySelectorAll('.cov-filter'),function(b){b.addEventListener('click',function(){cur=b.getAttribute('data-f')||'all';
[].forEach.call(root.querySelectorAll('.cov-filter'),function(o){o.setAttribute('aria-pressed',o===b?'true':'false');});apply();});});
if(q)q.addEventListener('input',apply);
function setAll(open){[].forEach.call(root.querySelectorAll('tr.cov-sub:not([hidden]) button[aria-expanded]'),function(b){if((b.getAttribute('aria-expanded')==='true')!==open)b.click();});}
var ex=root.querySelector('[data-cov-act=expand]'),co=root.querySelector('[data-cov-act=collapse]');
if(ex)ex.addEventListener('click',function(){setAll(true);});if(co)co.addEventListener('click',function(){setAll(false);});
}catch(e){}})();"""


def coverage_html(d, fw_label=""):
    """The "Module coverage" section. d = the modules result 'data' dict; returns '' when there is no coverage data."""
    try:
        cov = [c for c in ((d or {}).get("coverage") or []) if isinstance(c, dict)]
        if not cov:
            return ""
        counts = {st: sum(1 for c in cov if c.get("state") == st) for st in STATES}
        total = len(cov)
        other = total - sum(counts.values())
        buildable = total - counts["excluded"]
        with_counters = [stats_of(c) for c in cov if c.get("handlers")]
        n_h = sum(s["n"] for s in with_counters)
        n_in = sum(s["entered"] for s in with_counters)
        hit = sum(s["hit"] for s in with_counters)
        tot = sum(s["tot"] for s in with_counters)
        ok_kind = "pass" if counts["exercised"] == buildable else "warn"
        stats = (ui.stat_card("Modules", str(total), "info", "package")
                 + ui.stat_card("Exercised", f'{counts["exercised"]} of {buildable}', ok_kind, "circle-check")
                 + ui.stat_card("Partly exercised", str(counts["partial"]), "warn" if counts["partial"] else "pass", "alert-triangle")
                 + ui.stat_card("Not run", str(counts["loaded-not-run"]), "warn" if counts["loaded-not-run"] else "pass", "circle-dashed")
                 + ui.stat_card("Excluded", str(counts["excluded"]), "fail" if counts["excluded"] else "pass", "circle-x")
                 + (ui.stat_card("Handlers entered", f"{n_in} of {n_h}", "pass" if n_in == n_h else "warn", "plug") if n_h else "")
                 + (ui.stat_card("Handler lines run", f"{pct(hit, tot):.0f} %", "info", "list-details") if tot else ""))
        note = (f'{counts["exercised"]} of {buildable} modules in the build ran completely ({pct(counts["exercised"], buildable):.0f} %)'
                if buildable else "No module is compiled into this build")
        note += f'; {counts["excluded"]} excluded because the simulator cannot fake their hardware.' if counts["excluded"] else "."
        if other:
            note += f" {other} with an unrecognised state."
        fw = f'<span class="cov-fwl">{ui.icon("git-branch", 13)}{e(fw_label)}</span>' if fw_label else ""
        tools = (f'<div class="cov-tools" role="group" aria-label="Filter modules">{filter_chips(counts, total)}</div>'
                 f'<div class="cov-tools"><input class="cov-search" type="search" placeholder="Filter modules" aria-label="Filter modules by file, event or state" autocomplete="off">'
                 f'<span class="cov-spacer"></span><button type="button" class="cov-btn" data-cov-act="expand">{ui.icon("eye", 14)}Open all</button>'
                 f'<button type="button" class="cov-btn" data-cov-act="collapse">{ui.icon("eye-off", 14)}Close all</button></div>'
                 f'<div class="cov-live mut" role="status" aria-live="polite" style="font-size:12px">Showing {total} of {total} modules</div>')
        table = (f'<table class="cov-tbl"><thead><tr><th>Module file</th><th>State</th><th>Events</th><th>Why</th></tr></thead><tbody>{table_rows(cov, fw_label)}</tbody></table>'
                 f'<div class="cov-empty" hidden>No module matches this filter.</div>')
        return (f'<style>{COVERAGE_CSS}</style><div class="cov" id="module-coverage">'
                f'<div class="cov-h"><h3>{ui.icon("shield-check", 20)}Module coverage</h3>{fw}</div>'
                f'<p class="cov-intro">Which modules the test workload really ran. A module that never runs cannot be checked while running, only by the source scan.</p>'
                f'<div class="cov-stats">{stats}</div>{progress_bar(counts, total)}<p class="cov-barnote">{e(note)}</p>'
                f'{ui.drawer("How to read this", legend_body(counts, total, fw_label), "cov-legend")}'
                f'{tools}{table}</div><script>{COVERAGE_JS}</script>')
    except Exception as exc:  # the report must never fail because of one section
        return f'<div class="cov" id="module-coverage"><p class="mut">Module coverage could not be drawn: {html.escape(type(exc).__name__)}</p></div>'

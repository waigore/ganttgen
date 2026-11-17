"""HTML Gantt chart rendering."""

from __future__ import annotations

import html
from datetime import date

from .calendar_util import iter_days
from .models import PHASES, Config, Schedule, TaskRow


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _day_class(d: date, config: Config) -> str:
    classes = ["day"]
    if d.weekday() in config.weekends:
        classes.append("weekend")
    if d in config.holiday_dates:
        classes.append("holiday")
    return " ".join(classes)


def _holiday_name(d: date, config: Config) -> str:
    for h in config.holidays:
        if h.date == d:
            return h.name
    return ""


def _bar_style(start: date, end: date, range_start: date, color: str) -> str:
    left = (start - range_start).days
    width = (end - start).days + 1
    return (
        f"left:calc({left} * var(--day-w));"
        f"width:calc({width} * var(--day-w));"
        f"background:{color};"
    )


def _milestone_groups(tasks: list[TaskRow]) -> list[tuple[str, list[TaskRow]]]:
    groups: list[tuple[str, list[TaskRow]]] = []
    for t in tasks:
        if not groups or groups[-1][0] != t.milestone:
            groups.append((t.milestone, [t]))
        else:
            groups[-1][1].append(t)
    return groups


def render_html(schedule: Schedule) -> str:
    cfg = schedule.config
    days = list(iter_days(schedule.range_start, schedule.range_end))
    day_count = len(days)
    holiday_map = {h.date: h.name for h in cfg.holidays}

    # Month header spans
    months: list[tuple[str, int]] = []
    for d in days:
        label = d.strftime("%b %Y")
        if not months or months[-1][0] != label:
            months.append((label, 1))
        else:
            months[-1] = (label, months[-1][1] + 1)

    caps = ", ".join(
        f"{_esc(cfg.teams[p].label)} {cfg.teams[p].capacity}" for p in PHASES
    )
    if cfg.schedule_mode == "compress":
        start_s = (
            cfg.project_start.isoformat() if cfg.project_start else "?"
        )
        align_note = (
            f"Compress mode from <strong>{_esc(start_s)}</strong> — "
            "milestone markers are targets only (not schedule pins)."
        )
        mode_note = (
            f"Ready-queue ASAP across milestones; team capacity [{caps}]."
        )
    else:
        align_note = (
            "Milestone marker aligns to <strong>Implement</strong> end; "
            "Test may run after the marker."
            if cfg.milestone_align == "implement"
            else "Milestone marker aligns to <strong>Test</strong> end."
        )
        mode_note = (
            f"Align mode — per-milestone ASAP then pin; team capacity [{caps}]."
        )

    css = """
:root {
  --ink: #1c1916;
  --muted: #6b645c;
  --paper: #f4f0e8;
  --panel: #faf8f4;
  --rule: #d4cdc2;
  --weekend: #ebe4d8;
  --holiday: #f0d8d0;
  --milestone: #9b2c2c;
  --day-w: 22px;
  --label-w: 140px;
  --row-h: 34px;
  --bar-h: 22px;
  --font-display: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
  --font-ui: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
  --font-mono: "SF Mono", Menlo, Consolas, monospace;
}
* { box-sizing: border-box; }
html { font-size: 14px; }
body {
  margin: 0;
  padding: 2rem 1.5rem 3rem;
  background:
    radial-gradient(ellipse 80% 50% at 10% -10%, #e8e0d2 0%, transparent 55%),
    radial-gradient(ellipse 60% 40% at 100% 0%, #ddd5c8 0%, transparent 50%),
    var(--paper);
  color: var(--ink);
  font-family: var(--font-ui);
  line-height: 1.45;
}
header.page {
  max-width: 100%;
  margin: 0 0 1.75rem;
  padding-bottom: 1rem;
  border-bottom: 2px solid var(--ink);
}
header.page h1 {
  margin: 0 0 0.35rem;
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 2rem;
  letter-spacing: -0.02em;
}
header.page .meta {
  color: var(--muted);
  font-size: 0.92rem;
  max-width: 62rem;
}
header.page .meta strong { color: var(--ink); font-weight: 600; }
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 1rem 1.5rem;
  margin: 1rem 0 0;
  padding: 0;
  list-style: none;
  font-size: 0.85rem;
}
.legend li { display: flex; align-items: center; gap: 0.45rem; }
.swatch {
  width: 0.85rem; height: 0.85rem; border-radius: 2px;
  display: inline-block;
}
.swatch.weekend { background: var(--weekend); border: 1px solid var(--rule); }
.swatch.holiday { background: var(--holiday); border: 1px solid var(--rule); }
.swatch.milestone { background: var(--milestone); }
section.view {
  margin: 2.25rem 0 0;
}
section.view h2 {
  margin: 0 0 0.75rem;
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 600;
}
.chart-shell {
  overflow-x: auto;
  border: 1px solid var(--rule);
  background: var(--panel);
  box-shadow: 0 1px 0 rgba(28,25,22,0.04);
}
.chart {
  --cols: __DAY_COUNT__;
  position: relative;
  min-width: calc(var(--label-w) + var(--cols) * var(--day-w));
}
.head, .row, .ms-banner {
  display: grid;
  grid-template-columns: var(--label-w) 1fr;
  border-bottom: 1px solid var(--rule);
}
.ms-banner {
  background: #e8e2d6;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}
.ms-banner .label {
  padding: 0.4rem 0.75rem;
  border-right: 1px solid var(--rule);
}
.ms-banner .track {
  position: relative;
  min-height: 1.6rem;
}
.head {
  position: sticky;
  top: 0;
  z-index: 3;
  background: #efe9dd;
  font-size: 0.68rem;
}
.head .label {
  padding: 0.5rem 0.75rem;
  border-right: 1px solid var(--rule);
  display: flex;
  align-items: flex-end;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
}
.timeline {
  position: relative;
  display: flex;
  flex-direction: column;
}
.months, .dates {
  display: grid;
  grid-template-columns: repeat(var(--cols), var(--day-w));
}
.months span {
  border-right: 1px solid var(--rule);
  padding: 0.35rem 0.25rem 0.15rem;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
}
.dates span {
  border-right: 1px solid var(--rule);
  text-align: center;
  padding: 0.15rem 0 0.35rem;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 0.62rem;
}
.dates span.weekend { background: var(--weekend); }
.dates span.holiday { background: var(--holiday); color: var(--ink); }
.row .label {
  padding: 0.35rem 0.75rem;
  border-right: 1px solid var(--rule);
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: var(--row-h);
  background: var(--panel);
  position: sticky;
  left: 0;
  z-index: 2;
}
.row .label .id {
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 600;
}
.row .label .name {
  font-size: 0.72rem;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.row.team-row .label .id { font-family: var(--font-ui); font-size: 0.8rem; }
.track {
  position: relative;
  min-height: var(--row-h);
  display: grid;
  grid-template-columns: repeat(var(--cols), var(--day-w));
}
.track .cell {
  border-right: 1px solid color-mix(in srgb, var(--rule) 70%, transparent);
}
.track .cell.weekend { background: var(--weekend); }
.track .cell.holiday { background: var(--holiday); }
.bar {
  position: absolute;
  top: calc((var(--row-h) - var(--bar-h)) / 2);
  height: var(--bar-h);
  border-radius: 2px;
  color: #fff;
  font-family: var(--font-mono);
  font-size: 0.62rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  display: flex;
  align-items: center;
  padding: 0 0.35rem;
  white-space: nowrap;
  overflow: hidden;
  box-shadow: inset 0 0 0 1px rgba(0,0,0,0.12);
  z-index: 1;
}
.bar.seg-design { opacity: 0.95; }
.milestone-line {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--milestone);
  z-index: 2;
  pointer-events: none;
}
.milestone-line::after {
  content: attr(data-label);
  position: absolute;
  top: 0.15rem;
  left: 4px;
  color: var(--milestone);
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  white-space: nowrap;
  background: color-mix(in srgb, var(--panel) 85%, transparent);
  padding: 0 0.2rem;
}
.footnote {
  margin: 0.6rem 0 0;
  font-size: 0.78rem;
  color: var(--muted);
}
@media print {
  body { background: white; padding: 0.5cm; }
  .chart-shell { overflow: visible; box-shadow: none; }
}
""".replace("__DAY_COUNT__", str(day_count))

    def milestone_lines(scoped_ms: set[str] | None = None) -> str:
        parts: list[str] = []
        for ms, md in cfg.milestones.items():
            if scoped_ms is not None and ms not in scoped_ms:
                continue
            if md < schedule.range_start or md > schedule.range_end:
                continue
            # line at the end of the milestone day column
            offset = (md - schedule.range_start).days
            left = f"calc({offset} * var(--day-w) + var(--day-w) - 1px)"
            label = f"{ms} {md.isoformat()}"
            parts.append(
                f'<div class="milestone-line" style="left:{left}" '
                f'data-label="{_esc(label)}"></div>'
            )
        return "".join(parts)

    def timeline_head(label: str) -> str:
        month_cells = "".join(
            f'<span style="grid-column:span {span}">{_esc(name)}</span>'
            for name, span in months
        )
        date_cells = []
        for d in days:
            title = holiday_map.get(d, "")
            title_attr = f' title="{_esc(title)}"' if title else ""
            date_cells.append(
                f'<span class="{_day_class(d, cfg)}"{title_attr}>{d.day}</span>'
            )
        return f"""
<div class="head">
  <div class="label">{_esc(label)}</div>
  <div class="timeline">
    <div class="months">{month_cells}</div>
    <div class="dates">{"".join(date_cells)}</div>
  </div>
</div>"""

    def track_cells() -> str:
        return "".join(
            f'<div class="cell {_day_class(d, cfg)}"></div>' for d in days
        )

    # ---- View 1: by SP ----
    sp_rows: list[str] = [timeline_head("SP / Program")]
    for ms, group in _milestone_groups(schedule.tasks):
        md = cfg.milestones[ms]
        sp_rows.append(
            f'<div class="ms-banner"><div class="label">{_esc(ms)} · '
            f'{md.isoformat()}</div><div class="track">'
            f"{milestone_lines({ms})}</div></div>"
        )
        for t in group:
            bars = []
            for phase in PHASES:
                st = schedule.by_key[f"{t.id}:{phase}"]
                assert st.start and st.end
                color = cfg.teams[phase].color
                short = phase[:1].upper()
                bars.append(
                    f'<div class="bar seg-{phase}" style="'
                    f'{_bar_style(st.start, st.end, schedule.range_start, color)}" '
                    f'title="{_esc(t.id)} {_esc(phase)} '
                    f'{st.start.isoformat()} → {st.end.isoformat()} '
                    f'({st.duration}d)">{_esc(short)}</div>'
                )
            sp_rows.append(
                f'<div class="row"><div class="label">'
                f'<span class="id">{_esc(t.id)}</span>'
                f'<span class="name">{_esc(t.name)} · {t.size}</span>'
                f"</div><div class=\"track\">{track_cells()}"
                f"{''.join(bars)}{milestone_lines({ms})}</div></div>"
            )

    # ---- View 2: by team ----
    team_rows: list[str] = [timeline_head("Team")]
    all_ms = set(cfg.milestones)
    for phase in PHASES:
        team = cfg.teams[phase]
        bars = []
        for t in schedule.tasks:
            st = schedule.by_key[f"{t.id}:{phase}"]
            assert st.start and st.end
            bars.append(
                f'<div class="bar" style="'
                f'{_bar_style(st.start, st.end, schedule.range_start, team.color)}" '
                f'title="{_esc(t.id)} {_esc(phase)} '
                f'{st.start.isoformat()} → {st.end.isoformat()}">{_esc(t.id)}</div>'
            )
        team_rows.append(
            f'<div class="row team-row"><div class="label">'
            f'<span class="id">{_esc(team.label)}</span>'
            f'<span class="name">{_esc(phase)}</span>'
            f"</div><div class=\"track\">{track_cells()}"
            f"{''.join(bars)}{milestone_lines(all_ms)}</div></div>"
        )

    legend_teams = "".join(
        f'<li><span class="swatch" style="background:{_esc(cfg.teams[p].color)}"></span>'
        f"{_esc(cfg.teams[p].label)}</li>"
        for p in PHASES
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(cfg.title)}</title>
<style>{css}</style>
</head>
<body>
<header class="page">
  <h1>{_esc(cfg.title)}</h1>
  <p class="meta">{align_note} {mode_note}
  Range {schedule.range_start.isoformat()} → {schedule.range_end.isoformat()}.</p>
  <ul class="legend">
    {legend_teams}
    <li><span class="swatch weekend"></span>Weekend</li>
    <li><span class="swatch holiday"></span>Public holiday</li>
    <li><span class="swatch milestone"></span>Milestone</li>
  </ul>
</header>
<section class="view">
  <h2>By stored procedure / program</h2>
  <div class="chart-shell"><div class="chart">
    {"".join(sp_rows)}
  </div></div>
  <p class="footnote">Row order follows the CSV. Segments are Design → Implement → Test.</p>
</section>
<section class="view">
  <h2>By team</h2>
  <div class="chart-shell"><div class="chart">
    {"".join(team_rows)}
  </div></div>
  <p class="footnote">Overlapping bars on a team row use that team’s capacity (same-day concurrency).</p>
</section>
</body>
</html>
"""

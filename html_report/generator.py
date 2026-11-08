"""Генерация автономного HTML-отчёта по инциденту."""

import json
from pathlib import Path

from html_report.data_builder import build_html_report_data


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>1C Log Detective — Отчёт об инциденте</title>

<style>
:root {
    color-scheme: dark;
    --bg: #0b1120;
    --panel: #151f30;
    --panel2: #1c2a3d;
    --panel3: #22334a;
    --text: #e6edf7;
    --muted: #91a2b8;
    --accent: #69b4ff;
    --accent-soft: rgba(105, 180, 255, .12);
    --danger: #ff6b78;
    --danger-soft: rgba(255, 107, 120, .10);
    --warning: #f0b45c;
    --success: #54d39a;
    --border: #2b3b52;
    --radius: 12px;
    --shadow: 0 8px 24px rgba(0, 0, 0, .16);
}

* { box-sizing: border-box; }

html { scroll-behavior: smooth; }

body {
    margin: 0;
    padding: 32px;
    background:
        radial-gradient(ellipse at 50% -20%, #1c304b 0, transparent 55%),
        var(--bg);
    color: var(--text);
    font: 14px/1.6 system-ui, -apple-system, "Segoe UI", sans-serif;
}

main { max-width: 1440px; margin: 0 auto; }

header {
    padding: 8px 0 26px;
    margin-bottom: 24px;
    border-bottom: 1px solid var(--border);
}

h1 {
    margin: 0 0 8px;
    font-size: 30px;
    line-height: 1.25;
    font-weight: 700;
    letter-spacing: -.7px;
}

h2 {
    margin: 30px 0 14px;
    font-size: 20px;
    font-weight: 650;
    letter-spacing: -.25px;
}

h3 { margin: 0; font-size: 16px; font-weight: 650; }

.subtitle, .muted { color: var(--muted); }

.panel, .event, .finding, .incident-summary {
    background: linear-gradient(145deg, var(--panel), #131d2c);
    border: 1px solid var(--border);
    border-radius: var(--radius);
    box-shadow: var(--shadow);
}

.panel { padding: 20px; margin: 16px 0; }

.summary {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(155px, 1fr));
    gap: 14px;
    margin: 24px 0;
}

.metric {
    background: linear-gradient(145deg, var(--panel2), var(--panel));
    border: 1px solid var(--border);
    border-radius: var(--radius);
    padding: 17px 18px;
    transition: border-color .2s, transform .2s;
}

.metric:hover {
    border-color: #486789;
    transform: translateY(-2px);
}

.metric strong {
    display: block;
    font-size: 27px;
    line-height: 1.3;
    color: var(--accent);
    font-weight: 700;
}

.metric span { color: var(--muted); font-size: 12px; }

.incident-summary {
    padding: 22px;
    margin: 24px 0;
    border-left: 3px solid var(--danger);
}

.incident-summary h2 { margin: 0 0 18px; }

.overview-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
    gap: 12px;
}

.overview-item {
    background: var(--panel2);
    border: 1px solid rgba(255,255,255,.035);
    border-radius: 9px;
    padding: 13px 15px;
    min-width: 0;
}

.overview-label {
    color: var(--muted);
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: .55px;
    margin-bottom: 6px;
}

.overview-value { overflow-wrap: anywhere; font-weight: 600; }

.overview-cause {
    margin-top: 15px;
    padding: 16px;
    background: var(--danger-soft);
    border: 1px solid rgba(255,107,120,.2);
    border-radius: 9px;
}

.overview-cause .overview-value { font-weight: 400; }

.overview-events { margin-top: 13px; color: var(--muted); font-size: 12px; }

.event {
    margin: 10px 0;
    padding: 16px 18px;
    transition: border-color .15s, background .15s;
}

.event:hover { border-color: #48617e; }

.event-header { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }

.event-type {
    font-weight: 700;
    color: var(--accent);
    letter-spacing: .2px;
}

.event .event-type[data-type="EXCP"] { color: #e05252; }
.event .event-type[data-type="TTIMEOUT"] { color: #e69a45; }
.event .event-type[data-type="TLOCK"] { color: #e2c34f; }
.event .event-type[data-type="SDBL"] { color: #568bd6; }
.event .event-type[data-type="DBMSSQL"],
.event .event-type[data-type="DBV8DBENG"] { color: #55b9d0; }
.event .event-type[data-type="CALL"] { color: #8993a3; }

.timeline-legend {
    display: flex;
    flex-wrap: wrap;
    gap: 10px 18px;
    margin: 10px 0 14px;
    color: var(--muted);
    font-size: 12px;
}

.legend-item {
    display: inline-flex;
    align-items: center;
    gap: 6px;
}

.legend-dot {
    width: 9px;
    height: 9px;
    border-radius: 50%;
    display: inline-block;
}

.legend-dot[data-type="EXCP"] { background: #e05252; }
.legend-dot[data-type="TTIMEOUT"] { background: #e69a45; }
.legend-dot[data-type="TLOCK"] { background: #e2c34f; }
.legend-dot[data-type="SDBL"] { background: #568bd6; }
.legend-dot[data-type="DBMSSQL"],
.legend-dot[data-type="DBV8DBEng"] { background: #55b9d0; }
.legend-dot[data-type="CALL"] { background: #8993a3; }

.timestamp {
    color: var(--muted);
    font-variant-numeric: tabular-nums;
    font-family: "Cascadia Code", Consolas, monospace;
    font-size: 12px;
}

.description { margin: 10px 0; white-space: pre-wrap; overflow-wrap: anywhere; }

.meta { color: var(--muted); font-size: 12px; overflow-wrap: anywhere; }

.error-event {
    border-color: rgba(255,107,120,.65);
    background: linear-gradient(110deg, rgba(105,32,48,.28), var(--panel));
    box-shadow: inset 3px 0 0 var(--danger), var(--shadow);
}

.error-event .event-type { color: var(--danger); }

.timeout-event {
    border-color: rgba(230, 154, 69, .45);
    background: linear-gradient(
        110deg,
        rgba(230, 154, 69, .10),
        var(--panel)
    );
    box-shadow: inset 3px 0 0 #e69a45, var(--shadow);
}

.timeout-event .event-type {
    color: #e69a45;
}

details { margin-top: 12px; }

summary { cursor: pointer; color: var(--accent); }
summary:hover { color: #a5d3ff; }

pre {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
    background: #0a101b;
    border: 1px solid var(--border);
    border-radius: 9px;
    padding: 14px;
    font-size: 12px;
    line-height: 1.55;
    color: #c8d5e6;
    overflow-x: auto;
}

.controls {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: center;
    margin: 16px 0;
}

.filter-toggle {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    color: var(--muted);
    cursor: pointer;
    padding: 8px 11px;
    border: 1px solid var(--border);
    border-radius: 8px;
    background: var(--panel);
    transition: .15s;
}

.filter-toggle:hover { color: var(--text); border-color: var(--accent); }

.filter-toggle input[type="checkbox"] {
    width: auto;
    margin: 0;
    accent-color: var(--accent);
}

input, select {
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    padding: 10px 12px;
    min-width: 190px;
    font: inherit;
    outline: none;
}

input:focus, select:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }

button {
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 8px;
    color: var(--text);
    padding: 9px 14px;
    font: inherit;
    cursor: pointer;
    transition: .15s;
}

button:hover { border-color: var(--accent); background: var(--panel3); }

.lane { border-left: 2px solid var(--border); padding-left: 18px; }

.timeline-scale {
    overflow-x: auto;
    padding: 30px 24px 42px;
    margin: 14px 0 22px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: var(--radius);
}

.timeline-track {
    position: relative;
    min-width: 600px;
    height: 100px;
    margin: 0 12px;
}

.timeline-axis {
    position: absolute;
    top: 42px;
    left: 0;
    right: 0;
    height: 3px;
    background: var(--border);
    border-radius: 3px;
}

.timeline-edge {
    position: absolute;
    top: 0;
    color: var(--muted);
    font-size: 12px;
    font-weight: 600;
}

.timeline-start {
    left: 0;
}

.timeline-end {
    right: 0;
}

.timeline-point {
    position: absolute;
    top: 37px;
    transform: translateX(-50%);
    width: 14px;
    height: 14px;
    padding: 0;
    border: 2px solid var(--panel);
    border-radius: 50%;
    background: var(--accent);
    cursor: pointer;
    z-index: 2;
}

.timeline-point:hover {
    transform: translateX(-50%) scale(1.4);
    z-index: 5;
}

.timeline-point[data-type="EXCP"] {
    background: #e05252;
}

.timeline-point[data-type="TTIMEOUT"] {
    background: #e69a45;
}

.timeline-point[data-type="TLOCK"] {
    background: #e2c34f;
}

.timeline-point[data-type="SDBL"] {
    background: #568bd6;
}

.timeline-point[data-type="DBMSSQL"],
.timeline-point[data-type="DBV8DBEng"] {
    background: #55b9d0;
}

.timeline-point[data-type="CALL"] {
    background: #8993a3;
}

.timeline-point.active {
    outline: 2px solid var(--text);
    outline-offset: 4px;
}

.timeline-point.related-point {
    outline: 2px dashed var(--accent);
    outline-offset: 4px;
}

.timeline-point-label {
    position: absolute;
    top: var(--label-top, 23px);
    left: 50%;
    transform: translateX(-50%);
    color: var(--text);
    font-size: 10px;
    font-weight: 700;
    white-space: nowrap;
    pointer-events: none;
}

@media (max-width: 760px) {
    .timeline-scale {
        padding-left: 14px;
        padding-right: 14px;
    }
}

.finding {
    margin: 10px 0;
    padding: 17px 18px;
    border-left: 3px solid var(--accent);
}

.finding strong { color: var(--accent); }

.finding-summary { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; }

.finding-count { color: var(--muted); font-size: 12px; }

.finding-events {
    margin-top: 13px;
    padding-top: 12px;
    border-top: 1px solid var(--border);
}

.finding-events > summary { font-size: 12px; }

.finding-event-link {
    display: block;
    width: 100%;
    margin-top: 7px;
    padding: 10px 12px;
    text-align: left;
    color: var(--accent);
    background: var(--panel2);
    border: 1px solid var(--border);
    border-radius: 8px;
    cursor: pointer;
}

.finding-event-link:hover { background: var(--panel3); border-color: var(--accent); }

.event-highlight {
    border-color: var(--accent);
    box-shadow: 0 0 0 2px var(--accent-soft), var(--shadow);
}

.empty { color: var(--muted); padding: 16px 0; }

footer {
    margin-top: 40px;
    padding-top: 18px;
    border-top: 1px solid var(--border);
    color: var(--muted);
    font-size: 12px;
}

@media (max-width: 760px) {
    body { padding: 18px; }
    h1 { font-size: 24px; }
    h2 { font-size: 18px; }
    .panel, .incident-summary { padding: 15px; }
    .summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 420px) {
    body { padding: 12px; }
    .summary { grid-template-columns: 1fr 1fr; gap: 8px; }
    .metric { padding: 12px; }
    .metric strong { font-size: 22px; }
    input, select { min-width: 0; width: 100%; }
}

/* ===== Visual refinement ===== */

:root {
    --bg: #0a0f1a;
    --panel: #121c2b;
    --panel2: #192638;
    --panel3: #22344b;
    --border: #293b52;
    --accent: #70baff;
    --danger: #ff6878;
    --warning: #f3b65e;
    --success: #55d6a0;
    --radius: 14px;
    --shadow: 0 10px 30px rgba(0, 0, 0, .20);
}

body {
    padding: 36px;
    background:
        radial-gradient(ellipse at 15% 0%, rgba(45, 100, 160, .16), transparent 38%),
        radial-gradient(ellipse at 90% 10%, rgba(90, 60, 140, .10), transparent 35%),
        var(--bg);
    line-height: 1.65;
}

main {
    max-width: 1480px;
}

header {
    padding: 12px 0 28px;
    margin-bottom: 28px;
    border-bottom: 1px solid rgba(112, 186, 255, .18);
}

h1 {
    font-size: 34px;
    letter-spacing: -1px;
    background: linear-gradient(100deg, #ffffff, #83bdff);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}

.subtitle {
    font-size: 14px;
    letter-spacing: .2px;
}

h2 {
    margin-top: 34px;
    padding-bottom: 10px;
    border-bottom: 1px solid rgba(145, 162, 184, .12);
}

.panel,
.event,
.finding,
.incident-summary {
    border-color: rgba(145, 162, 184, .15);
    box-shadow: var(--shadow);
}

.panel {
    padding: 22px;
}

.metric {
    padding: 19px;
    background: linear-gradient(145deg, #1c2d43, #141f30);
}

.metric strong {
    font-size: 30px;
    letter-spacing: -.7px;
}

.incident-summary {
    padding: 26px;
    background: linear-gradient(125deg, #251c2b, #151e2d 65%);
}

.overview-item {
    background: rgba(255, 255, 255, .035);
    border-color: rgba(255, 255, 255, .055);
}

.overview-cause {
    background: rgba(255, 107, 120, .08);
    border-color: rgba(255, 107, 120, .22);
}

.event {
    padding: 18px 20px;
    background: linear-gradient(110deg, #172437, #121c2b);
}

.error-event {
    background: linear-gradient(110deg, rgba(105, 32, 48, .35), #17202f);
}

.finding {
    background: linear-gradient(110deg, #17283b, #121c2b);
}

.timeline-scale {
    background: linear-gradient(110deg, #172437, #111b2a);
    padding: 28px 18px;
}

input,
select,
button,
.filter-toggle {
    border-radius: 10px;
}

button {
    padding: 10px 16px;
    font-weight: 600;
}

#export-bug-report {
    background: linear-gradient(110deg, #2468a8, #347fc0);
    border-color: #438fd0;
    color: #fff;
}

#export-bug-report:hover {
    background: linear-gradient(110deg, #307fca, #4598dc);
    box-shadow: 0 4px 18px rgba(65, 145, 220, .25);
}

pre {
    background: #090f19;
    border-color: rgba(112, 186, 255, .16);
    border-radius: 10px;
    padding: 17px;
    line-height: 1.65;
}

details > summary {
    padding: 4px 0;
    font-weight: 600;
}

footer {
    margin-top: 50px;
    padding-top: 22px;
}

@media (max-width: 760px) {
    body { padding: 18px; }
    h1 { font-size: 27px; }
    .panel { padding: 16px; }
}

/* Первый экран: карточка инцидента и KPI */
.incident-hero-layout {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 220px;
    gap: 20px;
    align-items: stretch;
    margin-bottom: 24px;
}

.incident-hero-card {
    min-width: 0;
    padding: 28px;
    border: 1px solid #334155;
    border-left: 4px solid #ef4444;
    border-radius: 16px;
    background: linear-gradient(145deg, #1e293b, #111827);
    box-shadow: 0 12px 30px rgba(0, 0, 0, 0.22);
}

.incident-hero-eyebrow {
    margin-bottom: 12px;
    color: #f87171;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: 2px;
}

.incident-hero-title {
    margin: 0 0 24px;
    font-size: 25px;
    line-height: 1.35;
}

.incident-hero-details {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 18px;
}

.incident-hero-detail {
    min-width: 0;
}

.incident-hero-cause {
    margin-top: 24px;
    padding: 18px;
    border-radius: 10px;
    background: rgba(15, 23, 42, 0.75);
}

.incident-hero-footer {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: 18px;
    margin-top: 22px;
}

.incident-hero-confidence {
    display: flex;
    flex-direction: column;
    gap: 5px;
}

.incident-hero-evidence {
    display: flex;
    align-items: baseline;
    gap: 8px;
    color: #94a3b8;
}

.incident-hero-evidence strong {
    color: #e2e8f0;
    font-size: 22px;
}

.incident-hero-resource {
    display: flex;
    flex-direction: column;
    gap: 6px;
    margin-top: 18px;
}

.incident-kpis {
    display: grid;
    grid-template-rows: repeat(3, minmax(100px, 1fr));
    gap: 12px;
}

.incident-kpi {
    display: flex;
    flex-direction: column;
    justify-content: center;
    padding: 18px;
    border: 1px solid #334155;
    border-radius: 14px;
    background: #1e293b;
}

.incident-kpi-label {
    color: #94a3b8;
    font-size: 12px;
    font-weight: 700;
    letter-spacing: 1px;
}

.incident-kpi-value {
    margin: 5px 0;
    color: #f8fafc;
    font-size: 30px;
    font-weight: 800;
}

.incident-kpi-description {
    color: #94a3b8;
    font-size: 12px;
}

@media (max-width: 760px) {
    .incident-hero-layout {
        grid-template-columns: 1fr;
    }

    .incident-kpis {
        grid-template-columns: repeat(3, minmax(0, 1fr));
        grid-template-rows: auto;
    }

    .incident-kpi {
        padding: 12px;
    }

    .incident-kpi-value {
        font-size: 24px;
    }
}

@media (max-width: 480px) {
    .incident-hero-card {
        padding: 18px;
    }

    .incident-hero-details {
        grid-template-columns: 1fr;
    }

    .incident-kpis {
        grid-template-columns: 1fr;
    }
}

/* ===== Переключение светлой и тёмной темы ===== */

.theme-toggle {
    margin-top: 16px;
    padding: 9px 15px;
    border: 1px solid var(--border);
    border-radius: 9px;
    background: var(--panel2);
    color: var(--text);
    font: inherit;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: background .2s, border-color .2s;
}

.theme-toggle:hover {
    border-color: var(--accent);
    background: var(--panel3);
}

html[data-theme="light"] {
    color-scheme: light;
    --bg: #f1f5f9;
    --panel: #ffffff;
    --panel2: #f8fafc;
    --panel3: #eaf0f7;
    --text: #172033;
    --muted: #64748b;
    --accent: #1769aa;
    --accent-soft: rgba(23, 105, 170, .10);
    --danger: #dc3545;
    --danger-soft: rgba(220, 53, 69, .09);
    --warning: #a96808;
    --success: #168452;
    --border: #d5deea;
    --shadow: 0 8px 24px rgba(30, 50, 75, .08);
}

html[data-theme="light"] body {
    color: var(--text);
    background:
        radial-gradient(ellipse at 15% 0%, rgba(45, 100, 160, .07), transparent 38%),
        radial-gradient(ellipse at 90% 10%, rgba(90, 60, 140, .04), transparent 35%),
        var(--bg);
}

html[data-theme="light"] h1 {
    background: linear-gradient(100deg, #172033, #1769aa);
    -webkit-background-clip: text;
    background-clip: text;
    color: transparent;
}

html[data-theme="light"] .metric {
    background: linear-gradient(145deg, #ffffff, #edf3f9);
}

html[data-theme="light"] .incident-summary {
    background: linear-gradient(125deg, #f5eff5, #ffffff 65%);
}

html[data-theme="light"] .overview-item {
    background: rgba(30, 50, 75, .035);
    border-color: rgba(30, 50, 75, .10);
}

html[data-theme="light"] .overview-cause {
    background: rgba(220, 53, 69, .055);
    border-color: rgba(220, 53, 69, .20);
}

html[data-theme="light"] .event,
html[data-theme="light"] .finding {
    background: linear-gradient(110deg, #ffffff, #f1f5f9);
}

html[data-theme="light"] .error-event {
    background: linear-gradient(110deg, #fff0f1, #f8fafc);
}

html[data-theme="light"] .timeline-scale {
    background: linear-gradient(110deg, #f1f5f9, #ffffff);
}

html[data-theme="light"] pre {
    color: #243247;
    background: #eaf0f6;
    border-color: #d5deea;
}

html[data-theme="light"] .incident-hero-card {
    border-color: #cbd5e1;
    background: linear-gradient(145deg, #ffffff, #edf2f8);
    box-shadow: 0 12px 30px rgba(30, 50, 75, .09);
}

html[data-theme="light"] .incident-hero-cause {
    background: rgba(226, 232, 240, .75);
}

html[data-theme="light"] .incident-hero-evidence {
    color: #64748b;
}

html[data-theme="light"] .incident-hero-evidence strong {
    color: #172033;
}

html[data-theme="light"] .incident-kpi {
    border-color: #cbd5e1;
    background: #f8fafc;
}

html[data-theme="light"] .incident-kpi-label,
html[data-theme="light"] .incident-kpi-description {
    color: #64748b;
}

html[data-theme="light"] .incident-kpi-value {
    color: #172033;
}

html[data-theme="light"] table th,
html[data-theme="light"] table td {
    border-color: var(--border);
}

html[data-theme="light"] input,
html[data-theme="light"] select,
html[data-theme="light"] textarea {
    color: var(--text);
    background: var(--panel);
    border-color: var(--border);
}

html[data-theme="light"] .theme-toggle {
    color: var(--text);
    background: #ffffff;
    border-color: #cbd5e1;
}


/* ===== Обновлённая верхняя панель ===== */

.app-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 24px;
    padding: 20px 22px;
    margin-bottom: 26px;
    border: 1px solid var(--border);
    border-radius: 16px;
    background: linear-gradient(120deg, var(--panel), var(--panel2));
    box-shadow: var(--shadow);
}

.brand {
    display: flex;
    align-items: center;
    gap: 15px;
    min-width: 240px;
}

.brand-mark {
    display: grid;
    place-items: center;
    flex: 0 0 48px;
    width: 48px;
    height: 48px;
    border-radius: 13px;
    background: linear-gradient(135deg, #2878bd, #55a5e8);
    color: #ffffff;
    font-size: 19px;
    font-weight: 800;
    letter-spacing: -1px;
    box-shadow: 0 5px 18px rgba(45, 125, 195, .25);
}

.brand-text h1 {
    margin: 0;
    font-size: 25px;
}

.brand-text .subtitle {
    margin-top: 4px;
    font-size: 12px;
}

.header-actions {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    flex-wrap: wrap;
    gap: 10px;
}

.incident-counter {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 9px 13px;
    border: 1px solid var(--border);
    border-radius: 10px;
    background: var(--panel2);
}

.incident-counter-value {
    color: var(--accent);
    font-size: 22px;
    font-weight: 750;
    line-height: 1;
}

.incident-counter-label {
    color: var(--muted);
    font-size: 12px;
    white-space: nowrap;
}

.header-selector {
    display: flex;
    align-items: center;
    flex-wrap: wrap;
    gap: 7px;
}

.header-selector label {
    color: var(--muted);
    font-size: 12px;
}

.header-selector select {
    max-width: 300px;
    min-width: 180px;
}

.app-header .theme-toggle {
    margin: 0;
}

.app-header #export-bug-report {
    white-space: nowrap;
}

html[data-theme="light"] .app-header {
    background: linear-gradient(120deg, #ffffff, #f1f6fc);
    border-color: #d8e1eb;
}

html[data-theme="light"] .incident-counter {
    background: #f8fafc;
    border-color: #d8e1eb;
}

@media (max-width: 900px) {
    .app-header {
        align-items: flex-start;
    }

    .header-actions {
        justify-content: flex-start;
        width: 100%;
    }
}

@media (max-width: 560px) {
    .app-header {
        padding: 16px;
    }

    .brand {
        min-width: 0;
    }

    .brand-text h1 {
        font-size: 21px;
    }

    .header-actions {
        align-items: stretch;
        flex-direction: column;
    }

    .header-actions > *,
    .header-selector select {
        width: 100%;
        max-width: none;
    }

    .header-selector {
        align-items: stretch;
        flex-direction: column;
    }

    .incident-counter {
        justify-content: center;
    }
}

</style>

</head>
<body>
<main>
<header class="app-header">
    <div class="brand">
        <div class="brand-mark">1C</div>
        <div class="brand-text">
            <h1>1C Log Detective</h1>
            <div class="subtitle">Расследование технологического журнала 1С</div>
        </div>
    </div>

    <div class="header-actions">
        <div class="incident-counter">
            <span class="incident-counter-value" id="incident-count">0</span>
            <span class="incident-counter-label">инцидентов найдено</span>
        </div>

        <div id="incident-selector" class="header-selector" hidden>
            <label for="incident-select">Инцидент</label>
            <select id="incident-select" aria-label="Выберите инцидент"></select>
            <span id="incident-position" class="muted"></span>
        </div>

        <button type="button" id="theme-toggle" class="theme-toggle">
            ☀ Светлая тема
        </button>

        <button id="export-bug-report" type="button">
            Экспорт отчёта
        </button>
    </div>
</header>

<section id="incident-summary" class="incident-summary"></section>
<div id="status" class="panel" hidden></div>

<h2>Статистика цепочки</h2>
<section id="summary" class="summary"></section>

<section id="incident" class="panel"></section>

<h2>Временная шкала</h2>
<div class="timeline-controls">
    <div class="filter-row filter-row-types">
        <div id="event-filter-chips" class="event-filter-chips"></div>
        <select id="event-filter" aria-label="Фильтр по типу события" hidden>
            <option value="ALL">Все типы событий</option>
            <option value="EXCP">EXCP</option>
            <option value="SDBL">SDBL</option>
            <option value="DBV8DBEng">DBV8DBEng</option>
        </select>
    </div>

    <div class="filter-row filter-row-search">
        <input id="search" type="search" placeholder="Поиск по событиям...">
        <select id="user-filter" aria-label="Фильтр по пользователю">
            <option value="ALL">Все пользователи</option>
        </select>
    </div>

    <div class="filter-row filter-row-options">
        <label class="filter-toggle">
            <input id="only-problems" type="checkbox">
            Только проблемы
        </label>
        <label class="filter-toggle">
            <input id="include-related-sessions" type="checkbox">
            Включить связанные сеансы
        </label>
    </div>
</div>


<div class="timeline-legend">
    <span class="legend-item"><i class="legend-dot" data-type="EXCP"></i> EXCP — ошибка</span>
    <span class="legend-item"><i class="legend-dot" data-type="TTIMEOUT"></i> TTIMEOUT — ожидание</span>
    <span class="legend-item"><i class="legend-dot" data-type="TLOCK"></i> TLOCK — блокировка</span>
    <span class="legend-item"><i class="legend-dot" data-type="SDBL"></i> SDBL — запрос 1С</span>
    <span class="legend-item"><i class="legend-dot" data-type="DBV8DBEng"></i> DBMS — SQL/СУБД</span>
    <span class="legend-item"><i class="legend-dot" data-type="CALL"></i> CALL — контекст вызова</span>
</div>
<div id="timeline-scale" class="timeline-scale"></div>

<h3>До исключения</h3>
<div id="before" class="lane"></div>

<h3>Центральное исключение</h3>
<div id="error-event"></div>

<h3>После исключения</h3>
<div id="after" class="lane"></div>

<h2>События других потоков</h2>
<div id="related-events"></div>

<h2>Диагностические признаки</h2>
<div id="findings"></div>

<h2>Сводка по связанным событиям</h2>
<div id="related-findings"></div>

<h2>Что проверить дальше</h2>
<ol id="next-checks"></ol>

<footer>Отчёт сформирован 1C Log Detective. Данные встроены в файл; подключение к серверу не требуется.</footer>
</main>

<script id="report-data" type="application/json">__REPORT_DATA__</script>
<script>
"use strict";

const data = JSON.parse(document.getElementById("report-data").textContent);

const incidents = Array.isArray(data.incidents) && data.incidents.length
    ? data.incidents
    : [data];

let currentIncidentIndex = incidents.length - 1;

function getCurrentData() {
    return incidents[currentIncidentIndex];
}


function buildBugReportMarkdown() {
    const current = getCurrentData();
    const incident = current.incident || {};
    const overview = current.overview || {};
    const period = overview.period || {};
    const timeline = current.timeline || {};

    const lines = [
        "# Bug report — 1C Log Detective",
        "",
        "## 1. Проблема",
        [
            incident.exception_category,
            incident.description,
            incident.exception_detail,
        ].filter(Boolean).join(" — ") || "Описание отсутствует.",
        "",
        "## 2. Контекст",
        `- Время ошибки: ${incident.timestamp || "Неизвестно"}`,
        `- Пользователь: ${incident.user || "Неизвестно"}`,
        `- Процесс: ${incident.process || "Неизвестно"}`,
        `- Поток: ${incident.thread || "Неизвестно"}`,
        `- Контекст 1С: ${incident.context || "Неизвестно"}`,
        `- Индекс события: ${incident.error_index ?? "Неизвестно"}`,
        `- Ресурс: ${incident.exception_resource || "Неизвестно"}`,
        `- GUID: ${incident.exception_guid || "Неизвестно"}`,
        "",
        "## 3. Период анализа",
        period.start && period.end
            ? `${period.start} – ${period.end}`
            : "Период неизвестен.",
        "",
    ];

    function addEvent(event, includeRaw = false) {
        if (!event) return;

        lines.push(
            `### ${event.event_type || "OTHER"} — ${event.timestamp || "время неизвестно"}`,
            `- Индекс: ${event.index ?? "неизвестно"}`,
            `- Уровень: ${event.level || "неизвестно"}`,
            `- Пользователь: ${event.user || "неизвестно"}`,
            `- Процесс: ${event.process || "неизвестно"}`,
            `- Поток: ${event.thread || "неизвестно"}`,
            `- Контекст: ${event.context || "неизвестно"}`,
            `- Описание: ${event.description || "Отсутствует."}`
        );

        if (event.sql) {
            lines.push(
                "",
                `Тип SQL: ${event.sql_type || "неизвестно"}`,
                `Таблицы: ${(event.sql_tables || []).join(", ") || "не определены"}`,
                "",
                "```sql",
                event.sql,
                "```"
            );
        }

        if (event.rows !== undefined && event.rows !== null) {
            lines.push(`Возвращено строк: ${event.rows}`);
        }

        if (event.rows_affected !== undefined && event.rows_affected !== null) {
            lines.push(`Затронуто строк: ${event.rows_affected}`);
        }

        if (event.correlation_reason) {
            lines.push(`Причина корреляции: ${event.correlation_reason}`);
        }

        if (event.correlation_strength) {
            lines.push(`Сила корреляции: ${event.correlation_strength}`);
        }

        if (includeRaw && event.raw_text) {
            lines.push("", "**Исходный текст события:**", "", "```text",
                event.raw_text, "```");
        }

        lines.push("");
    }

    lines.push(
        "## 4. Итог анализа",
        `- Вероятная причина: ${overview.probable_cause || "Причина не установлена."}`,
        `- Уверенность: ${overview.confidence || "Недостаточно данных"}`,
        `- Обнаруженный симптом: ${overview.detected_symptom || "Не определён"}`,
        `- Ресурс ошибки: ${overview.lock_resource || "Не определён"}`,
        `- Количество событий-доказательств: ${overview.evidence_count ?? 0}`,
        ""
    );

    lines.push("## 5. Хронология событий");

    const before = Array.isArray(timeline.before) ? timeline.before : [];
    const after = Array.isArray(timeline.after) ? timeline.after : [];

    lines.push(`### До ошибки (${before.length} событий)`, "");

    before.forEach(event => addEvent(event));

    lines.push("### Центральное исключение", "");
    addEvent(timeline.error, true);

    lines.push(`### После ошибки (${after.length} событий)`, "");

    after.forEach(event => addEvent(event));

    const relatedEvents = current.related_events || [];

    lines.push(
        `## 6. События других потоков (${relatedEvents.length})`,
        ""
    );

    if (relatedEvents.length) {
        relatedEvents.forEach(event => addEvent(event, true));
    } else {
        lines.push("События других потоков не обнаружены.", "");
    }

    function addFindingGroup(title, findings) {
        lines.push(`## ${title}`, "");

        if (!findings.length) {
            lines.push("Не обнаружено.", "");
            return;
        }

        for (const finding of findings) {
            const events = finding.events || [];

            lines.push(
                `### ${finding.title || finding.code || finding.event_type || "Признак"}`,
                `- Код: ${finding.code || "Не указан"}`,
                `- Категория признака: ${finding.confidence || "Не указана"}`,
                `- Количество событий: ${finding.count ?? events.length}`,
                "",
                "**События-доказательства:**"
            );

            if (!events.length) {
                lines.push("- События отсутствуют.");
            }

            for (const event of events) {
                const description = event.description || "";

                const details = description
                    ? description
                    : event.sql
                        ? `SQL (${event.sql_type || "тип неизвестен"}): ${event.sql}`
                        : "Описание отсутствует.";

                lines.push(
                    `- #${event.index ?? "?"} — ` +
                    `${event.event_type || "OTHER"}, ` +
                    `${event.timestamp || "время неизвестно"}: ` +
                    details
                );
            }

            lines.push("");
        }
    }

    addFindingGroup(
        "7. Диагностические признаки",
        current.findings || []
    );

    addFindingGroup(
        "8. Связанные диагностические признаки",
        current.related_findings || []
    );

    lines.push("## 9. Что проверить", "");

    const checks = current.next_checks || [];

    if (checks.length) {
        checks.forEach(check => lines.push(`- ${check}`));
    } else {
        lines.push("Рекомендации отсутствуют.");
    }

    lines.push(
        "",
        "---",
        "",
        "Отчёт сформирован автоматически с помощью 1C Log Detective."
    );

    return lines.join("\n");
}


function renderIncidentSelector() {
    const section = document.getElementById("incident-selector");
    const select = document.getElementById("incident-select");
    const position = document.getElementById("incident-position");
    const counter = document.getElementById("incident-count");

    if (counter) {
        counter.textContent = String(incidents.length);
    }

    if (incidents.length <= 1) {
        section.hidden = true;
        return;
    }

    section.hidden = false;
    clear(select);

    incidents.forEach((incident, index) => {
        const info = incident.incident || {};
        const option = document.createElement("option");

        const timestamp = info.timestamp || "Время неизвестно";
        const category = info.exception_category || "Исключение";
        const description = info.description || "";

        option.value = String(index);
        option.textContent =
            `${index + 1}. ${timestamp} — ${category}` +
            (description ? ` — ${description.slice(0, 70)}` : "");

        select.append(option);
    });

    select.value = String(currentIncidentIndex);
    position.textContent =
        `Инцидент ${currentIncidentIndex + 1} из ${incidents.length}`;
}

function node(tag, className, text) {
    const item = document.createElement(tag);
    if (className) item.className = className;
    if (text !== undefined && text !== null) item.textContent = String(text);
    return item;
}

function clear(element) {
    element.replaceChildren();
}

function renderEvent(event, isError = false) {
    const eventType = String(event.event_type || "").toUpperCase();

    const cardClass = isError
        ? "event error-event"
        : eventType === "TTIMEOUT"
            ? "event timeout-event"
            : "event";

    const card = node("article", cardClass);
    const header = node("div", "event-header");
    const typeBadge = node("span", "event-type", event.event_type || "EVENT");
    typeBadge.dataset.type = String(event.event_type || "EVENT").toUpperCase();

    header.append(
        typeBadge,
        node("span", "timestamp", event.timestamp || "Время не указано")
    );
    card.append(header);

    if (event.description) {
        card.append(node("div", "description", event.description));
    }
    else if (eventType === "SDBL" || eventType === "DBV8DBENG") {
        const sqlSummary = [];

        if (event.sql_type) {
            sqlSummary.push(`Тип SQL: ${event.sql_type}`);
        }

        if (Array.isArray(event.sql_tables) && event.sql_tables.length) {
            sqlSummary.push(`Таблицы: ${event.sql_tables.join(", ")}`);
        }

        if (event.rows !== undefined && event.rows !== null) {
            sqlSummary.push(`Возвращено строк: ${event.rows}`);
        }

        if (event.rows_affected !== undefined && event.rows_affected !== null) {
            sqlSummary.push(`Затронуто строк: ${event.rows_affected}`);
        }

        if (sqlSummary.length) {
            card.append(node("div", "description", sqlSummary.join(" · ")));
        }
    }

    const meta = [
        event.user ? "Пользователь: " + event.user : "",
        event.process ? "Процесс: " + event.process : "",
        event.thread ? "Поток: " + event.thread : "",
        event.context ? "Контекст: " + event.context : ""
    ].filter(Boolean);

    if (meta.length) card.append(node("div", "meta", meta.join(" · ")));

    if (event.raw_text) {
        const rawDetails = document.createElement("details");
        rawDetails.className = "raw-event";

        rawDetails.append(
            node("summary", "", "Исходная строка журнала (RAW)")
        );

        rawDetails.append(
            node("pre", "", event.raw_text)
        );

        card.append(rawDetails);
    }
    const excluded = new Set([
        "index", "timestamp", "event_type", "level", "description",
        "raw_text", "user", "process", "thread", "context",
        "user_relation", "is_error"
    ]);
    const extra = {};
    for (const [key, value] of Object.entries(event)) {
        if (!excluded.has(key) && value !== null && value !== "" &&
            !(Array.isArray(value) && value.length === 0) &&
            !(typeof value === "object" && !Array.isArray(value) &&
              Object.keys(value).length === 0)) {
            extra[key] = value;
        }
    }

    if (Object.keys(extra).length) {
        const details = document.createElement("details");
        details.append(node("summary", "", "Подробности события"));
        const pre = node("pre", "", JSON.stringify(extra, null, 2));
        details.append(pre);
        card.append(details);
    }

    if (event.index !== undefined && event.index !== null) {
        card.dataset.eventIndex = String(event.index);
    }

    return card;
}

function renderEvents(targetId, events) {
    const target = document.getElementById(targetId);
    clear(target);

    if (!events.length) {
        target.append(node("div", "empty", "Событий нет."));
        return;
    }

    if (targetId === "related-events") {
        target.append(
            node(
                "div",
                "empty",
                "Контекстные совпадения: пользователь и процесс совпадают, " +
                "но причинная связь с исключением не подтверждена."
            )
        );
    }

    for (const event of events) {
        const card = renderEvent(event);

        if (targetId === "related-events") {
            card.append(
                node(
                    "div",
                    "meta",
                    "Основание: совпадают пользователь и процесс; " +
                    "поток отличается от потока исключения."
                )
            );
        }

        target.append(card);
    }
}

function renderEventFilterCounts() {
    const select = document.getElementById("event-filter");
    const chips = document.getElementById("event-filter-chips");
    const currentData = getCurrentData();

    const events = [
        ...(currentData.timeline.before || []),
        ...(currentData.timeline.error ? [currentData.timeline.error] : []),
        ...(currentData.timeline.after || []),
        ...(currentData.related_events || [])
    ];

    // Исключаем дубликаты событий по индексу.
    const uniqueEvents = new Map();

    for (const event of events) {
        const key = event.index ?? event;
        uniqueEvents.set(key, event);
    }

    const counts = new Map();

    for (const event of uniqueEvents.values()) {
        const type = event.event_type || "EVENT";
        counts.set(type, (counts.get(type) || 0) + 1);
    }

    const selected = select.value;
    const types = [...counts.keys()].sort();

    select.replaceChildren();

    const allOption = document.createElement("option");
    allOption.value = "ALL";
    allOption.textContent = `Все типы событий (${uniqueEvents.size})`;
    select.append(allOption);

    for (const type of types) {
        const option = document.createElement("option");
        option.value = type;
        option.textContent = `${type} (${counts.get(type)})`;
        select.append(option);
    }

    select.value = counts.has(selected) ? selected : "ALL";

    // Создаём визуальные кнопки типов событий.
    if (chips) {
        chips.replaceChildren();

        const buttons = [
            {
                value: "ALL",
                label: "Все",
                count: uniqueEvents.size
            },
            ...types.map(type => ({
                value: type,
                label: type,
                count: counts.get(type)
            }))
        ];

        for (const item of buttons) {
            const button = document.createElement("button");
            button.type = "button";
            button.className = "event-filter-chip";
            button.dataset.value = item.value;
            button.setAttribute(
                "aria-pressed",
                String(select.value === item.value)
            );

            button.append(
                document.createTextNode(item.label + " ")
            );

            const count = document.createElement("span");
            count.className = "event-filter-chip-count";
            count.textContent = item.count;
            button.append(count);

            button.addEventListener("click", () => {
                select.value = item.value;
                renderTimeline();
            });

            chips.append(button);
        }
    }
}

function renderUserFilterOptions(events) {
    const select = document.getElementById("user-filter");
    const selected = select.value;

    const users = [...new Set(
        events
            .map(event => (event.user || "").trim())
            .filter(Boolean)
    )].sort((a, b) => a.localeCompare(b, "ru"));

    select.replaceChildren();

    const allOption = document.createElement("option");
    allOption.value = "ALL";
    allOption.textContent = "Все пользователи";
    select.append(allOption);

    for (const user of users) {
        const option = document.createElement("option");
        option.value = user;
        option.textContent = user;
        select.append(option);
    }

    select.value = users.includes(selected) ? selected : "ALL";
}

function matches(event) {
    const type = document.getElementById("event-filter").value;
    const user = document.getElementById("user-filter").value;
    const query = document.getElementById("search").value.trim().toLowerCase();
    const onlyProblems = document.getElementById("only-problems").checked;

    if (type !== "ALL" && event.event_type !== type) return false;
    if (user !== "ALL" && (event.user || "").trim() !== user) return false;

    if (
        onlyProblems &&
        event.event_type !== "EXCP" &&
        event.level !== "WARNING"
    ) {
        return false;
    }

    if (query && !JSON.stringify(event).toLowerCase().includes(query)) return false;
    return true;
}

function renderTimelineScale(events, relatedEvents = []) {
    const target = document.getElementById("timeline-scale");
    clear(target);

    if (!events.length) {
        target.append(node("div", "empty", "Нет событий для отображения."));
        return;
    }

    function getTimeValue(value) {
        if (!value) return null;

        const match = String(value).match(
            /^(\d+):(\d{2})(?:\.(\d+))?/
        );

        if (!match) return null;

        const minutes = Number(match[1]);
        const seconds = Number(match[2]);
        const fraction = match[3] || "0";

        return (
            minutes * 60000 +
            seconds * 1000 +
            Number("0." + fraction) * 1000
        );
    }

    function getEventLabel(type) {
        const labels = {
            CALL: "CALL",
            SDBL: "SDBL",
            DBV8DBEng: "DB ENGINE",
            TLOCK: "TLOCK",
            TTIMEOUT: "TIMEOUT",
            EXCP: "EXCP"
        };

        return labels[type] || type || "EVENT";
    }

    
function getTimelineTooltip(event, isRelated) {
    const lines = [];
    const type = String(event.event_type || "EVENT").toUpperCase();

    lines.push(getEventLabel(type));
    lines.push(event.timestamp || "Время неизвестно");

    const add = (label, value) => {
        if (value === undefined || value === null || value === "") {
            return;
        }

        if (Array.isArray(value)) {
            value = value.join(", ");
        } else if (typeof value === "object") {
            return;
        }

        value = String(value).replace(/\s+/g, " ").trim();

        if (!value) {
            return;
        }

        if (value.length > 120) {
            value = value.slice(0, 117) + "...";
        }

        lines.push(`${label}: ${value}`);
    };

    if (type === "SDBL" || type === "DBV8DBEng") {
        add("SQL", event.sql_type);
        add("Таблицы", event.sql_tables);
        add("Возвращено строк", event.rows);
        add("Затронуто строк", event.rows_affected);

        if (event.sql) {
            add("Запрос", event.sql);
        }
    }

    else if (type === "EXCP") {
        add("Ошибка", event.exception_category);
        add("Ресурс", event.exception_resource);
        add("Детали", event.exception_detail);
    }

    else if (type === "TTIMEOUT") {
        add("Соединение", event.connection);

        add(
            "Ожидание",
            event.waited ??
            event.wait_time ??
            event.duration
        );

        add(
            "Ожидающие соединения",
            event.waitconnections
        );

        add("Описание", event.description);
    }

    else if (type === "TLOCK") {
        const lock = event.lock || {};
        const firstLock =
            Array.isArray(lock.locks) && lock.locks.length
                ? lock.locks[0]
                : lock;

        add("База", lock.database);
        add("Регион", firstLock.region || lock.regions);
        add("Режим", firstLock.lock_mode || lock.lock_mode);

        const fields =
            firstLock.resource_fields || lock.resource_fields || {};

        for (const [key, value] of Object.entries(fields)) {
            add(key, value);
        }
    }

    else {
        add("Описание", event.description);
    }

    if (isRelated) {
        lines.push("Связанный поток");
    }

    return lines.join("\n");
}

    const prepared = events.map((event, index) => ({
        event,
        time: getTimeValue(event.timestamp),
        originalIndex: index
    }));

    const knownTimes = prepared
        .map(item => item.time)
        .filter(value => value !== null);

    const minTime = knownTimes.length
        ? Math.min(...knownTimes)
        : 0;

    const maxTime = knownTimes.length
        ? Math.max(...knownTimes)
        : 0;

    const duration = maxTime - minTime;

    const baseWidth = 600;
    const minGap = 48;
    const maxGap = 90;
    const sidePadding = 50;

    const positions = [];
    let previousNatural = null;
    let previousPosition = null;

    prepared.forEach((item, index) => {
        let naturalPosition;

        if (item.time !== null && duration > 0) {
            naturalPosition =
                sidePadding +
                ((item.time - minTime) / duration) * baseWidth;
        } else {
            naturalPosition =
                sidePadding +
                (
                    prepared.length > 1
                        ? index / (prepared.length - 1)
                        : 0.5
                ) * baseWidth;
        }

        let position = naturalPosition;

        if (previousPosition !== null) {
            const naturalGap = Math.max(
                0,
                naturalPosition - previousNatural
            );

            position =
                previousPosition +
                Math.min(maxGap, Math.max(minGap, naturalGap));
        }

        positions.push(position);

        previousNatural = naturalPosition;
        previousPosition = position;
    });

    const trackWidth = Math.max(
        baseWidth + sidePadding * 2,
        positions[positions.length - 1] + sidePadding
    );

    const relatedIndexes = new Set(
        relatedEvents.map(event => String(event.index))
    );

    const scale = node("div", "timeline-track");
    scale.style.width = `${trackWidth}px`;
    scale.style.minWidth = `${trackWidth}px`;

    const axis = node("div", "timeline-axis");
    scale.append(axis);

    const firstTimestamp = prepared[0].event.timestamp || "";
    const lastTimestamp =
        prepared[prepared.length - 1].event.timestamp || "";

    scale.append(
        node(
            "span",
            "timeline-edge timeline-start",
            String(firstTimestamp).split("-", 1)[0]
        ),
        node(
            "span",
            "timeline-edge timeline-end",
            String(lastTimestamp).split("-", 1)[0]
        )
    );

    prepared.forEach((item, index) => {
        const event = item.event;
        const isRelated = relatedIndexes.has(String(event.index));
        const label = getEventLabel(event.event_type);

        const point = node(
            "button",
            isRelated
                ? "timeline-point related-point"
                : "timeline-point"
        );

        point.type = "button";
        point.style.left = `${positions[index]}px`;

        // Чередуем строки подписей, чтобы длинные названия
        // не накладывались друг на друга.
        point.style.setProperty(
            "--label-top",
            index % 2 === 0 ? "23px" : "43px"
        );

        point.dataset.type = event.event_type || "EVENT";

       point.title = getTimelineTooltip(event, isRelated);

        point.setAttribute(
            "aria-label",
            `Открыть событие ${label} ${event.timestamp || ""}`
        );

        point.append(
            node("span", "timeline-point-label", label)
        );

        point.addEventListener("click", () => {
            jumpToTimelineEvent(event.index);
        });

        scale.append(point);
    });

    target.append(scale);
}

function renderTimeline() {
    renderEventFilterCounts();

    const currentData = getCurrentData();
    const relatedEvents = currentData.related_events || [];

    const allEvents = [
        ...(currentData.timeline.before || []),
        ...(currentData.timeline.error ? [currentData.timeline.error] : []),
        ...(currentData.timeline.after || []),
        ...relatedEvents
    ];

    renderUserFilterOptions(allEvents);

    const before = (currentData.timeline.before || []).filter(matches);
    const after = (currentData.timeline.after || []).filter(matches);
    const error = currentData.timeline.error;

    const filteredRelatedEvents = relatedEvents.filter(matches);

    renderEvents("before", before);
    renderEvents("after", after);
    renderEvents("related-events", filteredRelatedEvents);

    const includeRelated = document.getElementById(
        "include-related-sessions"
    ).checked;

    const timelineEvents = [
        ...before,
        ...(error && matches(error) ? [error] : []),
        ...after,
        ...(includeRelated ? filteredRelatedEvents : [])
    ].sort((a, b) => Number(a.index) - Number(b.index));

    renderTimelineScale(timelineEvents, filteredRelatedEvents);
}

function jumpToTimelineEvent(index) {
    if (index === undefined || index === null) {
        return;
    }

    // Сбрасываем фильтры, чтобы целевое событие обязательно было видно.
    document.getElementById("event-filter").value = "ALL";
    document.getElementById("user-filter").value = "ALL";
    document.getElementById("search").value = "";
    document.getElementById("only-problems").checked = false;

    const isRelatedEvent = (getCurrentData().related_events || []).some(
        event => String(event.index) === String(index)
    );

    document.getElementById("include-related-sessions").checked =
        isRelatedEvent;

    renderTimeline();

    const eventIndex = String(index);
    const containers = ["before", "after", "related-events"];
    let targetEvent = null;

    for (const containerId of containers) {
        const container = document.getElementById(containerId);

        targetEvent = Array.from(
            container.querySelectorAll("[data-event-index]")
        ).find(event => event.dataset.eventIndex === eventIndex);

        if (targetEvent) {
            break;
        }
    }

    if (!targetEvent) {
        return;
    }

    // Автоматически раскрываем исходную строку журнала.
    const rawDetails = targetEvent.querySelector("details.raw-event");

    if (rawDetails) {
        rawDetails.open = true;
    }

    // Если RAW есть — прокручиваем непосредственно к нему.
    const scrollTarget = rawDetails || targetEvent;

    scrollTarget.scrollIntoView({
        behavior: "smooth",
        block: "center"
    });

    targetEvent.classList.add("event-highlight");

    window.setTimeout(() => {
        targetEvent.classList.remove("event-highlight");
    }, 2500);
}

function createFindingEventLink(event) {
    const label = [
        event.event_type || "EVENT",
        event.timestamp || "Время не указано",
        event.index !== undefined && event.index !== null
            ? "#" + event.index
            : "#?"
    ].join(" · ");

    const button = node("button", "finding-event-link", label);
    button.type = "button";
    button.addEventListener("click", () => {
        jumpToTimelineEvent(event.index);
    });

    return button;
}

function renderFindings() {
    const target = document.getElementById("findings");
    clear(target);

    const findings = getCurrentData().findings || [];

    if (!findings.length) {
        target.append(node("div", "empty", "Диагностические признаки отсутствуют."));
        return;
    }

    for (const finding of findings) {
        const card = node("div", "finding");
        const heading = node("div", "finding-summary");

        heading.append(
            node("strong", "", finding.title || finding.code || "Признак"),
            node(
                "span",
                "finding-count",
                "Количество: " + (finding.count ?? 0) +
                (finding.confidence ? " · Категория: " + finding.confidence : "")
            )
        );

        card.append(heading);

        const events = Array.isArray(finding.events)
            ? finding.events
            : [];

        if (events.length) {
            const details = document.createElement("details");
            details.className = "finding-events";
            details.append(
                node("summary", "", "События признака (" + events.length + ")")
            );

            for (const event of events) {
                details.append(createFindingEventLink(event));
            }

            card.append(details);
        } else {
            card.append(
                node("div", "empty", "События для этого признака не представлены.")
            );
        }

        target.append(card);
    }
}

function renderRelatedFindings() {
    const target = document.getElementById("related-findings");
    clear(target);

    const findings = getCurrentData().related_findings || [];

    if (!findings.length) {
        target.append(node("div", "empty", "Связанные группы не обнаружены."));
        return;
    }

    for (const finding of findings) {
        const card = node("div", "finding");
        const heading = node("div", "finding-summary");

        heading.append(
            node("strong", "", finding.event_type || "События"),
            node(
                "span",
                "finding-count",
                "Количество: " + (finding.count ?? 0)
            )
        );

        card.append(heading);

        const events = Array.isArray(finding.events)
            ? finding.events
            : [];

        if (events.length) {
            const details = document.createElement("details");
            details.className = "finding-events";
            details.append(
                node("summary", "", "Перейти к событиям (" + events.length + ")")
            );

            for (const event of events) {
                details.append(createFindingEventLink(event));
            }

            card.append(details);
        }

        target.append(card);
    }
}

function renderNextChecks() {
    const target = document.getElementById("next-checks");
    clear(target);

    const checks = getCurrentData().next_checks || [];

    if (!checks.length) {
        target.append(
            node("li", "empty", "Рекомендации отсутствуют.")
        );
        return;
    }

    for (const check of checks) {
        target.append(node("li", "", check));
    }
}

function renderIncidentSummary() {
    const target = document.getElementById("incident-summary");
    clear(target);

    const currentData = getCurrentData();
    const overview = currentData.overview;
    const incident = currentData.incident || {};
    const session = incident.background_session;

    if (!overview) {
        target.append(
            node("div", "empty", "Сводка инцидента недоступна.")
        );
        return;
    }

    const eventCounts = overview.event_counts || {};

    const excpCount = eventCounts.EXCP || 0;
    const tlockCount = eventCounts.TLOCK || 0;
    const timeoutCount = eventCounts.TTIMEOUT || 0;

    const layout = node("div", "incident-hero-layout");

    // Основная карточка инцидента.
    const card = node("section", "incident-hero-card");

    card.append(
        node("div", "incident-hero-eyebrow", "INCIDENT DETECTED")
    );

    const title =
        overview.detected_symptom ||
        incident.exception_category ||
        "Обнаружено исключение 1С";

    card.append(node("h2", "incident-hero-title", title));

    const period = overview.period || {};
    const periodText = period.start
        ? period.start + (period.end ? " — " + period.end : "")
        : "Не определён";

    const users = (overview.users || []).join(", ");
    const objects = (overview.objects || []).join(", ");

    const details = node("div", "incident-hero-details");

    function addDetail(label, value) {
        const item = node("div", "incident-hero-detail");
        item.append(node("div", "overview-label", label));
        item.append(
            node("div", "overview-value", value || "Не определено")
        );
        details.append(item);
    }

    addDetail("Период", periodText);
    addDetail("Пользователь", users);
    addDetail("Объект", objects);

    card.append(details);

    const cause = node("div", "incident-hero-cause");
    cause.append(
        node("div", "overview-label", "Вероятная причина")
    );
    cause.append(
        node(
            "div",
            "overview-value",
            overview.probable_cause || "Причина не установлена."
        )
    );
    card.append(cause);

    const footer = node("div", "incident-hero-footer");

    const confidence = node("div", "incident-hero-confidence");
    confidence.append(node("div", "overview-label", "Уверенность"));
    confidence.append(
        node(
            "div",
            "overview-value",
            overview.confidence || "Недостаточно данных"
        )
    );
    footer.append(confidence);

    const evidence = node("div", "incident-hero-evidence");
    evidence.append(
        node(
            "strong",
            "",
            overview.evidence_count ?? 0
        )
    );
    evidence.append(node("span", "", "подтверждающих событий"));
    footer.append(evidence);

    card.append(footer);

    if (overview.lock_resource) {
        const resource = node("div", "incident-hero-resource");
        resource.append(
            node("span", "overview-label", "Ресурс блокировки")
        );
        resource.append(
            node("span", "overview-value", overview.lock_resource)
        );
        card.append(resource);
    }

    // KPI справа от карточки.
    const kpis = node("div", "incident-kpis");

    function addKpi(label, value, description) {
        const item = node("div", "incident-kpi");
        item.append(node("div", "incident-kpi-label", label));
        item.append(
            node("div", "incident-kpi-value", String(value))
        );
        item.append(
            node("div", "incident-kpi-description", description)
        );
        kpis.append(item);
    }

    addKpi("EXCP", excpCount, "Исключения");
    addKpi("TTIMEOUT", timeoutCount, "Тайм-ауты ожидания");
    addKpi("TLOCK", tlockCount, "События блокировок");

    layout.append(card);
    layout.append(kpis);
    target.append(layout);

    // Дополнительные сведения о фоновой сессии.
    if (session) {
        const sessionBlock = node("div", "overview-cause");

        sessionBlock.append(
            node("div", "overview-label", "Фоновый сеанс")
        );

        const sessionGrid = node("div", "overview-grid");

        function addSessionItem(label, value) {
            const item = node("div", "overview-item");
            item.append(node("div", "overview-label", label));
            item.append(
                node("div", "overview-value", value || "Не определено")
            );
            sessionGrid.append(item);
        }

        addSessionItem("Номер задания", session.nmb);
        addSessionItem("Приложение", session.appl);
        addSessionItem("ID сеанса", session.id);
        addSessionItem("Начало", session.start_timestamp);
        addSessionItem("Завершение", session.finish_timestamp);

        sessionBlock.append(sessionGrid);
        target.append(sessionBlock);
    }
}

function addItemToTarget(target, label, value) {
    const item = node("div", "overview-item");
    item.style.marginTop = "12px";
    item.append(node("div", "overview-label", label));
    item.append(node("div", "overview-value", value));
    target.append(item);
}

function render() {
    const currentData = getCurrentData();

    if (currentData.error) {
        const status = document.getElementById("status");
        status.hidden = false;
        status.textContent = currentData.error;
    }

    const summary = document.getElementById("summary");
    clear(summary);

    const metrics = currentData.summary || {};

    const labels = [
        ["events_count", "Событий в цепочке"],
        ["before_count", "До исключения"],
        ["after_count", "После исключения"],
        ["related_events_count", "Другие потоки"],
        ["findings_count", "Признаки"]
    ];

    for (const [key, label] of labels) {
        const metric = node("div", "metric");
        metric.append(node("strong", "", metrics[key] ?? 0));
        metric.append(node("span", "", label));
        summary.append(metric);
    }

    const incident = document.getElementById("incident");
    clear(incident);

    const info = currentData.incident;

    if (info) {
        incident.append(node("h3", "", "Суть инцидента"));

        if (info.timestamp) {
            incident.append(
                node("div", "meta", "Время: " + info.timestamp)
            );
        }

        if (info.description) {
            incident.append(
                node("div", "description", info.description)
            );
        }

        if (info.exception_category) {
            incident.append(
                node("div", "meta", "Категория: " + info.exception_category)
            );
        }

        if (info.exception_detail) {
            incident.append(
                node("div", "meta", "Подробности: " + info.exception_detail)
            );
        }

        if (info.exception_resource) {
            incident.append(
                node("div", "meta", "Ресурс: " + info.exception_resource)
            );
        }

        if (info.exception_guid) {
            incident.append(
                node("div", "meta", "GUID: " + info.exception_guid)
            );
        }

        incident.append(node("h3", "", "Контекст инцидента"));

        const rows = [
            ["Пользователь", info.user],
            ["Процесс", info.process],
            ["Поток", info.thread],
            ["Контекст", info.context],
            ["Индекс события", info.error_index]
        ];

        for (const [label, value] of rows) {
            if (value !== undefined && value !== null && value !== "") {
                incident.append(
                    node("div", "meta", label + ": " + value)
                );
            }
        }
    }

    const errorTarget = document.getElementById("error-event");
    clear(errorTarget);

    if (currentData.timeline.error) {
        errorTarget.append(renderEvent(currentData.timeline.error, true));
    } else {
        errorTarget.append(
            node("div", "empty", "Центральное исключение отсутствует.")
        );
    }

    renderIncidentSummary();
    renderTimeline();
    renderFindings();
    renderRelatedFindings();
    renderNextChecks();
    renderIncidentSelector();
}

// Сбрасываем восстановленные браузером значения фильтров.
document.getElementById("search").value = "";
document.getElementById("event-filter").value = "ALL";
document.getElementById("user-filter").value = "ALL";
document.getElementById("only-problems").checked = false;
document.getElementById("include-related-sessions").checked = false;

document.getElementById("search").addEventListener("input", renderTimeline);
document.getElementById("event-filter").addEventListener("change", renderTimeline);
document.getElementById("user-filter").addEventListener("change", renderTimeline);
document.getElementById("only-problems").addEventListener("change", renderTimeline);
document.getElementById("include-related-sessions").addEventListener("change", renderTimeline);

document.getElementById("incident-select").addEventListener("change", event => {
    currentIncidentIndex = Number(event.target.value);

    document.getElementById("search").value = "";
    document.getElementById("event-filter").value = "ALL";
    document.getElementById("user-filter").value = "ALL";
    document.getElementById("only-problems").checked = false;
    document.getElementById("include-related-sessions").checked = false;

    render();
});

document.getElementById("export-bug-report").addEventListener("click", () => {
    const markdown = buildBugReportMarkdown();

    const blob = new Blob(
        [markdown],
        { type: "text/markdown;charset=utf-8" }
    );

    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");

    link.href = url;
    link.download = `bug-report-${currentIncidentIndex + 1}.md`;

    document.body.append(link);
    link.click();
    link.remove();

    URL.revokeObjectURL(url);
});


// ===== Переключение темы отчёта =====
const themeButton = document.getElementById("theme-toggle");

function applyReportTheme(theme, save = false) {
    const selectedTheme = theme === "light" ? "light" : "dark";

    document.documentElement.dataset.theme = selectedTheme;

    themeButton.textContent = selectedTheme === "dark"
        ? "☀ Светлая тема"
        : "🌙 Тёмная тема";

    themeButton.setAttribute(
        "aria-pressed",
        String(selectedTheme === "light")
    );

    if (save) {
        try {
            localStorage.setItem("1c-log-detective-theme", selectedTheme);
        } catch (error) {
            // Отчёт продолжает работать, даже если браузер запрещает localStorage.
        }
    }
}

let savedTheme = "dark";

try {
    savedTheme = localStorage.getItem("1c-log-detective-theme") || "dark";
} catch (error) {
    // При недоступном localStorage используем тёмную тему.
}

applyReportTheme(savedTheme);

themeButton.addEventListener("click", () => {
    const currentTheme = document.documentElement.dataset.theme;
    applyReportTheme(currentTheme === "dark" ? "light" : "dark", true);
});

render();
</script>
</body>
</html>
"""


def generate_html_report(analysis_result: dict, output_path: str | Path) -> Path:
    """
    Создаёт автономный HTML-файл.

    Возвращает путь к созданному файлу.
    """
    report_data = build_html_report_data(analysis_result)

    json_data = json.dumps(
        report_data,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    # Не допускаем закрытия script-тега данными из журнала.
    json_data = (
        json_data.replace("&", "\\u0026")
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )

    html = HTML_TEMPLATE.replace("__REPORT_DATA__", json_data)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")

    return path

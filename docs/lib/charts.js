// political-eye: SVG chart primitives (no dependencies).
// Each chart sizes itself to its box, has a hover layer, a legend for two or
// more series, and an optional "Show as table" view. Thin marks, recessive
// axes, one y axis per chart (never two scales).
import { $, css, el, fmt, hideTip, isDark, showTip, tipRow, table } from "./ui.js";
import { L, lang } from "./i18n.js";

// A plain number on an axis, in the page's language: 0,2 / 0.2; grouped only from 10 000 up, so years stay 2018.
const axisNum = (v) => (+v).toLocaleString(lang() === "en" ? "en-US" : "pt-BR", { maximumFractionDigits: 3, useGrouping: Math.abs(+v) >= 10000 });

const NS = "http://www.w3.org/2000/svg";
export function svg(tag, attrs = {}) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) if (v != null) e.setAttribute(k, v);
  return e;
}
const text = (s, attrs) => { const t = svg("text", attrs); t.textContent = s; return t; };

// ------------------------------------------------------------ colour

export const RAMP = ["#cde2fb", "#b7d3f6", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7", "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#104281", "#0d366b"];
const RED = ["#fbd5d4", "#f6b0ae", "#ef8987", "#e66767", "#e34948", "#c73a3a", "#a52f2f"];
const hex = (s) => [1, 3, 5].map((k) => parseInt(s.slice(k, k + 2), 16));
const mix = (a, b, r) => `rgb(${hex(a).map((c, k) => Math.round(c + (hex(b)[k] - c) * r)).join(",")})`;
function ramp(list, t) {
  const f = Math.max(0, Math.min(1, t)) * (list.length - 1), i = Math.floor(f);
  return i >= list.length - 1 ? list[list.length - 1] : mix(list[i], list[i + 1], f - i);
}
/** Sequential blue, 0..1; near zero recedes toward the surface in both modes. */
export const seq = (t) => ramp(isDark() ? [...RAMP].reverse().slice(0, 11) : RAMP, t);
/** Diverging blue (negative) <-> red (positive) around a grey midpoint, t in -1..1. */
export function div(t) {
  const mid = css("--mid");
  const toward = t < 0 ? RAMP[8] : RED[4];
  return mix(mid.length === 7 ? mid : "#f0efec", toward, Math.min(1, Math.abs(t)));
}
export const slot = (i) => css(`--s${i}`);

// ------------------------------------------------------------ scales

export function niceTicks(lo, hi, n = 4) {
  if (!(hi > lo)) return [lo];
  const step0 = (hi - lo) / n, mag = 10 ** Math.floor(Math.log10(step0)), err = step0 / mag;
  const step = (err >= 7.5 ? 10 : err >= 3.5 ? 5 : err >= 1.5 ? 2 : 1) * mag;
  const out = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(+v.toFixed(10));
  return out;
}
/** Ticks from 0 whose last one is at or above hi (so the tallest mark stays inside the plot). */
function upTo(hi, n = 4) {
  const t = niceTicks(0, hi, n);
  if (t.length > 1 && t[t.length - 1] < hi) t.push(+(t[t.length - 1] + t[1] - t[0]).toFixed(10));
  return t;
}
/** Ticks for a log10 axis (lo, hi in log10 units): decades, plus 2× and 5× when the range spans under three decades. */
function logTicks(lo, hi) {
  const out = [];
  for (let k = Math.floor(lo); k <= Math.ceil(hi); k++) for (const m of hi - lo < 3 ? [1, 2, 5] : [1]) { const v = k + Math.log10(m); if (v >= lo - 1e-9 && v <= hi + 1e-9) out.push(v); }
  return out.length >= 2 ? out : niceTicks(lo, hi, 4);
}
const linear = (d0, d1, r0, r1) => (v) => (d1 === d0 ? (r0 + r1) / 2 : r0 + ((v - d0) / (d1 - d0)) * (r1 - r0));
export const monthIndex = (m) => +m.slice(0, 4) * 12 + (+m.slice(5, 7) - 1);
export const monthLabel = (i) => `${Math.floor(i / 12)}-${String((i % 12) + 1).padStart(2, "0")}`;
const dayMs = (d) => Date.parse(`${d}T00:00:00Z`);

function xAccessor(type) {
  if (type === "month") return { val: monthIndex, label: (v) => monthLabel(v), ticks: (lo, hi, w) => {
    const years = Math.max(1, Math.round((hi - lo) / 12 / Math.max(1, Math.floor(w / 70))));
    const out = []; for (let y = Math.ceil(lo / 12); y * 12 <= hi; y += years) out.push(y * 12); return out;
  }, tick: (v) => String(Math.floor(v / 12)) };
  if (type === "day") return { val: dayMs, label: (v) => new Date(v).toISOString().slice(0, 10), ticks: (lo, hi, w) => {
    const n = Math.max(2, Math.floor(w / 90)), out = [], d = new Date(lo);
    d.setUTCDate(1); const span = (hi - lo) / 864e5 / 30.4; const every = Math.max(1, Math.ceil(span / n));
    for (; d.getTime() <= hi; d.setUTCMonth(d.getUTCMonth() + every)) if (d.getTime() >= lo) out.push(d.getTime());
    return out;
  }, tick: (v) => new Date(v).toISOString().slice(0, 7) };
  return { val: (v) => +v, label: axisNum, ticks: (lo, hi, w) => niceTicks(lo, hi, Math.max(2, Math.floor(w / 80))), tick: axisNum };
}

/** Left margin that fits the widest y label (10px system sans: ~6px a character). */
const marginFor = (labels, min = 36) => Math.max(min, Math.max(...labels.map((l) => String(l).length)) * 6 + 12);

function frame(box, height) {
  const w = Math.max(240, box.clientWidth || 600);
  const s = svg("svg", { width: w, height, role: "img" });
  return { w, s };
}

function addTableToggle(box, tbl) {
  if (!tbl) return;
  const holder = el("div", { hidden: true });
  const btn = el("button", { className: "toggle", type: "button", textContent: L("Mostrar como tabela", "Show as table"), "aria-expanded": "false" });
  btn.addEventListener("click", () => {
    holder.hidden = !holder.hidden;
    btn.textContent = holder.hidden ? L("Mostrar como tabela", "Show as table") : L("Ocultar tabela", "Hide table");
    btn.setAttribute("aria-expanded", String(!holder.hidden));
    if (!holder.hidden && !holder.firstChild) table(holder, tbl.rows, tbl.cols, { pageSize: 15, name: tbl.name || "chart" });
  });
  box.append(btn, holder);
}

export function legend(box, items) {
  if (items.length < 2) return;
  box.append(el("div", { className: "legend" }, ...items.map((it) => el("span", {},
    el("i", { className: it.shape || "", style: it.color ? `background:${it.color}` : "" }), it.label))));
}

// ------------------------------------------------------------ line

/**
 * line(box, {series: [{name, color, points: [[x, y], ...]}], x: "month"|"day"|"num", y: {format, min, max, label},
 *            height, bands: [{from, to, label}], marks: [{x, label}], ref: [{y, label}], table, title})
 * Gaps (y == null) break the line. Crosshair + tooltip with every series at the nearest x.
 */
export function line(box, o) {
  box.replaceChildren();
  const H = o.height || 240, mr = 12, mt = 12, mb = 26;
  const X = xAccessor(o.x || "num"), yf = o.y?.format || ((v) => fmt(v, 2));
  const pts = o.series.flatMap((s) => [...s.points.filter((p) => p[1] != null),
    ...(s.band || []).filter((p) => p[1] != null).flatMap((p) => [[p[0], p[1]], [p[0], p[2]]])]);
  let ml = 48;
  if (!pts.length) { box.append(el("p", { className: "empty", textContent: o.empty || L("Sem dados.", "No data.") })); return; }
  const xs = pts.map((p) => X.val(p[0])), ys = pts.map((p) => +p[1]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  let y0 = o.y?.min ?? Math.min(0, ...ys), y1 = o.y?.max ?? Math.max(...ys);
  if (y1 === y0) y1 = y0 + 1;
  const yt = niceTicks(y0, y1, 4);
  if (o.y?.max == null) y1 = Math.max(y1, yt[yt.length - 1]);
  ml = marginFor(yt.map(yf));
  const { w, s } = frame(box, H);
  const sx = linear(x0, x1, ml, w - mr);
  const sy = linear(y0, y1, H - mb, mt);
  const grid = css("--grid"), axis = css("--axis"), muted = css("--muted"), ink2 = css("--ink2");
  for (const b of o.bands || []) {
    if (X.val(b.to) <= x0 || X.val(b.from) >= x1) continue;   // a band outside the axis draws nothing, label included
    const a = sx(X.val(b.from)), c = sx(X.val(b.to));
    s.append(svg("rect", { x: Math.max(ml, a), y: mt, width: Math.max(0, Math.min(w - mr, c) - Math.max(ml, a)), height: H - mt - mb, fill: grid, opacity: 0.6 }));
    // A label that would run past the right edge is drawn from the band's right end instead.
    const over = b.label && Math.max(ml, a) + 4 + String(b.label).length * 5.8 > w - mr;
    if (b.label) s.append(text(b.label, over ? { x: Math.min(w - mr, c) - 4, y: mt + 11, "text-anchor": "end", "font-size": 10, fill: muted } : { x: Math.max(ml, a) + 4, y: mt + 11, "font-size": 10, fill: muted }));
  }
  for (const v of yt) {
    s.append(svg("line", { x1: ml, x2: w - mr, y1: sy(v), y2: sy(v), stroke: v === yt[0] && y0 === 0 ? axis : grid }));
    s.append(text(yf(v), { x: ml - 6, y: sy(v) + 4, "text-anchor": "end", "font-size": 10, fill: muted }));
  }
  for (const v of o.xTicks ? o.xTicks.map(X.val) : X.ticks(x0, x1, w - ml - mr)) s.append(text(X.tick(v), { x: sx(v), y: H - 8, "text-anchor": "middle", "font-size": 10, fill: muted }));
  for (const m of o.marks || []) {
    if (X.val(m.x) <= x0 || X.val(m.x) > x1) continue;   // a mark at or past the edge would sit on the axis
    const xv = sx(X.val(m.x));
    s.append(svg("line", { x1: xv, x2: xv, y1: mt, y2: H - mb, stroke: axis, "stroke-dasharray": "3 3" }));
    const over = m.label && xv + 3 + String(m.label).length * 5.8 > w - mr;
    if (m.label) s.append(text(m.label, { x: over ? xv - 3 : xv + 3, y: H - mb - 4, "text-anchor": over ? "end" : "start", "font-size": 10, fill: muted }));
  }
  for (const r of o.ref || []) {
    s.append(svg("line", { x1: ml, x2: w - mr, y1: sy(r.y), y2: sy(r.y), stroke: r.color || ink2, "stroke-dasharray": "4 3" }));
    if (r.label) s.append(text(r.label, { x: w - mr, y: sy(r.y) - 4, "text-anchor": "end", "font-size": 10, fill: ink2 }));
  }
  for (const se of o.series) {
    if (!se.band) continue;
    let seg = [];
    const flush = () => {
      if (seg.length > 1) {
        const top = seg.map((p) => `${sx(X.val(p[0])).toFixed(1)},${sy(+p[2]).toFixed(1)}`), bot = seg.map((p) => `${sx(X.val(p[0])).toFixed(1)},${sy(+p[1]).toFixed(1)}`).reverse();
        s.append(svg("path", { d: `M${top.join("L")}L${bot.join("L")}Z`, fill: se.color, opacity: 0.16 }));
      }
      seg = [];
    };
    for (const p of se.band) { if (p[1] == null || p[2] == null) flush(); else seg.push(p); }
    flush();
  }
  for (const se of o.series) {
    let d = "", pen = false;
    se.points.forEach((p, i) => {
      if (p[1] == null) { pen = false; return; }
      const solo = (i === 0 || se.points[i - 1][1] == null) && (i === se.points.length - 1 || se.points[i + 1]?.[1] == null);
      if (solo) s.append(svg("circle", { cx: sx(X.val(p[0])), cy: sy(+p[1]), r: 2.2, fill: se.color }));
      d += `${pen ? "L" : "M"}${sx(X.val(p[0])).toFixed(1)},${sy(+p[1]).toFixed(1)}`; pen = true;
    });
    s.append(svg("path", { d, fill: "none", stroke: se.color, "stroke-width": se.width || 2, "stroke-linejoin": "round", "stroke-linecap": "round", opacity: se.opacity ?? 1 }));
  }
  const hair = svg("line", { y1: mt, y2: H - mb, stroke: ink2, opacity: 0 });
  s.append(hair);
  const allX = [...new Set(o.series.flatMap((se) => se.points.map((p) => p[0])))].sort((a, b) => X.val(a) - X.val(b));
  const hit = svg("rect", { x: ml, y: 0, width: w - ml - mr, height: H, fill: "transparent" });
  hit.addEventListener("pointermove", (ev) => {
    const r = s.getBoundingClientRect(), px = ev.clientX - r.left;
    let best = allX[0], bd = Infinity;
    for (const xv of allX) { const d = Math.abs(sx(X.val(xv)) - px); if (d < bd) { bd = d; best = xv; } }
    hair.setAttribute("x1", sx(X.val(best))); hair.setAttribute("x2", sx(X.val(best))); hair.setAttribute("opacity", 1);
    const rows = o.series.map((se) => { const p = se.points.find((q) => q[0] === best); return tipRow(se.color, p && p[1] != null ? yf(+p[1]) : "–", se.name); });
    showTip(ev, [el("strong", { textContent: X.label(X.val(best)) }), ...(o.series.length > 8 ? rows.slice(0, 8) : rows)]);
  });
  hit.addEventListener("pointerleave", () => { hair.setAttribute("opacity", 0); hideTip(); });
  s.append(hit);
  s.setAttribute("aria-label", o.title || o.series.map((x) => x.name).join(", "));
  box.append(s);
  legend(box, o.series.filter((x) => !x.hideLegend).map((x) => ({ label: x.name, color: x.color })));
  addTableToggle(box, o.table);
}

// ------------------------------------------------------------ bars

/** bars(box, {rows: [{label, value, color?, note?, title?}], format, max, onClick, table}) - ranked horizontal bars. */
export function bars(box, o) {
  box.replaceChildren();
  if (!o.rows.length) { box.append(el("p", { className: "empty", textContent: o.empty || L("Sem dados.", "No data.") })); return; }
  const bh = o.barHeight || 18, gap = 6, lw = Math.min(o.labelWidth || 180, (box.clientWidth || 600) * 0.42), vw = 70;
  const { w, s } = frame(box, o.rows.length * (bh + gap) + 4);
  const max = o.max ?? Math.max(...o.rows.map((r) => Math.abs(r.value)), 1e-9);
  const sx = linear(0, max, 0, w - lw - vw - 8), ink = css("--ink"), ink2 = css("--ink2"), col = css("--line");
  const f = o.format || ((v) => fmt(v));
  o.rows.forEach((r, i) => {
    const y = i * (bh + gap);
    const fit = Math.floor((lw - 10) / 6.6);
    const label = r.label.length > fit ? r.label.slice(0, fit - 1) + "…" : r.label;
    s.append(text(label, { x: lw - 8, y: y + bh / 2 + 4, "text-anchor": "end", "font-size": 12, fill: ink2 }));
    const bw = Math.max(1, sx(Math.abs(r.value)));
    const rect = svg("rect", { x: lw, y, width: bw, height: bh, rx: 3, fill: r.color || col });
    s.append(rect);
    s.append(text(f(r.value), { x: lw + bw + 6, y: y + bh / 2 + 4, "font-size": 11, fill: ink }));
    const hit = svg("rect", { x: 0, y: y - gap / 2, width: w, height: bh + gap, fill: "transparent", style: o.onClick ? "cursor:pointer" : "" });
    hit.addEventListener("pointermove", (ev) => showTip(ev, [el("strong", { textContent: r.title || r.label }), el("div", { className: "row", textContent: `${f(r.value)}${r.note ? ` · ${r.note}` : ""}` })]));
    hit.addEventListener("pointerleave", hideTip);
    if (o.onClick) hit.addEventListener("click", () => o.onClick(r));
    s.append(hit);
  });
  s.setAttribute("aria-label", o.title || L("Barras ordenadas", "Ranked bars"));
  box.append(s);
  legend(box, o.legend || []);
  addTableToggle(box, o.table);
}

// ------------------------------------------------------------ stacked columns

/** stack(box, {x: [labels], series: [{name, color, values: []}], format, height, table}) - columns stacked, 2px gaps. */
export function stack(box, o) {
  box.replaceChildren();
  const mb = o.rotate ? Math.min(140, 14 + 6 * Math.max(...o.x.map((x) => String(x).length))) : 24;
  const H = (o.height || 240) + (o.rotate ? mb - 24 : 0), mr = 8, mt = 10;
  const totals = o.x.map((_, i) => o.series.reduce((a, se) => a + Math.max(0, se.values[i] || 0), 0));
  const yt = upTo(Math.max(...totals, 1e-9), 4), y1 = yt[yt.length - 1];
  const f = o.format || ((v) => fmt(v)), grid = css("--grid"), muted = css("--muted"), surface = css("--surface");
  const ml = marginFor(yt.map(f));
  const { w, s } = frame(box, H);
  const sy = linear(0, y1, H - mb, mt), n = o.x.length, band = (w - ml - mr) / n, bw = Math.max(3, Math.min(42, band * 0.7));
  for (const v of yt) {
    s.append(svg("line", { x1: ml, x2: w - mr, y1: sy(v), y2: sy(v), stroke: grid }));
    s.append(text(f(v), { x: ml - 6, y: sy(v) + 4, "text-anchor": "end", "font-size": 10, fill: muted }));
  }
  const every = o.rotate ? 1 : Math.ceil(n / Math.max(1, Math.floor((w - ml - mr) / 44)));
  o.x.forEach((lab, i) => {
    const cx = ml + band * (i + 0.5);
    if (i % every === 0) s.append(o.rotate
      ? text(String(lab), { x: cx, y: H - mb + 12, "text-anchor": "end", "font-size": 10, fill: muted, transform: `rotate(-40 ${cx} ${H - mb + 12})` })
      : text(String(lab), { x: cx, y: H - 8, "text-anchor": "middle", "font-size": 10, fill: muted }));
    let acc = 0;
    o.series.forEach((se) => {
      const v = Math.max(0, se.values[i] || 0);
      if (!v) return;
      const yTop = sy(acc + v), yBot = sy(acc);
      const r = svg("rect", { x: cx - bw / 2, y: yTop, width: bw, height: Math.max(0.5, yBot - yTop - (acc ? 2 : 0)), fill: se.color, stroke: surface, "stroke-width": 0 });
      r.addEventListener("pointermove", (ev) => showTip(ev, [el("strong", { textContent: `${lab} · ${se.name}` }),
        tipRow(se.color, f(v), "", true), el("div", { className: "row", textContent: `${totals[i] ? ((100 * v) / totals[i]).toFixed(0) : 0}% ${L("de", "of")} ${f(totals[i])}` })]));
      r.addEventListener("pointerleave", hideTip);
      s.append(r);
      acc += v;
    });
  });
  s.setAttribute("aria-label", o.title || L("Colunas empilhadas", "Stacked columns"));
  box.append(s);
  legend(box, o.series.map((x) => ({ label: x.name, color: x.color })));
  addTableToggle(box, o.table);
}

// ------------------------------------------------------------ histogram

/** histogram(box, {values, bins, domain: [lo, hi], refs: [{x, label, color}], format, tickFormat (axis only; "" hides a tick), xLabel, table}) */
export function histogram(box, o) {
  box.replaceChildren();
  const vals = o.values.filter((v) => v != null && !Number.isNaN(v));
  if (!vals.length) { box.append(el("p", { className: "empty", textContent: o.empty || L("Sem dados.", "No data.") })); return; }
  const H = o.height || 220, ml = 44, mr = 10, mb = 30;
  const [lo, hi] = o.domain || [Math.min(...vals), Math.max(...vals)], nb = o.bins || 30, step = (hi - lo) / nb;
  const counts = new Array(nb).fill(0);
  for (const v of vals) counts[Math.min(nb - 1, Math.max(0, Math.floor((v - lo) / step)))]++;
  const { w, s } = frame(box, H);
  const sx = linear(lo, hi, ml, w - mr);
  // Reference labels go in rows above the plot, a new row only when a label would overlap the one before it.
  const rows = [], placed = [...(o.refs || [])].sort((a, b) => a.x - b.x).map((r) => {
    const x = sx(r.x), end = x > w * 0.8, width = String(r.label ?? "").length * 5.8 + 6;
    const [a, b] = end ? [x - width, x] : [x, x + width];
    let row = rows.findIndex((right) => a > right);
    if (row < 0) { row = rows.length; rows.push(-Infinity); }
    rows[row] = b;
    return { r, x, end, row };
  });
  const mt = 18 + 12 * Math.max(0, rows.length - 1);
  const yt = upTo(Math.max(...counts), 4), sy = linear(0, yt[yt.length - 1], H - mb, mt);
  const f = o.format || ((v) => fmt(v, 1)), grid = css("--grid"), muted = css("--muted"), col = css("--line"), ink2 = css("--ink2");
  for (const v of yt) { s.append(svg("line", { x1: ml, x2: w - mr, y1: sy(v), y2: sy(v), stroke: grid })); s.append(text(fmt(v), { x: ml - 6, y: sy(v) + 4, "text-anchor": "end", "font-size": 10, fill: muted })); }
  for (const v of niceTicks(lo, hi, Math.max(2, Math.floor((w - ml) / 70)))) s.append(text((o.tickFormat || f)(v), { x: sx(v), y: H - 14, "text-anchor": "middle", "font-size": 10, fill: muted }));
  if (o.xLabel) s.append(text(o.xLabel, { x: (ml + w - mr) / 2, y: H - 1, "text-anchor": "middle", "font-size": 10, fill: muted }));
  counts.forEach((c, i) => {
    if (!c) return;
    const x = sx(lo + i * step) + 1, bw = Math.max(1, sx(lo + (i + 1) * step) - sx(lo + i * step) - 2);
    const r = svg("rect", { x, y: sy(c), width: bw, height: sy(0) - sy(c), rx: 2, fill: o.color ? o.color(lo + (i + 0.5) * step) : col });
    r.addEventListener("pointermove", (ev) => showTip(ev, [el("strong", { textContent: `${f(lo + i * step)} – ${f(lo + (i + 1) * step)}` }), el("div", { className: "row", textContent: `${fmt(c)} ${o.unit || L("itens", "items")}` })]));
    r.addEventListener("pointerleave", hideTip);
    s.append(r);
  });
  for (const { r, x, end, row } of placed) {
    const y = mt - 8 - 12 * row;
    s.append(svg("line", { x1: x, x2: x, y1: y + 2, y2: H - mb, stroke: r.color || ink2, "stroke-width": 1.5, "stroke-dasharray": "4 3" }));
    s.append(text(r.label, { x: x + (end ? -3 : 3), y, "text-anchor": end ? "end" : "start", "font-size": 10, fill: ink2 }));
  }
  s.setAttribute("aria-label", o.title || L("Histograma", "Histogram"));
  box.append(s);
  addTableToggle(box, o.table);
}

// ------------------------------------------------------------ scatter

/**
 * scatter(box, {points: [{x, y, label, color, r, title, rows: [...tooltip lines]}], x: {format, label, log}, y: {...},
 *               labels: n (direct-label the n points farthest from the centre), legend, onClick, table})
 */
export function scatter(box, o) {
  box.replaceChildren();
  const P = o.points.filter((p) => p.x != null && p.y != null && !Number.isNaN(+p.x) && !Number.isNaN(+p.y));
  if (!P.length) { box.append(el("p", { className: "empty", textContent: o.empty || L("Sem dados.", "No data.") })); return; }
  const H = o.height || 320, mr = 14, mt = 12, mb = 38;
  const tx = (v) => (o.x?.log ? Math.log10(Math.max(v, 1)) : +v), ty = (v) => (o.y?.log ? Math.log10(Math.max(v, 1)) : +v);
  const xs = P.map((p) => tx(p.x)), ys = P.map((p) => ty(p.y));
  const xd = [o.x?.min ?? Math.min(...xs), o.x?.max ?? Math.max(...xs)], yd = [o.y?.min ?? Math.min(...ys), o.y?.max ?? Math.max(...ys)];
  const yfmt0 = o.y?.format || ((v) => fmt(v, 2));
  const yTicks = o.y?.log ? logTicks(yd[0], yd[1]) : niceTicks(yd[0], yd[1], 4);
  const ml = marginFor(yTicks.map((v) => yfmt0(o.y?.log ? 10 ** v : v))) + (o.y?.label ? 18 : 0);
  const { w, s } = frame(box, H);
  const sx = linear(xd[0], xd[1] === xd[0] ? xd[0] + 1 : xd[1], ml, w - mr), sy = linear(yd[0], yd[1] === yd[0] ? yd[0] + 1 : yd[1], H - mb, mt);
  const grid = css("--grid"), muted = css("--muted"), surface = css("--surface"), ink2 = css("--ink2");
  const xf = o.x?.format || ((v) => fmt(v, 2)), yf = o.y?.format || ((v) => fmt(v, 2));
  const unlog = (v, log) => (log ? 10 ** v : v);
  for (const v of yTicks) { s.append(svg("line", { x1: ml, x2: w - mr, y1: sy(v), y2: sy(v), stroke: grid })); s.append(text(yf(unlog(v, o.y?.log)), { x: ml - 6, y: sy(v) + 4, "text-anchor": "end", "font-size": 10, fill: muted })); }
  for (const v of o.x?.log ? logTicks(xd[0], xd[1]) : niceTicks(xd[0], xd[1], Math.max(2, Math.floor((w - ml) / 90)))) { s.append(svg("line", { x1: sx(v), x2: sx(v), y1: mt, y2: H - mb, stroke: grid })); s.append(text(xf(unlog(v, o.x?.log)), { x: sx(v), y: H - mb + 14, "text-anchor": "middle", "font-size": 10, fill: muted })); }
  if (o.x?.label) s.append(text(o.x.label, { x: (ml + w - mr) / 2, y: H - 4, "text-anchor": "middle", "font-size": 11, fill: ink2 }));
  if (o.y?.label) s.append(text(o.y.label, { x: 12, y: (mt + H - mb) / 2, "text-anchor": "middle", "font-size": 11, fill: ink2, transform: `rotate(-90 12 ${(mt + H - mb) / 2})` }));
  if (o.diagonal) {
    const lo = Math.max(xd[0], yd[0]), hi = Math.min(xd[1], yd[1]);
    if (hi > lo) s.append(svg("line", { x1: sx(lo), y1: sy(lo), x2: sx(hi), y2: sy(hi), stroke: ink2, "stroke-dasharray": "4 3" }));
    if (o.diagonal.label) s.append(text(o.diagonal.label, { x: sx(hi) - 4, y: sy(hi) + 12, "text-anchor": "end", "font-size": 10, fill: ink2 }));
  }
  for (const r of o.refs || []) {
    if (r.y != null) { s.append(svg("line", { x1: ml, x2: w - mr, y1: sy(r.y), y2: sy(r.y), stroke: r.color || ink2, "stroke-dasharray": "3 3" })); s.append(text(r.label || "", { x: w - mr, y: sy(r.y) - 4, "text-anchor": "end", "font-size": 10, fill: r.color || ink2 })); }
    if (r.x != null) { s.append(svg("line", { x1: sx(r.x), x2: sx(r.x), y1: mt, y2: H - mb, stroke: r.color || ink2, "stroke-dasharray": "3 3" })); s.append(text(r.label || "", { x: sx(r.x) + 4, y: mt + 10, "font-size": 10, fill: r.color || ink2 })); }
  }
  const order = [...P].sort((a, b) => (a.z || 0) - (b.z || 0));
  for (const p of order) s.append(svg("circle", { cx: sx(tx(p.x)), cy: sy(ty(p.y)), r: p.r || 4, fill: p.color || css("--other"), stroke: surface, "stroke-width": 1.2, opacity: p.opacity ?? 0.9 }));
  if (o.labels) {
    const cx = (xd[0] + xd[1]) / 2, cy = (yd[0] + yd[1]) / 2;
    const far = o.labelRank ? P.filter((p) => p.label).sort(o.labelRank).slice(0, o.labels) : P.filter((p) => p.label).sort((a, b) => ((tx(b.x) - cx) / (xd[1] - xd[0] || 1)) ** 2 + ((ty(b.y) - cy) / (yd[1] - yd[0] || 1)) ** 2
      - ((tx(a.x) - cx) / (xd[1] - xd[0] || 1)) ** 2 - ((ty(a.y) - cy) / (yd[1] - yd[0] || 1)) ** 2).slice(0, o.labels);
    const placed = [];
    for (const p of far) {
      const right = sx(tx(p.x)) < w * 0.75, lx = sx(tx(p.x)) + (right ? 7 : -7), ly = sy(ty(p.y)) + 4;
      const wd = String(p.label).length * 5.6, box0 = right ? [lx, lx + wd] : [lx - wd, lx];
      if (placed.some((q) => Math.abs(q.y - ly) < 12 && q.a < box0[1] && box0[0] < q.b)) continue;
      placed.push({ y: ly, a: box0[0], b: box0[1] });
      s.append(text(p.label, { x: lx, y: ly, "text-anchor": right ? "start" : "end", "font-size": 10, fill: ink2 }));
    }
  }
  const hit = svg("rect", { x: ml, y: mt, width: w - ml - mr, height: H - mt - mb, fill: "transparent" });
  let cur = null;
  const ring = svg("circle", { r: 7, fill: "none", stroke: css("--ink"), "stroke-width": 1.5, opacity: 0 });
  hit.addEventListener("pointermove", (ev) => {
    const r = s.getBoundingClientRect(), px = ev.clientX - r.left, py = ev.clientY - r.top;
    let best = null, bd = 16 * 16;
    for (const p of P) { const d = (sx(tx(p.x)) - px) ** 2 + (sy(ty(p.y)) - py) ** 2; if (d < bd) { bd = d; best = p; } }
    cur = best;
    if (!best) { ring.setAttribute("opacity", 0); hideTip(); hit.style.cursor = ""; return; }
    ring.setAttribute("cx", sx(tx(best.x))); ring.setAttribute("cy", sy(ty(best.y))); ring.setAttribute("opacity", 1);
    hit.style.cursor = o.onClick ? "pointer" : "";
    showTip(ev, [el("strong", { textContent: best.title || best.label }), ...(best.rows || []).map((t) => el("div", { className: "row", textContent: t })),
      el("div", { className: "row", textContent: `${o.x?.label || "x"}: ${xf(best.x)} · ${o.y?.label || "y"}: ${yf(best.y)}` })]);
  });
  hit.addEventListener("pointerleave", () => { ring.setAttribute("opacity", 0); hideTip(); cur = null; });
  if (o.onClick) hit.addEventListener("click", () => cur && o.onClick(cur));
  s.append(ring, hit);
  s.setAttribute("aria-label", o.title || L("Gráfico de dispersão", "Scatter plot"));
  box.append(s);
  legend(box, o.legend || []);
  addTableToggle(box, o.table);
}

// ------------------------------------------------------------ heatmap

/** heatmap(box, {rows: [labels], cols: [labels], value: (i, j) => number|null, color: (v) => css, format, cell, labelWidth, tip}) */
export function heatmap(box, o) {
  box.replaceChildren();
  const nr = o.rows.length, nc = o.cols.length;
  if (!nr || !nc) { box.append(el("p", { className: "empty", textContent: o.empty || L("Sem dados.", "No data.") })); return; }
  const lw = o.labelWidth || 110, th = o.colLabelHeight ?? 70, w0 = box.clientWidth || 600;
  const cw = Math.max(o.minCell || 4, Math.min(o.cell || 32, Math.floor((w0 - lw - 4) / nc))), chh = o.rowHeight || Math.max(14, Math.min(28, cw));
  const s = svg("svg", { width: lw + cw * nc + 4, height: th + chh * nr + 4, role: "img" });
  const ink2 = css("--ink2"), f = o.format || ((v) => fmt(v, 2));
  o.rows.forEach((r, i) => s.append(text(r, { x: lw - 6, y: th + i * chh + chh / 2 + 4, "text-anchor": "end", "font-size": 11, fill: ink2 })));
  const every = Math.ceil(11 / cw);
  o.cols.forEach((c, j) => { if (j % every === 0 || o.allColLabels) s.append(text(c, { transform: `translate(${lw + j * cw + cw / 2 + 4},${th - 6}) rotate(-90)`, "font-size": 10, fill: ink2 })); });
  for (let i = 0; i < nr; i++) for (let j = 0; j < nc; j++) {
    const v = o.value(i, j);
    if (v == null || Number.isNaN(v)) continue;
    const g = cw > 6 ? 1 : 0;
    const r = svg("rect", { x: lw + j * cw + g, y: th + i * chh + g, width: cw - 2 * g, height: chh - 2 * g, rx: cw > 10 ? 2 : 0, fill: o.color(v) });
    r.addEventListener("pointermove", (ev) => showTip(ev, o.tip ? o.tip(i, j, v) : [el("strong", { textContent: f(v) }), el("div", { className: "row", textContent: `${o.rows[i]} × ${o.cols[j]}` })]));
    r.addEventListener("pointerleave", hideTip);
    s.append(r);
    if (o.cellText && cw >= 26 && chh >= 16) {
      const dark = (o.dark ? o.dark(v) : false), light = isDark() ? !dark : dark;
      s.append(text(o.cellText(v), { x: lw + j * cw + cw / 2, y: th + i * chh + chh / 2 + 4, "text-anchor": "middle", "font-size": 10, fill: light ? "#ffffff" : "#0b0b0b", "pointer-events": "none" }));
    }
  }
  s.setAttribute("aria-label", o.title || L("Mapa de calor", "Heatmap"));
  const wrap = el("div", { className: "tablewrap" }, s);
  box.append(wrap);
  if (o.legendItems) legend(box, o.legendItems);
  addTableToggle(box, o.table);
}

/** A horizontal colour key for a sequential or diverging scale. */
export function colorKey(box, { color, from, to, steps = 9, label = "" }) {
  const k = el("div", { className: "legend" }, el("span", { textContent: label }));
  const bar = el("span", { style: "display:inline-flex;align-items:center;gap:0" });
  for (let i = 0; i < steps; i++) bar.append(el("i", { style: `background:${color(i / (steps - 1))};width:16px;border-radius:0;margin:0` }));
  k.append(el("span", { textContent: from }), bar, el("span", { textContent: to }));
  box.append(k);
}

// ------------------------------------------------------------ map

/**
 * choropleth(box, {shapes: {code: path}, viewBox, value: (code) => v|null, color: (v) => css, tip: (code, v) => [nodes],
 *                  onClick, outline: {code: path} (state borders drawn on top), legend: node})
 */
export function choropleth(box, o) {
  box.replaceChildren();
  const [vw, vh] = o.viewBox;
  const w = Math.min(box.clientWidth || 600, o.maxWidth || 760), h = (w * vh) / vw;
  const s = svg("svg", { width: w, height: h, viewBox: `0 0 ${vw} ${vh}`, role: "img" });
  const empty = css("--grid"), surface = css("--surface"), axis = css("--axis");
  const g = svg("g");
  const byPath = new Map();
  for (const [code, d] of Object.entries(o.shapes)) {
    const v = o.value(code);
    const p = svg("path", { d, fill: v == null ? empty : o.color(v), stroke: o.stroke ? surface : "none", "stroke-width": o.stroke || 0 });
    byPath.set(p, code);
    g.append(p);
  }
  s.append(g);
  if (o.outline) for (const d of Object.values(o.outline)) s.append(svg("path", { d, fill: "none", stroke: axis, "stroke-width": o.outlineWidth || 0.8, "pointer-events": "none", "vector-effect": "non-scaling-stroke" }));
  const hl = svg("path", { fill: "none", stroke: css("--ink"), "stroke-width": o.highlightWidth || 1.5, "pointer-events": "none", "vector-effect": "non-scaling-stroke" });
  s.append(hl);
  g.addEventListener("pointermove", (ev) => {
    const code = byPath.get(ev.target);
    if (!code) return;
    hl.setAttribute("d", o.shapes[code]);
    showTip(ev, o.tip(code, o.value(code)));
  });
  g.addEventListener("pointerleave", () => { hl.setAttribute("d", ""); hideTip(); });
  if (o.onClick) { g.style.cursor = "pointer"; g.addEventListener("click", (ev) => { const c = byPath.get(ev.target); if (c) o.onClick(c); }); }
  s.setAttribute("aria-label", o.title || L("Mapa", "Map"));
  box.append(s);
  if (o.fit) {   // zoom to the shapes drawn (a state, say) instead of the whole country
    const b = g.getBBox();
    if (b.width > 0 && b.height > 0) {
      const pad = 0.04 * Math.max(b.width, b.height), bw = b.width + 2 * pad, bh = b.height + 2 * pad;
      const maxH = o.maxHeight || 480, ww = Math.min(w, (maxH * bw) / bh);
      s.setAttribute("viewBox", `${b.x - pad} ${b.y - pad} ${bw} ${bh}`);
      s.setAttribute("width", ww); s.setAttribute("height", (ww * bh) / bw);
    }
  }
  if (o.legend) box.append(o.legend);
  addTableToggle(box, o.table);
}

// ------------------------------------------------------------ concentration

/** Lorenz curve and Gini of non-negative values. Returns gini. */
export function gini(values) {
  const v = values.filter((x) => x > 0).sort((a, b) => a - b), n = v.length;
  if (!n) return null;
  const sum = v.reduce((a, b) => a + b, 0);
  let acc = 0;
  v.forEach((x, i) => { acc += (2 * (i + 1) - n - 1) * x; });
  return acc / (n * sum);
}
export function lorenz(box, o) {
  box.replaceChildren();
  const v = o.values.filter((x) => x > 0).sort((a, b) => a - b), n = v.length;
  if (!n) { box.append(el("p", { className: "empty", textContent: L("Sem dados.", "No data.") })); return null; }
  const sum = v.reduce((a, b) => a + b, 0);
  const pts = [[0, 0]]; let acc = 0;
  const step = Math.max(1, Math.floor(n / 200));
  v.forEach((x, i) => { acc += x; if ((i + 1) % step === 0 || i === n - 1) pts.push([(i + 1) / n, acc / sum]); });
  const G = gini(v);
  line(box, {
    series: [{ name: L("Partes iguais", "Equal shares"), color: css("--axis"), points: [[0, 0], [1, 1]], width: 1.5 }, { name: o.name || L("Real", "Actual"), color: css("--line"), points: pts }],
    x: "num", y: { min: 0, max: 1, format: (y) => `${Math.round(y * 100)}%` }, height: o.height || 240, title: o.title,
  });
  return G;
}

// ------------------------------------------------------------ strip

/**
 * strip(box, {rows: [{label, points: [{x, title, rows, color}]}], x: {format, label, min, max}, onClick})
 * One row per category, every point along x, jittered vertically; the median marked.
 */
export function strip(box, o) {
  box.replaceChildren();
  const all = o.rows.flatMap((r) => r.points.map((p) => +p.x)).filter((v) => !Number.isNaN(v));
  if (!all.length) { box.append(el("p", { className: "empty", textContent: o.empty || L("Sem dados.", "No data.") })); return; }
  const rh = o.rowHeight || 26, lw = o.labelWidth || 120, mr = 10, mt = 6, mb = 30;
  const H = mt + rh * o.rows.length + mb;
  const { w, s } = frame(box, H);
  const lo = o.x?.min ?? Math.min(...all), hi = o.x?.max ?? Math.max(...all);
  const sx = linear(lo, hi === lo ? lo + 1 : hi, lw, w - mr), xf = o.x?.format || ((v) => fmt(v, 1));
  const grid = css("--grid"), muted = css("--muted"), ink2 = css("--ink2"), ink = css("--ink"), surface = css("--surface");
  for (const v of niceTicks(lo, hi, Math.max(2, Math.floor((w - lw) / 90)))) {
    s.append(svg("line", { x1: sx(v), x2: sx(v), y1: mt, y2: H - mb, stroke: grid }));
    s.append(text(xf(v), { x: sx(v), y: H - mb + 14, "text-anchor": "middle", "font-size": 10, fill: muted }));
  }
  if (o.x?.label) s.append(text(o.x.label, { x: (lw + w - mr) / 2, y: H - 3, "text-anchor": "middle", "font-size": 11, fill: ink2 }));
  const hits = [];
  o.rows.forEach((r, i) => {
    const cy = mt + rh * i + rh / 2;
    s.append(text(r.label, { x: lw - 8, y: cy + 4, "text-anchor": "end", "font-size": 11, fill: ink2 }));
    r.points.forEach((p, k) => {
      const jit = ((k * 7919) % 11) / 10 - 0.5, x = sx(+p.x), y = cy + jit * (rh * 0.55);
      s.append(svg("circle", { cx: x, cy: y, r: 3.2, fill: p.color || css("--line"), stroke: surface, "stroke-width": 0.8, opacity: 0.85 }));
      hits.push([x, y, p]);
    });
    const xs = r.points.map((p) => +p.x).sort((a, b) => a - b);
    if (xs.length) {
      const med = xs[Math.floor((xs.length - 1) / 2)] / 2 + xs[Math.ceil((xs.length - 1) / 2)] / 2;
      s.append(svg("line", { x1: sx(med), x2: sx(med), y1: cy - rh * 0.42, y2: cy + rh * 0.42, stroke: ink, "stroke-width": 2 }));
    }
  });
  const ring = svg("circle", { r: 6, fill: "none", stroke: ink, "stroke-width": 1.5, opacity: 0 });
  const hit = svg("rect", { x: lw, y: mt, width: w - lw - mr, height: H - mt - mb, fill: "transparent" });
  let cur = null;
  hit.addEventListener("pointermove", (ev) => {
    const b = s.getBoundingClientRect(), px = ev.clientX - b.left, py = ev.clientY - b.top;
    let best = null, bd = 12 * 12;
    for (const h of hits) { const d = (h[0] - px) ** 2 + (h[1] - py) ** 2; if (d < bd) { bd = d; best = h; } }
    cur = best && best[2];
    if (!best) { ring.setAttribute("opacity", 0); hideTip(); return; }
    ring.setAttribute("cx", best[0]); ring.setAttribute("cy", best[1]); ring.setAttribute("opacity", 1);
    showTip(ev, [el("strong", { textContent: best[2].title }), ...(best[2].rows || []).map((t) => el("div", { className: "row", textContent: t }))]);
  });
  hit.addEventListener("pointerleave", () => { ring.setAttribute("opacity", 0); hideTip(); });
  if (o.onClick) { hit.style.cursor = "pointer"; hit.addEventListener("click", () => cur && o.onClick(cur)); }
  s.append(ring, hit);
  s.setAttribute("aria-label", o.title || L("Faixas de pontos", "Dot strips"));
  box.append(s);
  addTableToggle(box, o.table);
}

// ------------------------------------------------------------ network

/**
 * network(box, {nodes: [{x, y (any range), r, color, ring, title, rows}], edges: [[i, j, weight]], height})
 * A laid-out graph in SVG; hovering a node highlights its neighbours.
 */
export function network(box, o) {
  box.replaceChildren();
  if (!o.nodes.length) { box.append(el("p", { className: "empty", textContent: o.empty || L("Sem dados.", "No data.") })); return; }
  const H = o.height || 520, pad = 12;
  const { w, s } = frame(box, H);
  const xs = o.nodes.map((n) => n.x), ys = o.nodes.map((n) => n.y);
  const sx = linear(Math.min(...xs), Math.max(...xs), pad, w - pad), sy = linear(Math.min(...ys), Math.max(...ys), pad, H - pad);
  const edge = css("--edge"), surface = css("--surface"), ink = css("--ink");
  const adj = o.nodes.map(() => []);
  const eg = svg("g", { stroke: `rgb(${edge})`, "stroke-opacity": Math.max(0.05, Math.min(0.3, 300 / Math.max(o.edges.length, 1))), "stroke-width": 0.7 });
  for (const [i, j] of o.edges) {
    adj[i].push(j); adj[j].push(i);
    eg.append(svg("line", { x1: sx(o.nodes[i].x), y1: sy(o.nodes[i].y), x2: sx(o.nodes[j].x), y2: sy(o.nodes[j].y) }));
  }
  s.append(eg);
  const ng = svg("g");
  const circles = o.nodes.map((n) => {
    const c = svg("circle", { cx: sx(n.x), cy: sy(n.y), r: n.r || 3, fill: n.color || css("--line"), stroke: n.ring ? ink : surface, "stroke-width": n.ring ? 1.4 : 0.8 });
    ng.append(c);
    return c;
  });
  s.append(ng);
  const hl = svg("g", { "pointer-events": "none" });
  s.append(hl);
  const hit = svg("rect", { x: 0, y: 0, width: w, height: H, fill: "transparent" });
  hit.addEventListener("pointermove", (ev) => {
    const b = s.getBoundingClientRect(), px = ev.clientX - b.left, py = ev.clientY - b.top;
    let best = -1, bd = 14 * 14;
    o.nodes.forEach((n, i) => { const d = (sx(n.x) - px) ** 2 + (sy(n.y) - py) ** 2; if (d < bd) { bd = d; best = i; } });
    hl.replaceChildren();
    if (best < 0) { hideTip(); return; }
    const n = o.nodes[best];
    for (const j of adj[best]) hl.append(svg("line", { x1: sx(n.x), y1: sy(n.y), x2: sx(o.nodes[j].x), y2: sy(o.nodes[j].y), stroke: ink, "stroke-width": 1.2, opacity: 0.7 }));
    for (const j of [best, ...adj[best]]) hl.append(svg("circle", { cx: sx(o.nodes[j].x), cy: sy(o.nodes[j].y), r: (o.nodes[j].r || 3) + 1.5, fill: "none", stroke: ink, "stroke-width": 1.5 }));
    showTip(ev, [el("strong", { textContent: n.title }), ...(n.rows || []).map((t) => el("div", { className: "row", textContent: t })), el("div", { className: "row", textContent: `${adj[best].length} connections` })]);
  });
  hit.addEventListener("pointerleave", () => { hl.replaceChildren(); hideTip(); });
  s.append(hit);
  s.setAttribute("aria-label", o.title || L("Rede", "Network"));
  box.append(s);
  legend(box, o.legend || []);
  addTableToggle(box, o.table);
}

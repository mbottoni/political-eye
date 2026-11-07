// Graph definitions for the explorer page, mirroring politicaleye/camara/graphs.py.
// tests/camara/parity.mjs runs this file under Node against every month in
// data/camara/ and fails CI if any node or edge count differs from index.csv.

export const DEFAULTS = Object.freeze({
  tau: 0.8, minShared: 10, lop: 0.025, obstructionAsNo: true,
  maxAuthors: 50, minItems: 1, exclude: Object.freeze(["RPD", "DOC"]),
});

/** RFC 4180 CSV -> array of row objects keyed by the header. */
export function parseCSV(text) {
  const rows = [];
  let row = [], field = "", quoted = false;
  let i = text.charCodeAt(0) === 0xfeff ? 1 : 0;
  for (; i < text.length; i++) {
    const c = text[i];
    if (quoted) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; } else quoted = false;
      } else field += c;
    } else if (c === '"') quoted = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n") { row.push(field); rows.push(row); row = []; field = ""; }
    else if (c !== "\r") field += c;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  if (!rows.length) return [];
  const [head, ...body] = rows;
  return body.map((r) => Object.fromEntries(head.map((h, k) => [h, r[k] ?? ""])));
}

export function legislatura(month) {
  const y = +month.slice(0, 4), m = +month.slice(5, 7);
  return Math.floor((y - (m === 1 ? 1 : 0) - 1795) / 4);
}

/** Deputies x votações matrix of +1/-1/0, lopsided votes and inactive deputies dropped. */
export function voteMatrix(votes, { lop = DEFAULTS.lop, obstructionAsNo = DEFAULTS.obstructionAsNo } = {}) {
  const sign = (v) => (v === "Sim" ? 1 : v === "Não" || (obstructionAsNo && v === "Obstrução") ? -1 : 0);
  const rows = [];
  for (const r of votes) {
    const s = sign(r.voto);
    if (s) rows.push([+r.deputado_id, r.votacao_id, s]);
  }
  const ids = [...new Set(rows.map((r) => r[0]))].sort((a, b) => a - b);
  const cols = [...new Set(rows.map((r) => r[1]))];
  const ri = new Map(ids.map((d, i) => [d, i])), ci = new Map(cols.map((c, j) => [c, j]));
  const n = ids.length, v = cols.length, M = new Int8Array(n * v);
  for (const [d, c, s] of rows) M[ri.get(d) * v + ci.get(c)] = s;

  const keep = [];
  for (let j = 0; j < v; j++) {
    let yes = 0, no = 0;
    for (let i = 0; i < n; i++) { const s = M[i * v + j]; if (s === 1) yes++; else if (s === -1) no++; }
    if (yes + no > 0 && Math.min(yes, no) / (yes + no) >= lop) keep.push(j);
  }
  const active = [];
  for (let i = 0; i < n; i++) if (keep.some((j) => M[i * v + j] !== 0)) active.push(i);
  const V = keep.length, out = new Int8Array(active.length * V);
  active.forEach((i, a) => keep.forEach((j, b) => { out[a * V + b] = M[i * v + j]; }));
  return { ids: active.map((i) => ids[i]), votacoes: keep.map((j) => cols[j]), M: out, n: active.length, v: V };
}

/** Every pair with >= minShared common votes; nodes have >= minShared votes. */
export function covote(vm, { minShared = DEFAULTS.minShared } = {}) {
  const { n, v, M, ids } = vm;
  const nodes = [];
  for (let i = 0; i < n; i++) {
    let c = 0;
    for (let j = 0; j < v; j++) if (M[i * v + j]) c++;
    if (c >= minShared) nodes.push(ids[i]);
  }
  const u = [], w = [], shared = [], agree = [];
  for (let a = 0; a < n; a++) {
    for (let b = a + 1; b < n; b++) {
      let s = 0, g = 0;
      for (let j = 0; j < v; j++) {
        const x = M[a * v + j], y = M[b * v + j];
        if (x && y) { s++; if (x === y) g++; }
      }
      if (s >= minShared) { u.push(ids[a]); w.push(ids[b]); shared.push(s); agree.push(g); }
    }
  }
  return { nodes, u, v: w, shared, agree };
}

/** Co-signing pairs: n_items and Newman weight sum(1/(k-1)). */
export function cosponsor(authorship, { maxAuthors = DEFAULTS.maxAuthors, types = null, exclude = DEFAULTS.exclude } = {}) {
  const ex = new Set(exclude || []), only = types ? new Set(types) : null;
  const items = new Map(), signers = new Set();
  for (const r of authorship) {
    if ((only && !only.has(r.sigla_tipo)) || ex.has(r.sigla_tipo)) continue;
    const d = +r.deputado_id;
    signers.add(d);
    let s = items.get(r.proposicao_id);
    if (!s) items.set(r.proposicao_id, (s = []));
    s.push(d);
  }
  const pairs = new Map();
  for (const ds of items.values()) {
    const k = ds.length;
    if (k < 2 || (maxAuthors != null && k > maxAuthors)) continue;
    const sorted = [...ds].sort((a, b) => a - b);
    for (let a = 0; a < k; a++) {
      for (let b = a + 1; b < k; b++) {
        const key = sorted[a] * 1e7 + sorted[b];
        const e = pairs.get(key);
        if (e) { e[0] += 1; e[1] += 1 / (k - 1); } else pairs.set(key, [1, 1 / (k - 1)]);
      }
    }
  }
  const u = [], w = [], nItems = [], weight = [];
  for (const [key, [c, wt]] of pairs) {
    u.push(Math.floor(key / 1e7)); w.push(key % 1e7); nItems.push(c); weight.push(wt);
  }
  return { nodes: [...signers].sort((a, b) => a - b), u, v: w, nItems, weight };
}

// Cyclic Jacobi eigen-decomposition of a symmetric n x n matrix (row-major).
function jacobi(A, n) {
  const V = new Float64Array(n * n);
  for (let i = 0; i < n; i++) V[i * n + i] = 1;
  for (let sweep = 0; sweep < 60; sweep++) {
    let off = 0;
    for (let p = 0; p < n; p++) for (let q = p + 1; q < n; q++) off += A[p * n + q] ** 2;
    if (off < 1e-20) break;
    for (let p = 0; p < n; p++) {
      for (let q = p + 1; q < n; q++) {
        const apq = A[p * n + q];
        if (Math.abs(apq) < 1e-300) continue;
        const theta = (A[q * n + q] - A[p * n + p]) / (2 * apq);
        const t = (theta >= 0 ? 1 : -1) / (Math.abs(theta) + Math.sqrt(theta * theta + 1));
        const c = 1 / Math.sqrt(t * t + 1), s = t * c;
        for (let k = 0; k < n; k++) {
          const akp = A[k * n + p], akq = A[k * n + q];
          A[k * n + p] = c * akp - s * akq; A[k * n + q] = s * akp + c * akq;
        }
        for (let k = 0; k < n; k++) {
          const apk = A[p * n + k], aqk = A[q * n + k];
          A[p * n + k] = c * apk - s * aqk; A[q * n + k] = s * apk + c * aqk;
        }
        for (let k = 0; k < n; k++) {
          const vkp = V[k * n + p], vkq = V[k * n + q];
          V[k * n + p] = c * vkp - s * vkq; V[k * n + q] = s * vkp + c * vkq;
        }
      }
    }
  }
  const order = [...Array(n).keys()].sort((a, b) => A[b * n + b] - A[a * n + a]);
  return { values: order.map((i) => A[i * n + i]), vectors: order.map((i) => Array.from({ length: n }, (_, k) => V[k * n + i])) };
}

/**
 * Positions: first two principal components of the deputies' votes, signs
 * pinned like figures._pca2 (third moment), PT on the left when present.
 */
export function pca2(vm, nodeIds, partyOf = () => "") {
  const { v, M, ids } = vm;
  const row = new Map(ids.map((d, i) => [d, i]));
  const n = nodeIds.length, X = new Float64Array(n * v);
  for (let j = 0; j < v; j++) {
    let s = 0, c = 0;
    for (let a = 0; a < n; a++) { const x = M[row.get(nodeIds[a]) * v + j]; if (x) { s += x; c++; } }
    const mean = c ? s / c : 0;
    for (let a = 0; a < n; a++) { const x = M[row.get(nodeIds[a]) * v + j]; X[a * v + j] = x ? x - mean : 0; }
  }
  const C = new Float64Array(v * v);
  for (let a = 0; a < n; a++) {
    for (let i = 0; i < v; i++) {
      const xi = X[a * v + i];
      if (!xi) continue;
      for (let k = 0; k < v; k++) C[i * v + k] += xi * X[a * v + k];
    }
  }
  const { vectors } = jacobi(C, v);
  const P = Array.from({ length: n }, () => [0, 0]);
  for (let k = 0; k < Math.min(2, v); k++) {
    const e = vectors[k];
    for (let a = 0; a < n; a++) { let s = 0; for (let j = 0; j < v; j++) s += X[a * v + j] * e[j]; P[a][k] = s; }
    let skew = 0, big = 0;
    for (const p of P) { skew += p[k] ** 3; if (Math.abs(p[k]) > Math.abs(big)) big = p[k]; }
    if ((Math.abs(skew) > 1e-9 ? skew : big) < 0) for (const p of P) p[k] = -p[k];
  }
  const pt = nodeIds.map((d, a) => (partyOf(d) === "PT" ? P[a][0] : null)).filter((x) => x !== null);
  if (pt.length && pt.reduce((s, x) => s + x, 0) / pt.length > 0) for (const p of P) p[0] = -p[0];
  return P;
}

/** The counts data/index.csv records for a month, under default parameters. */
export function monthSummary(votes, authorship, p = DEFAULTS) {
  const vm = voteMatrix(votes, p);
  const cv = covote(vm, p);
  const cs = cosponsor(authorship, p);
  let covoteEdges = 0, agreeSum = 0;
  for (let i = 0; i < cv.u.length; i++) {
    const a = cv.agree[i] / cv.shared[i];
    agreeSum += a;
    if (a >= p.tau) covoteEdges++;
  }
  const signers = new Set(cs.nodes);
  return {
    votacoes_contested: vm.v,
    covote_nodes: cv.nodes.length,
    covote_edges: covoteEdges,
    mean_agreement: cv.u.length ? agreeSum / cv.u.length : null,
    cosponsor_nodes: cs.nodes.length,
    cosponsor_edges: cs.nItems.filter((c) => c >= p.minItems).length,
    aligned_nodes: cv.nodes.filter((d) => signers.has(d)).length,
  };
}

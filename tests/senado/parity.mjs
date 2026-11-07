// The Senado explorer recomputes the graphs in the browser with the Câmara's
// code (docs/camara/core.js), over the same 12-month windows. This checks,
// for every month in data/senado/, that it gets exactly the counts the
// Python package wrote to data/senado/index.csv.
//
//   node tests/senado/parity.mjs
import { existsSync, readFileSync } from "node:fs";
import * as core from "../../docs/camara/core.js";
import { SENADO, windowMonths } from "../../docs/senado/window.js";

const data = new URL("../../data/senado/", import.meta.url);
const read = (p) => readFileSync(new URL(p, data), "utf8");
const has = (p) => existsSync(new URL(p, data));
const INT = ["votacoes_contested", "covote_nodes", "covote_edges", "cosponsor_nodes", "cosponsor_edges", "aligned_nodes"];

let bad = 0;
const rows = core.parseCSV(read("index.csv"));
const cache = new Map();
const table = (kind, m) => {
  const k = `${kind}/${m}`;
  if (!cache.has(k)) cache.set(k, has(`${k}.csv`) ? core.parseCSV(read(`${k}.csv`)) : []);
  return cache.get(k);
};
for (const row of rows) {
  const ms = windowMonths(row.month);
  if (ms[0] !== row.window_start) { bad++; console.error(`${row.month} window_start: python ${row.window_start}, js ${ms[0]}`); }
  const votes = ms.flatMap((m) => table("votes", m));
  const authorship = ms.flatMap((m) => table("authorship", m));
  const got = core.monthSummary(votes, authorship, SENADO);
  for (const k of INT) {
    if (got[k] !== +row[k]) { bad++; console.error(`${row.month} ${k}: python ${row[k]}, js ${got[k]}`); }
  }
  const py = row.mean_agreement === "" ? null : +row.mean_agreement;
  const ok = py === null ? got.mean_agreement === null : Math.abs(got.mean_agreement - py) < 1e-4;
  if (!ok) { bad++; console.error(`${row.month} mean_agreement: python ${py}, js ${got.mean_agreement}`); }
}
if (bad) {
  console.error(`parity: ${bad} mismatches`);
  process.exit(1);
}
console.log(`parity: ${rows.length} windows identical to data/senado/index.csv`);

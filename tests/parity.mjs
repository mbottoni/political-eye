// The explorer recomputes the graphs in the browser (docs/core.js). This
// checks, for every month in data/, that it gets exactly the node and edge
// counts the Python package wrote to data/index.csv.
//
//   node tests/parity.mjs
import { readFileSync } from "node:fs";
import * as core from "../docs/core.js";

const data = new URL("../data/", import.meta.url);
const read = (p) => readFileSync(new URL(p, data), "utf8");
const INT = ["votacoes_contested", "covote_nodes", "covote_edges", "cosponsor_nodes", "cosponsor_edges", "aligned_nodes"];

let bad = 0;
const rows = core.parseCSV(read("index.csv"));
for (const row of rows) {
  const m = row.month;
  const got = core.monthSummary(core.parseCSV(read(`votes/${m}.csv`)), core.parseCSV(read(`authorship/${m}.csv`)));
  for (const k of INT) {
    if (got[k] !== +row[k]) { bad++; console.error(`${m} ${k}: python ${row[k]}, js ${got[k]}`); }
  }
  const pyMean = row.mean_agreement === "" ? null : +row.mean_agreement;
  const ok = pyMean === null ? got.mean_agreement === null : Math.abs(got.mean_agreement - pyMean) < 1e-4;
  if (!ok) { bad++; console.error(`${m} mean_agreement: python ${pyMean}, js ${got.mean_agreement}`); }
}

// PCA: the eigen-solver must actually diagonalise.
const rng = (() => { let s = 7; return () => ((s = (s * 1103515245 + 12345) % 2 ** 31) / 2 ** 31); })();
const votes = [];
for (let d = 1; d <= 60; d++) for (let j = 0; j < 30; j++) {
  const r = rng();
  votes.push({ deputado_id: String(d), votacao_id: `v${j}`, voto: r < 0.45 ? "Sim" : r < 0.9 ? "Não" : "Abstenção" });
}
const vm = core.voteMatrix(votes, { lop: 0 });
const P = core.pca2(vm, vm.ids);
const P2 = core.pca2({ ...vm, M: vm.M.map((x) => -x) }, vm.ids);
const pinned = P.every((p, i) => Math.abs(p[0] - P2[i][0]) < 1e-8 && Math.abs(p[1] - P2[i][1]) < 1e-8);
if (!pinned) { bad++; console.error("pca2: negating every vote changed the picture (signs not pinned)"); }

if (bad) {
  console.error(`parity: ${bad} mismatches`);
  process.exit(1);
}
console.log(`parity: ${rows.length} months identical to data/index.csv; PCA signs pinned`);

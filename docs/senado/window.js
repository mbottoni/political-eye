// The Senado's defaults and windows, mirroring politicaleye/senado/graphs.py.
// A graph pools the WINDOW months ending at a month, never reaching back
// before its legislature began (1 February 2019, 2023, 2027...).
import { DEFAULTS, legislatura } from "../camara/core.js";

export const WINDOW = 12;
export const SENADO = Object.freeze({
  ...DEFAULTS, minShared: 10, maxAuthors: 20, exclude: Object.freeze([]), obstructionAsNo: false,
  member: "senador_id", item: "processo_id",
});

const shift = (month, k) => {
  const n = +month.slice(0, 4) * 12 + (+month.slice(5, 7) - 1) + k;
  return `${String(Math.floor(n / 12)).padStart(4, "0")}-${String((n % 12) + 1).padStart(2, "0")}`;
};

export function windowMonths(month, window = WINDOW) {
  const legStart = `${1795 + 4 * legislatura(month)}-02`;
  let m = shift(month, -(window - 1));
  if (m < legStart) m = legStart;
  const out = [];
  for (; m <= month; m = shift(m, 1)) out.push(m);
  return out;
}

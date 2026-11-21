import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import { VIEWBOX, GEO } from "../public/geo.js";

const KEYS = ["69001","69002","69003","69004","69005","69006","69007","69008","69009",
  "69100","69300","69500","69200","69600","69190","69130"];
const [, , W, H] = VIEWBOX.split(" ").map(Number);

test("geo has exactly the 16 expected areas", () => {
  assert.deepEqual(Object.keys(GEO).sort(), [...KEYS].sort());
});
test("paths are valid SVG path strings", () => {
  for (const [k, g] of Object.entries(GEO)) {
    assert.equal(typeof g.name, "string", k);
    assert.match(g.path, /^M[\d.\s,LMZ-]+Z$/, k);
  }
});
test("label points are inside the viewBox", () => {
  for (const [k, g] of Object.entries(GEO)) {
    assert.ok(Number.isFinite(g.cx) && g.cx > 0 && g.cx < W, k);
    assert.ok(Number.isFinite(g.cy) && g.cy > 0 && g.cy < H, k);
  }
});
test("geo.js is small", () => {
  assert.ok(fs.statSync(new URL("../public/geo.js", import.meta.url)).size < 60 * 1024);
});

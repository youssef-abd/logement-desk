import test from "node:test";
import assert from "node:assert/strict";
import { applyMark } from "../lib/marks.js";

test("applyMark sets, replaces by newest, removes and validates", () => {
  let m = applyMark({}, { id: "bienici:a1", s: "contacted", t: 5 });
  assert.deepEqual(m, { "bienici:a1": { s: "contacted", t: 5 } });
  assert.deepEqual(applyMark(m, { id: "bienici:a1", s: "visit", t: 4 }), m);            // older write ignored
  assert.equal(applyMark(m, { id: "bienici:a1", s: "visit", t: 6 })["bienici:a1"].s, "visit");
  assert.deepEqual(applyMark(m, { id: "bienici:a1", s: "none", t: 9 }), {});
  assert.equal(applyMark(m, { id: "x y", s: "visit", t: 1 }), null);
  assert.equal(applyMark(m, { id: "a", s: "hacked", t: 1 }), null);
  assert.equal(applyMark(m, { id: "a", s: "visit", t: "1" }), null);
});

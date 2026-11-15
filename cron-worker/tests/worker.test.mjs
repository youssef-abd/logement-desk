import test from "node:test";
import assert from "node:assert/strict";
import { minutesSince, isDue } from "../src/index.js";

test("minutesSince and isDue", () => {
  assert.equal(minutesSince("2026-11-15T10:00:00Z", Date.parse("2026-11-15T11:30:00Z")), 90);
  assert.equal(minutesSince(null, 1), Infinity);
  assert.equal(isDue(Date.parse("2026-11-15T10:03:00Z")), true);   // first 10 minutes of the hour: do the hourly check
  assert.equal(isDue(Date.parse("2026-11-15T10:23:00Z")), false);
});

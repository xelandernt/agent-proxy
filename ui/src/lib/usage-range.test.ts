import assert from "node:assert/strict";
import test from "node:test";
import { resolveUsageRange } from "./usage-range.ts";

test("preset ranges roll forward on each resolution", () => {
	const range = { presetMinutes: 60 };
	const first = resolveUsageRange(range, new Date("2026-01-01T01:00:00Z"));
	const second = resolveUsageRange(range, new Date("2026-01-01T01:30:00Z"));

	assert.deepEqual(first, {
		from: "2026-01-01T00:00:00.000Z",
		to: "2026-01-01T01:00:00.000Z",
	});
	assert.deepEqual(second, {
		from: "2026-01-01T00:30:00.000Z",
		to: "2026-01-01T01:30:00.000Z",
	});
});

test("custom ranges remain fixed", () => {
	const range = {
		from: new Date("2026-01-01T00:00:00Z"),
		to: new Date("2026-01-02T00:00:00Z"),
	};

	assert.deepEqual(resolveUsageRange(range), {
		from: "2026-01-01T00:00:00.000Z",
		to: "2026-01-02T00:00:00.000Z",
	});
});

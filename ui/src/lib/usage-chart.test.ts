import assert from "node:assert/strict";
import test from "node:test";
import type { SeriesBucket } from "#/lib/mcp";
import { stackSeries } from "./usage-chart.ts";

function point(total: number, alpha: number, beta: number): SeriesBucket {
	return {
		ts: "2026-01-01T00:00:00Z",
		total,
		tools: [
			{ name: "alpha", count: alpha },
			{ name: "beta", count: beta },
		],
		methods: [],
		clients: [],
		statuses: [],
	};
}

test("stackSeries stacks names at each timestamp", () => {
	const result = stackSeries([point(4, 1, 3), point(6, 2, 4)], "tools", [
		"alpha",
		"beta",
	]);

	assert.deepEqual(result.rows, [
		[1, 2],
		[4, 6],
	]);
	assert.equal(result.max, 6);
});

test("stackSeries does not accumulate totals over time", () => {
	const result = stackSeries([point(1, 0, 0), point(1, 0, 0)], "total", [
		"requests",
	]);

	assert.deepEqual(result.rows, [[1, 1]]);
});

import assert from "node:assert/strict";
import test from "node:test";
import {
	chartTickIndices,
	formatChartTime,
	humanizeChartValue,
	niceChartCeil,
} from "./chart-axis.ts";

test("builds readable chart axes", () => {
	assert.equal(niceChartCeil(73), 100);
	assert.equal(niceChartCeil(0.000073), 0.0001);
	assert.equal(humanizeChartValue(1250), "1.3k");
	assert.deepEqual(chartTickIndices(25), [0, 6, 12, 18, 24]);
	assert.equal(formatChartTime("2026-08-19T12:30:00Z"), "Aug 19, 12:30 PM");
});

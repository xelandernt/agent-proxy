import assert from "node:assert/strict";
import test from "node:test";
import {
	accountingCoverage,
	formatModelCost,
	type ModelUsageAggregate,
	modelUsagePointValue,
} from "./model-usage-view.ts";

const aggregate: ModelUsageAggregate = {
	requests: 3,
	successful_requests: 2,
	failed_requests: 1,
	metered_requests: 2,
	input_tokens: 10,
	output_tokens: 5,
	total_tokens: 15,
	costed_requests: 1,
	cost_usd: "0.100000000001",
};

test("formats decimal costs and keeps unknown distinct from zero", () => {
	assert.equal(formatModelCost(null), "Unknown");
	assert.equal(formatModelCost("0"), "$0.00");
	assert.equal(formatModelCost("0.100000000001"), "$0.10");
});

test("describes partial token and cost coverage", () => {
	assert.equal(
		accountingCoverage(aggregate, "tokens"),
		"2 of 3 requests metered",
	);
	assert.equal(accountingCoverage(aggregate, "cost"), "1 of 3 requests costed");
	assert.equal(
		accountingCoverage({ ...aggregate, costed_requests: 3 }, "cost"),
		null,
	);
});

test("charts unknown values as zero without changing report facts", () => {
	const point = { ...aggregate, ts: "2026-08-18T12:00:00Z" };
	assert.equal(modelUsagePointValue(point, "requests"), 3);
	assert.equal(
		modelUsagePointValue({ ...point, total_tokens: null }, "tokens"),
		0,
	);
	assert.equal(modelUsagePointValue({ ...point, cost_usd: null }, "cost"), 0);
});

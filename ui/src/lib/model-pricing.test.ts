import assert from "node:assert/strict";
import test from "node:test";
import { customPricingFromInputs, formatModelPrice } from "./model-pricing.ts";

test("returns no custom pricing when every field is blank", () => {
	assert.equal(
		customPricingFromInputs({ input: "", cachedInput: " ", output: "" }),
		null,
	);
});

test("requires an atomic custom price set", () => {
	assert.throws(
		() =>
			customPricingFromInputs({ input: "2", cachedInput: "", output: "10" }),
		/all three custom prices/,
	);
});

test("accepts zero and preserves exact decimal strings", () => {
	assert.deepEqual(
		customPricingFromInputs({ input: "2.25", cachedInput: "0", output: "10" }),
		{
			input_usd_per_million_tokens: "2.25",
			cached_input_usd_per_million_tokens: "0",
			output_usd_per_million_tokens: "10",
		},
	);
});

test("rejects negative and non-numeric prices", () => {
	assert.throws(
		() =>
			customPricingFromInputs({ input: "-1", cachedInput: "0", output: "1" }),
		/non-negative numbers/,
	);
	assert.throws(
		() =>
			customPricingFromInputs({ input: "free", cachedInput: "0", output: "1" }),
		/non-negative numbers/,
	);
});

test("formats small per-million prices without hiding configured precision", () => {
	assert.equal(formatModelPrice("2.500000000000"), "$2.50");
	assert.equal(formatModelPrice("0.000000000001"), "$0.000000000001");
});

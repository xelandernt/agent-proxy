import type { ModelPricing } from "#/api/generated/fastAPI";

const USD_PRICE_FORMAT = new Intl.NumberFormat("en-US", {
	style: "currency",
	currency: "USD",
	minimumFractionDigits: 2,
	maximumFractionDigits: 12,
});

export interface ModelPricingInputs {
	input: string;
	cachedInput: string;
	output: string;
}

export function customPricingFromInputs(
	inputs: ModelPricingInputs,
): ModelPricing | null {
	const values = [inputs.input, inputs.cachedInput, inputs.output].map(
		(value) => value.trim(),
	);
	if (values.every((value) => value === "")) return null;
	if (values.some((value) => value === "")) {
		throw new Error("Enter all three custom prices or leave all three blank.");
	}
	if (
		values.some((value) => !Number.isFinite(Number(value)) || Number(value) < 0)
	) {
		throw new Error("Custom prices must be non-negative numbers.");
	}
	return {
		input_usd_per_million_tokens: values[0],
		cached_input_usd_per_million_tokens: values[1],
		output_usd_per_million_tokens: values[2],
	};
}

export function formatModelPrice(value: string): string {
	const parsed = Number(value);
	return Number.isFinite(parsed) ? USD_PRICE_FORMAT.format(parsed) : "Unknown";
}

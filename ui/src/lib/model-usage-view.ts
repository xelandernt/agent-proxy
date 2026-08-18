import type {
	ModelUsageSeriesPoint,
	UserModelUsageReport,
} from "#/api/generated/fastAPI";

export type ModelUsageMetric = "requests" | "tokens" | "cost";
export type ModelUsageAggregate = Pick<
	UserModelUsageReport,
	| "requests"
	| "successful_requests"
	| "failed_requests"
	| "metered_requests"
	| "input_tokens"
	| "output_tokens"
	| "total_tokens"
	| "costed_requests"
	| "cost_usd"
>;

const USD_FORMAT = new Intl.NumberFormat("en-US", {
	style: "currency",
	currency: "USD",
	minimumFractionDigits: 2,
	maximumFractionDigits: 6,
});

export function formatModelCost(value: string | null): string {
	if (value === null) return "Unknown";
	const parsed = Number(value);
	return Number.isFinite(parsed) ? USD_FORMAT.format(parsed) : "Unknown";
}

export function accountingCoverage(
	aggregate: ModelUsageAggregate,
	kind: "tokens" | "cost",
): string | null {
	const covered =
		kind === "tokens" ? aggregate.metered_requests : aggregate.costed_requests;
	if (covered === aggregate.requests) return null;
	return `${covered} of ${aggregate.requests} requests ${kind === "tokens" ? "metered" : "costed"}`;
}

export function modelUsagePointValue(
	point: ModelUsageSeriesPoint,
	metric: ModelUsageMetric,
): number {
	if (metric === "requests") return point.requests;
	if (metric === "tokens") return point.total_tokens ?? 0;
	const cost = Number(point.cost_usd ?? 0);
	return Number.isFinite(cost) ? cost : 0;
}

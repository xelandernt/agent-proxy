import { type UsageRange, usageRangeKey } from "./usage-range.ts";

export type ModelUsageFilters = {
	models?: string[];
	apiKeyIds?: string[];
	userId?: string;
};

export type ModelUsageAudience = "user" | "admin";

export function modelUsageQueryKey(
	audience: ModelUsageAudience,
	kind: "summary" | "series",
	range: UsageRange | null,
	filters: ModelUsageFilters,
) {
	return [
		audience,
		"model-usage",
		kind,
		...usageRangeKey(range),
		filters.models ?? null,
		filters.apiKeyIds ?? null,
		filters.userId ?? null,
	] as const;
}

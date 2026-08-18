import { type UsageRange, usageRangeKey } from "./usage-range.ts";

export type ModelUsageFilters = {
	model?: string;
	apiKeyId?: string;
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
		filters.model ?? null,
		filters.apiKeyId ?? null,
		filters.userId ?? null,
	] as const;
}

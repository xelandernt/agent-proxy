export type UsageRange = { presetMinutes: number } | { from: Date; to: Date };

export function resolveUsageRange(
	range: UsageRange,
	now: Date = new Date(),
): { from: string; to: string } {
	if ("presetMinutes" in range) {
		return {
			from: new Date(
				now.getTime() - range.presetMinutes * 60_000,
			).toISOString(),
			to: now.toISOString(),
		};
	}
	return { from: range.from.toISOString(), to: range.to.toISOString() };
}

export function usageRangeKey(range: UsageRange | null): readonly unknown[] {
	if (range === null) return ["invalid"];
	if ("presetMinutes" in range) return ["preset", range.presetMinutes];
	return ["custom", range.from.toISOString(), range.to.toISOString()];
}

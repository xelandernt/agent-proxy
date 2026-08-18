export type UsageRange = { presetMinutes: number } | { from: Date; to: Date };

function calendarDateAtTime(date: Date, time: string): Date | null {
	const match = /^(?:[01]\d|2[0-3]):[0-5]\d$/.exec(time);
	if (!match) return null;

	const [hours, minutes] = time.split(":").map(Number);
	const dateTime = new Date(date);
	dateTime.setHours(hours, minutes, 0, 0);
	return dateTime;
}

export function usageRangeForCalendarDateTimes(
	fromDate: Date,
	fromTime: string,
	toDate: Date,
	toTime: string,
): { from: Date; to: Date } | null {
	const from = calendarDateAtTime(fromDate, fromTime);
	const to = calendarDateAtTime(toDate, toTime);
	if (!from || !to || from >= to) return null;
	return { from, to };
}

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

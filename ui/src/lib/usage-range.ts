export type UsageRange = { presetMinutes: number } | { from: Date; to: Date };

const UTC_DATE_FORMAT = new Intl.DateTimeFormat("en-US", {
	month: "short",
	day: "numeric",
	year: "numeric",
	timeZone: "UTC",
});

function calendarDateAtTime(date: Date, time: string): Date | null {
	const match = /^(?:[01]\d|2[0-3]):[0-5]\d$/.exec(time);
	if (!match) return null;

	const [hours, minutes] = time.split(":").map(Number);
	return new Date(
		Date.UTC(
			date.getFullYear(),
			date.getMonth(),
			date.getDate(),
			hours,
			minutes,
		),
	);
}

export function calendarDateForUtcInstant(value: Date): Date {
	return new Date(
		value.getUTCFullYear(),
		value.getUTCMonth(),
		value.getUTCDate(),
	);
}

export function formatUtcTime(value: Date): string {
	return `${value.getUTCHours().toString().padStart(2, "0")}:${value
		.getUTCMinutes()
		.toString()
		.padStart(2, "0")}`;
}

export function formatUtcDateTime(value: Date): string {
	return `${UTC_DATE_FORMAT.format(value)} ${formatUtcTime(value)}`;
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

const TIME_FORMAT = new Intl.DateTimeFormat("en-US", {
	month: "short",
	day: "numeric",
	hour: "2-digit",
	minute: "2-digit",
	timeZone: "UTC",
});

export function formatChartTime(value: string): string {
	return TIME_FORMAT.format(new Date(value));
}

/** Round a positive maximum up to a readable 1, 2, 5, or 10 × 10^n value. */
export function niceChartCeil(value: number): number {
	if (value <= 0) return 1;
	const magnitude = 10 ** Math.floor(Math.log10(value));
	const normalized = value / magnitude;
	const nice =
		normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
	return nice * magnitude;
}

export function humanizeChartValue(value: number): string {
	if (value < 1000) return String(value);
	const units = ["k", "M", "B"];
	let unit = -1;
	let scaled = value;
	while (scaled >= 1000 && unit < units.length - 1) {
		scaled /= 1000;
		unit += 1;
	}
	const digits = scaled % 1 === 0 ? scaled.toFixed(0) : scaled.toFixed(1);
	return `${digits}${units[unit]}`;
}

export function chartTickIndices(length: number, maximum = 5): number[] {
	return Array.from({ length: Math.min(maximum, length) }, (_, index) =>
		Math.round((index * (length - 1)) / Math.max(1, maximum - 1)),
	).filter((value, index, all) => all.indexOf(value) === index);
}

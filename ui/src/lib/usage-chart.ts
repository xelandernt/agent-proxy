import type { ItemCount, SeriesBucket, SeriesReport } from "#/lib/mcp";

export type UsageDimension =
	| "total"
	| "tools"
	| "methods"
	| "clients"
	| "statuses";

export function rowsFor(
	point: SeriesBucket,
	dimension: UsageDimension,
): ItemCount[] {
	if (dimension === "total") {
		return [{ name: "requests", count: point.total }];
	}
	return point[dimension];
}

export function chartPoints(report: SeriesReport): SeriesBucket[] {
	if (report.points.length > 0) return report.points;

	return [
		{
			ts: report.end,
			total: 0,
			tools: [],
			methods: [],
			clients: [],
			statuses: [],
		},
	];
}

export function stackSeries(
	points: SeriesBucket[],
	dimension: UsageDimension,
	names: string[],
): { rows: number[][]; max: number } {
	const rows: number[][] = names.map(() => points.map(() => 0));
	let max = 1;
	for (let pointIndex = 0; pointIndex < points.length; pointIndex++) {
		let stacked = 0;
		for (let seriesIndex = 0; seriesIndex < names.length; seriesIndex++) {
			const count = rowsFor(points[pointIndex], dimension).find(
				(item) => item.name === names[seriesIndex],
			)?.count;
			stacked += count ?? 0;
			rows[seriesIndex][pointIndex] = stacked;
		}
		max = Math.max(max, stacked);
	}
	return { rows, max };
}

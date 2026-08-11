import { useMemo, useState } from "react";
import type { ItemCount, SeriesBucket, SeriesReport } from "#/lib/mcp";
import { cn } from "#/lib/utils";

const DIMENSIONS = [
	{ id: "total", label: "Total" },
	{ id: "tools", label: "Tools" },
	{ id: "methods", label: "Methods" },
	{ id: "clients", label: "Clients" },
	{ id: "statuses", label: "Statuses" },
] as const;

type DimensionId = (typeof DIMENSIONS)[number]["id"];

const SERIES_COLORS = [
	"var(--lagoon)",
	"var(--palm)",
	"var(--sea-ink-soft)",
	"var(--lagoon-deep)",
	"var(--kicker)",
	"var(--sea-ink)",
];

const VIEWBOX = { width: 800, height: 200, padTop: 8, padBottom: 8 };

function countsFor(point: ItemCount[], name: string): number {
	for (const item of point) {
		if (item.name === name) return item.count;
	}
	return 0;
}

function rowsFor(point: SeriesBucket, dimension: DimensionId): ItemCount[] {
	if (dimension === "total") {
		return point.total > 0 ? [{ name: "requests", count: point.total }] : [];
	}
	return point[dimension];
}

export function UsageChart({ report }: { report: SeriesReport }) {
	const [dimension, setDimension] = useState<DimensionId>("total");
	const [hidden, setHidden] = useState<
		Record<DimensionId, ReadonlySet<string>>
	>({
		total: new Set(),
		tools: new Set(),
		methods: new Set(),
		clients: new Set(),
		statuses: new Set(),
	});

	const counts = useMemo(() => {
		const map = new Map<string, number>();
		for (const point of report.points) {
			for (const row of rowsFor(point, dimension)) {
				map.set(row.name, (map.get(row.name) ?? 0) + row.count);
			}
		}
		return map;
	}, [report, dimension]);

	const names = useMemo(
		() =>
			[...counts.entries()].sort((a, b) => b[1] - a[1]).map(([name]) => name),
		[counts],
	);

	const visibleNames = names.filter((name) => !hidden[dimension].has(name));

	const total = useMemo(
		() => report.points.reduce((sum, point) => sum + point.total, 0),
		[report],
	);

	if (total === 0) {
		return <p className="text-sm text-muted-foreground">No activity.</p>;
	}

	const toggleHidden = (name: string) => {
		setHidden((previous) => {
			const current = previous[dimension];
			const next = new Set(current);
			if (next.has(name)) {
				next.delete(name);
			} else {
				next.add(name);
			}
			return { ...previous, [dimension]: next };
		});
	};

	return (
		<div className="flex flex-col gap-4">
			<div className="flex flex-wrap items-center gap-2">
				{DIMENSIONS.map((item) => (
					<button
						key={item.id}
						type="button"
						onClick={() => setDimension(item.id)}
						className={cn(
							"rounded border px-2.5 py-1 font-mono text-xs transition-colors",
							dimension === item.id
								? "border-transparent bg-foreground text-background"
								: "border-border text-muted-foreground hover:text-foreground",
						)}
					>
						{item.label}
					</button>
				))}
			</div>
			<StackedAreas
				report={report}
				dimension={dimension}
				names={visibleNames}
			/>
			<Legend
				names={names}
				counts={counts}
				hidden={hidden[dimension]}
				onToggle={toggleHidden}
			/>
		</div>
	);
}

function StackedAreas({
	report,
	dimension,
	names,
}: {
	report: SeriesReport;
	dimension: DimensionId;
	names: string[];
}) {
	const points = report.points;

	const cumulative = useMemo(() => {
		const rows: number[][] = names.map(() => points.map(() => 0));
		let max = 1;
		for (let seriesIndex = 0; seriesIndex < names.length; seriesIndex++) {
			const name = names[seriesIndex];
			let running = 0;
			for (let index = 0; index < points.length; index++) {
				running += countsFor(rowsFor(points[index], dimension), name);
				rows[seriesIndex][index] = running;
				if (running > max) max = running;
			}
		}
		return { rows, max };
	}, [points, dimension, names]);

	const yMax = cumulative.max;
	const timeFormat = new Intl.DateTimeFormat(undefined, {
		month: "short",
		day: "numeric",
		hour: "2-digit",
		minute: "2-digit",
	});
	const width = VIEWBOX.width;
	const plotHeight = VIEWBOX.height - VIEWBOX.padTop - VIEWBOX.padBottom;
	const xFor = (index: number) =>
		points.length <= 1 ? width / 2 : (index / (points.length - 1)) * width;
	const yFor = (value: number) =>
		VIEWBOX.padTop + (1 - value / yMax) * plotHeight;

	const areas = names.map((_name, seriesIndex) => {
		const top = cumulative.rows[seriesIndex];
		const below = seriesIndex === 0 ? null : cumulative.rows[seriesIndex - 1];
		let path = "";
		top.forEach((value, index) => {
			path += `${index === 0 ? "M" : "L"}${xFor(index).toFixed(2)},${yFor(value).toFixed(2)}`;
		});
		for (let index = points.length - 1; index >= 0; index--) {
			const value = below?.[index] ?? 0;
			path += `L${xFor(index).toFixed(2)},${yFor(value).toFixed(2)}`;
		}
		return `${path}Z`;
	});

	return (
		<div>
			<div className="relative h-44 w-full">
				<svg
					viewBox={`0 0 ${width} ${VIEWBOX.height}`}
					preserveAspectRatio="none"
					className="h-full w-full"
					role="img"
					aria-label={`Requests per ${report.bucket} over the selected window`}
				>
					{[0, 0.5, 1].map((fraction) => (
						<line
							key={fraction}
							x1={0}
							x2={width}
							y1={yFor(yMax * fraction)}
							y2={yFor(yMax * fraction)}
							stroke="var(--line)"
							strokeWidth={1}
							vectorEffect="non-scaling-stroke"
						/>
					))}
					{areas.map((path, index) => (
						<path
							key={names[index]}
							d={path}
							fill={SERIES_COLORS[index % SERIES_COLORS.length]}
							fillOpacity={0.55}
						/>
					))}
				</svg>
				<span className="absolute -top-5 right-0 font-mono text-[10px] tabular-nums text-muted-foreground">
					max {yMax}
				</span>
			</div>
			<div className="mt-1 flex items-center justify-between font-mono text-[10px] text-muted-foreground">
				<span>
					{timeFormat.format(new Date(points[0]?.ts ?? report.start))}
				</span>
				<span>{report.bucket} buckets</span>
				<span>
					{timeFormat.format(
						new Date(points[points.length - 1]?.ts ?? report.end),
					)}
				</span>
			</div>
		</div>
	);
}

function Legend({
	names,
	counts,
	hidden,
	onToggle,
}: {
	names: string[];
	counts: Map<string, number>;
	hidden: ReadonlySet<string>;
	onToggle: (name: string) => void;
}) {
	return (
		<div className="flex flex-wrap gap-x-4 gap-y-1">
			{names.map((name, index) => {
				const isHidden = hidden.has(name);
				return (
					<button
						key={name}
						type="button"
						onClick={() => onToggle(name)}
						className={cn(
							"flex items-center gap-1.5 font-mono text-xs text-foreground",
							isHidden && "opacity-40 line-through",
						)}
					>
						<span
							className="size-2 rounded-full"
							style={{
								backgroundColor: SERIES_COLORS[index % SERIES_COLORS.length],
							}}
						/>
						<span className="truncate">{name}</span>
						<span className="tabular-nums text-foreground/70">
							{counts.get(name) ?? 0}
						</span>
					</button>
				);
			})}
		</div>
	);
}

import { useMemo, useState } from "react";
import type { SeriesBucket, SeriesReport } from "#/lib/mcp";
import {
	chartPoints,
	rowsFor,
	stackSeries,
	type UsageDimension,
} from "#/lib/usage-chart";
import { cn } from "#/lib/utils";

const DIMENSIONS = [
	{ id: "total", label: "Total" },
	{ id: "tools", label: "Tools" },
	{ id: "methods", label: "Methods" },
	{ id: "clients", label: "Clients" },
	{ id: "statuses", label: "Statuses" },
] as const;

type DimensionId = UsageDimension;

const SERIES_COLORS = [
	"var(--lagoon)",
	"var(--palm)",
	"var(--sea-ink-soft)",
	"var(--lagoon-deep)",
	"var(--kicker)",
	"var(--sea-ink)",
];

const VIEWBOX = { width: 800, height: 200, padTop: 8, padBottom: 8 };
const TICK_FRACTIONS = [0, 0.5, 1] as const;

// Built once at module scope: gateway timestamps are UTC, and explicit
// locale and time zone keep server and browser rendering identical.
const TIME_FORMAT = new Intl.DateTimeFormat("en-US", {
	month: "short",
	day: "numeric",
	hour: "2-digit",
	minute: "2-digit",
	timeZone: "UTC",
});

/** Round a maximum up to a "nice" number (1, 2, 5, 10 × 10^n). */
function niceCeil(value: number): number {
	const magnitude = 10 ** Math.floor(Math.log10(value));
	const normalized = value / magnitude;
	const nice =
		normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10;
	return nice * magnitude;
}

function humanize(value: number): string {
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

	const points = useMemo(() => chartPoints(report), [report]);

	const counts = useMemo(() => {
		const map = new Map<string, number>();
		for (const point of points) {
			for (const row of rowsFor(point, dimension)) {
				map.set(row.name, (map.get(row.name) ?? 0) + row.count);
			}
		}
		return map;
	}, [points, dimension]);

	const names = useMemo(
		() =>
			[...counts.entries()].sort((a, b) => b[1] - a[1]).map(([name]) => name),
		[counts],
	);

	const visibleNames = names.filter((name) => !hidden[dimension].has(name));

	// Colors follow the full (unfiltered) ordering so a series keeps its
	// color when others are hidden, matching the legend.
	const colorFor = (name: string) =>
		SERIES_COLORS[names.indexOf(name) % SERIES_COLORS.length];

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
				points={points}
				bucket={report.bucket}
				dimension={dimension}
				names={visibleNames}
				colorFor={colorFor}
			/>
			<Legend
				names={names}
				counts={counts}
				hidden={hidden[dimension]}
				onToggle={toggleHidden}
				colorFor={colorFor}
			/>
		</div>
	);
}

function StackedAreas({
	points,
	bucket,
	dimension,
	names,
	colorFor,
}: {
	points: SeriesBucket[];
	bucket: SeriesReport["bucket"];
	dimension: DimensionId;
	names: string[];
	colorFor: (name: string) => string;
}) {
	const cumulative = useMemo(
		() => stackSeries(points, dimension, names),
		[points, dimension, names],
	);

	const yMax = niceCeil(cumulative.max);
	const width = VIEWBOX.width;
	const plotHeight = VIEWBOX.height - VIEWBOX.padTop - VIEWBOX.padBottom;
	const xFor = (index: number) =>
		points.length <= 1 ? width / 2 : (index / (points.length - 1)) * width;
	const yFor = (value: number) =>
		VIEWBOX.padTop + (1 - value / yMax) * plotHeight;

	const maxTicks = 5;
	const tickIndices = Array.from(
		{ length: Math.min(maxTicks, points.length) },
		(_, index) =>
			Math.round((index * (points.length - 1)) / Math.max(1, maxTicks - 1)),
	).filter((value, index, all) => all.indexOf(value) === index);

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
					aria-label={`Requests per ${bucket} over the selected window`}
				>
					{TICK_FRACTIONS.map((fraction) => (
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
							fill={colorFor(names[index])}
							fillOpacity={0.55}
						/>
					))}
				</svg>
				{TICK_FRACTIONS.map((fraction) => {
					const y = yFor(yMax * fraction);
					return (
						<span
							key={fraction}
							className="absolute right-0 font-mono text-[10px] tabular-nums text-muted-foreground"
							style={{
								top: `${(y / VIEWBOX.height) * 100}%`,
								transform: "translateY(-50%)",
							}}
						>
							{humanize(yMax * fraction)}
						</span>
					);
				})}
			</div>
			<div className="mt-1 relative h-4 font-mono text-[10px] text-muted-foreground">
				{tickIndices.map((index, tickIndex) => {
					const label = TIME_FORMAT.format(new Date(points[index].ts));
					const first = tickIndex === 0;
					const last = tickIndex === tickIndices.length - 1;
					return (
						<span
							key={index}
							className="absolute top-0 whitespace-nowrap"
							style={{
								left: `${(xFor(index) / width) * 100}%`,
								transform: first
									? "none"
									: last
										? "translateX(-100%)"
										: "translateX(-50%)",
							}}
						>
							{label}
						</span>
					);
				})}
			</div>
		</div>
	);
}

function Legend({
	names,
	counts,
	hidden,
	onToggle,
	colorFor,
}: {
	names: string[];
	counts: Map<string, number>;
	hidden: ReadonlySet<string>;
	onToggle: (name: string) => void;
	colorFor: (name: string) => string;
}) {
	return (
		<div className="flex flex-wrap gap-x-4 gap-y-1">
			{names.map((name) => {
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
								backgroundColor: colorFor(name),
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

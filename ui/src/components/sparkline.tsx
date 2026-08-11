import type { SeriesPoint } from "#/lib/mcp";

const WIDTH = 96;
const HEIGHT = 28;
const PAD = 2;

export function Sparkline({ points }: { points: SeriesPoint[] }) {
	if (points.length === 0) return null;
	const values = points.map((point) => point.total);
	const total = values.reduce((sum, value) => sum + value, 0);
	const max = Math.max(1, ...values);
	const step = values.length <= 1 ? 0 : (WIDTH - PAD * 2) / (values.length - 1);
	const xFor = (index: number) => PAD + index * step;
	const yFor = (value: number) =>
		HEIGHT - PAD - (value / max) * (HEIGHT - PAD * 2);

	let line = "";
	values.forEach((value, index) => {
		line += `${index === 0 ? "M" : "L"}${xFor(index).toFixed(2)},${yFor(value).toFixed(2)}`;
	});
	const baseline = yFor(0).toFixed(2);
	const area = `${line}L${xFor(values.length - 1).toFixed(2)},${baseline}L${xFor(0).toFixed(2)},${baseline}Z`;

	return (
		<svg
			viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
			preserveAspectRatio="none"
			className="h-7 w-full"
			role="img"
			aria-label={`${total} requests in the last 24 hours`}
		>
			<path d={area} fill="var(--lagoon)" fillOpacity={0.18} />
			<path
				d={line}
				fill="none"
				stroke="var(--lagoon)"
				strokeWidth={1.5}
				vectorEffect="non-scaling-stroke"
			/>
		</svg>
	);
}

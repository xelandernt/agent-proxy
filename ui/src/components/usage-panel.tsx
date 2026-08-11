import { ActivityIcon, RefreshCwIcon } from "lucide-react";
import { useMemo, useState } from "react";
import { Button } from "#/components/ui/button";
import {
	Card,
	CardAction,
	CardContent,
	CardHeader,
	CardTitle,
} from "#/components/ui/card";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "#/components/ui/empty";
import { Skeleton } from "#/components/ui/skeleton";
import { UsageChart } from "#/components/usage-chart";
import {
	REFRESH_INTERVAL_MS,
	useServerUsage,
	useServerUsageSeries,
} from "#/lib/queries";
import { useRefetchCountdown, useSpinWhile } from "#/lib/refresh";
import { cn } from "#/lib/utils";

const PRESETS = [
	{ label: "5m", minutes: 5 },
	{ label: "15m", minutes: 15 },
	{ label: "30m", minutes: 30 },
	{ label: "1h", minutes: 60 },
] as const;

function CountRow({ row }: { row: { name: string; count: number } }) {
	return (
		<div className="flex items-center justify-between gap-4 py-1.5 font-mono text-sm">
			<span className="min-w-0 truncate text-muted-foreground">{row.name}</span>
			<span className="tabular-nums text-foreground">{row.count}</span>
		</div>
	);
}

function CountList({
	title,
	rows,
}: {
	title: string;
	rows: { name: string; count: number }[];
}) {
	return (
		<div className="min-w-0 flex-1 rounded border p-4">
			<h3 className="mb-2 font-mono text-xs font-medium uppercase tracking-[0.2em] text-kicker">
				{title}
			</h3>
			{rows.length === 0 ? (
				<p className="text-sm text-muted-foreground">No activity.</p>
			) : (
				rows.map((row) => <CountRow key={row.name} row={row} />)
			)}
		</div>
	);
}

export function UsagePanel({ serverName }: { serverName: string }) {
	const [presetMinutes, setPresetMinutes] = useState<number>(60);
	const [customFrom, setCustomFrom] = useState<string>("");
	const [customTo, setCustomTo] = useState<string>("");
	const [customActive, setCustomActive] = useState(false);

	const range = useMemo(() => {
		if (customActive) {
			const from = new Date(customFrom);
			const to = new Date(customTo);
			if (Number.isNaN(from.getTime()) || Number.isNaN(to.getTime()))
				return null;
			return { from, to };
		}
		const to = new Date();
		return { from: new Date(to.getTime() - presetMinutes * 60_000), to };
	}, [customActive, customFrom, customTo, presetMinutes]);

	const usageQuery = useServerUsage(serverName, range);
	const seriesQuery = useServerUsageSeries(serverName, range);
	const countdown = useRefetchCountdown(
		seriesQuery.dataUpdatedAt,
		REFRESH_INTERVAL_MS,
	);

	const applyCustom = () => {
		if (!customFrom || !customTo) return;
		setCustomActive(true);
	};

	const error = usageQuery.error ?? seriesQuery.error;
	const loading = usageQuery.isLoading || seriesQuery.isLoading;
	const refreshing = useSpinWhile(
		usageQuery.isFetching || seriesQuery.isFetching,
	);

	return (
		<Card>
			<CardHeader>
				<CardTitle className="font-sans text-base font-semibold">
					Usage
				</CardTitle>
				<CardAction className="flex items-center gap-2">
					<span className="font-mono text-xs tabular-nums text-muted-foreground">
						refreshes in {countdown}s
					</span>
					<Button
						variant="outline"
						size="sm"
						onClick={() => {
							usageQuery.refetch();
							seriesQuery.refetch();
						}}
					>
						<RefreshCwIcon
							className={cn("size-3.5", refreshing && "animate-spin")}
						/>
						Refresh
					</Button>
				</CardAction>
			</CardHeader>
			<CardContent className="flex flex-col gap-4">
				<div className="flex flex-wrap items-center gap-2">
					{PRESETS.map((preset) => (
						<Button
							key={preset.minutes}
							variant={
								!customActive && preset.minutes === presetMinutes
									? "default"
									: "outline"
							}
							size="sm"
							onClick={() => {
								setCustomActive(false);
								setPresetMinutes(preset.minutes);
							}}
						>
							{preset.label}
						</Button>
					))}
					<div className="ml-auto flex items-center gap-2">
						<input
							type="datetime-local"
							value={customFrom}
							onChange={(event) => setCustomFrom(event.target.value)}
							aria-label="Custom range start"
							className="rounded border bg-transparent px-2 py-1 font-mono text-xs text-muted-foreground"
						/>
						<span className="text-xs text-muted-foreground">to</span>
						<input
							type="datetime-local"
							value={customTo}
							onChange={(event) => setCustomTo(event.target.value)}
							aria-label="Custom range end"
							className="rounded border bg-transparent px-2 py-1 font-mono text-xs text-muted-foreground"
						/>
						<Button
							variant="outline"
							size="sm"
							disabled={!customFrom || !customTo}
							onClick={applyCustom}
						>
							Apply
						</Button>
					</div>
				</div>
				{loading && (
					<div className="flex flex-col gap-4">
						<Skeleton className="h-44 w-full" />
						<Skeleton className="h-10 w-28" />
						<Skeleton className="h-40 w-full" />
					</div>
				)}
				{!loading && error && (
					<Empty>
						<EmptyMedia variant="icon">
							<ActivityIcon />
						</EmptyMedia>
						<EmptyHeader>
							<EmptyTitle>Could not load usage</EmptyTitle>
							<EmptyDescription>
								{error instanceof Error ? error.message : String(error)}
							</EmptyDescription>
						</EmptyHeader>
						<EmptyContent>
							<Button
								variant="outline"
								onClick={() => {
									usageQuery.refetch();
									seriesQuery.refetch();
								}}
							>
								Retry
							</Button>
						</EmptyContent>
					</Empty>
				)}
				{!loading && !error && usageQuery.data && seriesQuery.data && (
					<div className="flex flex-col gap-6">
						<UsageChart report={seriesQuery.data} />
						<div className="flex items-baseline gap-3">
							<span className="font-serif text-5xl font-bold tabular-nums tracking-tight">
								{usageQuery.data.total}
							</span>
							<span className="text-sm text-muted-foreground">requests</span>
						</div>
						<div className="flex flex-col gap-4 md:flex-row">
							<CountList title="By tool" rows={usageQuery.data.tools} />
							<CountList title="By method" rows={usageQuery.data.methods} />
							<CountList title="By client" rows={usageQuery.data.clients} />
							<CountList title="By status" rows={usageQuery.data.statuses} />
						</div>
					</div>
				)}
			</CardContent>
		</Card>
	);
}

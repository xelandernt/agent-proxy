import { ActivityIcon } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Button } from "#/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "#/components/ui/card";
import {
	Empty,
	EmptyContent,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "#/components/ui/empty";
import { Skeleton } from "#/components/ui/skeleton";
import { fetchServerUsage, type ItemCount, type UsageReport } from "#/lib/mcp";

const PRESETS = [
	{ label: "5m", minutes: 5 },
	{ label: "15m", minutes: 15 },
	{ label: "30m", minutes: 30 },
	{ label: "1h", minutes: 60 },
] as const;

type LoadState =
	| { status: "loading" }
	| { status: "error"; message: string }
	| { status: "ready"; report: UsageReport };

function CountRow({ row }: { row: ItemCount }) {
	return (
		<div className="flex items-center justify-between gap-4 py-1.5 font-mono text-sm">
			<span className="min-w-0 truncate text-muted-foreground">{row.name}</span>
			<span className="tabular-nums text-foreground">{row.count}</span>
		</div>
	);
}

function CountList({ title, rows }: { title: string; rows: ItemCount[] }) {
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

function UsageContent({
	state,
}: {
	state: Extract<LoadState, { status: "ready" }>;
}) {
	const { report } = state;
	return (
		<div className="flex flex-col gap-6">
			<div className="flex items-baseline gap-3">
				<span className="font-serif text-5xl font-bold tabular-nums tracking-tight">
					{report.total}
				</span>
				<span className="text-sm text-muted-foreground">requests</span>
			</div>
			<div className="flex flex-col gap-4 md:flex-row">
				<CountList title="By tool" rows={report.tools} />
				<CountList title="By method" rows={report.methods} />
				<CountList title="By client" rows={report.clients} />
				<CountList title="By status" rows={report.statuses} />
			</div>
		</div>
	);
}

export function UsagePanel({ serverName }: { serverName: string }) {
	const [presetMinutes, setPresetMinutes] = useState<number>(60);
	const [customFrom, setCustomFrom] = useState<string>("");
	const [customTo, setCustomTo] = useState<string>("");
	const [customActive, setCustomActive] = useState(false);
	const [state, setState] = useState<LoadState>({ status: "loading" });

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

	const load = useCallback(() => {
		if (!range) return undefined;
		const controller = new AbortController();
		setState({ status: "loading" });
		fetchServerUsage(serverName, range.from, range.to, controller.signal)
			.then((report) => setState({ status: "ready", report }))
			.catch((error: unknown) => {
				if (controller.signal.aborted) return;
				setState({
					status: "error",
					message: error instanceof Error ? error.message : String(error),
				});
			});
		return controller;
	}, [range, serverName]);

	useEffect(() => {
		const controller = load();
		return () => controller?.abort();
	}, [load]);

	const applyCustom = () => {
		if (!customFrom || !customTo) return;
		setCustomActive(true);
	};

	return (
		<Card>
			<CardHeader>
				<CardTitle className="font-sans text-base font-semibold">
					Usage
				</CardTitle>
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
				{state.status === "loading" && (
					<div className="flex flex-col gap-4">
						<Skeleton className="h-10 w-28" />
						<Skeleton className="h-40 w-full" />
					</div>
				)}
				{state.status === "error" && (
					<Empty>
						<EmptyMedia variant="icon">
							<ActivityIcon />
						</EmptyMedia>
						<EmptyHeader>
							<EmptyTitle>Could not load usage</EmptyTitle>
							<EmptyDescription>{state.message}</EmptyDescription>
						</EmptyHeader>
						<EmptyContent>
							<Button variant="outline" onClick={() => load()}>
								Retry
							</Button>
						</EmptyContent>
					</Empty>
				)}
				{state.status === "ready" && <UsageContent state={state} />}
			</CardContent>
		</Card>
	);
}

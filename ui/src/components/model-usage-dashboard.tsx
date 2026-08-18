import {
	ActivityIcon,
	CircleDollarSignIcon,
	RefreshCwIcon,
	TriangleAlertIcon,
} from "lucide-react";
import { useMemo, useState } from "react";
import type {
	AdminModelUsageReport,
	ModelUsageApiKeyBreakdown,
	ModelUsageModelBreakdown,
	ModelUsageSeriesReport,
	ModelUsageUserBreakdown,
	UserModelUsageReport,
} from "#/api/generated/fastAPI";
import { Alert, AlertDescription, AlertTitle } from "#/components/ui/alert";
import { Badge } from "#/components/ui/badge";
import { Button } from "#/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
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
import {
	Field,
	FieldError,
	FieldGroup,
	FieldLabel,
} from "#/components/ui/field";
import { Input } from "#/components/ui/input";
import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "#/components/ui/select";
import { Skeleton } from "#/components/ui/skeleton";
import {
	Table,
	TableBody,
	TableCell,
	TableHead,
	TableHeader,
	TableRow,
} from "#/components/ui/table";
import { ToggleGroup, ToggleGroupItem } from "#/components/ui/toggle-group";
import {
	type ModelUsageAudience,
	type ModelUsageFilters,
	useModelUsage,
	useModelUsageSeries,
} from "#/lib/model-gateway-queries";
import {
	accountingCoverage,
	formatModelCost,
	type ModelUsageMetric,
	modelUsagePointValue,
} from "#/lib/model-usage-view";
import type { UsageRange } from "#/lib/usage-range";

const PRESETS = [
	{ label: "24 hours", minutes: 24 * 60 },
	{ label: "7 days", minutes: 7 * 24 * 60 },
	{ label: "30 days", minutes: 30 * 24 * 60 },
] as const;

type Report = UserModelUsageReport | AdminModelUsageReport;

export function ModelUsageDashboard({
	audience,
}: {
	audience: ModelUsageAudience;
}) {
	const [range, setRange] = useState<UsageRange>({
		presetMinutes: 30 * 24 * 60,
	});
	const [customFrom, setCustomFrom] = useState("");
	const [customTo, setCustomTo] = useState("");
	const [filters, setFilters] = useState<ModelUsageFilters>({});
	const facets = useModelUsage(audience, range, { userId: filters.userId });
	const summary = useModelUsage(audience, range, filters);
	const series = useModelUsageSeries(audience, range, filters);
	const report = summary.data;
	const facetReport = facets.data;
	const users =
		audience === "admin" && facetReport && "users" in facetReport
			? facetReport.users
			: [];
	const customError =
		customFrom &&
		customTo &&
		new Date(`${customFrom}Z`) >= new Date(`${customTo}Z`)
			? "The end must be later than the start."
			: null;

	const updateCustomRange = (from: string, to: string) => {
		setCustomFrom(from);
		setCustomTo(to);
		if (!from || !to) return;
		const next = { from: new Date(`${from}Z`), to: new Date(`${to}Z`) };
		if (Number.isFinite(next.from.getTime()) && next.from < next.to)
			setRange(next);
	};

	const error = summary.error ?? series.error;
	const loading = summary.isLoading || series.isLoading;
	const refresh = () => {
		void summary.refetch();
		void series.refetch();
		if (filters.model || filters.apiKeyId) void facets.refetch();
	};

	return (
		<div className="mx-auto flex w-full max-w-7xl flex-col gap-6 p-8">
			<header className="flex flex-wrap items-start justify-between gap-4">
				<div>
					<h1 className="font-serif text-4xl font-bold tracking-tight">
						{audience === "admin" ? "Model usage" : "Your model usage"}
					</h1>
					<p className="mt-2 text-sm text-muted-foreground">
						Requests, tokens, outcomes, and frozen USD cost in UTC.
					</p>
				</div>
				<Button variant="outline" onClick={refresh} disabled={loading}>
					<RefreshCwIcon data-icon="inline-start" />
					Refresh
				</Button>
			</header>

			<Card>
				<CardHeader>
					<CardTitle>Report filters</CardTitle>
					<CardDescription>
						Ranges are inclusive at the start and exclusive at the end.
					</CardDescription>
				</CardHeader>
				<CardContent className="flex flex-col gap-4">
					<div className="flex flex-wrap gap-2">
						{PRESETS.map((preset) => (
							<Button
								key={preset.minutes}
								variant={
									"presetMinutes" in range &&
									range.presetMinutes === preset.minutes
										? "default"
										: "outline"
								}
								size="sm"
								onClick={() => setRange({ presetMinutes: preset.minutes })}
							>
								{preset.label}
							</Button>
						))}
					</div>
					<FieldGroup className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
						<Field data-invalid={Boolean(customError)}>
							<FieldLabel htmlFor="usage-from">From (UTC)</FieldLabel>
							<Input
								id="usage-from"
								type="datetime-local"
								value={customFrom}
								max={customTo || undefined}
								aria-invalid={Boolean(customError)}
								onChange={(event) =>
									updateCustomRange(event.target.value, customTo)
								}
							/>
						</Field>
						<Field data-invalid={Boolean(customError)}>
							<FieldLabel htmlFor="usage-to">To (UTC)</FieldLabel>
							<Input
								id="usage-to"
								type="datetime-local"
								value={customTo}
								min={customFrom || undefined}
								aria-invalid={Boolean(customError)}
								onChange={(event) =>
									updateCustomRange(customFrom, event.target.value)
								}
							/>
							{customError && <FieldError>{customError}</FieldError>}
						</Field>
						{audience === "admin" && (
							<FilterSelect
								label="User"
								value={filters.userId}
								items={users.map((user) => ({
									value: user.user_id,
									label: user.display_name ?? user.email,
								}))}
								onChange={(userId) =>
									setFilters({ userId, model: filters.model })
								}
							/>
						)}
						<FilterSelect
							label="Model"
							value={filters.model}
							items={(facetReport?.models ?? []).map((model) => ({
								value: model.model,
								label: model.model,
							}))}
							onChange={(model) => setFilters({ ...filters, model })}
						/>
						<FilterSelect
							label="API key"
							value={filters.apiKeyId}
							items={(facetReport?.api_keys ?? []).map((key) => ({
								value: key.api_key_id,
								label: `${key.name}${key.revoked ? " (revoked)" : ""}`,
							}))}
							onChange={(apiKeyId) => setFilters({ ...filters, apiKeyId })}
						/>
					</FieldGroup>
				</CardContent>
			</Card>

			{loading && <DashboardSkeleton />}
			{!loading && error && <DashboardError error={error} onRetry={refresh} />}
			{!loading && !error && report && series.data && (
				<DashboardReport report={report} series={series.data} />
			)}
		</div>
	);
}

function FilterSelect({
	label,
	value,
	items,
	onChange,
}: {
	label: string;
	value?: string;
	items: { value: string; label: string }[];
	onChange: (value: string | undefined) => void;
}) {
	return (
		<Field>
			<FieldLabel>{label}</FieldLabel>
			<Select
				value={value ?? "all"}
				onValueChange={(next) => onChange(next === "all" ? undefined : next)}
			>
				<SelectTrigger className="w-full">
					<SelectValue />
				</SelectTrigger>
				<SelectContent>
					<SelectGroup>
						<SelectItem value="all">All</SelectItem>
						{items.map((item) => (
							<SelectItem key={item.value} value={item.value}>
								{item.label}
							</SelectItem>
						))}
					</SelectGroup>
				</SelectContent>
			</Select>
		</Field>
	);
}

function DashboardReport({
	report,
	series,
}: {
	report: Report;
	series: ModelUsageSeriesReport;
}) {
	const tokenCoverage = accountingCoverage(report, "tokens");
	const costCoverage = accountingCoverage(report, "cost");
	return (
		<div className="flex flex-col gap-6">
			{(tokenCoverage || costCoverage) && (
				<Alert>
					<TriangleAlertIcon />
					<AlertTitle>Partial accounting</AlertTitle>
					<AlertDescription>
						{[tokenCoverage, costCoverage].filter(Boolean).join("; ")}.
					</AlertDescription>
				</Alert>
			)}
			<div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
				<MetricCard
					title="Requests"
					value={report.requests.toLocaleString()}
					detail={`${report.successful_requests} succeeded · ${report.failed_requests} failed`}
				/>
				<MetricCard
					title="Total tokens"
					value={report.total_tokens?.toLocaleString() ?? "Unknown"}
					detail={`${report.input_tokens?.toLocaleString() ?? "?"} input · ${report.output_tokens?.toLocaleString() ?? "?"} output`}
				/>
				<MetricCard
					title="Frozen cost"
					value={formatModelCost(report.cost_usd)}
					detail={`${report.costed_requests} costed requests`}
				/>
				<MetricCard
					title="Success rate"
					value={
						report.requests
							? `${Math.round((report.successful_requests / report.requests) * 100)}%`
							: "—"
					}
					detail={`${report.metered_requests} metered requests`}
				/>
			</div>
			<Card>
				<CardHeader>
					<CardTitle>Usage over time</CardTitle>
				</CardHeader>
				<CardContent>
					<ModelUsageChart report={series} />
				</CardContent>
			</Card>
			{report.requests === 0 ? <EmptyReport /> : <Breakdowns report={report} />}
		</div>
	);
}

function MetricCard({
	title,
	value,
	detail,
}: {
	title: string;
	value: string;
	detail: string;
}) {
	return (
		<Card>
			<CardHeader>
				<CardDescription>{title}</CardDescription>
				<CardTitle className="font-serif text-3xl tabular-nums">
					{value}
				</CardTitle>
			</CardHeader>
			<CardContent className="text-xs text-muted-foreground">
				{detail}
			</CardContent>
		</Card>
	);
}

function ModelUsageChart({ report }: { report: ModelUsageSeriesReport }) {
	const [metric, setMetric] = useState<ModelUsageMetric>("requests");
	const values = useMemo(
		() => report.points.map((point) => modelUsagePointValue(point, metric)),
		[report, metric],
	);
	const max = Math.max(1, ...values);
	const path = values
		.map(
			(value, index) =>
				`${index ? "L" : "M"}${values.length === 1 ? 400 : (index / (values.length - 1)) * 800},${190 - (value / max) * 180}`,
		)
		.join(" ");
	return (
		<div className="flex flex-col gap-4">
			<ToggleGroup
				type="single"
				variant="outline"
				value={metric}
				onValueChange={(value) => {
					if (value) setMetric(value as ModelUsageMetric);
				}}
			>
				<ToggleGroupItem value="requests">Requests</ToggleGroupItem>
				<ToggleGroupItem value="tokens">Tokens</ToggleGroupItem>
				<ToggleGroupItem value="cost">Cost</ToggleGroupItem>
			</ToggleGroup>
			<div className="h-52 w-full">
				<svg
					viewBox="0 0 800 200"
					preserveAspectRatio="none"
					className="size-full"
					role="img"
					aria-label={`${metric} per ${report.bucket}`}
				>
					<line x1="0" x2="800" y1="190" y2="190" stroke="var(--line)" />
					<path
						d={path || "M0,190 L800,190"}
						fill="none"
						stroke="var(--lagoon)"
						strokeWidth="3"
						vectorEffect="non-scaling-stroke"
					/>
				</svg>
			</div>
			<p className="font-mono text-xs text-muted-foreground">
				Peak:{" "}
				{metric === "cost"
					? formatModelCost(
							String(
								max === 1 && values.every((value) => value === 0) ? 0 : max,
							),
						)
					: max.toLocaleString()}
			</p>
		</div>
	);
}

function Breakdowns({ report }: { report: Report }) {
	return (
		<div className="grid gap-6 xl:grid-cols-2">
			<BreakdownTable title="By model" rows={report.models} kind="model" />
			<BreakdownTable title="By API key" rows={report.api_keys} kind="key" />
			{"users" in report && (
				<BreakdownTable title="By user" rows={report.users} kind="user" />
			)}
		</div>
	);
}

type BreakdownRow =
	| ModelUsageModelBreakdown
	| ModelUsageApiKeyBreakdown
	| ModelUsageUserBreakdown;
function BreakdownTable({
	title,
	rows,
	kind,
}: {
	title: string;
	rows: BreakdownRow[];
	kind: "model" | "key" | "user";
}) {
	const label = (row: BreakdownRow) =>
		kind === "model" && "model" in row
			? row.model
			: kind === "key" && "name" in row
				? row.name
				: "display_name" in row
					? (row.display_name ?? row.email)
					: "Unknown";
	return (
		<Card>
			<CardHeader>
				<CardTitle>{title}</CardTitle>
			</CardHeader>
			<CardContent>
				<Table>
					<TableHeader>
						<TableRow>
							<TableHead>Name</TableHead>
							<TableHead className="text-right">Requests</TableHead>
							<TableHead className="text-right">Tokens</TableHead>
							<TableHead className="text-right">Cost</TableHead>
						</TableRow>
					</TableHeader>
					<TableBody>
						{rows.map((row) => (
							<TableRow
								key={
									"model" in row
										? row.model
										: "api_key_id" in row
											? row.api_key_id
											: row.user_id
								}
							>
								<TableCell className="max-w-56 truncate">
									{label(row)}
									{"revoked" in row && row.revoked && (
										<Badge variant="secondary" className="ml-2">
											Revoked
										</Badge>
									)}
								</TableCell>
								<TableCell className="text-right tabular-nums">
									{row.requests}
								</TableCell>
								<TableCell className="text-right tabular-nums">
									{row.total_tokens ?? "—"}
								</TableCell>
								<TableCell className="text-right tabular-nums">
									{formatModelCost(row.cost_usd)}
								</TableCell>
							</TableRow>
						))}
					</TableBody>
				</Table>
			</CardContent>
		</Card>
	);
}

function DashboardSkeleton() {
	return (
		<div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
			<Skeleton className="h-36" />
			<Skeleton className="h-36" />
			<Skeleton className="h-36" />
			<Skeleton className="h-36" />
		</div>
	);
}
function DashboardError({
	error,
	onRetry,
}: {
	error: unknown;
	onRetry: () => void;
}) {
	return (
		<Empty>
			<EmptyMedia variant="icon">
				<ActivityIcon />
			</EmptyMedia>
			<EmptyHeader>
				<EmptyTitle>Could not load model usage</EmptyTitle>
				<EmptyDescription>
					{error instanceof Error ? error.message : String(error)}
				</EmptyDescription>
			</EmptyHeader>
			<EmptyContent>
				<Button variant="outline" onClick={onRetry}>
					Retry
				</Button>
			</EmptyContent>
		</Empty>
	);
}
function EmptyReport() {
	return (
		<Empty>
			<EmptyMedia variant="icon">
				<CircleDollarSignIcon />
			</EmptyMedia>
			<EmptyHeader>
				<EmptyTitle>No model usage</EmptyTitle>
				<EmptyDescription>
					No attempted model requests matched this range and filter combination.
				</EmptyDescription>
			</EmptyHeader>
		</Empty>
	);
}

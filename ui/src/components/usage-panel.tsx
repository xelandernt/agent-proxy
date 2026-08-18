import { format } from "date-fns";
import { ActivityIcon, CalendarIcon, RefreshCwIcon } from "lucide-react";
import { useState } from "react";
import type { DateRange } from "react-day-picker";
import { Button } from "#/components/ui/button";
import { Calendar } from "#/components/ui/calendar";
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
import {
	Field,
	FieldDescription,
	FieldError,
	FieldGroup,
	FieldLabel,
} from "#/components/ui/field";
import { Input } from "#/components/ui/input";
import {
	Popover,
	PopoverContent,
	PopoverTrigger,
} from "#/components/ui/popover";
import { Skeleton } from "#/components/ui/skeleton";
import { UsageChart } from "#/components/usage-chart";
import {
	REFRESH_INTERVAL_MS,
	useServerUsage,
	useServerUsageSeries,
} from "#/lib/queries";
import { useRefetchCountdown, useSpinWhile } from "#/lib/refresh";
import {
	type UsageRange,
	usageRangeForCalendarDateTimes,
} from "#/lib/usage-range";
import { cn } from "#/lib/utils";

const PRESETS = [
	{ label: "5m", minutes: 5 },
	{ label: "15m", minutes: 15 },
	{ label: "30m", minutes: 30 },
	{ label: "1h", minutes: 60 },
] as const;

function isValidTime(value: string): boolean {
	return /^(?:[01]\d|2[0-3]):[0-5]\d$/.test(value);
}

function normalizeTypedTime(nextValue: string): string {
	const digits = nextValue.replace(/\D/g, "").slice(0, 4);
	return digits.length > 2
		? `${digits.slice(0, 2)}:${digits.slice(2)}`
		: digits;
}

function isCurrentUtcCalendarDate(date: Date, now: Date): boolean {
	return (
		date.getFullYear() === now.getUTCFullYear() &&
		date.getMonth() === now.getUTCMonth() &&
		date.getDate() === now.getUTCDate()
	);
}

function formatUtcTime(now: Date): string {
	return `${now.getUTCHours().toString().padStart(2, "0")}:${now
		.getUTCMinutes()
		.toString()
		.padStart(2, "0")}`;
}

function formatDateTimeRange(range: UsageRange): string {
	if ("presetMinutes" in range) return "Custom range";
	return `${format(range.from, "LLL d, y HH:mm")} – ${format(range.to, "LLL d, y HH:mm")}`;
}

function TimeSelect({
	label,
	value,
	disabled,
	invalid,
	onChange,
}: {
	label: string;
	value: string;
	disabled: boolean;
	invalid: boolean;
	onChange: (value: string) => void;
}) {
	return (
		<Field data-invalid={invalid} data-disabled={disabled || undefined}>
			<FieldLabel>{label}</FieldLabel>
			<Input
				value={value}
				disabled={disabled}
				maxLength={5}
				inputMode="numeric"
				placeholder="HH:MM"
				aria-label={`${label} time`}
				aria-invalid={invalid}
				onChange={(event) => onChange(normalizeTypedTime(event.target.value))}
			/>
		</Field>
	);
}

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
	const [range, setRange] = useState<UsageRange>({ presetMinutes: 60 });
	const [draftDateRange, setDraftDateRange] = useState<DateRange>();
	const [draftStartTime, setDraftStartTime] = useState("00:00");
	const [draftEndTime, setDraftEndTime] = useState("23:59");
	const [datePickerOpen, setDatePickerOpen] = useState(false);
	const now = new Date();
	const utcToday = new Date(
		now.getUTCFullYear(),
		now.getUTCMonth(),
		now.getUTCDate(),
	);
	const maxEndTime =
		draftDateRange?.to && isCurrentUtcCalendarDate(draftDateRange.to, now)
			? formatUtcTime(now)
			: undefined;
	const customActive = "from" in range;
	const draftUsageRange =
		draftDateRange?.from && draftDateRange.to
			? usageRangeForCalendarDateTimes(
					draftDateRange.from,
					draftStartTime,
					draftDateRange.to,
					draftEndTime,
				)
			: null;
	const draftError =
		draftDateRange?.from && draftDateRange.to
			? maxEndTime && isValidTime(draftEndTime) && draftEndTime > maxEndTime
				? "The end time cannot be later than the current UTC time."
				: !draftUsageRange
					? "Enter valid times and make sure the end is later than the start."
					: null
			: null;

	const usageQuery = useServerUsage(serverName, range);
	const seriesQuery = useServerUsageSeries(serverName, range);
	const countdown = useRefetchCountdown(
		seriesQuery.dataUpdatedAt,
		REFRESH_INTERVAL_MS,
	);

	const resetDraft = () => {
		if ("from" in range) {
			setDraftDateRange({ from: range.from, to: range.to });
			setDraftStartTime(format(range.from, "HH:mm"));
			setDraftEndTime(format(range.to, "HH:mm"));
			return;
		}

		setDraftDateRange(undefined);
		setDraftStartTime("00:00");
		setDraftEndTime("23:59");
	};

	const setDatePickerVisibility = (open: boolean) => {
		if (open) resetDraft();
		setDatePickerOpen(open);
	};

	const selectDraftDateRange = (nextRange: DateRange | undefined) => {
		setDraftDateRange(nextRange);
		if (!nextRange?.to || !isCurrentUtcCalendarDate(nextRange.to, now)) return;

		const currentUtcTime = formatUtcTime(now);
		if (!isValidTime(draftEndTime) || draftEndTime > currentUtcTime) {
			setDraftEndTime(currentUtcTime);
		}
	};

	const applyDateRange = () => {
		if (!draftUsageRange || draftError) return;
		setRange(draftUsageRange);
		setDatePickerOpen(false);
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
								!customActive &&
								"presetMinutes" in range &&
								range.presetMinutes === preset.minutes
									? "default"
									: "outline"
							}
							size="sm"
							onClick={() => {
								setRange({ presetMinutes: preset.minutes });
								setDatePickerOpen(false);
							}}
						>
							{preset.label}
						</Button>
					))}
					<Popover open={datePickerOpen} onOpenChange={setDatePickerVisibility}>
						<PopoverTrigger asChild>
							<Button
								variant={customActive ? "default" : "outline"}
								size="sm"
								className="ml-auto justify-start font-normal"
								aria-label="Select a custom usage date range"
							>
								<CalendarIcon data-icon="inline-start" />
								{formatDateTimeRange(range)}
							</Button>
						</PopoverTrigger>
						<PopoverContent
							className="w-auto max-h-[var(--radix-popover-content-available-height)] overflow-y-auto p-0"
							align="end"
							side="bottom"
							avoidCollisions={false}
						>
							<div className="flex flex-col sm:flex-row">
								<Calendar
									mode="range"
									selected={draftDateRange}
									onSelect={selectDraftDateRange}
									disabled={{ after: utcToday }}
									numberOfMonths={1}
								/>
								<form
									className="border-t p-3 sm:w-64 sm:border-t-0 sm:border-l"
									onSubmit={(event) => {
										event.preventDefault();
										applyDateRange();
									}}
								>
									<FieldDescription>
										Choose both dates, then set their times.
									</FieldDescription>
									<FieldGroup className="mt-3 gap-3">
										<TimeSelect
											label="Start time"
											value={draftStartTime}
											disabled={!draftDateRange?.from || !draftDateRange.to}
											invalid={Boolean(draftError)}
											onChange={setDraftStartTime}
										/>
										<TimeSelect
											label="End time"
											value={draftEndTime}
											disabled={!draftDateRange?.from || !draftDateRange.to}
											invalid={Boolean(draftError)}
											onChange={setDraftEndTime}
										/>
									</FieldGroup>
									{draftError && <FieldError>{draftError}</FieldError>}
									<div className="mt-3 flex justify-end gap-2">
										<Button
											type="button"
											variant="outline"
											size="sm"
											onClick={() => {
												resetDraft();
												setDatePickerOpen(false);
											}}
										>
											Cancel
										</Button>
										<Button
											type="submit"
											size="sm"
											disabled={!draftUsageRange || Boolean(draftError)}
										>
											Apply
										</Button>
									</div>
								</form>
							</div>
						</PopoverContent>
					</Popover>
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

import { CalendarIcon } from "lucide-react";
import { useState } from "react";
import type { DateRange } from "react-day-picker";
import { Button } from "#/components/ui/button";
import { Calendar } from "#/components/ui/calendar";
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
import {
	calendarDateForUtcInstant,
	formatUtcDateTime,
	formatUtcTime,
	type UsageRange,
	usageRangeForCalendarDateTimes,
} from "#/lib/usage-range";

export type UsageRangePreset = {
	label: string;
	minutes: number;
};

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

function formatDateTimeRange(range: UsageRange): string {
	if ("presetMinutes" in range) return "Custom range";
	return `${formatUtcDateTime(range.from)} – ${formatUtcDateTime(range.to)}`;
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

export function UsageRangePicker({
	range,
	onChange,
	presets,
}: {
	range: UsageRange;
	onChange: (range: UsageRange) => void;
	presets: readonly UsageRangePreset[];
}) {
	const [draftDateRange, setDraftDateRange] = useState<DateRange>();
	const [draftStartTime, setDraftStartTime] = useState("00:00");
	const [draftEndTime, setDraftEndTime] = useState("23:59");
	const [open, setOpen] = useState(false);
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

	const resetDraft = () => {
		if ("from" in range) {
			setDraftDateRange({
				from: calendarDateForUtcInstant(range.from),
				to: calendarDateForUtcInstant(range.to),
			});
			setDraftStartTime(formatUtcTime(range.from));
			setDraftEndTime(formatUtcTime(range.to));
			return;
		}
		setDraftDateRange(undefined);
		setDraftStartTime("00:00");
		setDraftEndTime("23:59");
	};

	const setVisibility = (nextOpen: boolean) => {
		if (nextOpen) resetDraft();
		setOpen(nextOpen);
	};

	const selectDateRange = (nextRange: DateRange | undefined) => {
		setDraftDateRange(nextRange);
		if (!nextRange?.to || !isCurrentUtcCalendarDate(nextRange.to, now)) return;
		const currentUtcTime = formatUtcTime(now);
		if (!isValidTime(draftEndTime) || draftEndTime > currentUtcTime) {
			setDraftEndTime(currentUtcTime);
		}
	};

	const apply = () => {
		if (!draftUsageRange || draftError) return;
		onChange(draftUsageRange);
		setOpen(false);
	};

	return (
		<div className="flex flex-wrap items-center gap-2">
			{presets.map((preset) => (
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
						onChange({ presetMinutes: preset.minutes });
						setOpen(false);
					}}
				>
					{preset.label}
				</Button>
			))}
			<Popover open={open} onOpenChange={setVisibility}>
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
							onSelect={selectDateRange}
							disabled={{ after: utcToday }}
							numberOfMonths={1}
						/>
						<form
							className="border-t p-3 sm:w-64 sm:border-t-0 sm:border-l"
							onSubmit={(event) => {
								event.preventDefault();
								apply();
							}}
						>
							<FieldDescription>
								Choose both dates, then set their times in UTC.
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
										setOpen(false);
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
	);
}

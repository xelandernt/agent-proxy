import assert from "node:assert/strict";
import test from "node:test";
import {
	calendarDateForUtcInstant,
	formatUtcDateTime,
	formatUtcTime,
	resolveUsageRange,
	usageRangeForCalendarDateTimes,
} from "./usage-range.ts";

test("preset ranges roll forward on each resolution", () => {
	const range = { presetMinutes: 60 };
	const first = resolveUsageRange(range, new Date("2026-01-01T01:00:00Z"));
	const second = resolveUsageRange(range, new Date("2026-01-01T01:30:00Z"));

	assert.deepEqual(first, {
		from: "2026-01-01T00:00:00.000Z",
		to: "2026-01-01T01:00:00.000Z",
	});
	assert.deepEqual(second, {
		from: "2026-01-01T00:30:00.000Z",
		to: "2026-01-01T01:30:00.000Z",
	});
});

test("custom ranges remain fixed", () => {
	const range = {
		from: new Date("2026-01-01T00:00:00Z"),
		to: new Date("2026-01-02T00:00:00Z"),
	};

	assert.deepEqual(resolveUsageRange(range), {
		from: "2026-01-01T00:00:00.000Z",
		to: "2026-01-02T00:00:00.000Z",
	});
});

test("calendar ranges interpret selected dates and times as UTC", () => {
	const previousTimezone = process.env.TZ;
	process.env.TZ = "Europe/Vienna";
	try {
		const range = usageRangeForCalendarDateTimes(
			new Date(2026, 7, 19),
			"10:41",
			new Date(2026, 7, 20),
			"09:15",
		);

		assert.ok(range);
		assert.deepEqual(resolveUsageRange(range), {
			from: "2026-08-19T10:41:00.000Z",
			to: "2026-08-20T09:15:00.000Z",
		});
	} finally {
		if (previousTimezone === undefined) delete process.env.TZ;
		else process.env.TZ = previousTimezone;
	}
});

test("UTC instants restore the matching calendar date and display values", () => {
	const previousTimezone = process.env.TZ;
	process.env.TZ = "Europe/Vienna";
	try {
		const instant = new Date("2026-08-19T23:30:00Z");
		const calendarDate = calendarDateForUtcInstant(instant);

		assert.deepEqual(
			[
				calendarDate.getFullYear(),
				calendarDate.getMonth(),
				calendarDate.getDate(),
			],
			[2026, 7, 19],
		);
		assert.equal(formatUtcTime(instant), "23:30");
		assert.equal(formatUtcDateTime(instant), "Aug 19, 2026 23:30");
	} finally {
		if (previousTimezone === undefined) delete process.env.TZ;
		else process.env.TZ = previousTimezone;
	}
});

test("calendar ranges reject equal or reverse datetimes", () => {
	assert.equal(
		usageRangeForCalendarDateTimes(
			new Date(2026, 0, 1),
			"10:00",
			new Date(2026, 0, 1),
			"10:00",
		),
		null,
	);
});

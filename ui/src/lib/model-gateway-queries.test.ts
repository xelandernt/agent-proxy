import assert from "node:assert/strict";
import test from "node:test";
import {
	getAdminModelUsageApiAdminUsageGetUrl,
	getUserModelUsageSeriesApiUserUsageSeriesGetUrl,
} from "../api/generated/fastAPI.ts";
import { modelUsageQueryKey } from "./model-usage-query.ts";

test("model usage query keys separate audience, operation, range, and filters", () => {
	const range = {
		from: new Date("2026-08-01T00:00:00Z"),
		to: new Date("2026-08-02T00:00:00Z"),
	};
	const filters = { model: "alpha", apiKeyId: "key-1", userId: "user-1" };

	assert.notDeepEqual(
		modelUsageQueryKey("user", "summary", range, filters),
		modelUsageQueryKey("admin", "summary", range, filters),
	);
	assert.notDeepEqual(
		modelUsageQueryKey("admin", "summary", range, filters),
		modelUsageQueryKey("admin", "series", range, filters),
	);
	assert.notDeepEqual(
		modelUsageQueryKey("admin", "series", range, filters),
		modelUsageQueryKey("admin", "series", range, {
			...filters,
			model: "beta",
		}),
	);
});

test("generated URLs serialize role-specific model usage filters", () => {
	const adminUrl = getAdminModelUsageApiAdminUsageGetUrl({
		from: "2026-08-01T00:00:00Z",
		to: "2026-08-02T00:00:00Z",
		user_id: "user-1",
		model: "alpha",
		api_key_id: "key-1",
	});
	const userUrl = getUserModelUsageSeriesApiUserUsageSeriesGetUrl({
		from: "2026-08-01T00:00:00Z",
		to: "2026-08-02T00:00:00Z",
		bucket: "hour",
		model: "alpha",
		api_key_id: "key-1",
	});

	assert.match(adminUrl, /user_id=user-1/);
	assert.match(adminUrl, /model=alpha/);
	assert.match(userUrl, /bucket=hour/);
	assert.doesNotMatch(userUrl, /user_id=/);
});

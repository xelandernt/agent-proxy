import assert from "node:assert/strict";
import test from "node:test";
import {
	type AuthProviderSchema,
	formatStringMap,
	inputSpec,
	parseStringMap,
	parseTextValue,
} from "./auth-schema.ts";

const schema: AuthProviderSchema = {};

test("consent unions expose boolean and named choices", () => {
	const spec = inputSpec(
		{
			anyOf: [
				{ type: "boolean" },
				{ type: "string", enum: ["remember", "external"] },
			],
		},
		schema,
	);

	assert.deepEqual(spec, {
		kind: "choice",
		choices: [true, false, "remember", "external"],
	});
});

test("string or list fields preserve both supported shapes", () => {
	const spec = inputSpec(
		{
			anyOf: [{ type: "string" }, { type: "array", items: { type: "string" } }],
		},
		schema,
	);

	assert.deepEqual(spec, { kind: "string-or-list" });
	assert.equal(parseTextValue(spec.kind, "issuer-a"), "issuer-a");
	assert.deepEqual(parseTextValue(spec.kind, "issuer-a, issuer-b"), [
		"issuer-a",
		"issuer-b",
	]);
});

test("string maps format and parse without losing values", () => {
	const value = { prompt: "login", audience: "calendar" };

	assert.deepEqual(parseStringMap(formatStringMap(value)), value);
	assert.deepEqual(
		inputSpec(
			{ type: "object", additionalProperties: { type: "string" } },
			schema,
		),
		{ kind: "map" },
	);
});

test("nullable secrets remain password fields", () => {
	assert.deepEqual(
		inputSpec(
			{
				anyOf: [
					{ type: "string", format: "password", writeOnly: true },
					{ type: "null" },
				],
			},
			schema,
		),
		{ kind: "secret" },
	);
});

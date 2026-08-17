import assert from "node:assert/strict";
import test from "node:test";
import { adminError, extractFieldErrors } from "./admin-errors.ts";

test("admin validation details become field errors", () => {
	const errors = extractFieldErrors([
		{ loc: ["body", "auth", "client_secret"], msg: "Required" },
	]);
	assert.deepEqual(errors, [
		{ field: "auth.client_secret", message: "Required" },
	]);
});

test("provider conflicts preserve the server message", () => {
	const error = adminError(409, {
		detail: "Authentication provider 'shared' is used by servers: a, b.",
	});
	assert.equal(error.status, 409);
	assert.match(error.message, /servers: a, b/);
});

import assert from "node:assert/strict";
import test from "node:test";
import { authAudienceForUrl, isAuthenticationProbe } from "./api-fetch.ts";

test("maps protected API failures to the owning login area", () => {
	assert.equal(authAudienceForUrl("/api/admin/models", "/account"), "admin");
	assert.equal(authAudienceForUrl("/api/user/me", "/admin"), "user");
	assert.equal(
		authAudienceForUrl("/api/servers/series", "/admin/usage"),
		"admin",
	);
	assert.equal(authAudienceForUrl("/api/servers/series", "/account"), "user");
});

test("does not redirect for authentication probes", () => {
	assert.equal(isAuthenticationProbe("/api/admin/me"), true);
	assert.equal(isAuthenticationProbe("/api/user/me"), true);
	assert.equal(isAuthenticationProbe("/api/admin/models"), false);
});

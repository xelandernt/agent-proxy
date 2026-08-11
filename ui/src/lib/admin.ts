import { GATEWAY_URL } from "#/lib/mcp";

export type AdminServer = {
	name: string;
	description: string;
	upstream_url: string;
	auth: Record<string, unknown>;
	verify_upstream_tls: boolean;
};

export type ServerPayload = {
	name?: string;
	description: string;
	upstream_url: string;
	auth: Record<string, unknown>;
	verify_upstream_tls: boolean;
};

export type FieldError = {
	field: string;
	message: string;
};

export class AdminApiError extends Error {
	constructor(
		public readonly status: number,
		message: string,
		public readonly fieldErrors: FieldError[] = [],
	) {
		super(message);
	}
}

function extractFieldErrors(detail: unknown): FieldError[] {
	if (!Array.isArray(detail)) return [];
	const errors: FieldError[] = [];
	for (const item of detail) {
		if (!item || typeof item !== "object") continue;
		const entry = item as {
			loc?: unknown[];
			msg?: unknown;
			type?: unknown;
			ctx?: { error?: unknown };
		};
		const location = entry.loc ?? [];
		const path = location
			.slice(1)
			.map((part) => String(part))
			.join(".");
		if (!path) continue;
		const message =
			typeof entry.msg === "string"
				? entry.msg
				: entry.ctx?.error
					? String(entry.ctx.error)
					: "Invalid value";
		errors.push({ field: path, message });
	}
	return errors;
}

async function adminFetch<T>(
	token: string,
	path: string,
	init?: RequestInit,
): Promise<T | null> {
	const response = await fetch(`${GATEWAY_URL}${path}`, {
		...init,
		headers: {
			Authorization: `Bearer ${token}`,
			...(init?.body ? { "Content-Type": "application/json" } : {}),
			...init?.headers,
		},
	});
	if (!response.ok) {
		let message = `Request failed (${response.status}).`;
		let fieldErrors: FieldError[] = [];
		try {
			const payload = (await response.json()) as { detail?: unknown };
			if (typeof payload.detail === "string") {
				message = payload.detail;
			} else {
				fieldErrors = extractFieldErrors(payload.detail);
				if (fieldErrors.length > 0) {
					message = fieldErrors
						.map((error) => `${error.field}: ${error.message}`)
						.join("; ");
				}
			}
		} catch {
			// Non-JSON error body; keep the generic message.
		}
		throw new AdminApiError(response.status, message, fieldErrors);
	}
	if (response.status === 204) return null;
	return (await response.json()) as T;
}

export function listAdminServers(token: string): Promise<AdminServer[]> {
	return adminFetch<AdminServer[]>(token, "/api/admin/servers") as Promise<
		AdminServer[]
	>;
}

export function createAdminServer(
	token: string,
	payload: ServerPayload,
): Promise<AdminServer> {
	return adminFetch<AdminServer>(token, "/api/admin/servers", {
		method: "POST",
		body: JSON.stringify(payload),
	}) as Promise<AdminServer>;
}

export function updateAdminServer(
	token: string,
	name: string,
	payload: ServerPayload,
): Promise<AdminServer> {
	return adminFetch<AdminServer>(
		token,
		`/api/admin/servers/${encodeURIComponent(name)}`,
		{ method: "PUT", body: JSON.stringify(payload) },
	) as Promise<AdminServer>;
}

export function deleteAdminServer(token: string, name: string): Promise<null> {
	return adminFetch<null>(
		token,
		`/api/admin/servers/${encodeURIComponent(name)}`,
		{ method: "DELETE" },
	);
}

export function fetchAuthSchema(
	token: string,
): Promise<Record<string, unknown>> {
	return adminFetch<Record<string, unknown>>(
		token,
		"/api/admin/auth-schema",
	) as Promise<Record<string, unknown>>;
}

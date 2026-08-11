import type {
	ServerCreateRequest,
	ServerUpdateRequest,
	ServerView,
} from "#/api/generated/fastAPI";
import {
	authSchemaApiAdminAuthSchemaGet,
	createServerApiAdminServersPost,
	deleteServerApiAdminServersNameDelete,
	listServersApiAdminServersGet,
	updateServerApiAdminServersNamePut,
} from "#/api/generated/fastAPI";

export type AdminServer = ServerView;
export type ServerPayload = ServerCreateRequest | ServerUpdateRequest;

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

function adminError<T>(status: number, data: T): AdminApiError {
	let message = `Request failed (${status}).`;
	let fieldErrors: FieldError[] = [];
	const detail = (data as { detail?: unknown } | null | undefined)?.detail;
	if (typeof detail === "string") {
		message = detail;
	} else {
		fieldErrors = extractFieldErrors(detail);
		if (fieldErrors.length > 0) {
			message = fieldErrors
				.map((error) => `${error.field}: ${error.message}`)
				.join("; ");
		}
	}
	return new AdminApiError(status, message, fieldErrors);
}

export async function listAdminServers(): Promise<AdminServer[]> {
	const result = await listServersApiAdminServersGet();
	if (result.status === 200) return result.data as AdminServer[];
	throw adminError(result.status, result.data);
}

export async function createAdminServer(
	payload: ServerCreateRequest,
): Promise<AdminServer> {
	const result = await createServerApiAdminServersPost(payload);
	if (result.status === 201) return result.data as AdminServer;
	throw adminError(result.status, result.data);
}

export async function updateAdminServer(
	name: string,
	payload: ServerUpdateRequest,
): Promise<AdminServer> {
	const result = await updateServerApiAdminServersNamePut(name, payload);
	if (result.status === 200) return result.data as AdminServer;
	throw adminError(result.status, result.data);
}

export async function deleteAdminServer(name: string): Promise<void> {
	const result = await deleteServerApiAdminServersNameDelete(name);
	if (result.status === 204) return;
	throw adminError(result.status, result.data);
}

export async function fetchAuthSchema(): Promise<Record<string, unknown>> {
	const result = await authSchemaApiAdminAuthSchemaGet();
	if (result.status === 200) return result.data as Record<string, unknown>;
	throw adminError(result.status, result.data);
}

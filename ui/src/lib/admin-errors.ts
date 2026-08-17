export type FieldError = {
	field: string;
	message: string;
};

export class AdminApiError extends Error {
	readonly status: number;
	readonly fieldErrors: FieldError[];

	constructor(status: number, message: string, fieldErrors: FieldError[] = []) {
		super(message);
		this.status = status;
		this.fieldErrors = fieldErrors;
	}
}

export function extractFieldErrors(detail: unknown): FieldError[] {
	if (!Array.isArray(detail)) return [];
	const errors: FieldError[] = [];
	for (const item of detail) {
		if (!item || typeof item !== "object") continue;
		const entry = item as {
			loc?: unknown[];
			msg?: unknown;
			ctx?: { error?: unknown };
		};
		const path = (entry.loc ?? [])
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

export function adminError<T>(status: number, data: T): AdminApiError {
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

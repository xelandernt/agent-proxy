import type {
	AuthProviderCreateRequest,
	AuthProviderUpdateRequest,
	AuthProviderView,
	ServerCreateRequest,
	ServerUpdateRequest,
	ServerView,
} from "#/api/generated/fastAPI";
import {
	authSchemaApiAdminAuthSchemaGet,
	createAuthProviderApiAdminAuthProvidersPost,
	createServerApiAdminServersPost,
	deleteAuthProviderApiAdminAuthProvidersNameDelete,
	deleteServerApiAdminServersNameDelete,
	listAuthProvidersApiAdminAuthProvidersGet,
	listServersApiAdminServersGet,
	updateAuthProviderApiAdminAuthProvidersNamePut,
	updateServerApiAdminServersNamePut,
} from "#/api/generated/fastAPI";
import { adminError } from "#/lib/admin-errors";
import type { AuthProviderSchema } from "#/lib/auth-schema";

export type { FieldError } from "#/lib/admin-errors";
export {
	AdminApiError,
	adminError,
	extractFieldErrors,
} from "#/lib/admin-errors";

export type AdminServer = ServerView;
export type AdminAuthProvider = AuthProviderView;

export async function listAdminServers(): Promise<AdminServer[]> {
	const result = await listServersApiAdminServersGet();
	if (result.status === 200) return result.data as AdminServer[];
	throw adminError(result.status, result.data);
}

export async function listAdminAuthProviders(): Promise<AdminAuthProvider[]> {
	const result = await listAuthProvidersApiAdminAuthProvidersGet();
	if (result.status === 200) return result.data as AdminAuthProvider[];
	throw adminError(result.status, result.data);
}

export async function createAdminAuthProvider(
	payload: AuthProviderCreateRequest,
): Promise<AdminAuthProvider> {
	const result = await createAuthProviderApiAdminAuthProvidersPost(payload);
	if (result.status === 201) return result.data as AdminAuthProvider;
	throw adminError(result.status, result.data);
}

export async function updateAdminAuthProvider(
	name: string,
	payload: AuthProviderUpdateRequest,
): Promise<AdminAuthProvider> {
	const result = await updateAuthProviderApiAdminAuthProvidersNamePut(
		name,
		payload,
	);
	if (result.status === 200) return result.data as AdminAuthProvider;
	throw adminError(result.status, result.data);
}

export async function deleteAdminAuthProvider(name: string): Promise<void> {
	const result = await deleteAuthProviderApiAdminAuthProvidersNameDelete(name);
	if (result.status === 204) return;
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

export async function fetchAuthSchema(): Promise<AuthProviderSchema> {
	const result = await authSchemaApiAdminAuthSchemaGet();
	if (result.status === 200) return result.data as AuthProviderSchema;
	throw adminError(result.status, result.data);
}

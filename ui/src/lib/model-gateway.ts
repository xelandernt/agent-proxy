import type {
	ApiKeyCreate,
	ApiKeyCreated,
	ApiKeyUpdate,
	ApiKeyView,
	AvailableModelView,
	ModelDeploymentCreate,
	ModelDeploymentUpdate,
	ModelDeploymentView,
	UserView,
} from "#/api/generated/fastAPI";
import {
	createApiKeyApiUserApiKeysPost,
	createModelApiAdminModelsPost,
	deleteModelApiAdminModelsNameDelete,
	listApiKeysApiUserApiKeysGet,
	listModelsApiAdminModelsGet,
	listModelsApiUserModelsGet,
	meApiUserMeGet,
	revokeApiKeyApiUserApiKeysKeyIdDelete,
	updateApiKeyApiUserApiKeysKeyIdPatch,
	updateModelApiAdminModelsNamePatch,
} from "#/api/generated/fastAPI";
import { adminError } from "#/lib/admin-errors";

export async function listAdminModels(): Promise<ModelDeploymentView[]> {
	const result = await listModelsApiAdminModelsGet();
	if (result.status === 200) return result.data;
	throw adminError(result.status, result.data);
}

export async function createAdminModel(
	payload: ModelDeploymentCreate,
): Promise<ModelDeploymentView> {
	const result = await createModelApiAdminModelsPost(payload);
	if (result.status === 201) return result.data;
	throw adminError(result.status, result.data);
}

export async function updateAdminModel(
	name: string,
	payload: ModelDeploymentUpdate,
): Promise<ModelDeploymentView> {
	const result = await updateModelApiAdminModelsNamePatch(name, payload);
	if (result.status === 200) return result.data;
	throw adminError(result.status, result.data);
}

export async function deleteAdminModel(name: string): Promise<void> {
	const result = await deleteModelApiAdminModelsNameDelete(name);
	if (result.status === 204) return;
	throw adminError(result.status, result.data);
}

export async function getCurrentUser(): Promise<UserView> {
	const result = await meApiUserMeGet();
	if (result.status === 200) return result.data;
	throw adminError(result.status, result.data);
}

export async function listUserModels(): Promise<AvailableModelView[]> {
	const result = await listModelsApiUserModelsGet();
	if (result.status === 200) return result.data;
	throw adminError(result.status, result.data);
}

export async function listUserApiKeys(): Promise<ApiKeyView[]> {
	const result = await listApiKeysApiUserApiKeysGet();
	if (result.status === 200) return result.data;
	throw adminError(result.status, result.data);
}

export async function createUserApiKey(
	payload: ApiKeyCreate,
): Promise<ApiKeyCreated> {
	const result = await createApiKeyApiUserApiKeysPost(payload);
	if (result.status === 201) return result.data;
	throw adminError(result.status, result.data);
}

export async function updateUserApiKey(
	id: string,
	payload: ApiKeyUpdate,
): Promise<ApiKeyView> {
	const result = await updateApiKeyApiUserApiKeysKeyIdPatch(id, payload);
	if (result.status === 200) return result.data;
	throw adminError(result.status, result.data);
}

export async function revokeUserApiKey(id: string): Promise<void> {
	const result = await revokeApiKeyApiUserApiKeysKeyIdDelete(id);
	if (result.status === 204) return;
	throw adminError(result.status, result.data);
}

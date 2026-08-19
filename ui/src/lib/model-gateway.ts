import type {
	AdminModelUsageApiAdminUsageGetParams,
	AdminModelUsageReport,
	AdminModelUsageSeriesApiAdminUsageSeriesGetParams,
	ApiKeyCreate,
	ApiKeyCreated,
	ApiKeyUpdate,
	ApiKeyView,
	AvailableModelView,
	ModelDeploymentCreate,
	ModelDeploymentUpdate,
	ModelDeploymentView,
	ModelProviderCreate,
	ModelProviderUpdate,
	ModelProviderView,
	ModelUsageSeriesReport,
	UserModelUsageApiUserUsageGetParams,
	UserModelUsageReport,
	UserModelUsageSeriesApiUserUsageSeriesGetParams,
	UserView,
} from "#/api/generated/fastAPI";
import {
	adminModelUsageApiAdminUsageGet,
	adminModelUsageSeriesApiAdminUsageSeriesGet,
	createApiKeyApiUserApiKeysPost,
	createModelApiAdminModelsPost,
	createModelProviderApiAdminModelProvidersPost,
	deleteModelApiAdminModelsNameDelete,
	deleteModelProviderApiAdminModelProvidersNameDelete,
	listApiKeysApiUserApiKeysGet,
	listModelProvidersApiAdminModelProvidersGet,
	listModelsApiAdminModelsGet,
	listModelsApiUserModelsGet,
	meApiUserMeGet,
	revokeApiKeyApiUserApiKeysKeyIdDelete,
	updateApiKeyApiUserApiKeysKeyIdPatch,
	updateModelApiAdminModelsNamePatch,
	updateModelProviderApiAdminModelProvidersNamePut,
	userModelUsageApiUserUsageGet,
	userModelUsageSeriesApiUserUsageSeriesGet,
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

export async function listAdminModelProviders(): Promise<ModelProviderView[]> {
	const result = await listModelProvidersApiAdminModelProvidersGet();
	if (result.status === 200) return result.data;
	throw adminError(result.status, result.data);
}

export async function createAdminModelProvider(
	payload: ModelProviderCreate,
): Promise<ModelProviderView> {
	const result = await createModelProviderApiAdminModelProvidersPost(payload);
	if (result.status === 201) return result.data;
	throw adminError(result.status, result.data);
}

export async function updateAdminModelProvider(
	name: string,
	payload: ModelProviderUpdate,
): Promise<ModelProviderView> {
	const result = await updateModelProviderApiAdminModelProvidersNamePut(
		name,
		payload,
	);
	if (result.status === 200) return result.data;
	throw adminError(result.status, result.data);
}

export async function deleteAdminModelProvider(name: string): Promise<void> {
	const result =
		await deleteModelProviderApiAdminModelProvidersNameDelete(name);
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

export async function getUserModelUsage(
	params: UserModelUsageApiUserUsageGetParams,
): Promise<UserModelUsageReport> {
	const result = await userModelUsageApiUserUsageGet(params);
	if (result.status === 200) return result.data;
	throw adminError(result.status, result.data);
}

export async function getUserModelUsageSeries(
	params: UserModelUsageSeriesApiUserUsageSeriesGetParams,
): Promise<ModelUsageSeriesReport> {
	const result = await userModelUsageSeriesApiUserUsageSeriesGet(params);
	if (result.status === 200) return result.data;
	throw adminError(result.status, result.data);
}

export async function getAdminModelUsage(
	params: AdminModelUsageApiAdminUsageGetParams,
): Promise<AdminModelUsageReport> {
	const result = await adminModelUsageApiAdminUsageGet(params);
	if (result.status === 200) return result.data;
	throw adminError(result.status, result.data);
}

export async function getAdminModelUsageSeries(
	params: AdminModelUsageSeriesApiAdminUsageSeriesGetParams,
): Promise<ModelUsageSeriesReport> {
	const result = await adminModelUsageSeriesApiAdminUsageSeriesGet(params);
	if (result.status === 200) return result.data;
	throw adminError(result.status, result.data);
}

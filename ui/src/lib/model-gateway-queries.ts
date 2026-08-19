import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
	AdminModelUsageReport,
	ApiKeyCreate,
	ApiKeyUpdate,
	ModelDeploymentCreate,
	ModelDeploymentUpdate,
	ModelProviderCreate,
	ModelProviderUpdate,
	ModelUsageSeriesReport,
	UserModelUsageReport,
} from "#/api/generated/fastAPI";
import {
	createAdminModel,
	createAdminModelProvider,
	createUserApiKey,
	deleteAdminModel,
	deleteAdminModelProvider,
	getAdminModelUsage,
	getAdminModelUsageSeries,
	getCurrentUser,
	getUserModelUsage,
	getUserModelUsageSeries,
	listAdminModelProviders,
	listAdminModels,
	listUserApiKeys,
	listUserModels,
	revokeUserApiKey,
	updateAdminModel,
	updateAdminModelProvider,
	updateUserApiKey,
} from "#/lib/model-gateway";
import {
	type ModelUsageAudience,
	type ModelUsageFilters,
	modelUsageQueryKey,
} from "#/lib/model-usage-query";
import { REFRESH_INTERVAL_MS } from "#/lib/queries";
import { resolveUsageRange, type UsageRange } from "#/lib/usage-range";

export type {
	ModelUsageAudience,
	ModelUsageFilters,
} from "#/lib/model-usage-query";

function usageParams(range: UsageRange, filters: ModelUsageFilters) {
	return {
		...resolveUsageRange(range),
		models: filters.models,
		api_key_ids: filters.apiKeyIds,
		user_id: filters.userId,
	};
}

function seriesBucket(range: UsageRange): "minute" | "hour" | "day" {
	const { from, to } = resolveUsageRange(range);
	const minutes = (Date.parse(to) - Date.parse(from)) / 60_000;
	if (minutes <= 7 * 24 * 60) return "hour";
	return "day";
}

export function useModelUsage(
	audience: ModelUsageAudience,
	range: UsageRange | null,
	filters: ModelUsageFilters,
) {
	return useQuery<UserModelUsageReport | AdminModelUsageReport>({
		queryKey: modelUsageQueryKey(audience, "summary", range, filters),
		enabled: range !== null,
		refetchInterval: REFRESH_INTERVAL_MS,
		queryFn: async () => {
			if (range === null) throw new Error("Usage range is unavailable.");
			const params = usageParams(range, filters);
			return audience === "admin"
				? getAdminModelUsage(params)
				: getUserModelUsage(params);
		},
	});
}

export function useModelUsageSeries(
	audience: ModelUsageAudience,
	range: UsageRange | null,
	filters: ModelUsageFilters,
) {
	return useQuery<ModelUsageSeriesReport>({
		queryKey: modelUsageQueryKey(audience, "series", range, filters),
		enabled: range !== null,
		refetchInterval: REFRESH_INTERVAL_MS,
		queryFn: async () => {
			if (range === null) throw new Error("Usage range is unavailable.");
			const params = {
				...usageParams(range, filters),
				bucket: seriesBucket(range),
			};
			return audience === "admin"
				? getAdminModelUsageSeries(params)
				: getUserModelUsageSeries(params);
		},
	});
}

export function useAdminModels() {
	return useQuery({ queryKey: ["admin", "models"], queryFn: listAdminModels });
}

export function useAdminModelProviders() {
	return useQuery({
		queryKey: ["admin", "model-providers"],
		queryFn: listAdminModelProviders,
	});
}

export function useCreateModelProvider() {
	const client = useQueryClient();
	return useMutation({
		mutationFn: (payload: ModelProviderCreate) =>
			createAdminModelProvider(payload),
		onSuccess: () =>
			client.invalidateQueries({ queryKey: ["admin", "model-providers"] }),
	});
}

export function useUpdateModelProvider() {
	const client = useQueryClient();
	return useMutation({
		mutationFn: ({
			name,
			payload,
		}: {
			name: string;
			payload: ModelProviderUpdate;
		}) => updateAdminModelProvider(name, payload),
		onSuccess: async () => {
			await client.invalidateQueries({
				queryKey: ["admin", "model-providers"],
			});
			await client.invalidateQueries({ queryKey: ["admin", "models"] });
		},
	});
}

export function useDeleteModelProvider() {
	const client = useQueryClient();
	return useMutation({
		mutationFn: deleteAdminModelProvider,
		onSuccess: () =>
			client.invalidateQueries({ queryKey: ["admin", "model-providers"] }),
	});
}

export function useCreateModel() {
	const client = useQueryClient();
	return useMutation({
		mutationFn: (payload: ModelDeploymentCreate) => createAdminModel(payload),
		onSuccess: () =>
			client.invalidateQueries({ queryKey: ["admin", "models"] }),
	});
}

export function useUpdateModel() {
	const client = useQueryClient();
	return useMutation({
		mutationFn: ({
			name,
			payload,
		}: {
			name: string;
			payload: ModelDeploymentUpdate;
		}) => updateAdminModel(name, payload),
		onSuccess: async () => {
			await client.invalidateQueries({ queryKey: ["admin", "models"] });
			await client.invalidateQueries({ queryKey: ["user", "models"] });
		},
	});
}

export function useDeleteModel() {
	const client = useQueryClient();
	return useMutation({
		mutationFn: deleteAdminModel,
		onSuccess: async () => {
			await client.invalidateQueries({ queryKey: ["admin", "models"] });
			await client.invalidateQueries({ queryKey: ["user", "models"] });
		},
	});
}

export function useCurrentUser() {
	return useQuery({ queryKey: ["user", "me"], queryFn: getCurrentUser });
}

export function useUserModels() {
	return useQuery({ queryKey: ["user", "models"], queryFn: listUserModels });
}

export function useUserApiKeys() {
	return useQuery({ queryKey: ["user", "api-keys"], queryFn: listUserApiKeys });
}

export function useCreateApiKey() {
	const client = useQueryClient();
	return useMutation({
		mutationFn: (payload: ApiKeyCreate) => createUserApiKey(payload),
		onSuccess: () =>
			client.invalidateQueries({ queryKey: ["user", "api-keys"] }),
	});
}

export function useUpdateApiKey() {
	const client = useQueryClient();
	return useMutation({
		mutationFn: ({ id, payload }: { id: string; payload: ApiKeyUpdate }) =>
			updateUserApiKey(id, payload),
		onSuccess: () =>
			client.invalidateQueries({ queryKey: ["user", "api-keys"] }),
	});
}

export function useDeleteApiKey() {
	const client = useQueryClient();
	return useMutation({
		mutationFn: revokeUserApiKey,
		onSuccess: () =>
			client.invalidateQueries({ queryKey: ["user", "api-keys"] }),
	});
}

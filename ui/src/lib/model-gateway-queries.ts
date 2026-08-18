import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
	ApiKeyCreate,
	ApiKeyUpdate,
	ModelDeploymentCreate,
	ModelDeploymentUpdate,
} from "#/api/generated/fastAPI";
import {
	createAdminModel,
	createUserApiKey,
	deleteAdminModel,
	getCurrentUser,
	listAdminModels,
	listUserApiKeys,
	listUserModels,
	revokeUserApiKey,
	updateAdminModel,
	updateUserApiKey,
} from "#/lib/model-gateway";

export function useAdminModels() {
	return useQuery({ queryKey: ["admin", "models"], queryFn: listAdminModels });
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

export function useRevokeApiKey() {
	const client = useQueryClient();
	return useMutation({
		mutationFn: revokeUserApiKey,
		onSuccess: () =>
			client.invalidateQueries({ queryKey: ["user", "api-keys"] }),
	});
}

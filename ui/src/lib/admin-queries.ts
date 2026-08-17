import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
	AuthProviderCreateRequest,
	AuthProviderUpdateRequest,
	ServerCreateRequest,
	ServerUpdateRequest,
} from "#/api/generated/fastAPI";
import {
	createAdminAuthProvider,
	createAdminServer,
	deleteAdminAuthProvider,
	deleteAdminServer,
	fetchAuthSchema,
	listAdminAuthProviders,
	listAdminServers,
	updateAdminAuthProvider,
	updateAdminServer,
} from "#/lib/admin";

export function useAdminServers() {
	return useQuery({
		queryKey: ["admin", "servers"],
		queryFn: () => listAdminServers(),
	});
}

export function useAdminAuthProviders() {
	return useQuery({
		queryKey: ["admin", "auth-providers"],
		queryFn: () => listAdminAuthProviders(),
	});
}

export function useAuthSchema() {
	return useQuery({
		queryKey: ["admin", "auth-schema"],
		queryFn: () => fetchAuthSchema(),
	});
}

export function useCreateServer() {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: (payload: ServerCreateRequest) => createAdminServer(payload),
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["admin", "servers"] });
			await queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
		},
	});
}

export function useCreateAuthProvider() {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: (payload: AuthProviderCreateRequest) =>
			createAdminAuthProvider(payload),
		onSuccess: () =>
			queryClient.invalidateQueries({ queryKey: ["admin", "auth-providers"] }),
	});
}

export function useUpdateAuthProvider() {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: ({
			name,
			payload,
		}: {
			name: string;
			payload: AuthProviderUpdateRequest;
		}) => updateAdminAuthProvider(name, payload),
		onSuccess: async () => {
			await queryClient.invalidateQueries({
				queryKey: ["admin", "auth-providers"],
			});
			await queryClient.invalidateQueries({ queryKey: ["admin", "servers"] });
		},
	});
}

export function useDeleteAuthProvider() {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: (name: string) => deleteAdminAuthProvider(name),
		onSuccess: () =>
			queryClient.invalidateQueries({ queryKey: ["admin", "auth-providers"] }),
	});
}

export function useUpdateServer() {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: ({
			name,
			payload,
		}: {
			name: string;
			payload: ServerUpdateRequest;
		}) => updateAdminServer(name, payload),
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["admin", "servers"] });
			await queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
		},
	});
}

export function useDeleteServer() {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: (name: string) => deleteAdminServer(name),
		onSuccess: async () => {
			await queryClient.invalidateQueries({ queryKey: ["admin", "servers"] });
			await queryClient.invalidateQueries({ queryKey: ["mcp-servers"] });
		},
	});
}

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type {
	ServerCreateRequest,
	ServerUpdateRequest,
} from "#/api/generated/fastAPI";
import {
	createAdminServer,
	deleteAdminServer,
	fetchAuthSchema,
	listAdminServers,
	updateAdminServer,
} from "#/lib/admin";
import { getAdminToken } from "#/lib/auth";

export function useAdminServers() {
	return useQuery({
		queryKey: ["admin", "servers"],
		queryFn: () => listAdminServers(),
		enabled: getAdminToken() !== null,
	});
}

export function useAuthSchema() {
	return useQuery({
		queryKey: ["admin", "auth-schema"],
		queryFn: () => fetchAuthSchema(),
		enabled: getAdminToken() !== null,
	});
}

export function useCreateServer() {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: (payload: ServerCreateRequest) => createAdminServer(payload),
		onSuccess: () =>
			queryClient.invalidateQueries({ queryKey: ["admin", "servers"] }),
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
		onSuccess: () =>
			queryClient.invalidateQueries({ queryKey: ["admin", "servers"] }),
	});
}

export function useDeleteServer() {
	const queryClient = useQueryClient();
	return useMutation({
		mutationFn: (name: string) => deleteAdminServer(name),
		onSuccess: () =>
			queryClient.invalidateQueries({ queryKey: ["admin", "servers"] }),
	});
}

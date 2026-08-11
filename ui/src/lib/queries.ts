import { useQuery } from "@tanstack/react-query";
import {
	mcpServersWellKnownMcpServersGet,
	serversUsageSeriesApiServersSeriesGet,
	serverUsageApiServersNameUsageGet,
	serverUsageSeriesApiServersNameUsageSeriesGet,
} from "#/api/generated/fastAPI";

const REFRESH_INTERVAL_MS = 30_000;

function unwrap<T>(result: { data: unknown; status: number }): T {
	if (result.status >= 200 && result.status < 300) return result.data as T;
	throw new Error(`Request failed (${result.status}).`);
}

export function useMcpServers() {
	return useQuery({
		queryKey: ["mcp-servers"],
		queryFn: async () => unwrap(await mcpServersWellKnownMcpServersGet()),
	});
}

export function useUsageSeriesAll() {
	return useQuery({
		queryKey: ["servers", "series"],
		queryFn: async () => unwrap(await serversUsageSeriesApiServersSeriesGet()),
		refetchInterval: REFRESH_INTERVAL_MS,
	});
}

export function useServerUsage(serverName: string, from: Date, to: Date) {
	const fromISO = from.toISOString();
	const toISO = to.toISOString();
	return useQuery({
		queryKey: ["server", serverName, "usage", fromISO, toISO],
		queryFn: async () =>
			unwrap(
				await serverUsageApiServersNameUsageGet(serverName, {
					from: fromISO,
					to: toISO,
				}),
			),
		refetchInterval: REFRESH_INTERVAL_MS,
	});
}

export function useServerUsageSeries(serverName: string, from: Date, to: Date) {
	const fromISO = from.toISOString();
	const toISO = to.toISOString();
	return useQuery({
		queryKey: ["server", serverName, "usage-series", fromISO, toISO],
		queryFn: async () =>
			unwrap(
				await serverUsageSeriesApiServersNameUsageSeriesGet(serverName, {
					from: fromISO,
					to: toISO,
				}),
			),
		refetchInterval: REFRESH_INTERVAL_MS,
	});
}

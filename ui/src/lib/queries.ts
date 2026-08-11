import { useQuery } from "@tanstack/react-query";
import type {
	McpServersDocument,
	SeriesReport,
	UsageReport,
	UsageSeriesDocument,
} from "#/api/generated/fastAPI";
import {
	mcpServersWellKnownMcpServersGet,
	serversUsageSeriesApiServersSeriesGet,
	serverUsageApiServersNameUsageGet,
	serverUsageSeriesApiServersNameUsageSeriesGet,
} from "#/api/generated/fastAPI";

export const REFRESH_INTERVAL_MS = 30_000;

function unwrap<T>(result: { data: unknown; status: number }): T {
	if (result.status >= 200 && result.status < 300) return result.data as T;
	throw new Error(`Request failed (${result.status}).`);
}

export function useMcpServers() {
	return useQuery({
		queryKey: ["mcp-servers"],
		queryFn: async () =>
			unwrap<McpServersDocument>(await mcpServersWellKnownMcpServersGet()),
	});
}

export function useUsageSeriesAll() {
	return useQuery({
		queryKey: ["servers", "series"],
		queryFn: async () =>
			unwrap<UsageSeriesDocument>(
				await serversUsageSeriesApiServersSeriesGet(),
			),
		refetchInterval: REFRESH_INTERVAL_MS,
	});
}

export function useServerUsage(
	serverName: string,
	range: { from: Date; to: Date } | null,
) {
	const fromISO = range?.from.toISOString() ?? "";
	const toISO = range?.to.toISOString() ?? "";
	return useQuery({
		queryKey: ["server", serverName, "usage", fromISO, toISO],
		enabled: range !== null,
		queryFn: async () =>
			unwrap<UsageReport>(
				await serverUsageApiServersNameUsageGet(serverName, {
					from: fromISO,
					to: toISO,
				}),
			),
		refetchInterval: REFRESH_INTERVAL_MS,
	});
}

export function useServerUsageSeries(
	serverName: string,
	range: { from: Date; to: Date } | null,
) {
	const fromISO = range?.from.toISOString() ?? "";
	const toISO = range?.to.toISOString() ?? "";
	return useQuery({
		queryKey: ["server", serverName, "usage-series", fromISO, toISO],
		enabled: range !== null,
		queryFn: async () =>
			unwrap<SeriesReport>(
				await serverUsageSeriesApiServersNameUsageSeriesGet(serverName, {
					from: fromISO,
					to: toISO,
				}),
			),
		refetchInterval: REFRESH_INTERVAL_MS,
	});
}

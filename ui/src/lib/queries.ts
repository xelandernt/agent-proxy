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
import {
	resolveUsageRange,
	type UsageRange,
	usageRangeKey,
} from "#/lib/usage-range";

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

export function useServerUsage(serverName: string, range: UsageRange | null) {
	return useQuery({
		queryKey: ["server", serverName, "usage", ...usageRangeKey(range)],
		enabled: range !== null,
		queryFn: async () => {
			if (range === null) throw new Error("Usage range is unavailable.");
			const params = resolveUsageRange(range);
			return unwrap<UsageReport>(
				await serverUsageApiServersNameUsageGet(serverName, params),
			);
		},
		refetchInterval: REFRESH_INTERVAL_MS,
	});
}

export function useServerUsageSeries(
	serverName: string,
	range: UsageRange | null,
) {
	return useQuery({
		queryKey: ["server", serverName, "usage-series", ...usageRangeKey(range)],
		enabled: range !== null,
		queryFn: async () => {
			if (range === null) throw new Error("Usage range is unavailable.");
			const params = resolveUsageRange(range);
			return unwrap<SeriesReport>(
				await serverUsageSeriesApiServersNameUsageSeriesGet(serverName, params),
			);
		},
		refetchInterval: REFRESH_INTERVAL_MS,
	});
}

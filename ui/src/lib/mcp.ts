export type McpServerListing = {
	name: string;
	description: string;
	url: string;
	auth: "oauth2" | "none";
};

export type McpServersDocument = {
	servers: McpServerListing[];
};

export type ItemCount = {
	name: string;
	count: number;
};

export type UsageReport = {
	server: string;
	start: string;
	end: string;
	total: number;
	tools: ItemCount[];
	methods: ItemCount[];
	clients: ItemCount[];
	statuses: ItemCount[];
};

export type SeriesBucket = {
	ts: string;
	total: number;
	tools: ItemCount[];
	methods: ItemCount[];
	clients: ItemCount[];
	statuses: ItemCount[];
};

export type SeriesReport = {
	server: string;
	start: string;
	end: string;
	bucket: string;
	points: SeriesBucket[];
};

export type SeriesPoint = {
	ts: string;
	total: number;
};

export type ServerSeries = {
	name: string;
	points: SeriesPoint[];
};

export type UsageSeriesDocument = {
	servers: ServerSeries[];
};

export const GATEWAY_URL =
	import.meta.env.VITE_GATEWAY_URL ?? "http://localhost:8008";

export async function fetchMcpServers(
	signal?: AbortSignal,
): Promise<McpServersDocument> {
	const response = await fetch(`${GATEWAY_URL}/.well-known/mcp-servers`, {
		signal,
	});
	if (!response.ok) {
		throw new Error(`Failed to fetch MCP servers (${response.status})`);
	}
	return (await response.json()) as McpServersDocument;
}

export async function fetchServerUsage(
	name: string,
	from: Date,
	to: Date,
	signal?: AbortSignal,
): Promise<UsageReport> {
	const params = new URLSearchParams({
		from: from.toISOString(),
		to: to.toISOString(),
	});
	const response = await fetch(
		`${GATEWAY_URL}/api/servers/${encodeURIComponent(name)}/usage?${params}`,
		{ signal },
	);
	if (!response.ok) {
		throw new Error(`Failed to fetch usage (${response.status})`);
	}
	return (await response.json()) as UsageReport;
}

export async function fetchServerUsageSeries(
	name: string,
	from: Date,
	to: Date,
	signal?: AbortSignal,
): Promise<SeriesReport> {
	const params = new URLSearchParams({
		from: from.toISOString(),
		to: to.toISOString(),
	});
	const response = await fetch(
		`${GATEWAY_URL}/api/servers/${encodeURIComponent(name)}/usage/series?${params}`,
		{ signal },
	);
	if (!response.ok) {
		throw new Error(`Failed to fetch usage series (${response.status})`);
	}
	return (await response.json()) as SeriesReport;
}

export async function fetchUsageSeriesAll(
	signal?: AbortSignal,
): Promise<UsageSeriesDocument> {
	const response = await fetch(`${GATEWAY_URL}/api/servers/series`, { signal });
	if (!response.ok) {
		throw new Error(`Failed to fetch usage series (${response.status})`);
	}
	return (await response.json()) as UsageSeriesDocument;
}

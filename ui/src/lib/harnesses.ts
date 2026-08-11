export type Harness = {
	id: string;
	label: string;
	docsUrl: string;
	configFile: string;
	configLang: "json" | "toml";
	command?: (name: string, url: string) => string;
	config: (name: string, url: string) => string;
};

const mcpServersJson = (name: string, url: string) =>
	JSON.stringify(
		{
			mcpServers: {
				[name]: { type: "http", url },
			},
		},
		null,
		2,
	);

export const HARNESSES: Harness[] = [
	{
		id: "claude",
		label: "Claude Code",
		docsUrl: "https://code.claude.com/docs/en/mcp",
		configFile: "~/.claude.json",
		configLang: "json",
		command: (name, url) => `claude mcp add --transport http ${name} ${url}`,
		config: mcpServersJson,
	},
	{
		id: "cursor",
		label: "Cursor",
		docsUrl: "https://docs.cursor.com/context/model-context-protocol",
		configFile: ".cursor/mcp.json",
		configLang: "json",
		config: mcpServersJson,
	},
	{
		id: "codex",
		label: "Codex",
		docsUrl: "https://developers.openai.com/codex/config-reference",
		configFile: "~/.codex/config.toml",
		configLang: "toml",
		command: (name, url) => `codex mcp add ${name} --url ${url}`,
		config: (name, url) => `[mcp_servers.${name}]\nurl = "${url}"`,
	},
	{
		id: "copilot",
		label: "Copilot CLI",
		docsUrl:
			"https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-mcp-servers",
		configFile: "~/.copilot/mcp-config.json",
		configLang: "json",
		command: (name, url) => `copilot mcp add --transport http ${name} ${url}`,
		config: mcpServersJson,
	},
];

const SELECTED_HARNESS_KEY = "harness-id";

const listeners = new Set<() => void>();
let cached: string | null = null;

function readStored(): string {
	if (cached !== null) return cached;
	try {
		const stored = localStorage.getItem(SELECTED_HARNESS_KEY);
		cached =
			stored && HARNESSES.some((harness) => harness.id === stored)
				? stored
				: HARNESSES[0].id;
	} catch {
		cached = HARNESSES[0].id;
	}
	return cached;
}

export function selectedHarnessId(): string {
	return readStored();
}

export function setSelectedHarnessId(id: string): void {
	cached = id;
	try {
		localStorage.setItem(SELECTED_HARNESS_KEY, id);
	} catch {
		// storage unavailable — keep the preference in memory only
	}
	for (const listener of listeners) listener();
}

export function subscribeHarnessSelection(listener: () => void): () => void {
	listeners.add(listener);
	return () => {
		listeners.delete(listener);
	};
}

import { ExternalLinkIcon } from "lucide-react";

import {
	Select,
	SelectContent,
	SelectGroup,
	SelectItem,
	SelectTrigger,
	SelectValue,
} from "#/components/ui/select";
import { CopySnippet } from "#/lib/copy";
import { HARNESSES } from "#/lib/harnesses";
import type { McpServerListing } from "#/lib/mcp";

export function HarnessPanel({
	server,
	harnessId,
	onHarnessIdChange,
}: {
	server: McpServerListing;
	harnessId: string;
	onHarnessIdChange: (harnessId: string) => void;
}) {
	const harness =
		HARNESSES.find((candidate) => candidate.id === harnessId) ?? HARNESSES[0];
	const command = harness.command?.(server.name, server.url);
	const config = harness.config(server.name, server.url);

	return (
		<div className="flex flex-col gap-2">
			<div className="flex items-center justify-between gap-2">
				<Select value={harnessId} onValueChange={onHarnessIdChange}>
					<SelectTrigger size="sm" aria-label="Connect with">
						<SelectValue />
					</SelectTrigger>
					<SelectContent>
						<SelectGroup>
							{HARNESSES.map((candidate) => (
								<SelectItem key={candidate.id} value={candidate.id}>
									{candidate.label}
								</SelectItem>
							))}
						</SelectGroup>
					</SelectContent>
				</Select>
				<a
					href={harness.docsUrl}
					target="_blank"
					rel="noreferrer"
					className="inline-flex items-center gap-1 font-mono text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
				>
					docs
					<ExternalLinkIcon className="size-3" />
				</a>
			</div>
			{command && (
				<CopySnippet
					caption="command"
					content={command}
					label="Copy command"
					successMessage="Command copied"
				/>
			)}
			<CopySnippet
				caption={harness.configFile}
				content={config}
				label="Copy config"
				successMessage={`Config copied for "${server.name}"`}
			/>
		</div>
	);
}

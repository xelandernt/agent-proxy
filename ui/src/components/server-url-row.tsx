import { CopyButton, useCopy } from "#/lib/copy";
import { cn } from "#/lib/utils";

export function ServerUrlRow({ url }: { url: string }) {
	const { copied, copy } = useCopy(url, "URL copied", url);

	return (
		<div
			className={cn(
				"flex w-full items-center justify-between gap-3 rounded-lg border bg-muted/40 py-2 pl-3 pr-2 transition-shadow duration-300",
				copied && "copy-highlight",
			)}
		>
			<span className="min-w-0 truncate font-mono text-sm text-muted-foreground">
				{url}
			</span>
			<CopyButton copied={copied} onClick={copy} label="Copy URL" />
		</div>
	);
}

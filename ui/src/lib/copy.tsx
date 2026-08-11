import { CheckIcon, CopyIcon } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "#/components/ui/button";
import { cn } from "#/lib/utils";

export function useCopy(
	value: string,
	successMessage: string,
	successDescription?: string,
) {
	const [copied, setCopied] = useState(false);

	const copy = async () => {
		try {
			await navigator.clipboard.writeText(value);
			setCopied(true);
			toast.success(
				successMessage,
				successDescription ? { description: successDescription } : undefined,
			);
			window.setTimeout(() => setCopied(false), 2000);
		} catch {
			toast.error("Could not copy");
		}
	};

	return { copied, copy };
}

export function CopyButton({
	copied,
	onClick,
	label,
	iconOnly = false,
}: {
	copied: boolean;
	onClick: () => void;
	label: string;
	iconOnly?: boolean;
}) {
	return (
		<Button
			variant="ghost"
			size={iconOnly ? "icon" : "sm"}
			onClick={onClick}
			aria-label={copied ? "Copied" : label}
			title={label}
			className={cn(iconOnly ? "shrink-0" : "-mx-1 w-fit")}
		>
			<span className="grid size-4 place-items-center">
				<CheckIcon
					className={cn(
						"col-start-1 row-start-1 transition-all duration-300",
						copied ? "scale-100 opacity-100" : "scale-50 opacity-0",
					)}
				/>
				<CopyIcon
					className={cn(
						"col-start-1 row-start-1 transition-all duration-300",
						copied ? "scale-50 opacity-0" : "scale-100 opacity-100",
					)}
				/>
			</span>
			{!iconOnly && (copied ? "Copied" : label)}
		</Button>
	);
}

export function CopySnippet({
	caption,
	content,
	label,
	successMessage,
}: {
	caption: string;
	content: string;
	label: string;
	successMessage: string;
}) {
	const { copied, copy } = useCopy(content, successMessage);
	const multiline = content.includes("\n");

	return (
		<div className="flex flex-col gap-1">
			<p className="font-mono text-[11px] text-muted-foreground">{caption}</p>
			{multiline ? (
				<>
					<pre
						className={cn(
							"overflow-x-auto rounded-md border bg-muted/40 p-3 font-mono text-xs leading-relaxed transition-shadow duration-300",
							copied && "copy-highlight",
						)}
					>
						{content}
					</pre>
					<CopyButton copied={copied} onClick={copy} label={label} />
				</>
			) : (
				<div
					className={cn(
						"flex items-center justify-between gap-2 rounded-md border bg-muted/40 py-1.5 pl-3 pr-1.5 transition-shadow duration-300",
						copied && "copy-highlight",
					)}
				>
					<span className="min-w-0 truncate font-mono text-xs text-muted-foreground">
						{content}
					</span>
					<CopyButton copied={copied} onClick={copy} label={label} iconOnly />
				</div>
			)}
		</div>
	);
}

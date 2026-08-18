import type * as React from "react";
import { cn } from "#/lib/utils";

function Input({ className, type, ...props }: React.ComponentProps<"input">) {
	return (
		<input
			type={type}
			data-slot="input"
			className={cn(
				"border-input bg-background placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-ring/50 flex h-8 w-full min-w-0 rounded-md border px-2 py-1 font-mono text-sm shadow-xs outline-none transition-[color,box-shadow] focus-visible:ring-[3px] disabled:pointer-events-none disabled:cursor-not-allowed disabled:opacity-50",
				className,
			)}
			{...props}
		/>
	);
}

export { Input };

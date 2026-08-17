import { cn } from "#/lib/utils";

export function AgentGatewayLogo({ expanded }: { expanded: boolean }) {
	return (
		<span
			className={cn(
				"group flex min-w-0 items-center font-serif text-base font-bold tracking-tight transition-transform duration-200",
				expanded ? "translate-x-1.5" : "translate-x-2.5",
			)}
		>
			<span className="inline-flex origin-left items-center whitespace-nowrap transition-transform duration-300 group-hover:scale-105">
				<span className="shrink-0 text-primary">A</span>
				<span
					className={cn(
						"overflow-hidden text-foreground transition-[max-width,opacity] duration-300 ease-out",
						expanded ? "max-w-24 opacity-100" : "max-w-0 opacity-0",
					)}
				>
					gent Gateway
				</span>
			</span>
		</span>
	);
}

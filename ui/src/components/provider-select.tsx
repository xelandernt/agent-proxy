import { Link } from "@tanstack/react-router";
import type { AdminAuthProvider } from "#/lib/admin";

export function ProviderSelect({
	providers,
	value,
	onChange,
}: {
	providers: AdminAuthProvider[];
	value: string | null;
	onChange: (value: string | null) => void;
}) {
	return (
		<div className="flex flex-col gap-1.5">
			<span className="font-mono text-xs text-muted-foreground">
				Gateway authentication
			</span>
			<select
				value={value ?? ""}
				onChange={(event) => onChange(event.target.value || null)}
				className="h-9 w-full rounded-md border bg-background px-3 font-mono text-sm focus:outline-none focus:ring-2 focus:ring-ring"
			>
				<option value="">No gateway authentication</option>
				{providers.map((provider) => (
					<option key={provider.name} value={provider.name}>
						{provider.name} ({String(provider.auth.provider ?? "unknown")})
					</option>
				))}
			</select>
			{providers.length === 0 && (
				<p className="text-xs text-muted-foreground">
					No reusable providers yet.{" "}
					<Link
						to="/admin/auth-providers/new"
						search={{ provider: undefined }}
						className="underline underline-offset-4"
					>
						Create one
					</Link>{" "}
					or leave authentication disabled.
				</p>
			)}
		</div>
	);
}

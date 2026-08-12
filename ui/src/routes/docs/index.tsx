import { createFileRoute, Link } from "@tanstack/react-router";
import { BookOpenIcon, ServerCogIcon } from "lucide-react";

import { Button } from "#/components/ui/button";
import { PROVIDER_GUIDES } from "#/lib/provider-docs/registry";
import {
	PATTERN_LABELS,
	PATTERN_ORDER,
	type ProviderPattern,
} from "#/lib/provider-docs/types";

export const Route = createFileRoute("/docs/")({ component: DocsIndex });

function DocsIndex() {
	const guides = Object.values(PROVIDER_GUIDES).sort((a, b) =>
		a.name.localeCompare(b.name),
	);
	const byPattern = (pattern: ProviderPattern) =>
		guides.filter((guide) => guide.pattern === pattern);

	return (
		<div className="page-wrap flex flex-col gap-8 py-10">
			<header className="flex items-start justify-between gap-4">
				<div>
					<p className="island-kicker mb-2">Authentication</p>
					<h1 className="display-title mb-3 text-4xl font-bold tracking-tight">
						Provider setup guides
					</h1>
				</div>
				<Link to="/admin">
					<Button variant="ghost">
						<ServerCogIcon className="size-3.5" />
						Manage servers
					</Button>
				</Link>
			</header>

			{PATTERN_ORDER.map((pattern) => {
				const entries = byPattern(pattern);
				if (entries.length === 0) return null;
				return (
					<section key={pattern} className="island-shell rounded-2xl p-8">
						<p className="island-kicker mb-1">{PATTERN_LABELS[pattern]}</p>
						<h2 className="mb-4 font-serif text-2xl font-bold">
							{pattern === "oauth-proxy"
								? "Providers with fixed application credentials"
								: pattern === "remote-oauth"
									? "Providers with tenant-level registration"
									: pattern === "token-verification"
										? "Token verification only"
										: "Gateway-internal credentials"}
						</h2>
						<div className="grid gap-3 sm:grid-cols-2">
							{entries.map((guide) => (
								<Link
									key={guide.id}
									to="/docs/$provider"
									params={{ provider: guide.id }}
									className="feature-card flex flex-col gap-1 rounded-xl border border-[var(--line)] p-4 no-underline"
								>
									<span className="flex items-center gap-2 font-semibold text-[var(--sea-ink)]">
										<BookOpenIcon className="size-4 text-[var(--lagoon-deep)]" />
										{guide.name}
									</span>
									<span className="text-sm text-[var(--sea-ink-soft)]">
										{guide.tagline}
									</span>
								</Link>
							))}
						</div>
					</section>
				);
			})}
		</div>
	);
}

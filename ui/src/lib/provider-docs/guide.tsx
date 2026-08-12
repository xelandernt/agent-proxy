import { Link } from "@tanstack/react-router";
import { ArrowLeftIcon, BookOpenIcon, ServerCogIcon } from "lucide-react";

import { Button } from "#/components/ui/button";
import { FIELD_TOOLTIPS } from "#/lib/provider-docs/fields";
import {
	type FieldEntry,
	PATTERN_LABELS,
	type ProviderGuide,
	type ProviderStep,
} from "#/lib/provider-docs/types";

function StepCard({ step, index }: { step: ProviderStep; index: number }) {
	if (step.kind === "tip" || step.kind === "warning" || step.kind === "info") {
		const styles = {
			tip: "border-[var(--line)] text-[var(--sea-ink-soft)]",
			warning: "border-destructive/40 text-destructive",
			info: "border-[var(--line)] text-[var(--sea-ink-soft)]",
		}[step.kind];
		return (
			<div
				className={`rounded-md border border-l-4 border-l-[var(--lagoon)] ${styles} bg-[var(--surface)] p-4 text-sm`}
			>
				<p className="mb-1 font-mono text-xs uppercase tracking-wider">
					{step.kind}
				</p>
				{step.title && <p className="mb-1 font-semibold">{step.title}</p>}
				<p>{step.body}</p>
			</div>
		);
	}
	return (
		<div className="flex gap-3">
			<span className="mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full border border-[var(--line)] bg-[var(--surface)] font-mono text-xs text-[var(--sea-ink)]">
				{index + 1}
			</span>
			<div className="min-w-0">
				<p className="mb-1 font-semibold text-[var(--sea-ink)]">{step.title}</p>
				<p className="text-sm text-[var(--sea-ink-soft)]">{step.body}</p>
			</div>
		</div>
	);
}

function fieldText(entry: FieldEntry): string {
	return "shared" in entry ? (FIELD_TOOLTIPS[entry.key] ?? "") : entry.text;
}

function FieldRow({ entry }: { entry: FieldEntry }) {
	const text = fieldText(entry);
	return (
		<div className="flex flex-col gap-1 border-b border-[var(--line)] py-3 last:border-b-0 sm:grid sm:grid-cols-[220px_1fr] sm:gap-4">
			<code className="w-fit min-w-0 max-w-full break-all text-xs">
				{entry.key}
			</code>
			<p className="text-sm text-[var(--sea-ink-soft)]">{text}</p>
		</div>
	);
}

export function ProviderGuidePage({ guide }: { guide: ProviderGuide }) {
	return (
		<div className="page-wrap flex flex-col gap-8 py-10">
			<div className="flex items-center justify-between">
				<Link
					to="/docs"
					className="inline-flex w-fit items-center gap-1.5 font-mono text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
				>
					<ArrowLeftIcon className="size-3" />
					All provider guides
				</Link>
				<Link to="/admin">
					<Button variant="ghost" size="sm">
						<ServerCogIcon className="size-3.5" />
						Manage servers
					</Button>
				</Link>
			</div>

			<header className="island-shell rounded-2xl p-8">
				<p className="island-kicker mb-2">Auth provider guide</p>
				<h1 className="display-title mb-3 text-4xl font-bold tracking-tight">
					{guide.name}
				</h1>
				<p className="mb-4 max-w-2xl text-[var(--sea-ink-soft)]">
					{guide.tagline}
				</p>
				<div className="flex flex-wrap items-center gap-2">
					<span className="rounded-full border border-[var(--line)] bg-[var(--chip-bg)] px-3 py-1 font-mono text-xs">
						{PATTERN_LABELS[guide.pattern]}
					</span>
				</div>
			</header>

			<section className="island-shell rounded-2xl p-8">
				<h2 className="mb-1 font-serif text-2xl font-bold">
					Configure {guide.name}
				</h2>
				<p className="mb-6 text-sm text-[var(--sea-ink-soft)]">
					Set these up in the {guide.name} console before adding the server to
					the gateway, without the code.
				</p>
				<div className="flex flex-col gap-5">
					{guide.providerSteps.map((step, index) => (
						<StepCard key={step.title} step={step} index={index} />
					))}
				</div>
			</section>

			<section className="island-shell rounded-2xl p-8">
				<h2 className="mb-1 font-serif text-2xl font-bold">
					Fill out the proxy form
				</h2>
				<p className="mb-6 text-sm text-[var(--sea-ink-soft)]">
					In the gateway admin, open{" "}
					<Link to="/admin/new" className="underline underline-offset-2">
						New server
					</Link>{" "}
					and pick <code className="text-xs">{guide.id}</code> as the provider.
					Every field below shows how to fill it in; the same text appears as a
					tooltip next to each field in the form.
				</p>
				<div>
					{guide.fields.map((entry) => (
						<FieldRow key={entry.key} entry={entry} />
					))}
				</div>
			</section>

			<div className="flex justify-center pb-4">
				<Link to="/admin/new">
					<Button size="lg">
						<BookOpenIcon className="size-4" />
						Open the form and add this server
					</Button>
				</Link>
			</div>
		</div>
	);
}

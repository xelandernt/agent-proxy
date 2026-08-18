import { createFileRoute } from "@tanstack/react-router";
import { KeyRoundIcon, PlusIcon } from "lucide-react";
import type { FormEvent } from "react";
import { useRef, useState } from "react";
import { toast } from "sonner";
import type { ApiKeyCreated } from "#/api/generated/fastAPI";
import { ApiKeyCard } from "#/components/api-key-card";
import { ModelSelection } from "#/components/model-selection";
import { Button } from "#/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "#/components/ui/card";
import {
	Empty,
	EmptyDescription,
	EmptyHeader,
	EmptyMedia,
	EmptyTitle,
} from "#/components/ui/empty";
import {
	Field,
	FieldDescription,
	FieldGroup,
	FieldLabel,
} from "#/components/ui/field";
import { Input } from "#/components/ui/input";
import {
	Popover,
	PopoverContent,
	PopoverHeader,
	PopoverTitle,
	PopoverTrigger,
} from "#/components/ui/popover";
import { AdminApiError } from "#/lib/admin";
import { CopySnippet } from "#/lib/copy";
import {
	useCreateApiKey,
	useCurrentUser,
	useUserApiKeys,
	useUserModels,
} from "#/lib/model-gateway-queries";

export const Route = createFileRoute("/account/")({ component: AccountIndex });

function AccountIndex() {
	const user = useCurrentUser();
	const models = useUserModels();
	const keys = useUserApiKeys();
	const create = useCreateApiKey();
	const [name, setName] = useState("");
	const [selection, setSelection] = useState<string[] | null>(null);
	const [created, setCreated] = useState<ApiKeyCreated | null>(null);
	const creating = useRef(false);
	const [createOpen, setCreateOpen] = useState(false);
	const modelNames = models.data?.map((model) => model.name) ?? [];
	const activeKeys = keys.data?.filter((apiKey) => !apiKey.revoked_at) ?? [];
	const selected = selection ?? modelNames;

	const submit = async (event: FormEvent) => {
		event.preventDefault();
		if (creating.current) return;
		creating.current = true;
		try {
			const result = await create.mutateAsync({
				name: name.trim(),
				models: selected,
			});
			setCreated(result);
			setName("");
			setSelection(null);
			setCreateOpen(false);
			toast.success("API key created");
		} catch (error) {
			toast.error(
				error instanceof AdminApiError
					? error.message
					: "Could not create the API key.",
			);
		} finally {
			creating.current = false;
		}
	};

	return (
		<div className="mx-auto flex w-full max-w-4xl flex-col gap-8 p-8">
			<header className="flex items-start justify-between gap-4">
				<div>
					<h1 className="font-serif text-4xl font-bold tracking-tight">
						API keys
					</h1>
					<p className="mt-2 text-sm text-muted-foreground">
						{user.data
							? `Signed in as ${user.data.email}`
							: "Manage personal model access."}
					</p>
				</div>
				<Popover open={createOpen} onOpenChange={setCreateOpen}>
					<PopoverTrigger asChild>
						<Button>
							<PlusIcon className="size-4" />
							Create API key
						</Button>
					</PopoverTrigger>
					<PopoverContent
						align="end"
						className="w-[min(28rem,calc(100vw-2rem))]"
					>
						<PopoverHeader>
							<PopoverTitle>Create API key</PopoverTitle>
						</PopoverHeader>
						<form onSubmit={submit} className="mt-4">
							<FieldGroup>
								<Field>
									<FieldLabel htmlFor="new-key-name">Name</FieldLabel>
									<Input
										id="new-key-name"
										value={name}
										onChange={(event) => setName(event.target.value)}
										placeholder="Local development"
										required
									/>
								</Field>
								<Field>
									<FieldLabel>Allowed models</FieldLabel>
									{modelNames.length ? (
										<ModelSelection
											names={modelNames}
											selected={selected}
											onChange={setSelection}
										/>
									) : (
										<FieldDescription>
											No models are configured yet. Ask an administrator to
											create one.
										</FieldDescription>
									)}
								</Field>
								<Button
									type="submit"
									className="self-end"
									disabled={
										create.isPending || !name.trim() || selected.length === 0
									}
								>
									{create.isPending ? "Creating…" : "Create API key"}
								</Button>
							</FieldGroup>
						</form>
					</PopoverContent>
				</Popover>
			</header>

			{created && (
				<Card className="border-primary/50">
					<CardHeader>
						<CardTitle>Copy your new key now</CardTitle>
						<CardDescription>
							For security, the full key will not be shown again.
						</CardDescription>
					</CardHeader>
					<CardContent>
						<CopySnippet
							caption={created.name}
							content={created.key}
							label="Copy API key"
							successMessage="API key copied"
						/>
					</CardContent>
				</Card>
			)}

			<section className="flex flex-col gap-4">
				<h2 className="font-serif text-2xl font-semibold">Existing keys</h2>
				{keys.isLoading && (
					<p className="text-sm text-muted-foreground">Loading…</p>
				)}
				{keys.isError && (
					<p className="text-sm text-destructive">
						{keys.error instanceof Error
							? keys.error.message
							: String(keys.error)}
					</p>
				)}
				{keys.isSuccess && activeKeys.length === 0 && (
					<Empty>
						<EmptyMedia variant="icon">
							<KeyRoundIcon />
						</EmptyMedia>
						<EmptyHeader>
							<EmptyTitle>No API keys yet</EmptyTitle>
							<EmptyDescription>
								Create a key above to call <code>/v1/responses</code>.
							</EmptyDescription>
						</EmptyHeader>
					</Empty>
				)}
				{activeKeys.length > 0 && (
					<div className="overflow-x-auto rounded-lg border">
						<table className="w-full min-w-[50rem] text-left text-sm">
							<thead className="bg-muted/40 text-xs uppercase tracking-wide text-muted-foreground">
								<tr>
									<th scope="col" className="px-4 py-3 font-medium">
										Name
									</th>
									<th scope="col" className="px-4 py-3 font-medium">
										Key prefix
									</th>
									<th scope="col" className="px-4 py-3 font-medium">
										Allowed models
									</th>
									<th scope="col" className="px-4 py-3 font-medium">
										Created
									</th>
									<th scope="col" className="px-4 py-3 font-medium">
										Last used
									</th>
									<th scope="col" className="px-4 py-3 text-right font-medium">
										Actions
									</th>
								</tr>
							</thead>
							<tbody>
								{activeKeys.map((apiKey) => (
									<ApiKeyCard
										key={apiKey.id}
										apiKey={apiKey}
										models={modelNames}
									/>
								))}
							</tbody>
						</table>
					</div>
				)}
			</section>
		</div>
	);
}

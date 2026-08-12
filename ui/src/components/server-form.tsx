import { Link } from "@tanstack/react-router";
import { ArrowLeftIcon, BookOpenIcon, Loader2Icon } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";
import { toast } from "sonner";
import type {
	ServerCreateRequest,
	ServerCreateRequestAuth,
	ServerUpdateRequest,
} from "#/api/generated/fastAPI";
import {
	AuthProviderForm,
	type AuthProviderSchema,
} from "#/components/auth-provider-form";
import { Button } from "#/components/ui/button";
import {
	Card,
	CardContent,
	CardFooter,
	CardHeader,
} from "#/components/ui/card";
import { AdminApiError, type FieldError } from "#/lib/admin";
import {
	useAuthSchema,
	useCreateServer,
	useUpdateServer,
} from "#/lib/admin-queries";
import { cn } from "#/lib/utils";

type FormState =
	| { status: "loading" }
	| { status: "error"; message: string }
	| { status: "ready"; schema: AuthProviderSchema };

function TextField({
	label,
	value,
	onChange,
	placeholder,
	error,
	type = "text",
}: {
	label: string;
	value: string;
	onChange: (value: string) => void;
	placeholder?: string;
	error?: string;
	type?: string;
}) {
	return (
		<div className="flex flex-col gap-1.5">
			<span className="font-mono text-xs text-muted-foreground">{label}</span>
			<input
				type={type}
				value={value}
				onChange={(event) => onChange(event.target.value)}
				placeholder={placeholder}
				className={cn(
					"h-9 w-full rounded-md border bg-transparent px-3 font-mono text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring",
					error && "border-destructive",
				)}
			/>
			{error && <span className="text-xs text-destructive">{error}</span>}
		</div>
	);
}

export function ServerForm({
	title,
	description,
	mode,
	initial,
	onDone,
	onCancelHref,
}: {
	title: string;
	description: string;
	mode: "create" | "edit";
	initial?: {
		name?: string;
		description: string;
		upstream_url: string;
		auth: Record<string, unknown>;
		verify_upstream_tls: boolean;
		forward_client_credentials: boolean;
	};
	onDone: () => void;
	onCancelHref: string;
}) {
	const [name, setName] = useState(initial?.name ?? "");
	const [descriptionText, setDescriptionText] = useState(
		initial?.description ?? "",
	);
	const [upstreamUrl, setUpstreamUrl] = useState(initial?.upstream_url ?? "");
	const [verifyTls, setVerifyTls] = useState(
		initial?.verify_upstream_tls ?? true,
	);
	const [forwardClientCredentials, setForwardClientCredentials] = useState(
		initial?.forward_client_credentials ?? false,
	);
	const [auth, setAuth] = useState<Record<string, unknown>>(
		initial?.auth ?? {},
	);
	const [fieldErrors, setFieldErrors] = useState<FieldError[]>([]);
	const [saving, setSaving] = useState(false);
	const authSchemaQuery = useAuthSchema();
	const createMutation = useCreateServer();
	const updateMutation = useUpdateServer();

	const state: FormState = authSchemaQuery.isLoading
		? { status: "loading" }
		: authSchemaQuery.isError
			? {
					status: "error",
					message:
						authSchemaQuery.error instanceof Error
							? authSchemaQuery.error.message
							: String(authSchemaQuery.error),
				}
			: authSchemaQuery.isSuccess
				? {
						status: "ready",
						schema: authSchemaQuery.data,
					}
				: { status: "error", message: "Could not load the form." };

	const submit = async (event: FormEvent) => {
		event.preventDefault();
		setFieldErrors([]);
		// The live backend schema builds this value; the API remains the
		// authoritative validator for provider-specific field combinations.
		const authPayload = auth as unknown as ServerCreateRequestAuth;
		const common = {
			description: descriptionText,
			upstream_url: upstreamUrl,
			auth: authPayload,
			verify_upstream_tls: verifyTls,
			forward_client_credentials: forwardClientCredentials,
		};
		setSaving(true);
		try {
			if (mode === "create") {
				const payload: ServerCreateRequest = { name, ...common };
				await createMutation.mutateAsync(payload);
			} else if (initial?.name) {
				const payload: ServerUpdateRequest = common;
				await updateMutation.mutateAsync({
					name: initial.name,
					payload,
				});
			}
			toast.success(mode === "create" ? "Server created" : "Server updated");
			onDone();
		} catch (error) {
			setSaving(false);
			if (error instanceof AdminApiError) {
				setFieldErrors(error.fieldErrors);
				toast.error(error.message);
			} else {
				toast.error("Failed to save server.");
			}
		}
	};

	const errorFor = (path: string) =>
		fieldErrors.find((entry) => entry.field === path)?.message;

	return (
		<form
			onSubmit={submit}
			className="mx-auto flex w-full max-w-2xl flex-col gap-6 p-8"
		>
			<div className="flex items-center justify-between">
				<Link
					to="/admin"
					className="inline-flex w-fit items-center gap-1.5 font-mono text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
				>
					<ArrowLeftIcon className="size-3" />
					Back to servers
				</Link>
				<Link
					to="/docs"
					className="inline-flex items-center gap-1.5 font-mono text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
				>
					<BookOpenIcon className="size-3.5" />
					Provider Docs
				</Link>
			</div>

			<Card>
				<CardHeader className="flex flex-col items-start gap-2">
					<h1 className="bg-gradient-to-b from-foreground to-foreground/55 bg-clip-text font-serif text-3xl font-bold tracking-tight text-transparent">
						{title}
					</h1>
					<p className="text-sm text-muted-foreground">{description}</p>
				</CardHeader>

				{state.status === "loading" && (
					<CardContent>
						<p className="text-sm text-muted-foreground">Loading…</p>
					</CardContent>
				)}
				{state.status === "error" && (
					<CardContent>
						<p className="text-sm text-destructive">{state.message}</p>
					</CardContent>
				)}
				{state.status === "ready" && (
					<>
						<CardContent className="flex flex-col gap-4">
							{mode === "create" && (
								<TextField
									label="Name *"
									value={name}
									onChange={setName}
									placeholder="calendar"
									error={errorFor("name")}
								/>
							)}
							<TextField
								label="Description"
								value={descriptionText}
								onChange={setDescriptionText}
								placeholder="What does this server expose?"
								error={errorFor("description")}
							/>
							<TextField
								label="Upstream URL *"
								type="url"
								value={upstreamUrl}
								onChange={setUpstreamUrl}
								placeholder="http://calendar.internal:8000/mcp"
								error={errorFor("upstream_url")}
							/>
							<div className="flex items-center gap-2">
								<input
									id="verify-tls"
									type="checkbox"
									checked={verifyTls}
									onChange={(event) => setVerifyTls(event.target.checked)}
									className="size-4 rounded border-border accent-[var(--color-primary)]"
								/>
								<label
									htmlFor="verify-tls"
									className="font-mono text-xs text-muted-foreground"
								>
									verify_upstream_tls
								</label>
							</div>
							<div className="flex items-center gap-2">
								<input
									id="forward-client-credentials"
									type="checkbox"
									checked={forwardClientCredentials}
									onChange={(event) =>
										setForwardClientCredentials(event.target.checked)
									}
									className="size-4 rounded border-border accent-[var(--color-primary)]"
								/>
								<label
									htmlFor="forward-client-credentials"
									className="font-mono text-xs text-muted-foreground"
								>
									forward_client_credentials
								</label>
							</div>
						</CardContent>

						<div className="rounded-md border p-4">
							<p className="mb-3 font-mono text-xs font-medium uppercase tracking-[0.2em] text-kicker">
								Authentication
							</p>
							<AuthProviderForm
								schema={state.schema}
								value={auth}
								onChange={setAuth}
								fieldErrors={fieldErrors}
							/>
						</div>

						<CardFooter className="justify-end gap-2">
							<Link to={onCancelHref}>
								<Button type="button" variant="ghost">
									Cancel
								</Button>
							</Link>
							<Button type="submit" disabled={saving}>
								{saving && <Loader2Icon className="size-4 animate-spin" />}
								{mode === "create" ? "Create server" : "Save changes"}
							</Button>
						</CardFooter>
					</>
				)}
			</Card>
		</form>
	);
}

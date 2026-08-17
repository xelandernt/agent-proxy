import { Link } from "@tanstack/react-router";
import { ArrowLeftIcon, Loader2Icon } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";
import { toast } from "sonner";
import type {
	ServerCreateRequest,
	ServerUpdateRequest,
} from "#/api/generated/fastAPI";
import { ProviderSelect } from "#/components/provider-select";
import { Button } from "#/components/ui/button";
import {
	Card,
	CardContent,
	CardFooter,
	CardHeader,
} from "#/components/ui/card";
import {
	Tooltip,
	TooltipContent,
	TooltipProvider,
	TooltipTrigger,
} from "#/components/ui/tooltip";
import { AdminApiError, type FieldError } from "#/lib/admin";
import {
	useAdminAuthProviders,
	useCreateServer,
	useUpdateServer,
} from "#/lib/admin-queries";
import { cn } from "#/lib/utils";

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
		auth_provider: string | null;
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
	const [authProvider, setAuthProvider] = useState<string | null>(
		initial?.auth_provider ?? null,
	);
	const [fieldErrors, setFieldErrors] = useState<FieldError[]>([]);
	const [saving, setSaving] = useState(false);
	const providersQuery = useAdminAuthProviders();
	const createMutation = useCreateServer();
	const updateMutation = useUpdateServer();

	const submit = async (event: FormEvent) => {
		event.preventDefault();
		setFieldErrors([]);
		const common = {
			description: descriptionText,
			upstream_url: upstreamUrl,
			auth_provider: authProvider,
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
		<TooltipProvider delayDuration={250}>
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
				</div>

				<Card>
					<CardHeader className="flex flex-col items-start gap-2">
						<h1 className="bg-gradient-to-b from-foreground to-foreground/55 bg-clip-text font-serif text-3xl font-bold tracking-tight text-transparent">
							{title}
						</h1>
						<p className="text-sm text-muted-foreground">{description}</p>
					</CardHeader>

					{providersQuery.isLoading && (
						<CardContent>
							<p className="text-sm text-muted-foreground">Loading…</p>
						</CardContent>
					)}
					{providersQuery.isError && (
						<CardContent>
							<p className="text-sm text-destructive">
								{providersQuery.error instanceof Error
									? providersQuery.error.message
									: String(providersQuery.error)}
							</p>
						</CardContent>
					)}
					{providersQuery.isSuccess && (
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
								<Tooltip>
									<TooltipTrigger asChild>
										<label
											htmlFor="verify-tls"
											className="flex w-fit items-center gap-2 font-mono text-xs text-muted-foreground"
										>
											<input
												id="verify-tls"
												type="checkbox"
												checked={verifyTls}
												onChange={(event) => setVerifyTls(event.target.checked)}
												className="size-4 rounded border-border accent-[var(--color-primary)]"
											/>
											verify_upstream_tls
										</label>
									</TooltipTrigger>
									<TooltipContent side="right">
										Verify the upstream server's TLS certificate and hostname.
									</TooltipContent>
								</Tooltip>
								<ProviderSelect
									providers={providersQuery.data}
									value={authProvider}
									onChange={(next) => {
										setAuthProvider(next);
										if (next !== null) setForwardClientCredentials(false);
									}}
								/>
								<Tooltip>
									<TooltipTrigger asChild>
										<label
											htmlFor="forward-client-credentials"
											className="flex w-fit items-center gap-2 font-mono text-xs text-muted-foreground"
										>
											<input
												id="forward-client-credentials"
												type="checkbox"
												checked={forwardClientCredentials}
												disabled={authProvider !== null}
												onChange={(event) =>
													setForwardClientCredentials(event.target.checked)
												}
												className="size-4 rounded border-border accent-[var(--color-primary)]"
											/>
											forward_client_credentials
										</label>
									</TooltipTrigger>
									<TooltipContent side="right">
										Pass the incoming Authorization header through to the
										upstream server. This requires gateway authentication to be
										disabled.
									</TooltipContent>
								</Tooltip>
							</CardContent>

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
		</TooltipProvider>
	);
}

import { Link } from "@tanstack/react-router";
import { ArrowLeftIcon, Loader2Icon } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";
import { toast } from "sonner";
import type {
	AuthProviderCreateRequest,
	AuthProviderUpdateRequest,
	AuthProviderView,
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
	useCreateAuthProvider,
	useUpdateAuthProvider,
} from "#/lib/admin-queries";

export function AuthProviderEditor({
	mode,
	initial,
	initialProvider,
	onDone,
}: {
	mode: "create" | "edit";
	initial?: AuthProviderView;
	initialProvider?: string;
	onDone: () => void;
}) {
	const [name, setName] = useState(initial?.name ?? "");
	const [auth, setAuth] = useState<Record<string, unknown>>(
		(initial?.auth as Record<string, unknown> | undefined) ??
			(initialProvider ? { provider: initialProvider } : {}),
	);
	const [fieldErrors, setFieldErrors] = useState<FieldError[]>([]);
	const [saving, setSaving] = useState(false);
	const schemaQuery = useAuthSchema();
	const createMutation = useCreateAuthProvider();
	const updateMutation = useUpdateAuthProvider();

	const submit = async (event: FormEvent) => {
		event.preventDefault();
		setFieldErrors([]);
		setSaving(true);
		try {
			if (mode === "create") {
				const payload: AuthProviderCreateRequest = {
					name,
					auth: auth as unknown as AuthProviderCreateRequest["auth"],
				};
				await createMutation.mutateAsync(payload);
			} else if (initial) {
				const payload: AuthProviderUpdateRequest = {
					auth: auth as unknown as AuthProviderUpdateRequest["auth"],
				};
				await updateMutation.mutateAsync({ name: initial.name, payload });
			}
			toast.success(
				mode === "create" ? "Provider created" : "Provider updated",
			);
			onDone();
		} catch (error) {
			setSaving(false);
			if (error instanceof AdminApiError) {
				setFieldErrors(error.fieldErrors);
				toast.error(error.message);
			} else {
				toast.error("Failed to save provider.");
			}
		}
	};

	const content = schemaQuery.isLoading
		? "Loading provider schema…"
		: schemaQuery.isError
			? schemaQuery.error instanceof Error
				? schemaQuery.error.message
				: String(schemaQuery.error)
			: null;

	return (
		<form
			onSubmit={submit}
			className="mx-auto flex w-full max-w-2xl flex-col gap-6 p-8"
		>
			<div className="flex items-center justify-between">
				<Link
					to="/admin/auth-providers"
					className="inline-flex items-center gap-1.5 font-mono text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
				>
					<ArrowLeftIcon className="size-3" />
					Back to providers
				</Link>
				<Link
					to="/docs"
					className="font-mono text-xs text-muted-foreground underline underline-offset-4 hover:text-foreground"
				>
					Provider docs
				</Link>
			</div>
			<Card>
				<CardHeader>
					<h1 className="font-serif text-3xl font-bold tracking-tight">
						{mode === "create"
							? "New authentication provider"
							: `Edit ${initial?.name}`}
					</h1>
					<p className="text-sm text-muted-foreground">
						{mode === "create"
							? "Create a reusable definition before linking it to servers."
							: "Changes take effect immediately on every linked server. Existing credentials are never returned, so enter replacement values when editing."}
					</p>
				</CardHeader>
				{content ? (
					<CardContent>
						<p
							className={
								schemaQuery.isError
									? "text-sm text-destructive"
									: "text-sm text-muted-foreground"
							}
						>
							{content}
						</p>
					</CardContent>
				) : (
					<>
						<CardContent className="flex flex-col gap-4">
							{mode === "create" && (
								<div className="flex flex-col gap-1.5">
									<label
										htmlFor="provider-name"
										className="font-mono text-xs text-muted-foreground"
									>
										Name *
									</label>
									<input
										id="provider-name"
										value={name}
										onChange={(event) => setName(event.target.value)}
										className="h-9 rounded-md border bg-transparent px-3 font-mono text-sm"
									/>
									{fieldErrors.find((error) => error.field === "name")
										?.message && (
										<span className="text-xs text-destructive">
											{
												fieldErrors.find((error) => error.field === "name")
													?.message
											}
										</span>
									)}
								</div>
							)}
							<AuthProviderForm
								schema={schemaQuery.data as AuthProviderSchema}
								value={auth}
								onChange={setAuth}
								fieldErrors={fieldErrors}
								fieldPath="auth"
							/>
						</CardContent>
						<CardFooter className="justify-end gap-2">
							<Link to="/admin/auth-providers">
								<Button type="button" variant="ghost">
									Cancel
								</Button>
							</Link>
							<Button type="submit" disabled={saving}>
								{saving && <Loader2Icon className="size-4 animate-spin" />}
								{mode === "create" ? "Create provider" : "Save changes"}
							</Button>
						</CardFooter>
					</>
				)}
			</Card>
		</form>
	);
}

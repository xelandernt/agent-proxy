import { Trash2Icon } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";
import { toast } from "sonner";
import type { ApiKeyView } from "#/api/generated/fastAPI";
import { ModelSelection } from "#/components/model-selection";
import { Badge } from "#/components/ui/badge";
import { Button } from "#/components/ui/button";
import {
	Card,
	CardContent,
	CardDescription,
	CardHeader,
	CardTitle,
} from "#/components/ui/card";
import { Field, FieldLabel } from "#/components/ui/field";
import { Input } from "#/components/ui/input";
import { AdminApiError } from "#/lib/admin";
import { useRevokeApiKey, useUpdateApiKey } from "#/lib/model-gateway-queries";

type ApiKeyCardProps = {
	apiKey: ApiKeyView;
	models: string[];
};

export function ApiKeyCard({ apiKey, models }: ApiKeyCardProps) {
	const revokedAt = apiKey.revoked_at;
	const [selected, setSelected] = useState(apiKey.models);
	const update = useUpdateApiKey();
	const revoke = useRevokeApiKey();

	const save = async (event: FormEvent<HTMLFormElement>) => {
		event.preventDefault();
		if (update.isPending) return;
		const form = new FormData(event.currentTarget);
		const name = String(form.get("name") ?? "").trim();
		try {
			await update.mutateAsync({
				id: apiKey.id,
				payload: { name, models: selected },
			});
			toast.success(`Updated ${name}`);
		} catch (error) {
			toast.error(
				error instanceof AdminApiError
					? error.message
					: "Could not update the API key.",
			);
		}
	};

	const remove = async () => {
		if (
			revoke.isPending ||
			!window.confirm(`Revoke API key "${apiKey.name}"? This cannot be undone.`)
		) {
			return;
		}
		try {
			await revoke.mutateAsync(apiKey.id);
			toast.success(`Revoked ${apiKey.name}`);
		} catch (error) {
			toast.error(
				error instanceof AdminApiError
					? error.message
					: "Could not revoke the API key.",
			);
		}
	};

	return (
		<Card>
			<CardHeader>
				<CardTitle className="flex items-center justify-between gap-3 text-base">
					<span className="flex items-center gap-2">
						{apiKey.name}
						{revokedAt && <Badge variant="secondary">Revoked</Badge>}
					</span>
					<code className="text-xs font-normal text-muted-foreground">
						{apiKey.prefix}…
					</code>
				</CardTitle>
				<CardDescription>
					Created {new Date(apiKey.created_at).toLocaleString()}
					{apiKey.last_used_at
						? ` · Last used ${new Date(apiKey.last_used_at).toLocaleString()}`
						: " · Never used"}
				</CardDescription>
			</CardHeader>
			<CardContent>
				{revokedAt ? (
					<p className="text-sm text-muted-foreground">
						Revoked {new Date(revokedAt).toLocaleString()}. This key no longer
						has access to any model.
					</p>
				) : (
					<form onSubmit={save} className="flex flex-col gap-4">
						<Field>
							<FieldLabel htmlFor={`key-${apiKey.id}`}>Name</FieldLabel>
							<Input
								id={`key-${apiKey.id}`}
								name="name"
								defaultValue={apiKey.name}
								required
							/>
						</Field>
						<Field>
							<FieldLabel>Allowed models</FieldLabel>
							<ModelSelection
								names={models}
								selected={selected}
								onChange={setSelected}
							/>
						</Field>
						<div className="flex justify-end gap-2">
							<Button
								type="button"
								variant="outline"
								className="text-destructive"
								disabled={revoke.isPending}
								onClick={() => void remove()}
							>
								<Trash2Icon className="size-3.5" />
								{revoke.isPending ? "Revoking…" : "Revoke"}
							</Button>
							<Button
								type="submit"
								disabled={update.isPending || selected.length === 0}
							>
								{update.isPending ? "Saving…" : "Save access"}
							</Button>
						</div>
					</form>
				)}
			</CardContent>
		</Card>
	);
}

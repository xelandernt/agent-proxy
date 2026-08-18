import { MoreHorizontalIcon, PencilIcon, Trash2Icon } from "lucide-react";
import type { FormEvent } from "react";
import { useState } from "react";
import { toast } from "sonner";
import type { ApiKeyView } from "#/api/generated/fastAPI";
import { ModelSelection } from "#/components/model-selection";
import { Badge } from "#/components/ui/badge";
import { Button } from "#/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "#/components/ui/dropdown-menu";
import { Field, FieldLabel } from "#/components/ui/field";
import { Input } from "#/components/ui/input";
import {
	Popover,
	PopoverContent,
	PopoverHeader,
	PopoverTitle,
} from "#/components/ui/popover";
import { AdminApiError } from "#/lib/admin";
import { useDeleteApiKey, useUpdateApiKey } from "#/lib/model-gateway-queries";

type ApiKeyCardProps = {
	apiKey: ApiKeyView;
	models: string[];
};

function formatDate(value: string | null) {
	return value ? new Date(value).toLocaleString() : "Never";
}

export function ApiKeyCard({ apiKey, models }: ApiKeyCardProps) {
	const [editOpen, setEditOpen] = useState(false);
	const [deleted, setDeleted] = useState(false);
	const [name, setName] = useState(apiKey.name);
	const [selected, setSelected] = useState(apiKey.models);
	const update = useUpdateApiKey();
	const removeKey = useDeleteApiKey();

	const save = async (event: FormEvent<HTMLFormElement>) => {
		event.preventDefault();
		if (update.isPending) return;
		try {
			await update.mutateAsync({
				id: apiKey.id,
				payload: { name: name.trim(), models: selected },
			});
			setEditOpen(false);
			toast.success(`Updated ${name.trim()}`);
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
			removeKey.isPending ||
			!window.confirm(`Delete API key "${apiKey.name}"? This cannot be undone.`)
		) {
			return;
		}
		try {
			await removeKey.mutateAsync(apiKey.id);
			setDeleted(true);
			toast.success(`Deleted ${apiKey.name}`);
		} catch (error) {
			toast.error(
				error instanceof AdminApiError
					? error.message
					: "Could not delete the API key.",
			);
		}
	};

	if (deleted) return null;

	return (
		<tr className="border-b last:border-0">
			<td className="px-4 py-3 align-top font-medium">{apiKey.name}</td>
			<td className="px-4 py-3 align-top">
				<code className="text-xs text-muted-foreground">{apiKey.prefix}…</code>
			</td>
			<td className="max-w-64 px-4 py-3 align-top">
				<div className="flex flex-wrap gap-1">
					{apiKey.models.map((model) => (
						<Badge key={model} variant="outline" className="font-mono text-xs">
							{model}
						</Badge>
					))}
				</div>
			</td>
			<td className="whitespace-nowrap px-4 py-3 align-top text-sm text-muted-foreground">
				{formatDate(apiKey.created_at)}
			</td>
			<td className="whitespace-nowrap px-4 py-3 align-top text-sm text-muted-foreground">
				{formatDate(apiKey.last_used_at)}
			</td>
			<td className="px-4 py-3 text-right align-top">
				<Popover
					open={editOpen}
					onOpenChange={(open) => {
						setEditOpen(open);
						if (open) {
							setName(apiKey.name);
							setSelected(apiKey.models);
						}
					}}
				>
					<DropdownMenu>
						<DropdownMenuTrigger asChild>
							<Button
								variant="outline"
								size="icon"
								aria-label={`Actions for ${apiKey.name}`}
							>
								<MoreHorizontalIcon className="size-4" />
							</Button>
						</DropdownMenuTrigger>
						<DropdownMenuContent align="end">
							<DropdownMenuItem onSelect={() => setEditOpen(true)}>
								<PencilIcon />
								Edit API key
							</DropdownMenuItem>
							<DropdownMenuItem
								variant="destructive"
								disabled={removeKey.isPending}
								onSelect={(event) => {
									event.preventDefault();
									void remove();
								}}
							>
								<Trash2Icon />
								Delete API key
							</DropdownMenuItem>
						</DropdownMenuContent>
					</DropdownMenu>
					<PopoverContent
						align="end"
						className="w-[min(28rem,calc(100vw-2rem))]"
					>
						<PopoverHeader>
							<PopoverTitle>Edit API key</PopoverTitle>
						</PopoverHeader>
						<form onSubmit={save} className="mt-4 flex flex-col gap-4">
							<Field>
								<FieldLabel htmlFor={`key-${apiKey.id}`}>Name</FieldLabel>
								<Input
									id={`key-${apiKey.id}`}
									value={name}
									onChange={(event) => setName(event.target.value)}
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
							<Button
								type="submit"
								disabled={
									update.isPending || !name.trim() || selected.length === 0
								}
							>
								{update.isPending ? "Saving…" : "Save changes"}
							</Button>
						</form>
					</PopoverContent>
				</Popover>
			</td>
		</tr>
	);
}

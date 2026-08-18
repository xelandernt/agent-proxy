import { ChevronDownIcon } from "lucide-react";
import { Button } from "#/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuCheckboxItem,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuLabel,
	DropdownMenuTrigger,
} from "#/components/ui/dropdown-menu";

type ModelSelectionProps = {
	names: string[];
	selected: string[];
	onChange: (next: string[]) => void;
};

export function ModelSelection({
	names,
	selected,
	onChange,
}: ModelSelectionProps) {
	const chosen = new Set(selected);
	const summary =
		selected.length === 0
			? "Select models"
			: selected.length === 1
				? selected[0]
				: `${selected.length} models selected`;

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button
					type="button"
					variant="outline"
					className="w-full justify-between font-normal"
					aria-label={`Allowed models: ${summary}`}
				>
					<span className="truncate">{summary}</span>
					<ChevronDownIcon data-icon="inline-end" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="start" className="max-h-72 min-w-64">
				<DropdownMenuGroup>
					<DropdownMenuLabel>Allowed models</DropdownMenuLabel>
					{names.map((name) => (
						<DropdownMenuCheckboxItem
							key={name}
							checked={chosen.has(name)}
							onSelect={(event) => event.preventDefault()}
							onCheckedChange={(checked) =>
								onChange(
									checked
										? names.filter(
												(entry) => chosen.has(entry) || entry === name,
											)
										: selected.filter((entry) => entry !== name),
								)
							}
						>
							<code>{name}</code>
						</DropdownMenuCheckboxItem>
					))}
				</DropdownMenuGroup>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}

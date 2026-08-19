import { ChevronDownIcon } from "lucide-react";
import { Button } from "#/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuCheckboxItem,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuLabel,
	DropdownMenuSeparator,
	DropdownMenuTrigger,
} from "#/components/ui/dropdown-menu";

type FilterItem = { value: string; label: string };

export function FilterMultiSelect({
	label,
	allLabel,
	items,
	selected,
	onChange,
}: {
	label: string;
	allLabel: string;
	items: FilterItem[];
	selected: string[];
	onChange: (selected: string[]) => void;
}) {
	const chosen = new Set(selected);
	const summary =
		selected.length === 0
			? allLabel
			: selected.length === 1
				? (items.find((item) => item.value === selected[0])?.label ??
					selected[0])
				: `${selected.length} selected`;

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button
					type="button"
					variant="outline"
					className="w-full justify-between font-normal"
					aria-label={`${label}: ${summary}`}
				>
					<span className="truncate">{summary}</span>
					<ChevronDownIcon data-icon="inline-end" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="start" className="max-h-72 min-w-64">
				<DropdownMenuGroup>
					<DropdownMenuLabel>{label}</DropdownMenuLabel>
					<DropdownMenuCheckboxItem
						checked={selected.length === 0}
						onSelect={(event) => event.preventDefault()}
						onCheckedChange={() => onChange([])}
					>
						{allLabel}
					</DropdownMenuCheckboxItem>
					<DropdownMenuSeparator />
					{items.map((item) => (
						<DropdownMenuCheckboxItem
							key={item.value}
							checked={chosen.has(item.value)}
							onSelect={(event) => event.preventDefault()}
							onCheckedChange={(checked) =>
								onChange(
									checked
										? items
												.filter(
													(entry) =>
														chosen.has(entry.value) ||
														entry.value === item.value,
												)
												.map((entry) => entry.value)
										: selected.filter((value) => value !== item.value),
								)
							}
						>
							{item.label}
						</DropdownMenuCheckboxItem>
					))}
				</DropdownMenuGroup>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}

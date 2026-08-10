import {
	CheckIcon,
	MonitorIcon,
	MoonIcon,
	SunIcon,
	WavesIcon,
} from "lucide-react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { Button } from "#/components/ui/button";
import {
	DropdownMenu,
	DropdownMenuContent,
	DropdownMenuGroup,
	DropdownMenuItem,
	DropdownMenuTrigger,
} from "#/components/ui/dropdown-menu";
import {
	isDitherEnabled,
	setDitherEnabled,
	subscribeDither,
} from "#/lib/dither";
import { cn } from "#/lib/utils";

export function DitherToggle() {
	const enabled = useSyncExternalStore(
		subscribeDither,
		isDitherEnabled,
		() => false,
	);

	return (
		<Button
			variant="ghost"
			size="icon"
			aria-label="Toggle background animation"
			aria-pressed={enabled}
			onClick={() => setDitherEnabled(!enabled)}
		>
			<WavesIcon className={cn("size-4", enabled && "text-lagoon")} />
		</Button>
	);
}

export function ThemeToggle() {
	const { setTheme, theme } = useTheme();

	const options = [
		{ value: "light", label: "Light", icon: SunIcon },
		{ value: "dark", label: "Dark", icon: MoonIcon },
		{ value: "system", label: "System", icon: MonitorIcon },
	] as const;

	return (
		<DropdownMenu>
			<DropdownMenuTrigger asChild>
				<Button variant="ghost" size="icon" aria-label="Toggle theme">
					<SunIcon className="hidden size-4 dark:block" />
					<MoonIcon className="size-4 dark:hidden" />
				</Button>
			</DropdownMenuTrigger>
			<DropdownMenuContent align="end">
				<DropdownMenuGroup>
					{options.map((option) => (
						<DropdownMenuItem
							key={option.value}
							onClick={() => setTheme(option.value)}
						>
							<option.icon />
							{option.label}
							{theme === option.value && <CheckIcon className="ml-auto" />}
						</DropdownMenuItem>
					))}
				</DropdownMenuGroup>
			</DropdownMenuContent>
		</DropdownMenu>
	);
}

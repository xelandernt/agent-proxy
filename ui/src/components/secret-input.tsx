import { EyeIcon, EyeOffIcon } from "lucide-react";
import { useState } from "react";
import {
	InputGroup,
	InputGroupAddon,
	InputGroupButton,
	InputGroupInput,
} from "#/components/ui/input-group";

export function SecretInput({
	id,
	label,
	value,
	onChange,
	required = false,
	stored = false,
}: {
	id?: string;
	label: string;
	value: string;
	onChange: (value: string) => void;
	required?: boolean;
	stored?: boolean;
}) {
	const [visible, setVisible] = useState(false);
	return (
		<InputGroup>
			<InputGroupInput
				id={id}
				type={visible ? "text" : "password"}
				value={value}
				onChange={(event) => onChange(event.target.value)}
				placeholder={
					stored ? "Stored value — enter to replace" : "Enter a value"
				}
				required={required}
				autoComplete="new-password"
				aria-label={label}
			/>
			<InputGroupAddon align="inline-end">
				<InputGroupButton
					onClick={() => setVisible((current) => !current)}
					aria-label={`${visible ? "Hide" : "Show"} ${label}`}
					aria-pressed={visible}
				>
					{visible ? <EyeOffIcon /> : <EyeIcon />}
				</InputGroupButton>
			</InputGroupAddon>
		</InputGroup>
	);
}

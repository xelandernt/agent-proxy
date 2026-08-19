import type { ModelPricingView } from "#/api/generated/fastAPI";
import { Badge } from "#/components/ui/badge";
import { formatModelPrice } from "#/lib/model-pricing";

export function ModelPricingSummary({
	pricing,
}: {
	pricing: ModelPricingView | null;
}) {
	if (!pricing) return null;
	const rows = [
		["Input", pricing.input_usd_per_million_tokens],
		["Cached input", pricing.cached_input_usd_per_million_tokens],
		["Output", pricing.output_usd_per_million_tokens],
	];

	return (
		<div className="flex flex-col gap-3">
			<Badge variant="secondary" className="w-fit">
				{pricing.is_custom ? "Custom pricing" : "Automatic pricing"}
			</Badge>
			<dl className="grid grid-cols-[1fr_auto] gap-x-4 gap-y-1 text-xs">
				{rows.map(([label, value]) => (
					<div key={label} className="contents">
						<dt className="text-muted-foreground">{label}</dt>
						<dd className="font-mono text-right">
							{formatModelPrice(value)} / 1M
						</dd>
					</div>
				))}
			</dl>
		</div>
	);
}

import { FIELD_TOOLTIPS } from "./fields";
import type { ProviderGuide } from "./types";

type GuideModule = { guide: ProviderGuide };

const modules = import.meta.glob<GuideModule>("./guides/*.ts", {
	eager: true,
});

export const PROVIDER_GUIDES: Record<string, ProviderGuide> =
	Object.fromEntries(
		Object.entries(modules).map(([, module]) => [
			module.guide.id,
			module.guide,
		]),
	);

export function getProviderGuide(id: string): ProviderGuide | undefined {
	return PROVIDER_GUIDES[id];
}

export function hasProviderGuide(id: string): boolean {
	return id in PROVIDER_GUIDES;
}

/** Tooltip text for a form field: provider-specific text wins, shared text is the fallback. */
export function getFieldTooltip(
	providerId: string,
	key: string,
): string | undefined {
	const guide = PROVIDER_GUIDES[providerId];
	const entry = guide?.fields.find((field) => field.key === key);
	if (entry && !("shared" in entry)) return entry.text;
	return FIELD_TOOLTIPS[key];
}

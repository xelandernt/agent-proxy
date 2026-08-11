const STORAGE_KEY = "dither-enabled";

const listeners = new Set<() => void>();
let cached: boolean | null = null;

function readStored(): boolean {
	if (cached !== null) return cached;
	try {
		cached = localStorage.getItem(STORAGE_KEY) === "1";
	} catch {
		cached = false;
	}
	return cached;
}

export function isDitherEnabled(): boolean {
	return readStored();
}

export function setDitherEnabled(enabled: boolean): void {
	cached = enabled;
	try {
		if (enabled) {
			localStorage.setItem(STORAGE_KEY, "1");
		} else {
			localStorage.removeItem(STORAGE_KEY);
		}
	} catch {
		// storage unavailable — keep the preference in memory only
	}
	for (const listener of listeners) listener();
}

export function subscribeDither(listener: () => void): () => void {
	listeners.add(listener);
	return () => {
		listeners.delete(listener);
	};
}

import { useEffect, useReducer } from "react";

/**
 * Seconds remaining until the next automatic refetch of a query whose last
 * successful fetch happened at `dataUpdatedAt`. Ticks once per second.
 */
export function useRefetchCountdown(
	dataUpdatedAt: number,
	intervalMs: number,
): number {
	const [, tick] = useReducer((value: number) => value + 1, 0);
	useEffect(() => {
		const id = setInterval(tick, 1000);
		return () => clearInterval(id);
	}, []);
	const remaining = dataUpdatedAt + intervalMs - Date.now();
	return Math.max(0, Math.ceil(remaining / 1000));
}

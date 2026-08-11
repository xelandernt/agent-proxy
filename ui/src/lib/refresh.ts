import { useEffect, useReducer, useRef, useState } from "react";

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

/**
 * True while a refetch is in flight, and for at least `minMs` after it starts
 * so a fast fetch still produces a visible animation. Spins on the rising edge
 * of `isFetching` only — never while idle.
 */
export function useSpinWhile(isFetching: boolean, minMs = 600): boolean {
	const [spinning, setSpinning] = useState(false);
	const isFetchingRef = useRef(false);
	const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

	useEffect(() => {
		if (isFetching === isFetchingRef.current) return;
		isFetchingRef.current = isFetching;
		if (!isFetching) return;
		setSpinning(true);
		if (timeoutRef.current !== null) clearTimeout(timeoutRef.current);
		timeoutRef.current = setTimeout(() => setSpinning(false), minMs);
	}, [isFetching, minMs]);

	useEffect(
		() => () => {
			if (timeoutRef.current !== null) clearTimeout(timeoutRef.current);
		},
		[],
	);

	return isFetching || spinning;
}

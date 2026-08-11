import { useEffect, useRef, useSyncExternalStore } from "react";

import { isDitherEnabled, subscribeDither } from "#/lib/dither";

const RAMP = " .:-=+xX#8@";

const BAYER_THRESHOLDS = [
	[0.03125, 0.53125, 0.15625, 0.65625],
	[0.78125, 0.28125, 0.90625, 0.40625],
	[0.21875, 0.71875, 0.09375, 0.59375],
	[0.96875, 0.46875, 0.84375, 0.34375],
];

const BASE_FONT_PX = 10;
const CHAR_WIDTH = BASE_FONT_PX * 0.6 + 1;
const LINE_HEIGHT_PX = BASE_FONT_PX * 1.35;
const MAX_CELLS = 35000;
const TICK_STEPS = [33, 50, 83];
const ADAPTIVE_UP_COST_MS = 8;
const ADAPTIVE_DOWN_COST_MS = 3;
const ADAPTIVE_DOWN_TICKS = 20;

const OCTAVES = [
	{ cell: 22, weight: 0.55, driftU: 0.4, driftV: 0.15, seed: 11 },
	{ cell: 11, weight: 0.45, driftU: -0.5, driftV: 0.6, seed: 37 },
];

const FLOW_W = 48;
const FLOW_H = 30;
const FLOW_VELOCITY_CLAMP = 0.16;

let cols = 200;
let rows = 60;
let fontScale = 1;

const flowVX = new Float32Array(FLOW_W * FLOW_H);
const flowVY = new Float32Array(FLOW_W * FLOW_H);
const flowE = new Float32Array(FLOW_W * FLOW_H);
const flowVX2 = new Float32Array(FLOW_W * FLOW_H);
const flowVY2 = new Float32Array(FLOW_W * FLOW_H);
const flowE2 = new Float32Array(FLOW_W * FLOW_H);

const pointer = {
	x: -2,
	y: -2,
	vx: 0,
	vy: 0,
	lastX: -2,
	lastY: -2,
	lastEventAt: 0,
};

function clamp(value: number, min: number, max: number): number {
	return Math.min(Math.max(value, min), max);
}

function smoothstep(a: number, b: number, x: number): number {
	const t = clamp((x - a) / (b - a), 0, 1);
	return t * t * (3 - 2 * t);
}

function hash(i: number, j: number, seed: number): number {
	let h = (Math.imul(i, 374761393) + Math.imul(j, 668265263) + seed) | 0;
	h = Math.imul(h ^ (h >>> 13), 1274126177);
	h ^= h >>> 16;
	return (h >>> 0) / 4294967296;
}

function vertexValue(i: number, j: number, seed: number, time: number): number {
	const h1 = hash(i, j, seed);
	const h2 = hash(i, j, seed + 1013);
	const phase = h1 * Math.PI * 2;
	const amplitude = 0.35 + h2 * 0.65;
	const speed = 0.6 + h2 * 1.8;
	return 0.5 + amplitude * 0.5 * Math.sin(phase + time * speed);
}

function buildLayer(
	time: number,
	octave: (typeof OCTAVES)[number],
): {
	cell: number;
	weight: number;
	gw: number;
	gh: number;
	grid: Float32Array;
} {
	const gw = Math.ceil(cols / octave.cell) + 1;
	const gh = Math.ceil(rows / octave.cell) + 1;
	const grid = new Float32Array(gw * gh);
	for (let j = 0; j < gh; j++) {
		for (let i = 0; i < gw; i++) {
			grid[j * gw + i] = vertexValue(i, j, octave.seed, time);
		}
	}
	return { cell: octave.cell, weight: octave.weight, gw, gh, grid };
}

function sampleLayer(
	layer: ReturnType<typeof buildLayer>,
	u: number,
	v: number,
): number {
	const su = u / layer.cell;
	const sv = v / layer.cell;
	const i0 = Math.floor(su);
	const j0 = Math.floor(sv);
	const i1 = (i0 + 1) % layer.gw;
	const j1 = (j0 + 1) % layer.gh;
	const fu = su - i0;
	const fv = sv - j0;
	const su2 = fu * fu * (3 - 2 * fu);
	const sv2 = fv * fv * (3 - 2 * fv);
	const v00 = layer.grid[j0 * layer.gw + i0];
	const v10 = layer.grid[j0 * layer.gw + i1];
	const v01 = layer.grid[j1 * layer.gw + i0];
	const v11 = layer.grid[j1 * layer.gw + i1];
	return (
		v00 +
		(v10 - v00) * su2 +
		(v01 - v00) * sv2 +
		(v00 - v10 - v01 + v11) * su2 * sv2
	);
}

function sampleFlow(arr: Float32Array, x: number, y: number): number {
	const i0 = clamp(Math.floor(x), 0, FLOW_W - 1);
	const j0 = clamp(Math.floor(y), 0, FLOW_H - 1);
	const i1 = Math.min(i0 + 1, FLOW_W - 1);
	const j1 = Math.min(j0 + 1, FLOW_H - 1);
	const uf = clamp(x - i0, 0, 1);
	const vf = clamp(y - j0, 0, 1);
	const v00 = arr[j0 * FLOW_W + i0];
	const v10 = arr[j0 * FLOW_W + i1];
	const v01 = arr[j1 * FLOW_W + i0];
	const v11 = arr[j1 * FLOW_W + i1];
	return (
		v00 * (1 - uf) * (1 - vf) +
		v10 * uf * (1 - vf) +
		v01 * (1 - uf) * vf +
		v11 * uf * vf
	);
}

function depositSplat(
	fromX: number,
	fromY: number,
	toX: number,
	toY: number,
	vx: number,
	vy: number,
	speed: number,
): void {
	const dist = Math.hypot((toX - fromX) * FLOW_W, (toY - fromY) * FLOW_H);
	const steps = Math.max(1, Math.ceil(dist * 0.75));
	for (let s = 0; s <= steps; s++) {
		const t = s / steps;
		const gx = clamp(fromX + (toX - fromX) * t, 0, 1) * (FLOW_W - 1);
		const gy = clamp(fromY + (toY - fromY) * t, 0, 1) * (FLOW_H - 1);
		const radius = 1.2 + speed * 1.25;
		const rad2 = radius * radius;
		const i0 = clamp(Math.floor(gy) - Math.ceil(radius), 0, FLOW_H - 1);
		const i1 = clamp(Math.ceil(gy) + Math.ceil(radius), 0, FLOW_H - 1);
		const j0 = clamp(Math.floor(gx) - Math.ceil(radius), 0, FLOW_W - 1);
		const j1 = clamp(Math.ceil(gx) + Math.ceil(radius), 0, FLOW_W - 1);
		for (let cy = i0; cy <= i1; cy++) {
			for (let cx = j0; cx <= j1; cx++) {
				const w = Math.exp(-((cx - gx) ** 2 + (cy - gy) ** 2) / (rad2 * 0.72));
				if (w < 0.01) continue;
				const idx = cy * FLOW_W + cx;
				flowVX[idx] = clamp(
					flowVX[idx] + vx * w * 0.48,
					-FLOW_VELOCITY_CLAMP,
					FLOW_VELOCITY_CLAMP,
				);
				flowVY[idx] = clamp(
					flowVY[idx] + vy * w * 0.48,
					-FLOW_VELOCITY_CLAMP,
					FLOW_VELOCITY_CLAMP,
				);
				flowE[idx] = Math.min(1.2, flowE[idx] + w * speed * 0.72);
			}
		}
	}
}

function stepFlow(dtMs: number): void {
	const steps = clamp(dtMs / 16.67, 0, 10);
	const velDamp = 0.935 ** steps;
	const energyDamp = 0.985 ** steps;
	const diff = Math.min(0.08, steps * 0.08);
	const advect = steps * 0.62;
	for (let j = 0; j < FLOW_H; j++) {
		for (let i = 0; i < FLOW_W; i++) {
			const idx = j * FLOW_W + i;
			const vx = flowVX[idx];
			const vy = flowVY[idx];
			const e = flowE[idx];
			const ax = sampleFlow(
				flowVX,
				i - vx * FLOW_W * advect,
				j - vy * FLOW_H * advect,
			);
			const ay = sampleFlow(
				flowVY,
				i - vx * FLOW_W * advect,
				j - vy * FLOW_H * advect,
			);
			const dx =
				(sampleFlow(flowVX, i - 1, j) +
					sampleFlow(flowVX, i + 1, j) +
					sampleFlow(flowVX, i, j - 1) +
					sampleFlow(flowVX, i, j + 1)) *
				0.25;
			const dy =
				(sampleFlow(flowVY, i - 1, j) +
					sampleFlow(flowVY, i + 1, j) +
					sampleFlow(flowVY, i, j - 1) +
					sampleFlow(flowVY, i, j + 1)) *
				0.25;
			const avgE =
				(sampleFlow(flowE, i - 1, j) +
					sampleFlow(flowE, i + 1, j) +
					sampleFlow(flowE, i, j - 1) +
					sampleFlow(flowE, i, j + 1)) *
				0.25;
			flowVX2[idx] = clamp(
				(ax + (dx - ax) * diff) * velDamp,
				-FLOW_VELOCITY_CLAMP,
				FLOW_VELOCITY_CLAMP,
			);
			flowVY2[idx] = clamp(
				(ay + (dy - ay) * diff) * velDamp,
				-FLOW_VELOCITY_CLAMP,
				FLOW_VELOCITY_CLAMP,
			);
			flowE2[idx] = Math.max(0, e + (avgE - e) * diff * 0.65) * energyDamp;
		}
	}
	flowVX.set(flowVX2);
	flowVY.set(flowVY2);
	flowE.set(flowE2);
}

function onPointerMove(event: PointerEvent): void {
	if (event.pointerType === "touch") return;
	const px = clamp(event.clientX / window.innerWidth, 0, 1);
	const py = clamp(event.clientY / window.innerHeight, 0, 1);
	const now = performance.now();
	if (pointer.lastEventAt > 0) {
		const dt = clamp(now - pointer.lastEventAt, 8, 50);
		const scale = 16.67 / dt;
		const vx = (px - pointer.lastX) * scale;
		const vy = (py - pointer.lastY) * scale;
		pointer.vx += (vx - pointer.vx) * 0.68;
		pointer.vy += (vy - pointer.vy) * 0.68;
		pointer.vx = clamp(pointer.vx, -0.14, 0.14);
		pointer.vy = clamp(pointer.vy, -0.14, 0.14);
		const speed = Math.min(1, Math.hypot(pointer.vx, pointer.vy) * 48);
		if (speed > 0.01) {
			depositSplat(
				pointer.lastX,
				pointer.lastY,
				px,
				py,
				pointer.vx,
				pointer.vy,
				speed,
			);
		}
	}
	pointer.x = px;
	pointer.y = py;
	pointer.lastX = px;
	pointer.lastY = py;
	pointer.lastEventAt = now;
}

function onPointerLeave(): void {
	pointer.x = -2;
	pointer.y = -2;
	pointer.vx = 0;
	pointer.vy = 0;
	pointer.lastEventAt = 0;
}

function glyphIndex(brightness: number, row: number, col: number): number {
	const v = clamp(brightness, 0, 1) * (RAMP.length - 1);
	const whole = Math.floor(v);
	const frac = v - whole;
	const threshold = BAYER_THRESHOLDS[row % 4][col % 4];
	return Math.min(RAMP.length - 1, whole + (frac > threshold ? 1 : 0));
}

function renderFrame(time: number, dtMs: number): string {
	stepFlow(dtMs);
	const velDamp = 0.975 ** (dtMs / 16.67);
	pointer.vx *= velDamp;
	pointer.vy *= velDamp;
	const movement = Math.hypot(pointer.vx, pointer.vy);
	const movementVisibility = smoothstep(0.002, 0.006, movement);
	const sizeSpeed = clamp(movement * 10, 0, 1);
	const headRadius = (0.035 + sizeSpeed * 0.035) * 0.75;

	const layers = OCTAVES.map((octave) => ({
		layer: buildLayer(time, octave),
		driftU: time * octave.driftU * octave.cell,
		driftV: time * octave.driftV * octave.cell,
	}));
	const lines = new Array<string>(rows);
	for (let row = 0; row < rows; row++) {
		const codes = new Uint16Array(cols);
		for (let col = 0; col < cols; col++) {
			const fx = (col / cols) * (FLOW_W - 1);
			const fy = (row / rows) * (FLOW_H - 1);
			const flowX = sampleFlow(flowVX, fx, fy);
			const flowY = sampleFlow(flowVY, fx, fy);
			const flowStrength = clamp(sampleFlow(flowE, fx, fy), 0, 1);
			const sampleU = col - flowX * flowStrength * 0.26 * cols;
			const sampleV = row - flowY * flowStrength * 0.26 * rows;

			let brightness = 0;
			for (const { layer, driftU, driftV } of layers) {
				const spanU = layer.gw * layer.cell;
				const spanV = layer.gh * layer.cell;
				const u = (((sampleU + driftU) % spanU) + spanU) % spanU;
				const v = (((sampleV + driftV) % spanV) + spanV) % spanV;
				brightness += layer.weight * sampleLayer(layer, u, v);
			}

			const relX = (col + 0.5) / cols - pointer.x;
			const relY = (row + 0.5) / rows - pointer.y;
			const relative = Math.hypot(relX, relY);
			const head =
				(1 - smoothstep(headRadius, headRadius * 1.7, relative)) *
				movementVisibility;
			const cut = clamp(flowStrength * 0.35 + head * 0.4, 0, 0.85);
			codes[col] = RAMP.charCodeAt(
				glyphIndex(Math.max(0, brightness - cut), row, col),
			);
		}
		lines[row] = String.fromCharCode(...codes);
	}
	return lines.join("\n");
}

function fitField(): boolean {
	let scale = 1;
	let nextCols = 0;
	let nextRows = 0;
	for (let i = 0; i < 4; i++) {
		nextCols = Math.ceil(window.innerWidth / (CHAR_WIDTH * scale)) + 1;
		nextRows = Math.ceil(window.innerHeight / (LINE_HEIGHT_PX * scale)) + 2;
		if (nextCols * nextRows <= MAX_CELLS) break;
		scale *= Math.sqrt((nextCols * nextRows) / MAX_CELLS);
	}
	if (
		nextCols === cols &&
		nextRows === rows &&
		Math.abs(scale - fontScale) < 0.001
	) {
		return false;
	}
	cols = nextCols;
	rows = nextRows;
	fontScale = scale;
	return true;
}

const STATIC_FRAME = renderFrame(0, 0);

export function BackgroundDither() {
	const preRef = useRef<HTMLPreElement>(null);
	const fieldRef = useRef<HTMLDivElement>(null);
	const enabled = useSyncExternalStore(
		subscribeDither,
		isDitherEnabled,
		() => false,
	);

	useEffect(() => {
		const pre = preRef.current;
		const field = fieldRef.current;
		if (!enabled || !pre || !field) return;

		const applyScale = () => {
			field.style.setProperty("--dither-scale", String(fontScale));
		};

		const reduced = window.matchMedia(
			"(prefers-reduced-motion: reduce)",
		).matches;
		if (reduced) {
			fitField();
			applyScale();
			pre.textContent = renderFrame(0, 0);
			return;
		}

		fitField();
		applyScale();
		pre.textContent = renderFrame(0, 0);

		let frame = 0;
		let last = 0;
		let tickIndex = 0;
		let fastTicks = 0;
		let running = false;

		const tick = (now: number) => {
			if (now - last >= TICK_STEPS[tickIndex]) {
				const dt = now - last;
				last = now;
				const start = performance.now();
				pre.textContent = renderFrame(now / 1000, dt);
				const cost = performance.now() - start;
				if (cost > ADAPTIVE_UP_COST_MS) {
					tickIndex = Math.min(tickIndex + 1, TICK_STEPS.length - 1);
					fastTicks = 0;
				} else if (cost < ADAPTIVE_DOWN_COST_MS) {
					fastTicks++;
					if (fastTicks >= ADAPTIVE_DOWN_TICKS) {
						tickIndex = Math.max(tickIndex - 1, 0);
						fastTicks = 0;
					}
				} else {
					fastTicks = 0;
				}
			}
			frame = requestAnimationFrame(tick);
		};

		const start = () => {
			if (running) return;
			running = true;
			frame = requestAnimationFrame(tick);
		};

		const stop = () => {
			running = false;
			cancelAnimationFrame(frame);
		};

		const onVisibility = () => (document.hidden ? stop() : start());

		const onResize = () => {
			if (fitField()) {
				applyScale();
				last = 0;
			}
		};

		const observer = new IntersectionObserver(
			([entry]) => (entry.isIntersecting ? start() : stop()),
			{ rootMargin: "160px 0px" },
		);
		observer.observe(pre);
		document.addEventListener("visibilitychange", onVisibility);
		window.addEventListener("resize", onResize);
		window.addEventListener("pointermove", onPointerMove);
		window.addEventListener("pointerleave", onPointerLeave);
		start();

		return () => {
			running = false;
			cancelAnimationFrame(frame);
			observer.disconnect();
			document.removeEventListener("visibilitychange", onVisibility);
			window.removeEventListener("resize", onResize);
			window.removeEventListener("pointermove", onPointerMove);
			window.removeEventListener("pointerleave", onPointerLeave);
		};
	}, [enabled]);

	if (!enabled) return null;

	return (
		<div className="dither-field" ref={fieldRef} aria-hidden="true">
			<pre ref={preRef}>{STATIC_FRAME}</pre>
		</div>
	);
}

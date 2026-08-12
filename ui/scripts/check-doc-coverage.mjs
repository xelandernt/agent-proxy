#!/usr/bin/env node
/**
 * Verify provider docs coverage against the gateway's OpenAPI schema.
 *
 * Usage: node scripts/check-doc-coverage.mjs [openapi.json]
 *
 * Checks, for every auth provider in the schema:
 *  1. a guide data file exists in src/lib/provider-docs/guides/ and its id
 *     matches the provider slug;
 *  2. the guide's field list matches the form's field set exactly (top-level
 *     properties minus const fields, plus properties of nested object fields
 *     such as token_introspection);
 *  3. no duplicate field keys inside a guide;
 *  4. every `shared: true` entry resolves to a key in FIELD_TOOLTIPS;
 *  5. every form field has tooltip text — a provider-specific `text` entry in
 *     the guide or a shared FIELD_TOOLTIPS entry.
 *
 * Exit code is non-zero when any check fails.
 */
import { build } from "esbuild";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const uiRoot = path.resolve(scriptDir, "..");
const guidesDir = path.join(uiRoot, "src/lib/provider-docs/guides");
const openapiPath = process.argv[2] ?? path.join(uiRoot, "..", "openapi.json");

async function loadModule(file) {
	const result = await build({
		entryPoints: [file],
		bundle: true,
		write: false,
		format: "esm",
		platform: "node",
		logLevel: "silent",
	});
	const code = result.outputFiles[0].text;
	const url =
		"data:text/javascript;base64," + Buffer.from(code).toString("base64");
	return import(url);
}

function resolveNode(node, schemas) {
	if (node.$ref) {
		const name = node.$ref.split("/").pop();
		if (schemas[name]) return resolveNode(schemas[name], schemas);
	}
	return node;
}

function effectiveNode(node, schemas) {
	const resolved = resolveNode(node, schemas);
	if (resolved.anyOf) {
		const nonNull = resolved.anyOf.find((candidate) => {
			const inner = resolveNode(candidate, schemas);
			return inner.type !== "null" && !(inner.enum && inner.enum.length === 1 && inner.enum[0] === null);
		});
		if (nonNull) return effectiveNode(nonNull, schemas);
	}
	return resolved;
}

/** Fields the form renders for a provider: key -> node, skipping const props. Nested object properties (e.g. token_introspection.timeout_seconds) are keyed by their bare property name, matching the form's tooltip lookup. */
function formFields(schema, schemas) {
	const properties = schema.properties ?? {};
	const fields = new Map();
	for (const [key, rawNode] of Object.entries(properties)) {
		if (rawNode.const !== undefined) continue;
		const node = effectiveNode(rawNode, schemas);
		if (node.type === "object") {
			fields.set(key, node);
			for (const [nestedKey, nestedNode] of Object.entries(
				node.properties ?? {},
			)) {
				fields.set(nestedKey, nestedNode);
			}
		} else {
			fields.set(key, node);
		}
	}
	return fields;
}

const problems = [];
const warnings = [];

function fail(message) {
	problems.push(message);
}

const [fieldsModule, ...guideModules] = await Promise.all([
	loadModule(path.join(uiRoot, "src/lib/provider-docs/fields.ts")),
	...fs
		.readdirSync(guidesDir)
		.filter((name) => name.endsWith(".ts"))
		.map((name) => loadModule(path.join(guidesDir, name))),
]);

const FIELD_TOOLTIPS = fieldsModule.FIELD_TOOLTIPS ?? {};
const guides = guideModules.map((module) => module.guide);

const spec = JSON.parse(fs.readFileSync(openapiPath, "utf8"));
const schemas = spec.components.schemas;
const union = (() => {
	for (const schema of Object.values(schemas)) {
		for (const property of Object.values(schema.properties ?? {})) {
			if (
				property.discriminator?.propertyName === "provider" &&
				property.discriminator?.mapping
			) {
				return property;
			}
		}
	}
	return Object.values(schemas).find(
		(schema) =>
			schema.discriminator?.propertyName === "provider" &&
			schema.discriminator?.mapping,
	);
})();
if (!union) {
	console.error("Could not find the auth provider discriminated union in the schema.");
	process.exit(1);
}

const mapping = union.discriminator.mapping;

for (const [slug, ref] of Object.entries(mapping)) {
	const schema = schemas[ref.split("/").pop()];
	const expected = formFields(schema, schemas);

	const guide = guides.find((entry) => entry.id === slug);
	if (!guide) {
		fail(`${slug}: no guide file in ${path.relative(process.cwd(), guidesDir)}/`);
		continue;
	}

	if (guide.id !== slug) {
		fail(`${slug}: guide id is "${guide.id}"`);
	}

	const seen = new Set();
	const guideKeys = new Map();
	for (const entry of guide.fields) {
		if (seen.has(entry.key)) {
			fail(`${slug}: duplicate field key "${entry.key}" in guide`);
		}
		seen.add(entry.key);
		guideKeys.set(entry.key, entry);
		if ("shared" in entry && !(entry.key in FIELD_TOOLTIPS)) {
			fail(
				`${slug}: field "${entry.key}" is marked shared but has no FIELD_TOOLTIPS entry`,
			);
		}
		if ("text" in entry && entry.text.trim() === "") {
			fail(`${slug}: field "${entry.key}" has empty text`);
		}
	}

	for (const key of expected.keys()) {
		const entry = guideKeys.get(key);
		if (!entry) {
			fail(`${slug}: guide is missing form field "${key}"`);
			continue;
		}
		if ("shared" in entry) {
			if (!FIELD_TOOLTIPS[key]) {
				fail(`${slug}: form field "${key}" has no tooltip text (shared entry missing from FIELD_TOOLTIPS)`);
			}
		}
	}

	for (const key of guideKeys.keys()) {
		if (!expected.has(key)) {
			fail(`${slug}: guide lists "${key}" which the form does not show`);
		}
	}
}

for (const [key] of Object.entries(FIELD_TOOLTIPS)) {
	const referenced = guides.some((guide) =>
		guide.fields.some((entry) => "shared" in entry && entry.key === key),
	);
	if (!referenced) {
		warnings.push(`FIELD_TOOLTIPS entry "${key}" is not referenced by any guide`);
	}
}

if (problems.length > 0) {
	console.error(`Provider docs coverage FAILED (${problems.length} problem(s)):`);
	for (const problem of problems) console.error(`  - ${problem}`);
	process.exit(1);
}

console.log(`Provider docs coverage OK (${Object.keys(mapping).length} providers, ${guides.length} guides).`);
if (warnings.length > 0) {
	for (const warning of warnings) console.warn(`warning: ${warning}`);
}

import { readFile, writeFile } from "node:fs/promises";

const TARGET = new URL("../src/api/generated/fastAPI.ts", import.meta.url);
const PRIVATE_CONSTS = [
	"McpServerListingAuth",
	"SupabaseAuthProviderConfigAlgorithm",
];

for (const name of PRIVATE_CONSTS) {
	const source = await readFile(TARGET, "utf8");
	const next = source.replace(
		`export const ${name} = {`,
		`const ${name} = {`,
	);
	if (next !== source) await writeFile(TARGET, next);
}

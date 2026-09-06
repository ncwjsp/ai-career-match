import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import openapiTS, { astToString } from "openapi-typescript";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const schema = JSON.parse(fs.readFileSync(path.resolve(webRoot, "../../contracts/openapi.json"), "utf8"));
const ast = await openapiTS(schema);
const source = "// Generated from canonical backend OpenAPI. Do not edit.\n" + astToString(ast);
const output = path.join(webRoot, "src/lib/api/generated.ts");
if (process.argv.includes("--check")) {
  if (!fs.existsSync(output) || fs.readFileSync(output, "utf8") !== source) {
    throw new Error("Generated API types are stale. Run pnpm api:generate.");
  }
  console.log("Generated API types are current.");
} else {
  fs.writeFileSync(output, source);
  console.log("Wrote src/lib/api/generated.ts");
}

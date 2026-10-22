// Qualification evidence only. Never shipped in or called by the application.
const fs = require("node:fs");
const path = require("node:path");
const forbidden = new Set(["braces", "micromatch", "fast-glob"]);
let files = 0;
let bytes = 0;
function walk(directory) {
  for (const name of fs.readdirSync(directory)) {
    const file = path.join(directory, name);
    const entry = fs.lstatSync(file);
    if (entry.isSymbolicLink()) throw new Error("unqualified_runtime_symlink");
    if (entry.isDirectory()) { walk(file); continue; }
    if (++files > 25000) throw new Error("runtime_inventory_bound");
    if (name !== "package.json" && !name.endsWith(".js") && !name.endsWith(".cjs")) continue;
    bytes += entry.size;
    if (bytes > 200 * 1024 * 1024) throw new Error("runtime_inventory_bound");
    const text = fs.readFileSync(file, "utf8");
    if (name === "package.json" && forbidden.has(JSON.parse(text).name)) throw new Error("dev_glob_package_in_runtime");
    if (/node_modules\/(braces|micromatch|fast-glob)\//.test(text) || /require\(["'](?:braces|micromatch|fast-glob)["']\)/.test(text) || /next\/dist\/compiled\/micromatch/.test(text)) throw new Error("dev_glob_code_in_runtime");
  }
}
const sha = process.env.FLA_RELEASE_SHA;
if (!/^[0-9a-f]{40}$/.test(sha || "")) throw new Error("missing_image_release_identity");
walk("/app");
console.log(JSON.stringify({kind:"frontend-dev-glob-absence",result:"PASS",release_sha:sha,files,bytes,forbidden:[...forbidden]}));

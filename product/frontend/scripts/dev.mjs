// The supervisor passes --strictPort: serve a prebuilt bundle for internal QA.
// This avoids Next dev's /proc memory instrumentation in restricted containers.
// Normal `npm run dev` keeps the original loopback-only Next dev behavior.
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";

const managedPreview = process.argv.includes("--strictPort");
if (managedPreview && !existsSync(".next/BUILD_ID"))
  throw new Error(
    "Run npm run build before starting the supervised FINLEAK preview.",
  );
const args = process.argv
  .slice(2)
  .filter((arg) => arg !== "--strictPort")
  .map((arg) => (arg === "--host" ? "--hostname" : arg));
if (!args.includes("--hostname")) args.unshift("--hostname", "127.0.0.1");
const child = spawn(
  process.execPath,
  [
    fileURLToPath(import.meta.resolve("next/dist/bin/next")),
    managedPreview ? "start" : "dev",
    ...args,
  ],
  { stdio: "inherit", env: { ...process.env, NEXT_TELEMETRY_DISABLED: "1" } },
);
for (const signal of ["SIGTERM", "SIGINT"])
  process.on(signal, () => child.kill(signal));
child.on("error", (error) => {
  console.error(error.message);
  process.exitCode = 1;
});
child.on("exit", (code, signal) => {
  process.exitCode = code ?? (signal === "SIGINT" ? 130 : 1);
});

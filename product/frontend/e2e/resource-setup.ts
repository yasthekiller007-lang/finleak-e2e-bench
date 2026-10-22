import { spawn } from "node:child_process";
import { writeFileSync } from "node:fs";

export default function setup() {
  const child = spawn(
    "uv",
    ["run", "python", "-m", "acceptance.resource_monitor"],
    {
      cwd: "../backend",
      env: process.env,
      stdio: "ignore",
      detached: true,
    },
  );
  if (!child.pid) throw new Error("Resource observer did not start");
  writeFileSync("../.local/phase7/observer.pid", String(child.pid));
  child.unref();
}

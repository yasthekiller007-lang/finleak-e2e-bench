import { readFileSync } from "node:fs";

export default async function teardown() {
  const pid = Number(readFileSync("../.local/phase7/observer.pid", "utf8"));
  try {
    process.kill(-pid, "SIGTERM");
  } catch {
    throw new Error("Resource observer was unavailable");
  }
  for (let i = 0; i < 100; i++) {
    try {
      process.kill(pid, 0);
    } catch {
      return;
    }
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error("Resource observer did not stop within its bound");
}

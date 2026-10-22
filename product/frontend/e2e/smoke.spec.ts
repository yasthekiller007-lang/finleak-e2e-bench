import { expect, test } from "@playwright/test";
import { login } from "./helpers";

test("E2E-01 second-engine login, no membership, keyboard logout", async ({
  page,
  browser,
}) => {
  await login(page, "unassigned");
  await expect(
    page.getByRole("heading", { name: "No organization access yet" }),
  ).toBeVisible();
  const signOut = page.getByRole("button", { name: "Sign out" });
  await expect(signOut).toBeEnabled();
  await signOut.focus();
  await expect(signOut).toBeFocused();
  const logout = page.waitForResponse(
    (r) =>
      r.url().endsWith("/api/auth/signout") && r.request().method() === "POST",
  );
  await signOut.press("Enter");
  expect((await logout).ok()).toBe(true);
  await expect(page).toHaveURL(/\/login$/);
  expect(await (await page.request.get("/api/auth/session")).json()).toEqual(
    {},
  );
  test
    .info()
    .annotations.push({ type: "browser", description: browser.version() });
});

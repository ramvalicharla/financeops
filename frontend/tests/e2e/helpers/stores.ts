import type { Page } from "@playwright/test"

/**
 * Opens the ModuleManager dialog via the ?modal=module-manager URL param.
 * ModuleTabs.tsx contains a useEffect that calls openModuleManager() when this
 * param is present, so no direct store access or permission bypass is needed.
 * This works regardless of canPerformAction("module.manage") returning false.
 */
export async function openModuleManager(page: Page): Promise<void> {
  const current = page.url()
  const url = new URL(current)
  url.searchParams.set("modal", "module-manager")
  await page.goto(url.toString())
  // Wait for the dialog to become visible after the useEffect fires
  await page.waitForSelector('[role="dialog"]', { state: "visible", timeout: 5000 })
}

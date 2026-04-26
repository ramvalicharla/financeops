/**
 * SP-3B keyboard reorder end-to-end verification
 *
 * Drives Space → ArrowDown × 2 → Space through a real Chromium instance
 * and captures screenshots at every step. Soft assertions only — the goal
 * is to see what happened, not gate CI. INITIAL_ORDER and FINAL_ORDER are
 * printed to console for human review.
 *
 * Run:
 *   npx playwright test tests/e2e/phase3/sp3b-keyboard-manual.spec.ts --project=chromium
 */
import { expect, test } from "@playwright/test"
import * as path from "path"
import {
  apiResponse,
  enableAuthBypassHeader,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "../helpers/mocks"

const SCREENSHOTS = path.resolve(__dirname, "screenshots")

const WORKSPACE_TABS = [
  {
    workspace_key: "dashboard",
    workspace_name: "Dashboard",
    href: "/dashboard",
    match_prefixes: ["/dashboard"],
    module_codes: [],
  },
  {
    workspace_key: "accounting",
    workspace_name: "Accounting",
    href: "/accounting",
    match_prefixes: ["/accounting"],
    module_codes: [],
  },
  {
    workspace_key: "reconciliation",
    workspace_name: "Reconciliation",
    href: "/reconciliation",
    match_prefixes: ["/reconciliation"],
    module_codes: [],
  },
]

const CONTEXT_PAYLOAD = {
  tenant_id: "tenant-001",
  tenant_slug: "acme",
  workspace_tabs: WORKSPACE_TABS,
  current_organisation: {
    organisation_id: "org-001",
    organisation_name: "Acme",
    source: "mock",
  },
  current_entity: {
    entity_id: "entity-001",
    entity_code: "ACME-LTD",
    entity_name: "Acme Ltd",
    source: "mock",
  },
  available_entities: [
    { entity_id: "entity-001", entity_code: "ACME-LTD", entity_name: "Acme Ltd" },
  ],
  current_module: {
    module_key: "dashboard",
    module_name: "Dashboard",
    module_code: "dashboard",
    source: "mock",
  },
  enabled_modules: [],
  current_period: {
    period_label: "Apr 2026",
    fiscal_year: 2026,
    period_number: 4,
    source: "mock",
    period_id: "period-2026-04",
    status: "open",
  },
}

test("SP-3B — keyboard reorder end-to-end (Space → ArrowDown×2 → Space)", async ({
  page,
}) => {
  // ── Setup ──────────────────────────────────────────────────────────────────
  // Clear module-order store so the dialog seeds from backend tabs (clean slate)
  await page.addInitScript(() => {
    localStorage.removeItem("finqor:module-order:v1")
  })

  await enableAuthBypassHeader(page)
  await mockCSRF(page)
  await mockSession(page)

  await page.route("**/api/v1/platform/control-plane/context**", async (route) => {
    await fulfillJson(route, apiResponse(CONTEXT_PAYLOAD))
  })

  // ── Navigate — ?modal=module-manager triggers ModuleTabs useEffect ─────────
  await page.goto("/dashboard?modal=module-manager")
  await page.waitForSelector('[role="dialog"]', { state: "visible", timeout: 10_000 })

  const dialog = page.getByRole("dialog")
  const list = page.getByRole("list", { name: "Active modules" })
  await expect(list).toBeVisible({ timeout: 8_000 })

  // Helper: read current row order by inspecting drag-handle aria-labels
  const getOrder = async (): Promise<string[]> => {
    const handles = list.getByRole("button", { name: /Drag to reorder/i })
    const count = await handles.count()
    const labels: string[] = []
    for (let i = 0; i < count; i++) {
      const label = await handles.nth(i).getAttribute("aria-label")
      labels.push(label?.replace("Drag to reorder ", "") ?? `row-${i}`)
    }
    return labels
  }

  // ── Step 0: initial state ──────────────────────────────────────────────────
  const INITIAL_ORDER = await getOrder()
  console.log("INITIAL_ORDER:", JSON.stringify(INITIAL_ORDER))
  test.info().annotations.push({
    type: "INITIAL_ORDER",
    description: INITIAL_ORDER.join(" → "),
  })

  await page.screenshot({
    path: path.join(SCREENSHOTS, "keyboard-step-0-initial.png"),
    clip: await dialog.boundingBox() ?? undefined,
  })

  // ── Step 1: focus first drag handle ───────────────────────────────────────
  const firstHandle = list.getByRole("button", { name: /Drag to reorder/i }).first()
  await expect(firstHandle).toBeVisible()

  const focusedLabel = await firstHandle.getAttribute("aria-label")
  console.log("Focusing:", focusedLabel)
  test.info().annotations.push({ type: "focused_handle", description: focusedLabel ?? "" })

  await firstHandle.focus()
  await page.waitForTimeout(120)

  // Confirm focus landed on the right element
  const activeLabel = await page.evaluate(
    () => document.activeElement?.getAttribute("aria-label") ?? "none",
  )
  console.log("document.activeElement aria-label:", activeLabel)
  test.info().annotations.push({ type: "activeElement_after_focus", description: activeLabel })

  await page.screenshot({
    path: path.join(SCREENSHOTS, "keyboard-step-1-handle-focused.png"),
    clip: await dialog.boundingBox() ?? undefined,
  })

  // ── Step 2: Space — pick up ────────────────────────────────────────────────
  await page.keyboard.press("Space")
  await page.waitForTimeout(220)

  // Check whether a DragOverlay appeared (dnd-kit renders one when isDragging)
  const overlayVisible = await page.evaluate(() => {
    // DragOverlay renders into a portal with data-rfd-drag-handle-draggable-id or similar.
    // @dnd-kit renders the overlay as a sibling of the DndContext root.
    // Check for the overlay li which has shadow-lg class.
    return document.querySelectorAll("li.shadow-lg, li[style*='transform']").length > 0
  })
  console.log("DragOverlay / transform-li visible after Space:", overlayVisible)
  test.info().annotations.push({
    type: "drag_overlay_after_space",
    description: String(overlayVisible),
  })

  await page.screenshot({
    path: path.join(SCREENSHOTS, "keyboard-step-2-picked-up.png"),
    clip: await dialog.boundingBox() ?? undefined,
  })

  // ── Step 3: ArrowDown × 2 ─────────────────────────────────────────────────
  await page.keyboard.press("ArrowDown")
  await page.waitForTimeout(120)
  await page.keyboard.press("ArrowDown")
  await page.waitForTimeout(120)

  await page.screenshot({
    path: path.join(SCREENSHOTS, "keyboard-step-3-mid-move.png"),
    clip: await dialog.boundingBox() ?? undefined,
  })

  // ── Step 4: Space — drop ──────────────────────────────────────────────────
  await page.keyboard.press("Space")
  await page.waitForTimeout(350)

  await page.screenshot({
    path: path.join(SCREENSHOTS, "keyboard-step-4-dropped.png"),
    clip: await dialog.boundingBox() ?? undefined,
  })

  // ── Evaluate result ────────────────────────────────────────────────────────
  const FINAL_ORDER = await getOrder()
  console.log("FINAL_ORDER:", JSON.stringify(FINAL_ORDER))
  test.info().annotations.push({
    type: "FINAL_ORDER",
    description: FINAL_ORDER.join(" → "),
  })

  const movedItem = INITIAL_ORDER[0]
  const finalIndex = FINAL_ORDER.indexOf(movedItem)
  const orderChanged = JSON.stringify(INITIAL_ORDER) !== JSON.stringify(FINAL_ORDER)

  console.log(`"${movedItem}" moved from index 0 → index ${finalIndex}`)
  console.log("Orders differ:", orderChanged)
  test.info().annotations.push({
    type: "result",
    description: orderChanged
      ? `REORDER WORKED — "${movedItem}" moved from index 0 to index ${finalIndex}`
      : `REORDER DID NOT WORK — order unchanged`,
  })

  // Soft assertions — surface the result without failing the test
  expect.soft(orderChanged, "Expected FINAL_ORDER to differ from INITIAL_ORDER").toBe(true)
  expect
    .soft(finalIndex, `Expected "${movedItem}" at index 2 (moved 2 down)`)
    .toBe(Math.min(2, INITIAL_ORDER.length - 1))
})

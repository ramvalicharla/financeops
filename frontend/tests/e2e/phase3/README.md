# Phase 3 E2E Verification Suite

Playwright specs covering SP-3A (ModuleManager dialog), SP-3B (drag-to-reorder),
and SP-3C (auditor sidebar filtering).

## SP-3B — What the specs cover

- Drag handle button is rendered per active-module row (`aria-label="Drag to reorder <Name>"`)
- Each handle has `tabindex="0"` and `aria-roledescription="sortable"` (injected by `@dnd-kit/sortable`)
- Pre-seeded `localStorage` order (`finqor:module-order:v1`) is reflected in the dialog's item order
- Novel backend tabs not in the stored order are appended after the stored keys

## SP-3B — What the specs do NOT cover

Live keyboard reorder (Space → ArrowDown → Space → confirm row moved) is **not tested** by
Playwright in this suite. `@dnd-kit`'s `KeyboardSensor` attaches its move/drop listeners to
`window` after the pickup keydown. In Playwright's headless Chromium the window-level keydown
events do not reliably propagate through the sensor's internal state machine, so keyboard DnD
interactions produce no-ops during automation.

**Manual verification required before push (≈30 seconds in Chrome):**

1. Open the app, navigate to any dashboard route.
2. Click the `+` button in the workspace tab bar to open Module Manager.
3. In the **Active** tab, press `Tab` until a "Drag to reorder" handle is focused (visible ring).
4. Press `Space` — the item should be announced as "picked up".
5. Press `ArrowDown` twice — the item should move down two positions.
6. Press `Space` — the item should be announced as "dropped".
7. Confirm the row appears two positions lower than its original slot.

**Upstream verification:** `@dnd-kit`'s own test suite covers the `KeyboardSensor` interaction
contract. See `node_modules/@dnd-kit/core/src/__tests__/` (or the upstream repo at
https://github.com/clauderic/dnd-kit) as the authoritative reference for keyboard DnD correctness.

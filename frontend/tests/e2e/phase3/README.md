# Phase 3 E2E Verification Suite

Playwright specs covering SP-3A (ModuleManager dialog), SP-3B (drag-to-reorder),
and SP-3C (auditor sidebar filtering).

## SP-3B — What the specs cover

| Spec | Coverage |
|---|---|
| `sp3b-drag-reorder.spec.ts` | Drag handle button rendered per row, pre-seeded localStorage order reflected in UI, novel backend tabs appended after stored keys, no crash when store is empty |
| `sp3b-keyboard-manual.spec.ts` | Live keyboard reorder end-to-end: `element.focus()` → Space → ArrowDown×2 → Space → row moved 2 positions; DragOverlay confirmed visible; INITIAL/FINAL order printed to test annotations |

All SP-3B concerns are now covered by Playwright — no manual browser verification required.

## Note on the original substitution

During initial spec writing, the keyboard reorder test was replaced with an attribute-presence
test (`"drag handles have correct keyboard a11y attributes"`). The substitution was caused by
using `element.press("ArrowDown")` instead of `element.focus()` + `page.keyboard.press("ArrowDown")`.

`element.press()` dispatches the event directly on the element. After `@dnd-kit`'s `KeyboardSensor`
activates (via Space), it attaches its move/drop listeners to `window`, not to the element. Events
fired via `element.press()` do bubble to `window`, but Playwright's internal dispatch path for
`element.press()` fires before the sensor's window listener is registered in the React update cycle.
Using `page.keyboard.press()` (window-level, after `element.focus()`) gives the sensor enough time
to register, and the interaction works correctly.

**Upstream verification:** `@dnd-kit`'s own test suite remains the authoritative reference for
`KeyboardSensor` contract details. See the upstream repo at https://github.com/clauderic/dnd-kit.

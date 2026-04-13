import type { Page } from "@playwright/test"

type HookUpdate = {
  index: number
  value: unknown
}

export async function dispatchComponentHookState(
  page: Page,
  componentName: string,
  anchorText: string,
  updates: HookUpdate[],
) {
  await page.evaluate(
    ({ componentName, anchorText, updates }) => {
      const getFiberKey = (node: Element): string | undefined =>
        Object.keys(node).find((key) => key.startsWith("__reactFiber$"))

      const anchors = Array.from(
        document.querySelectorAll("button, h1, h2, main, [role='heading']"),
      ).filter((node) => node.textContent?.includes(anchorText))

      if (!anchors.length) {
        throw new Error(`Unable to find anchor element for "${anchorText}".`)
      }

      const resolveFiberForAnchor = (anchor: Element) => {
        let fiberOwner: Element | null = anchor
        let fiberKey = fiberOwner ? getFiberKey(fiberOwner) : undefined
        while (!fiberKey && fiberOwner?.parentElement) {
          fiberOwner = fiberOwner.parentElement
          fiberKey = getFiberKey(fiberOwner)
        }
        if (!fiberKey || !fiberOwner) {
          return null
        }

        let fiber = (fiberOwner as Element & Record<string, unknown>)[fiberKey] as
          | {
              memoizedState?: unknown
              next?: unknown
              queue?: { dispatch?: (value: unknown) => void }
              return?: unknown
              type?: { name?: string }
            }
          | undefined

        while (
          fiber &&
          (typeof fiber.type === "string" || fiber.type?.name !== componentName)
        ) {
          fiber = fiber.return as typeof fiber
        }

        return fiber?.memoizedState ? fiber : null
      }

      const resolveComponentFromFiberOwner = (fiberOwner: Element) => {
        const fiberKey = getFiberKey(fiberOwner)
        if (!fiberKey) {
          return null
        }

        let fiber = (fiberOwner as Element & Record<string, unknown>)[fiberKey] as
          | {
              memoizedState?: unknown
              next?: unknown
              queue?: { dispatch?: (value: unknown) => void }
              return?: unknown
              type?: { name?: string }
            }
          | undefined

        while (
          fiber &&
          (typeof fiber.type === "string" || fiber.type?.name !== componentName)
        ) {
          fiber = fiber.return as typeof fiber
        }

        return fiber?.memoizedState ? fiber : null
      }

      let fiber:
        | {
            memoizedState?: unknown
            next?: unknown
            queue?: { dispatch?: (value: unknown) => void }
            return?: unknown
            type?: { name?: string }
          }
        | null = null
      for (const anchor of anchors) {
        const resolved = resolveFiberForAnchor(anchor)
        if (resolved) {
          fiber = resolved
          break
        }
      }

      if (!fiber) {
        const elements = Array.from(document.querySelectorAll("*"))
        for (const element of elements) {
          const resolved = resolveComponentFromFiberOwner(element)
          if (resolved) {
            fiber = resolved
            break
          }
        }
      }

      if (!fiber?.memoizedState) {
        throw new Error(`Unable to locate component "${componentName}".`)
      }

      const getHookAtIndex = (start: typeof fiber.memoizedState, targetIndex: number) => {
        let hook = start as
          | {
              next?: unknown
              queue?: { dispatch?: (value: unknown) => void }
            }
          | undefined
        let index = 0
        while (hook && index < targetIndex) {
          hook = hook.next as typeof hook
          index += 1
        }
        return hook
      }

      for (const update of updates) {
        const hook = getHookAtIndex(fiber.memoizedState, update.index)
        if (!hook?.queue?.dispatch) {
          throw new Error(
            `Hook ${update.index} on component "${componentName}" is not dispatchable.`,
          )
        }
        hook.queue.dispatch(update.value)
      }
    },
    { componentName, anchorText, updates },
  )
}

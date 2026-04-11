export interface BackendWorkspaceTab {
  workspace_key: string
  workspace_name: string
  href: string
  match_prefixes: string[]
  module_codes: string[]
}

export const resolveWorkspaceFromTabs = (
  pathname: string,
  workspaceTabs: BackendWorkspaceTab[],
): BackendWorkspaceTab | null => {
  return (
    workspaceTabs.find((tab) =>
      tab.match_prefixes.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)),
    ) ?? null
  )
}

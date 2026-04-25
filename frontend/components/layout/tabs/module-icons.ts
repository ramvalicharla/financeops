import type { LucideIcon } from "lucide-react"
import {
  LayoutDashboard,
  Plug,
  BookOpen,
  Scale,
  CalendarCheck,
  FileBarChart,
  Settings,
  CircleDot,
} from "lucide-react"

/**
 * Maps backend `workspace_key` → Lucide icon component.
 *
 * Keys MUST match values in backend _WORKSPACE_DEFINITIONS
 * (control_plane.py:44–99). When backend adds or renames a workspace,
 * this map must be updated or the tab falls back to CircleDot.
 *
 * Ref: spec §1.5 (icon + label per tab); audit Risk #3.
 */
export const MODULE_ICON_MAP: Record<string, LucideIcon> = {
  dashboard: LayoutDashboard,
  erp: Plug,
  accounting: BookOpen,
  reconciliation: Scale,
  close: CalendarCheck,
  reports: FileBarChart,
  settings: Settings,
}

export const FALLBACK_MODULE_ICON: LucideIcon = CircleDot

export function getModuleIcon(workspaceKey: string | undefined | null): LucideIcon {
  if (!workspaceKey) return FALLBACK_MODULE_ICON
  return MODULE_ICON_MAP[workspaceKey.toLowerCase()] ?? FALLBACK_MODULE_ICON
}

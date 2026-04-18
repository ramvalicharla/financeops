"use client"

import { useCallback, useEffect, useMemo, useState } from "react"
import { useSession } from "next-auth/react"
import { DataTable } from "@/components/admin/DataTable"
import { RoleSelector } from "@/components/admin/RoleSelector"
import {
  deactivatePlatformUser,
  listPlatformUsers,
  updatePlatformUserRole,
} from "@/lib/api/platform-admin"
import type { PlatformUser, PlatformUserRole } from "@/lib/types/platform-admin"
import { canPerformAction } from "@/lib/ui-access"

const editableRoles: PlatformUserRole[] = [
  "platform_owner",
  "platform_admin",
  "platform_support",
  "super_admin",
]

export default function AdminUsersPage() {
  const { data: session } = useSession()
  const canUpdateUsers = canPerformAction("platform.users.update", session?.user?.role)
  const canDeleteUsers = canPerformAction("platform.users.delete", session?.user?.role)
  const [rows, setRows] = useState<PlatformUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const payload = await listPlatformUsers({ limit: 200, offset: 0 })
      setRows(payload.data)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load users")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void load()
  }, [load])

  const activeCount = useMemo(
    () => rows.filter((row) => row.is_active).length,
    [rows],
  )

  const changeRole = async (row: PlatformUser, role: PlatformUserRole) => {
    setMessage(null)
    setError(null)
    try {
      await updatePlatformUserRole(row.id, role)
      setMessage(`Updated role for ${row.email} to ${role}.`)
      await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to update role")
    }
  }

  const deactivate = async (row: PlatformUser) => {
    setMessage(null)
    setError(null)
    try {
      await deactivatePlatformUser(row.id)
      setMessage(`Deactivated user ${row.email}.`)
      await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to deactivate user")
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">Platform Users</h1>
        <p className="text-sm text-muted-foreground">
          Assign roles, promote to admin, and deactivate users.
        </p>
        <p className="mt-2 text-xs text-muted-foreground">
          Active users: {activeCount} / {rows.length}
        </p>
        {!canUpdateUsers ? (
          <p className="mt-2 text-sm text-muted-foreground">
            Only platform owners can change platform-user roles or deactivate accounts.
          </p>
        ) : null}
      </header>

      {message ? <p className="text-sm text-emerald-300">{message}</p> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}
      {loading ? <p className="text-sm text-muted-foreground">Loading users...</p> : null}

      <DataTable
        rows={rows}
        emptyMessage="No platform users found."
        columns={[
          {
            key: "user",
            header: "User",
            render: (row) => (
              <div>
                <p className="font-medium text-foreground">{row.full_name}</p>
                <p className="text-xs text-muted-foreground">{row.email}</p>
              </div>
            ),
          },
          {
            key: "role",
            header: "Role",
            render: (row) => (
              <RoleSelector
                value={row.role}
                roles={editableRoles}
                onChange={(next) => {
                  void changeRole(row, next)
                }}
                disabled={!row.is_active || !canUpdateUsers}
              />
            ),
          },
          {
            key: "mfa",
            header: "MFA",
            render: (row) => (
              <span className="text-muted-foreground">
                {row.mfa_enabled ? "Enabled" : row.force_mfa_setup ? "Setup required" : "Disabled"}
              </span>
            ),
          },
          {
            key: "status",
            header: "Status",
            render: (row) => (
              <span className={row.is_active ? "text-emerald-300" : "text-muted-foreground"}>
                {row.is_active ? "Active" : "Inactive"}
              </span>
            ),
          },
          {
            key: "actions",
            header: "Actions",
            render: (row) => (
              <div className="flex items-center gap-2">
                {canUpdateUsers && row.role !== "platform_admin" ? (
                  <button
                    type="button"
                    className="rounded-md border border-border px-2 py-1 text-xs text-foreground"
                    onClick={() => {
                      void changeRole(row, "platform_admin")
                    }}
                    disabled={!row.is_active}
                  >
                    Promote to admin
                  </button>
                ) : null}
                {canDeleteUsers ? (
                  <button
                    type="button"
                    className="rounded-md border border-[hsl(var(--brand-danger)/0.5)] px-2 py-1 text-xs text-[hsl(var(--brand-danger))]"
                    onClick={() => {
                      void deactivate(row)
                    }}
                    disabled={!row.is_active}
                  >
                    Deactivate
                  </button>
                ) : null}
              </div>
            ),
          },
        ]}
      />
    </div>
  )
}

"use client"

import { useEffect, useMemo, useState } from "react"
import { DataTable } from "@/components/admin/DataTable"
import {
  assignRbacRole,
  createRbacRole,
  grantRbacPermission,
  listPlatformUsers,
  listRbacAssignments,
  listRbacPermissions,
  listRbacRolePermissions,
  listRbacRoles,
} from "@/lib/api/platform-admin"
import type {
  PlatformUser,
  RbacAssignment,
  RbacPermission,
  RbacRole,
  RbacRolePermission,
} from "@/lib/types/platform-admin"

const nowIso = () => new Date().toISOString()

export default function AdminRbacPage() {
  const [roles, setRoles] = useState<RbacRole[]>([])
  const [permissions, setPermissions] = useState<RbacPermission[]>([])
  const [rolePermissions, setRolePermissions] = useState<RbacRolePermission[]>([])
  const [assignments, setAssignments] = useState<RbacAssignment[]>([])
  const [users, setUsers] = useState<PlatformUser[]>([])
  const [error, setError] = useState<string | null>(null)
  const [message, setMessage] = useState<string | null>(null)

  const [newRoleCode, setNewRoleCode] = useState("")
  const [newRoleScope, setNewRoleScope] = useState("PLATFORM")
  const [selectedRoleId, setSelectedRoleId] = useState("")
  const [selectedPermissionId, setSelectedPermissionId] = useState("")
  const [selectedUserId, setSelectedUserId] = useState("")
  const [selectedAssignRoleId, setSelectedAssignRoleId] = useState("")

  const load = async () => {
    setError(null)
    try {
      const [rolesData, permissionData, rolePermissionData, assignmentData, usersData] =
        await Promise.all([
          listRbacRoles(),
          listRbacPermissions(),
          listRbacRolePermissions(),
          listRbacAssignments(),
          listPlatformUsers({ limit: 200, offset: 0 }),
        ])
      setRoles(rolesData)
      setPermissions(permissionData)
      setRolePermissions(rolePermissionData)
      setAssignments(assignmentData)
      setUsers(usersData.data)
      if (!selectedRoleId && rolesData[0]) setSelectedRoleId(rolesData[0].id)
      if (!selectedAssignRoleId && rolesData[0]) setSelectedAssignRoleId(rolesData[0].id)
      if (!selectedPermissionId && permissionData[0]) setSelectedPermissionId(permissionData[0].id)
      if (!selectedUserId && usersData.data[0]) setSelectedUserId(usersData.data[0].id)
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load RBAC data")
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const roleMap = useMemo(
    () => new Map(roles.map((role) => [role.id, role.role_code])),
    [roles],
  )
  const permissionMap = useMemo(
    () => new Map(permissions.map((permission) => [permission.id, permission.permission_code])),
    [permissions],
  )
  const userMap = useMemo(
    () => new Map(users.map((user) => [user.id, user.email])),
    [users],
  )

  const onCreateRole = async () => {
    if (!newRoleCode.trim()) return
    setMessage(null)
    setError(null)
    try {
      await createRbacRole({
        role_code: newRoleCode.trim(),
        role_scope: newRoleScope,
        is_active: true,
      })
      setMessage(`Created role ${newRoleCode.trim()}.`)
      setNewRoleCode("")
      await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to create role")
    }
  }

  const onGrantPermission = async () => {
    if (!selectedRoleId || !selectedPermissionId) return
    setMessage(null)
    setError(null)
    try {
      await grantRbacPermission({
        role_id: selectedRoleId,
        permission_id: selectedPermissionId,
        effect: "allow",
      })
      setMessage("Permission assigned to role.")
      await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to assign permission")
    }
  }

  const onAssignRole = async () => {
    if (!selectedUserId || !selectedAssignRoleId) return
    setMessage(null)
    setError(null)
    try {
      await assignRbacRole({
        user_id: selectedUserId,
        role_id: selectedAssignRoleId,
        context_type: "tenant",
        context_id: null,
        assigned_by: null,
        effective_from: nowIso(),
      })
      setMessage("User-role mapping created.")
      await load()
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to map user to role")
    }
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold text-foreground">RBAC</h1>
        <p className="text-sm text-muted-foreground">
          Manage roles, role-permission grants, and user-role mappings.
        </p>
      </header>

      {message ? <p className="text-sm text-emerald-300">{message}</p> : null}
      {error ? <p className="text-sm text-[hsl(var(--brand-danger))]">{error}</p> : null}

      <section className="grid gap-3 rounded-xl border border-border bg-card p-4 md:grid-cols-3">
        <div className="space-y-2">
          <p className="text-sm font-medium text-foreground">Create Role</p>
          <input
            value={newRoleCode}
            onChange={(event) => setNewRoleCode(event.target.value)}
            placeholder="ROLE_CODE"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          />
          <input
            value={newRoleScope}
            onChange={(event) => setNewRoleScope(event.target.value)}
            placeholder="role_scope"
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          />
          <button
            type="button"
            onClick={() => void onCreateRole()}
            className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
          >
            Create Role
          </button>
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium text-foreground">Assign Permission</p>
          <select
            value={selectedRoleId}
            onChange={(event) => setSelectedRoleId(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="">Select role</option>
            {roles.map((role) => (
              <option key={role.id} value={role.id}>
                {role.role_code}
              </option>
            ))}
          </select>
          <select
            value={selectedPermissionId}
            onChange={(event) => setSelectedPermissionId(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="">Select permission</option>
            {permissions.map((permission) => (
              <option key={permission.id} value={permission.id}>
                {permission.permission_code}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void onGrantPermission()}
            className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
          >
            Grant Permission
          </button>
        </div>

        <div className="space-y-2">
          <p className="text-sm font-medium text-foreground">Map User to Role</p>
          <select
            value={selectedUserId}
            onChange={(event) => setSelectedUserId(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="">Select user</option>
            {users.map((user) => (
              <option key={user.id} value={user.id}>
                {user.email}
              </option>
            ))}
          </select>
          <select
            value={selectedAssignRoleId}
            onChange={(event) => setSelectedAssignRoleId(event.target.value)}
            className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
          >
            <option value="">Select role</option>
            {roles.map((role) => (
              <option key={role.id} value={role.id}>
                {role.role_code}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void onAssignRole()}
            className="rounded-md border border-border px-3 py-2 text-sm text-foreground"
          >
            Assign Role
          </button>
        </div>
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Roles</h2>
        <DataTable
          rows={roles}
          emptyMessage="No roles found."
          columns={[
            { key: "role_code", header: "Role Code", render: (row) => row.role_code },
            { key: "role_scope", header: "Scope", render: (row) => row.role_scope },
            { key: "active", header: "Active", render: (row) => (row.is_active ? "Yes" : "No") },
          ]}
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">Role Permissions</h2>
        <DataTable
          rows={rolePermissions}
          emptyMessage="No role-permission mappings found."
          columns={[
            {
              key: "role",
              header: "Role",
              render: (row) => roleMap.get(row.role_id) ?? row.role_id,
            },
            {
              key: "permission",
              header: "Permission",
              render: (row) => permissionMap.get(row.permission_id) ?? row.permission_id,
            },
            { key: "effect", header: "Effect", render: (row) => row.effect },
          ]}
        />
      </section>

      <section className="space-y-3">
        <h2 className="text-lg font-semibold text-foreground">User Role Mappings</h2>
        <DataTable
          rows={assignments}
          emptyMessage="No user-role assignments found."
          columns={[
            {
              key: "user",
              header: "User",
              render: (row) => userMap.get(row.user_id) ?? row.user_id,
            },
            {
              key: "role",
              header: "Role",
              render: (row) => roleMap.get(row.role_id) ?? row.role_id,
            },
            { key: "context", header: "Context", render: (row) => row.context_type },
            {
              key: "from",
              header: "Effective From",
              render: (row) => new Date(row.effective_from).toLocaleString(),
            },
          ]}
        />
      </section>
    </div>
  )
}

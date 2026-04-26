"use client"

import { useState, useEffect, useCallback } from "react"
import { toast } from "sonner"
import { Loader2, UserPlus } from "lucide-react"
import apiClient from "@/lib/api/client"
import type { UserRole } from "@/lib/auth"
import { FormField } from "@/components/ui/FormField"
import { Button } from "@/components/ui/button"
import { Dialog } from "@/components/ui/Dialog"
import { ConfirmDialog } from "@/components/ui/ConfirmDialog"
import { TableSkeleton } from "@/components/ui/TableSkeleton"
import { listOrgEntities, type OrgEntity } from "@/lib/api/orgSetup"

interface TenantUser {
  user_id: string
  email: string
  full_name: string
  role: string
  is_active: boolean
  mfa_enabled: boolean
  invite_accepted_at: string | null
  created_at: string
}

interface InviteForm {
  full_name: string
  email: string
  role: UserRole
  entity_ids: string[]
}

interface InviteFieldErrors {
  full_name?: string
  email?: string
  role?: string
}

const ASSIGNABLE_ROLES: UserRole[] = [
  "org_admin",
  "finance_leader",
  "finance_team",
  "director",
  "entity_user",
  "auditor",
  "hr_manager",
  "employee",
  "read_only",
]

const ROLE_LABELS: Record<string, string> = {
  super_admin: "Super Admin",
  platform_owner: "Platform Owner",
  platform_admin: "Platform Admin",
  platform_support: "Platform Support",
  org_admin: "Org Admin",
  finance_leader: "Finance Leader",
  finance_team: "Finance Team",
  director: "Director",
  entity_user: "Entity User",
  auditor: "Auditor",
  hr_manager: "HR Manager",
  employee: "Employee",
  read_only: "Read Only",
}

const formatDate = (iso: string): string => {
  try {
    return new Date(iso).toLocaleDateString("en-GB", {
      day: "2-digit",
      month: "short",
      year: "numeric",
    })
  } catch {
    return "—"
  }
}

export function UsersPanel() {
  const [users, setUsers] = useState<TenantUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const [inviteOpen, setInviteOpen] = useState(false)
  const [inviteForm, setInviteForm] = useState<InviteForm>({
    full_name: "",
    email: "",
    role: "read_only",
    entity_ids: [],
  })
  const [inviteErrors, setInviteErrors] = useState<InviteFieldErrors>({})
  const [inviteLoading, setInviteLoading] = useState(false)

  const [entities, setEntities] = useState<OrgEntity[]>([])

  const [offboardTarget, setOffboardTarget] = useState<TenantUser | null>(null)
  const [offboardReason, setOffboardReason] = useState("")
  const [offboardLoading, setOffboardLoading] = useState(false)

  const [roleChanging, setRoleChanging] = useState<Record<string, boolean>>({})

  const fetchUsers = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const response = await apiClient.get<{ users: TenantUser[]; total: number }>("/api/v1/users")
      const payload = response.data as { users: TenantUser[]; total: number }
      setUsers(Array.isArray(payload?.users) ? payload.users : [])
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Failed to load users")
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    void fetchUsers()
    listOrgEntities()
      .then(setEntities)
      .catch(() => setEntities([]))
  }, [fetchUsers])

  const validateInvite = (): boolean => {
    const errs: InviteFieldErrors = {}
    if (!inviteForm.full_name.trim()) errs.full_name = "Full name is required."
    if (!inviteForm.email.trim()) errs.email = "Email address is required."
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(inviteForm.email.trim()))
      errs.email = "Enter a valid email address."
    if (!inviteForm.role) errs.role = "Role is required."
    setInviteErrors(errs)
    return Object.keys(errs).length === 0
  }

  const handleInvite = async () => {
    if (!validateInvite()) return
    setInviteLoading(true)
    try {
      await apiClient.post("/api/v1/users", {
        full_name: inviteForm.full_name.trim(),
        email: inviteForm.email.trim(),
        role: inviteForm.role,
        entity_ids: inviteForm.entity_ids,
      })
      toast.success(`Invitation sent to ${inviteForm.email.trim()}`)
      setInviteOpen(false)
      setInviteForm({ full_name: "", email: "", role: "read_only", entity_ids: [] })
      setInviteErrors({})
      void fetchUsers()
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "Failed to send invitation")
    } finally {
      setInviteLoading(false)
    }
  }

  const handleRoleChange = async (user: TenantUser, newRole: string) => {
    if (newRole === user.role) return
    setRoleChanging((prev) => ({ ...prev, [user.user_id]: true }))
    try {
      await apiClient.patch(`/api/v1/users/${user.user_id}/role`, { role: newRole })
      setUsers((prev) =>
        prev.map((u) => (u.user_id === user.user_id ? { ...u, role: newRole } : u)),
      )
      toast.success(`Role updated to ${ROLE_LABELS[newRole] ?? newRole}`)
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "Failed to update role")
    } finally {
      setRoleChanging((prev) => ({ ...prev, [user.user_id]: false }))
    }
  }

  const handleOffboardConfirm = async () => {
    if (!offboardTarget) return
    setOffboardLoading(true)
    try {
      if (offboardReason.trim()) {
        await apiClient.post(`/api/v1/users/${offboardTarget.user_id}/offboard`, {
          reason: offboardReason.trim(),
        })
      } else {
        await apiClient.request({
          method: "DELETE",
          url: `/api/v1/users/${offboardTarget.user_id}`,
        })
      }
      toast.success(`${offboardTarget.full_name} has been offboarded`)
      setOffboardTarget(null)
      setOffboardReason("")
      void fetchUsers()
    } catch (cause) {
      toast.error(cause instanceof Error ? cause.message : "Failed to offboard user")
    } finally {
      setOffboardLoading(false)
    }
  }

  const toggleEntityId = (id: string) => {
    setInviteForm((prev) => ({
      ...prev,
      entity_ids: prev.entity_ids.includes(id)
        ? prev.entity_ids.filter((e) => e !== id)
        : [...prev.entity_ids, id],
    }))
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Team Members</h2>
          <p className="text-sm text-muted-foreground">
            Manage users, roles, and access for your organisation.
          </p>
        </div>
        <Button onClick={() => setInviteOpen(true)} size="sm">
          <UserPlus className="h-4 w-4" />
          Invite User
        </Button>
      </div>

      {/* Error banner */}
      {error ? (
        <div className="flex items-center justify-between rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          <span>{error}</span>
          <Button variant="ghost" size="sm" onClick={() => void fetchUsers()}>
            Retry
          </Button>
        </div>
      ) : null}

      {/* Table */}
      <div className="overflow-hidden rounded-lg border border-border">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted/40">
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Name</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Email</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Role</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Status</th>
              <th className="px-4 py-3 text-left font-medium text-muted-foreground">Joined</th>
              <th className="px-4 py-3 text-right font-medium text-muted-foreground">Actions</th>
            </tr>
          </thead>

          {loading ? (
            <TableSkeleton rows={5} cols={6} />
          ) : users.length === 0 && !error ? (
            <tbody>
              <tr>
                <td colSpan={6} className="px-4 py-12 text-center text-sm text-muted-foreground">
                  No users yet. Invite your first team member.
                </td>
              </tr>
            </tbody>
          ) : (
            <tbody className="divide-y divide-border">
              {users.map((user) => (
                <tr key={user.user_id} className="hover:bg-muted/20 transition-colors">
                  <td className="px-4 py-3">
                    <span className="font-medium text-foreground">{user.full_name}</span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{user.email}</td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-1.5">
                      {roleChanging[user.user_id] ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-muted-foreground" />
                      ) : null}
                      <select
                        className="rounded-md border border-border bg-background px-2 py-1 text-xs text-foreground disabled:opacity-50"
                        value={user.role}
                        disabled={!!roleChanging[user.user_id]}
                        onChange={(e) => void handleRoleChange(user, e.target.value)}
                        aria-label={`Change role for ${user.full_name}`}
                      >
                        {/* Show current role even if it's a platform role (read-only appearance) */}
                        {!ASSIGNABLE_ROLES.includes(user.role as UserRole) ? (
                          <option value={user.role}>{ROLE_LABELS[user.role] ?? user.role}</option>
                        ) : null}
                        {ASSIGNABLE_ROLES.map((r) => (
                          <option key={r} value={r}>
                            {ROLE_LABELS[r]}
                          </option>
                        ))}
                      </select>
                    </div>
                  </td>
                  <td className="px-4 py-3">
                    {user.is_active ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-xs font-medium text-emerald-400">
                        Active
                      </span>
                    ) : user.invite_accepted_at === null ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-amber-500/15 px-2 py-0.5 text-xs font-medium text-amber-400">
                        Invited
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 rounded-full bg-gray-500/15 px-2 py-0.5 text-xs font-medium text-gray-400">
                        Inactive
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">{formatDate(user.created_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <Button
                      variant="destructive"
                      size="xs"
                      onClick={() => {
                        setOffboardTarget(user)
                        setOffboardReason("")
                      }}
                      aria-label={`Offboard ${user.full_name}`}
                    >
                      Offboard
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          )}
        </table>
      </div>

      {/* Invite User modal */}
      <Dialog
        open={inviteOpen}
        onClose={() => {
          if (!inviteLoading) {
            setInviteOpen(false)
            setInviteErrors({})
          }
        }}
        title="Invite User"
        description="Send an invitation email to a new team member."
        size="md"
      >
        <div className="space-y-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <FormField id="invite-name" label="Full name" error={inviteErrors.full_name} required>
              <input
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground"
                placeholder="Jane Smith"
                value={inviteForm.full_name}
                onChange={(e) => setInviteForm((f) => ({ ...f, full_name: e.target.value }))}
                disabled={inviteLoading}
              />
            </FormField>
            <FormField id="invite-email" label="Email address" error={inviteErrors.email} required>
              <input
                type="email"
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground"
                placeholder="jane@example.com"
                value={inviteForm.email}
                onChange={(e) => setInviteForm((f) => ({ ...f, email: e.target.value }))}
                disabled={inviteLoading}
              />
            </FormField>
          </div>
          <FormField id="invite-role" label="Role" error={inviteErrors.role} required>
            <select
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground"
              value={inviteForm.role}
              onChange={(e) =>
                setInviteForm((f) => ({ ...f, role: e.target.value as UserRole }))
              }
              disabled={inviteLoading}
            >
              {ASSIGNABLE_ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </select>
          </FormField>

          {entities.length > 0 ? (
            <div className="space-y-2">
              <p className="text-sm font-medium text-foreground">
                Entity access{" "}
                <span className="font-normal text-muted-foreground">(optional)</span>
              </p>
              <div className="max-h-40 overflow-y-auto rounded-md border border-border bg-background p-2 space-y-1">
                {entities.map((entity) => (
                  <label
                    key={entity.id}
                    className="flex cursor-pointer items-center gap-2 rounded px-2 py-1 text-sm hover:bg-muted/40"
                  >
                    <input
                      type="checkbox"
                      className="h-3.5 w-3.5 accent-primary"
                      checked={inviteForm.entity_ids.includes(entity.id)}
                      onChange={() => toggleEntityId(entity.id)}
                      disabled={inviteLoading}
                    />
                    <span className="text-foreground">
                      {entity.display_name ?? entity.legal_name}
                    </span>
                    <span className="ml-auto text-xs text-muted-foreground">
                      {entity.entity_type}
                    </span>
                  </label>
                ))}
              </div>
            </div>
          ) : null}

          <div className="flex justify-end gap-2 pt-2">
            <Button
              variant="outline"
              disabled={inviteLoading}
              onClick={() => {
                setInviteOpen(false)
                setInviteErrors({})
              }}
            >
              Cancel
            </Button>
            <Button onClick={() => void handleInvite()} disabled={inviteLoading}>
              {inviteLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Send Invitation
            </Button>
          </div>
        </div>
      </Dialog>

      {/* Offboard confirmation modal */}
      {offboardTarget ? (
        <Dialog
          open={!!offboardTarget}
          onClose={() => {
            if (!offboardLoading) {
              setOffboardTarget(null)
              setOffboardReason("")
            }
          }}
          title={`Offboard ${offboardTarget.full_name}`}
          description={`This will deactivate ${offboardTarget.full_name}'s account. This action cannot be undone.`}
          size="sm"
        >
          <div className="space-y-4">
            <div className="space-y-2">
              <label
                htmlFor="offboard-reason"
                className="text-sm font-medium text-foreground"
              >
                Reason{" "}
                <span className="font-normal text-muted-foreground">(optional)</span>
              </label>
              <textarea
                id="offboard-reason"
                rows={3}
                className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground resize-none"
                placeholder="e.g. Employee has left the organisation"
                value={offboardReason}
                onChange={(e) => setOffboardReason(e.target.value)}
                disabled={offboardLoading}
              />
            </div>
            <div className="flex items-center justify-between gap-3">
              <Button
                variant="outline"
                disabled={offboardLoading}
                onClick={() => {
                  setOffboardTarget(null)
                  setOffboardReason("")
                }}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                disabled={offboardLoading}
                onClick={() => void handleOffboardConfirm()}
              >
                {offboardLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                Offboard User
              </Button>
            </div>
          </div>
        </Dialog>
      ) : null}
    </div>
  )
}

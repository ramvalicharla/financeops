import { createMetadata } from "@/lib/metadata"

export const metadata = createMetadata("Users")

export default function UsersRolesSettingsPage() {
  return (
    <div className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold text-white">Users & Roles</h1>
      <p className="text-sm text-gray-400">User and role management is available via the platform users module.</p>
    </div>
  )
}


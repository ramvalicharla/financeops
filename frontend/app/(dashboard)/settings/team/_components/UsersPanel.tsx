// Users management is currently a placeholder. The real implementation
// is tracked in FU-016. This panel is composed into /settings/team
// (Users tab) so the URL and tab structure exist when real user
// management lands.

export function UsersPanel() {
  return (
    <div className="space-y-4 p-6">
      <h1 className="text-2xl font-semibold text-white">Users & Roles</h1>
      <p className="text-sm text-gray-400">
        User and role management is available via the platform users module.
      </p>
    </div>
  )
}

// Tenant Profile — tenant-level settings and activation state.

export const tenantProfileKeys = {
  dataActivationReminder: () =>
    ["tenant-profile", "data-activation-reminder"] as const,
} as const

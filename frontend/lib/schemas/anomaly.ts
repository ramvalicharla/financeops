import { z } from "zod"

const severitySchema = z
  .enum(["low", "medium", "high", "critical"])
  .or(z.enum(["LOW", "MEDIUM", "HIGH", "CRITICAL"]))

const statusSchema = z
  .enum(["open", "snoozed", "resolved", "escalated"])
  .or(z.enum(["OPEN", "SNOOZED", "RESOLVED", "ESCALATED"]))

export const AnomalySchema = z.object({
  id: z.string().min(1),
  severity: severitySchema,
  category: z.string(),
  status: statusSchema.optional(),
  alert_status: statusSchema.optional(),
  detected_at: z.string(),
})
  .refine((value) => Boolean(value.status ?? value.alert_status), {
    message: "status is required",
  })
  .passthrough()

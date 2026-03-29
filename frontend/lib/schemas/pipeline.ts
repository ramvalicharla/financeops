import { z } from "zod"

export const PipelineRunSchema = z.object({
  id: z.string().min(1),
  status: z.enum(["running", "completed", "failed", "partial"]),
  triggered_at: z.string(),
  sync_run_id: z.string().min(1),
}).passthrough()

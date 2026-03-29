import { z } from "zod"

export const BoardPackRunSchema = z.object({
  id: z.string().min(1),
  status: z.enum(["pending", "running", "completed", "failed"]).or(
    z.enum(["PENDING", "RUNNING", "COMPLETE", "FAILED"]),
  ),
  created_at: z.string(),
  sections: z
    .array(
      z.object({
        section_type: z.string(),
        title: z.string(),
      }),
    )
    .optional(),
}).passthrough()

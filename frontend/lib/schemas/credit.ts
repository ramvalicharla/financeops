import { z } from "zod"

export const CreditBalanceSchema = z.object({
  balance: z.string(),
  reserved: z.string(),
  available: z.string(),
  currency: z.string().length(3),
})


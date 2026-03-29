import { z } from "zod"

const MISLineSchema = z.object({
  line_item: z.string(),
  current_value: z.string(),
  previous_value: z.string(),
  variance: z.string(),
})

const MISDashboardTemplateSchema = z.object({
  period: z.string(),
  entities: z.array(
    z.object({
      entity_id: z.string().uuid(),
      entity_name: z.string(),
      lines: z.array(MISLineSchema),
    }),
  ),
})

const MISLineItemLegacySchema = z.object({
  line_item_id: z.string(),
  label: z.string(),
  current_value: z.string(),
  previous_value: z.string(),
  variance: z.string(),
  variance_pct: z.string(),
  is_heading: z.boolean(),
  indent_level: z.number().int(),
})

const MISChartPointLegacySchema = z.object({
  period: z.string(),
  label: z.string(),
  revenue: z.string(),
  gross_profit: z.string(),
  ebitda: z.string(),
})

const MISDashboardLegacySchema = z.object({
  entity_id: z.string(),
  period: z.string(),
  previous_period: z.string(),
  revenue: z.string(),
  gross_profit: z.string(),
  ebitda: z.string(),
  net_profit: z.string(),
  revenue_change_pct: z.string(),
  gross_profit_change_pct: z.string(),
  ebitda_change_pct: z.string(),
  net_profit_change_pct: z.string(),
  line_items: z.array(MISLineItemLegacySchema),
  chart_data: z.array(MISChartPointLegacySchema),
})

export const MISDashboardSchema = z.union([
  MISDashboardTemplateSchema,
  MISDashboardLegacySchema,
])


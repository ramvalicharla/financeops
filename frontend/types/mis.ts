export interface MISPeriod {
  period: string
  label: string
}

export interface MISLineItem {
  line_item_id: string
  label: string
  current_value: string
  previous_value: string
  variance: string
  variance_pct: string
  is_heading: boolean
  indent_level: number
}

export interface MISChartPoint {
  period: string
  label: string
  revenue: string
  gross_profit: string
  ebitda: string
}

export interface MISDashboard {
  entity_id: string
  period: string
  previous_period: string
  revenue: string
  gross_profit: string
  ebitda: string
  net_profit: string
  revenue_change_pct: string
  gross_profit_change_pct: string
  ebitda_change_pct: string
  net_profit_change_pct: string
  line_items: MISLineItem[]
  chart_data: MISChartPoint[]
}

"use client"

import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
} from "recharts"
import type { ScenarioComparisonScenario } from "@/lib/types/scenario"
import { formatINR } from "@/lib/utils"

interface ScenarioComparisonProps {
  scenarios: ScenarioComparisonScenario[]
}

export function ScenarioComparison({ scenarios }: ScenarioComparisonProps) {
  return (
    <section className="grid gap-4 md:grid-cols-3">
      {scenarios.map((scenario) => (
        <article
          key={scenario.scenario_name}
          className={`rounded-xl border border-border bg-card p-4 ${
            scenario.is_base_case ? "ring-1 ring-[hsl(var(--brand-primary))]" : ""
          }`}
        >
          <div
            className="mb-3 rounded-md px-3 py-2 text-sm font-semibold text-white"
            style={{ backgroundColor: scenario.colour_hex }}
          >
            {scenario.scenario_label}
          </div>
          <div className="space-y-1 text-sm text-foreground">
            <p>Revenue: {formatINR(scenario.summary.revenue_total)}</p>
            <p>EBITDA: {formatINR(scenario.summary.ebitda_total)}</p>
            <p>EBITDA Margin: {scenario.summary.ebitda_margin_pct}%</p>
          </div>
          <div className="mt-3 w-full h-24">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={scenario.monthly}>
                <Tooltip />
                <Line
                  type="monotone"
                  dataKey="revenue"
                  stroke={scenario.colour_hex}
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </article>
      ))}
    </section>
  )
}

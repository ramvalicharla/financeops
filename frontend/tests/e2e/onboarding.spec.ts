import { expect, test, type Page } from "@playwright/test"
import {
  apiResponse,
  enableAuthBypassHeader,
  fulfillJson,
  mockCSRF,
  mockSession,
} from "./helpers/mocks"

type OrgGroup = {
  id: string
  tenant_id: string
  group_name: string
  country_of_incorp: string
  country_code: string
  functional_currency: string
  reporting_currency: string
  logo_url: string | null
  website: string | null
  created_at: string
  updated_at: string | null
}

type OrgEntity = {
  id: string
  tenant_id: string
  org_group_id: string
  cp_entity_id: string | null
  legal_name: string
  display_name: string | null
  entity_type: string
  country_code: string
  state_code: string | null
  functional_currency: string
  reporting_currency: string
  fiscal_year_start: number
  applicable_gaap: string
  industry_template_id: string | null
  incorporation_number: string | null
  pan: string | null
  tan: string | null
  cin: string | null
  gstin: string | null
  lei: string | null
  tax_jurisdiction: string | null
  tax_rate: string | null
  is_active: boolean
  created_at: string
  updated_at: string | null
}

type OrgOwnership = {
  id: string
  tenant_id: string
  parent_entity_id: string
  child_entity_id: string
  ownership_pct: string
  consolidation_method: string
  effective_from: string
  effective_to: string | null
  notes: string | null
  created_at: string
}

type OrgEntityErpConfig = {
  id: string
  tenant_id: string
  org_entity_id: string
  erp_type: string
  erp_version: string | null
  connection_config: Record<string, unknown> | null
  is_primary: boolean
  connection_tested: boolean
  connection_tested_at: string | null
  is_active: boolean
  created_at: string
  updated_at: string | null
}

type OrgSetupSummary = {
  group: OrgGroup | null
  entities: OrgEntity[]
  ownership: OrgOwnership[]
  erp_configs: OrgEntityErpConfig[]
  current_step: number
  completed_at: string | null
  coa_account_count: number
  coa_status: "pending" | "uploaded" | "skipped" | "erp_connected"
  onboarding_score: number
  mapping_summary: {
    total: number
    mapped: number
    confirmed: number
    unmapped: number
    confidence_avg: string
  }
}

function makeGroup(overrides: Partial<OrgGroup> = {}): OrgGroup {
  return {
    id: "group-001",
    tenant_id: "tenant-001",
    group_name: "Acme Group",
    country_of_incorp: "India",
    country_code: "IN",
    functional_currency: "INR",
    reporting_currency: "INR",
    logo_url: null,
    website: "https://acme.test",
    created_at: "2026-04-01T00:00:00Z",
    updated_at: null,
    ...overrides,
  }
}

function makeEntity(
  id: string,
  legalName: string,
  overrides: Partial<OrgEntity> = {},
): OrgEntity {
  return {
    id,
    tenant_id: "tenant-001",
    org_group_id: "group-001",
    cp_entity_id: null,
    legal_name: legalName,
    display_name: null,
    entity_type: "WHOLLY_OWNED_SUBSIDIARY",
    country_code: "IN",
    state_code: "KA",
    functional_currency: "INR",
    reporting_currency: "INR",
    fiscal_year_start: 4,
    applicable_gaap: "INDAS",
    industry_template_id: null,
    incorporation_number: null,
    pan: null,
    tan: null,
    cin: null,
    gstin: null,
    lei: null,
    tax_jurisdiction: null,
    tax_rate: null,
    is_active: true,
    created_at: "2026-04-01T00:00:00Z",
    updated_at: null,
    ...overrides,
  }
}

function baseSummary(overrides: Partial<OrgSetupSummary> = {}): OrgSetupSummary {
  return {
    group: null,
    entities: [],
    ownership: [],
    erp_configs: [],
    current_step: 1,
    completed_at: null,
    coa_account_count: 0,
    coa_status: "pending",
    onboarding_score: 25,
    mapping_summary: {
      total: 0,
      mapped: 0,
      confirmed: 0,
      unmapped: 0,
      confidence_avg: "0.00",
    },
    ...overrides,
  }
}

async function mockOrgSetupApi(
  page: Page,
  initialSummary: OrgSetupSummary,
): Promise<{
  latestStep1Payload: () => Record<string, unknown> | null
  latestStep2Payload: () => Record<string, unknown> | null
  latestStep3Payload: () => Record<string, unknown> | null
  latestStep4Payload: () => Record<string, unknown> | null
}> {
  let summary = structuredClone(initialSummary)
  let lastStep1Payload: Record<string, unknown> | null = null
  let lastStep2Payload: Record<string, unknown> | null = null
  let lastStep3Payload: Record<string, unknown> | null = null
  let lastStep4Payload: Record<string, unknown> | null = null

  await page.route("**/api/v1/org-setup/summary", async (route) => {
    await fulfillJson(route, apiResponse(summary))
  })

  await page.route("**/api/v1/org-setup/step1", async (route) => {
    lastStep1Payload = (route.request().postDataJSON() ?? {}) as Record<string, unknown>
    summary = {
      ...summary,
      group: makeGroup({
        group_name: String(lastStep1Payload.group_name ?? "Acme Group"),
        country_of_incorp: String(lastStep1Payload.country_of_incorp ?? "India"),
        country_code: String(lastStep1Payload.country_code ?? "IN"),
        functional_currency: String(lastStep1Payload.functional_currency ?? "INR"),
        reporting_currency: String(lastStep1Payload.reporting_currency ?? "INR"),
        website:
          typeof lastStep1Payload.website === "string" ? lastStep1Payload.website : null,
      }),
      current_step: 2,
      onboarding_score: 40,
    }
    await fulfillJson(route, apiResponse({ group: summary.group }))
  })

  await page.route("**/api/v1/org-setup/step2", async (route) => {
    lastStep2Payload = (route.request().postDataJSON() ?? {}) as Record<string, unknown>
    const payloadEntities = Array.isArray(lastStep2Payload.entities)
      ? lastStep2Payload.entities
      : []
    summary = {
      ...summary,
      entities: payloadEntities.map((entity, index) =>
        makeEntity(`entity-${index + 1}`, String(entity.legal_name ?? `Entity ${index + 1}`), {
          display_name:
            typeof entity.display_name === "string" ? entity.display_name : null,
          entity_type: String(entity.entity_type ?? "WHOLLY_OWNED_SUBSIDIARY"),
          country_code: String(entity.country_code ?? "IN"),
          state_code: typeof entity.state_code === "string" ? entity.state_code : null,
          functional_currency: String(entity.functional_currency ?? "INR"),
          reporting_currency: String(entity.reporting_currency ?? "INR"),
          fiscal_year_start: Number(entity.fiscal_year_start ?? 4),
          applicable_gaap: String(entity.applicable_gaap ?? "INDAS"),
          incorporation_number:
            typeof entity.incorporation_number === "string"
              ? entity.incorporation_number
              : null,
          pan: typeof entity.pan === "string" ? entity.pan : null,
          tan: typeof entity.tan === "string" ? entity.tan : null,
          cin: typeof entity.cin === "string" ? entity.cin : null,
          gstin: typeof entity.gstin === "string" ? entity.gstin : null,
          lei: typeof entity.lei === "string" ? entity.lei : null,
        }),
      ),
      current_step: 3,
      onboarding_score: 55,
    }
    await fulfillJson(route, apiResponse({ entities: summary.entities }))
  })

  await page.route("**/api/v1/org-setup/step3", async (route) => {
    lastStep3Payload = (route.request().postDataJSON() ?? {}) as Record<string, unknown>
    const relationships = Array.isArray(lastStep3Payload.relationships)
      ? lastStep3Payload.relationships
      : []
    summary = {
      ...summary,
      ownership: relationships.map((relationship, index) => ({
        id: `ownership-${index + 1}`,
        tenant_id: "tenant-001",
        parent_entity_id: String(relationship.parent_entity_id ?? "entity-1"),
        child_entity_id: String(relationship.child_entity_id ?? "entity-2"),
        ownership_pct: String(relationship.ownership_pct ?? "51.0000"),
        consolidation_method: "Full consolidation",
        effective_from: String(relationship.effective_from ?? "2026-04-01"),
        effective_to: null,
        notes: typeof relationship.notes === "string" ? relationship.notes : null,
        created_at: "2026-04-01T00:00:00Z",
      })),
      current_step: 4,
      onboarding_score: 70,
    }
    await fulfillJson(route, apiResponse({ ownership: summary.ownership }))
  })

  await page.route("**/api/v1/org-setup/step4", async (route) => {
    lastStep4Payload = (route.request().postDataJSON() ?? {}) as Record<string, unknown>
    const configs = Array.isArray(lastStep4Payload.configs) ? lastStep4Payload.configs : []
    summary = {
      ...summary,
      erp_configs: configs.map((config, index) => ({
        id: `erp-${index + 1}`,
        tenant_id: "tenant-001",
        org_entity_id: String(config.org_entity_id ?? `entity-${index + 1}`),
        erp_type: String(config.erp_type ?? "MANUAL"),
        erp_version: typeof config.erp_version === "string" ? config.erp_version : null,
        connection_config: null,
        is_primary: Boolean(config.is_primary),
        connection_tested: false,
        connection_tested_at: null,
        is_active: true,
        created_at: "2026-04-01T00:00:00Z",
        updated_at: null,
      })),
      onboarding_score: 85,
    }
    await fulfillJson(route, apiResponse({ configs: summary.erp_configs }))
  })

  await page.route("**/api/auth/callback/credentials", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ ok: true, status: 200, url: "/dashboard" }),
    })
  })

  await page.route("**/api/v1/erp/connectors**", async (route) => {
    await fulfillJson(route, apiResponse([]))
  })

  await page.route("**/api/v1/anomalies**", async (route) => {
    await fulfillJson(route, apiResponse({ items: [], total: 0 }))
  })

  await page.route("**/api/v1/accounting/journals**", async (route) => {
    await fulfillJson(route, apiResponse({ items: [], total: 0 }))
  })

  return {
    latestStep1Payload: () => lastStep1Payload,
    latestStep2Payload: () => lastStep2Payload,
    latestStep3Payload: () => lastStep3Payload,
    latestStep4Payload: () => lastStep4Payload,
  }
}

test.describe("Onboarding wizard", () => {
  test.beforeEach(async ({ page }) => {
    await enableAuthBypassHeader(page)
    await mockCSRF(page)
    await mockSession(page)
  })

  test("loads the current org setup step 1 flow", async ({ page }) => {
    await mockOrgSetupApi(page, baseSummary())
    await page.goto("/org-setup")

    await expect(page.getByRole("heading", { name: "Org details" })).toBeVisible()
    await expect(page.getByLabel("Legal name")).toBeVisible()
    await expect(page.getByLabel("Country of incorporation")).toBeVisible()
    await expect(page.getByLabel("Website")).toBeVisible()
    await expect(page.getByRole("button", { name: "Continue" })).toBeDisabled()
  })

  test("submits step 1 and advances to entity structure", async ({ page }) => {
    const api = await mockOrgSetupApi(page, baseSummary())
    await page.goto("/org-setup")

    await page.getByLabel("Legal name").fill("Finqor Holdings Pvt Ltd")
    await page.getByLabel("Website").fill("https://finqor.test")
    await page.getByRole("button", { name: "Continue" }).click({ force: true })

    await expect(page.getByRole("heading", { name: "Entity structure" })).toBeVisible()
    expect(api.latestStep1Payload()).toMatchObject({
      group_name: "Finqor Holdings Pvt Ltd",
      website: "https://finqor.test",
      country_code: "IN",
      functional_currency: "INR",
      reporting_currency: "INR",
    })
  })

  test("step 2 supports multiple entities and submits the current entity payload", async ({
    page,
  }) => {
    const api = await mockOrgSetupApi(
      page,
      baseSummary({ current_step: 2, group: makeGroup({ group_name: "Finqor Group" }) }),
    )
    await page.goto("/org-setup")

    await page.getByLabel("Legal name").fill("Finqor India Pvt Ltd")
    await page.getByRole("button", { name: "Add entity" }).click()
    await page.locator("#entity-legal-name-1").fill("Finqor Singapore Pte Ltd")
    await expect(page.getByText("Finqor Group", { exact: false })).toBeVisible()
    await expect(page.getByText("Finqor Singapore Pte Ltd")).toBeVisible()

    await page.locator("form").evaluate((form) => {
      ;(form as HTMLFormElement).requestSubmit()
    })

    await expect(page.getByRole("heading", { name: "Chart of accounts" })).toBeVisible()
    expect(api.latestStep2Payload()).toMatchObject({
      group_id: "group-001",
      entities: [
        expect.objectContaining({ legal_name: "Finqor India Pvt Ltd" }),
        expect.objectContaining({ legal_name: "Finqor Singapore Pte Ltd" }),
      ],
    })
  })

  test("step 3 multi-entity flow shows relationship controls and derives the method badge", async ({
    page,
  }) => {
    const api = await mockOrgSetupApi(
      page,
      baseSummary({
        current_step: 3,
        group: makeGroup(),
        entities: [
          makeEntity("entity-1", "Finqor Holdings"),
          makeEntity("entity-2", "Finqor India"),
        ],
      }),
    )
    await page.goto("/org-setup")

    await page.getByLabel("Parent entity").selectOption("entity-1")
    await page.getByLabel("Child entity").selectOption("entity-2")
    await page.getByLabel("Ownership (%)").fill("25.0000")
    await expect(page.getByText("Equity method")).toBeVisible()

    await page.getByRole("button", { name: "Continue" }).click()

    await expect(page.getByRole("heading", { name: "Connect ERP" })).toBeVisible()
    expect(api.latestStep3Payload()).toMatchObject({
      relationships: [
        expect.objectContaining({
          parent_entity_id: "entity-1",
          child_entity_id: "entity-2",
          ownership_pct: "25.0000",
        }),
      ],
    })
  })

  test("step 3 single-entity flow skips ownership structure", async ({ page }) => {
    const api = await mockOrgSetupApi(
      page,
      baseSummary({
        current_step: 3,
        group: makeGroup(),
        entities: [makeEntity("entity-1", "Finqor India")],
      }),
    )
    await page.goto("/org-setup")

    await expect(
      page.getByText("Single entity - no ownership structure required."),
    ).toBeVisible()
    await page.getByRole("button", { name: "Continue" }).click()

    await expect(page.getByRole("heading", { name: "Connect ERP" })).toBeVisible()
    expect(api.latestStep3Payload()).toMatchObject({ relationships: [] })
  })

  test("step 4 shows ERP options and skip moves into invite team", async ({ page }) => {
    const api = await mockOrgSetupApi(
      page,
      baseSummary({
        current_step: 4,
        group: makeGroup(),
        entities: [
          makeEntity("entity-1", "Finqor India"),
          makeEntity("entity-2", "Finqor Singapore"),
        ],
      }),
    )
    await page.goto("/org-setup")

    await expect(page.getByText("Finqor India")).toBeVisible()
    await page.locator("#erp-system-0").selectOption("TALLY_PRIME")
    await expect(page.getByLabel("Version")).toBeVisible()
    await page.getByLabel("Version").fill("4.1")
    await page.getByRole("button", { name: "Continue" }).click()

    await expect(page.getByRole("heading", { name: "Invite team" })).toBeVisible()
    expect(api.latestStep4Payload()).toEqual(
      expect.objectContaining({
        configs: expect.arrayContaining([
          expect.objectContaining({
            org_entity_id: "entity-1",
            erp_type: "TALLY_PRIME",
            erp_version: "4.1",
            is_primary: true,
          }),
        ]),
      }),
    )
  })

  test("step 5 invite team uses the current CTA text and row controls", async ({ page }) => {
    await mockOrgSetupApi(
      page,
      baseSummary({
        current_step: 4,
        group: makeGroup(),
        entities: [makeEntity("entity-1", "Finqor India")],
      }),
    )
    await page.goto("/org-setup")

    await page.getByRole("button", { name: "Skip for now" }).click()

    await expect(page.getByRole("heading", { name: "Invite team" })).toBeVisible()
    await page.getByPlaceholder("colleague@company.com").fill("ops@finqor.test")
    await expect(page.getByRole("button", { name: "Send invites & finish" })).toBeVisible()
    await expect(page.getByRole("button", { name: "Skip for now" })).toBeVisible()
    await page.getByRole("button", { name: "Add another" }).click()
    await expect(page.getByPlaceholder("colleague@company.com")).toHaveCount(2)
    await page.getByLabel("Remove invite").last().click()
    await expect(page.getByPlaceholder("colleague@company.com")).toHaveCount(1)
  })

  test("completed state shows the new summary cards and exit CTA", async ({ page }) => {
    await mockOrgSetupApi(
      page,
      baseSummary({
        current_step: 4,
        completed_at: "2026-04-13T10:00:00Z",
        group: makeGroup({ group_name: "Finqor Group" }),
        entities: [
          makeEntity("entity-1", "Finqor India"),
          makeEntity("entity-2", "Finqor Singapore"),
        ],
        erp_configs: [
          {
            id: "erp-1",
            tenant_id: "tenant-001",
            org_entity_id: "entity-1",
            erp_type: "TALLY_PRIME",
            erp_version: "4.1",
            connection_config: null,
            is_primary: true,
            connection_tested: false,
            connection_tested_at: null,
            is_active: true,
            created_at: "2026-04-01T00:00:00Z",
            updated_at: null,
          },
        ],
        coa_account_count: 132,
        coa_status: "uploaded",
        onboarding_score: 96,
        mapping_summary: {
          total: 132,
          mapped: 129,
          confirmed: 127,
          unmapped: 5,
          confidence_avg: "0.91",
        },
      }),
    )
    await page.goto("/org-setup?next=/sync")

    await expect(page.getByRole("heading", { name: "Organisation setup complete" })).toBeVisible()
    await expect(page.getByText("Finqor Group")).toBeVisible()
    await expect(page.getByText("Entities configured")).toBeVisible()
    await expect(page.getByText("ERP tools configured")).toBeVisible()
    await expect(page.getByText("96/100")).toBeVisible()
    await expect(page.getByText("127 accounts confirmed")).toBeVisible()
    await expect(page.getByRole("button", { name: "Enter Finqor ->" })).toBeVisible()
    await page.getByRole("button", { name: "Enter Finqor ->" }).click()
    await page.waitForURL("**/sync")
  })
})

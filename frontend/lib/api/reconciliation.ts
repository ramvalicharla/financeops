import apiClient from "@/lib/api/client"
import { useTenantStore } from "@/lib/store/tenant"
import type {
  GLTBAccount,
  GLTBReconResult,
  JournalEntry,
  PayrollCostCentre,
  PayrollReconSummary,
} from "@/types/reconciliation"

type PrimitiveListEnvelope = {
  items?: unknown[]
  data?: unknown[]
  entries?: unknown[]
  rows?: unknown[]
  next_cursor?: unknown
}

type NormalizedGlEntry = {
  id: string
  accountCode: string
  accountName: string
  entityName: string
  period: string
  currency: string
  debitAmountMinor: number
  creditAmountMinor: number
}

type NormalizedTbRow = {
  id: string
  accountCode: string
  accountName: string
  entityName: string
  period: string
  currency: string
  openingBalanceMinor: number
  closingBalanceMinor: number
}

type NormalizedReconItem = {
  id: string
  accountCode: string
  accountName: string
  glTotalMinor: number
  tbClosingBalanceMinor: number
  differenceMinor: number
  status: GLTBAccount["status"]
}

const PAGE_SIZE = 500
const RECONCILIATION_SHAPE_ERROR = "Invalid reconciliation response shape"
const RECONCILIATION_EXPORT_UNSUPPORTED = "Reconciliation export not supported yet"
const RECONCILIATION_ENTRY_DETAIL_UNSUPPORTED =
  "Reconciliation journal entry detail not supported yet"
const PAYROLL_RECONCILIATION_UNSUPPORTED =
  "Payroll reconciliation is not supported by the current backend contract"
const IS_DEBUG_ENABLED = process.env.NODE_ENV !== "production"

let hasLoggedQueryScopedPeriod = false

const isRecord = (value: unknown): value is Record<string, unknown> =>
  value !== null && typeof value === "object"

const toRecord = (value: unknown): Record<string, unknown> =>
  isRecord(value) ? value : {}

const toStringValue = (value: unknown): string =>
  typeof value === "string" ? value : value == null ? "" : String(value)

const parseMinorUnits = (value: unknown, row: unknown): number => {
  if (value === "" || value === null || value === undefined) {
    throw new Error(`Invalid empty amount in reconciliation data: ${JSON.stringify(row)}`)
  }

  const normalized = toStringValue(value).trim()
  if (!/^[+-]?\d+(\.\d+)?$/.test(normalized)) {
    throw new Error(`Invalid amount in reconciliation data: ${JSON.stringify(row)}`)
  }

  const negative = normalized.startsWith("-")
  const unsigned = normalized.replace(/^[+-]/, "")
  const [wholePart, fractionalPart = ""] = unsigned.split(".")
  const minorUnitsText = `${wholePart}${fractionalPart.padEnd(2, "0").slice(0, 2)}`
  const minorUnits = Number(minorUnitsText)
  if (!Number.isSafeInteger(minorUnits)) {
    throw new Error(`Invalid amount in reconciliation data: ${JSON.stringify(row)}`)
  }

  return negative ? -minorUnits : minorUnits
}

const formatAmount = (valueMinor: number): string => (valueMinor / 100).toFixed(2)

const debugReconciliationCall = (path: string, payload?: unknown) => {
  if (IS_DEBUG_ENABLED) {
    console.debug("Reconciliation API call", {
      method: "GET",
      path,
      payload,
    })
  }
}

const debugReconciliationResponse = (path: string, response: unknown) => {
  if (IS_DEBUG_ENABLED) {
    console.debug("Reconciliation API response", {
      path,
      response,
    })
  }
}

const extractList = (value: unknown): unknown[] => {
  if (Array.isArray(value)) {
    return value
  }

  const envelope = toRecord(value) as PrimitiveListEnvelope
  if (Array.isArray(envelope.items)) {
    return envelope.items
  }
  if (Array.isArray(envelope.data)) {
    return envelope.data
  }
  if (Array.isArray(envelope.entries)) {
    return envelope.entries
  }
  if (Array.isArray(envelope.rows)) {
    return envelope.rows
  }

  console.error("Invalid reconciliation list response", value)
  throw new Error("Invalid reconciliation list response shape")
}

const parsePeriod = (period: string): { periodYear: number; periodMonth: number } => {
  const match = /^(\d{4})-(\d{2})$/.exec(period.trim())
  if (!match) {
    throw new Error("Invalid reconciliation period")
  }

  const periodYear = Number(match[1])
  const periodMonth = Number(match[2])
  if (!Number.isInteger(periodYear) || !Number.isInteger(periodMonth) || periodMonth < 1 || periodMonth > 12) {
    throw new Error("Invalid reconciliation period")
  }

  return { periodYear, periodMonth }
}

const requireEntityQueryName = (entityId: string): string => {
  const entity = useTenantStore
    .getState()
    .entity_roles.find((item) => item.entity_id === entityId)

  if (!entity?.entity_name) {
    throw new Error("Unable to resolve reconciliation entity")
  }

  return entity.entity_name
}

const requireEntityName = (value: unknown): string => {
  const row = toRecord(value)
  const entityName = toStringValue(row.entity_name).trim()
  if (!entityName) {
    console.warn("Missing entity_name in reconciliation row", value)
    return "UNKNOWN"
  }
  return entityName
}

const normalizeGlEntry = (value: unknown): NormalizedGlEntry => {
  const row = toRecord(value)
  return {
    id: toStringValue(row.entry_id ?? row.id),
    accountCode: toStringValue(row.account_code),
    accountName: toStringValue(row.account_name),
    entityName: requireEntityName(row),
    period: toStringValue(row.period),
    currency: toStringValue(row.currency ?? row.currency_code),
    debitAmountMinor: parseMinorUnits(row.debit_amount, row),
    creditAmountMinor: parseMinorUnits(row.credit_amount, row),
  }
}

const normalizeTbRow = (value: unknown): NormalizedTbRow => {
  const row = toRecord(value)
  return {
    id: toStringValue(row.row_id ?? row.id),
    accountCode: toStringValue(row.account_code),
    accountName: toStringValue(row.account_name),
    entityName: requireEntityName(row),
    period: toStringValue(row.period),
    currency: toStringValue(row.currency ?? row.currency_code),
    openingBalanceMinor: parseMinorUnits(row.opening_balance, row),
    closingBalanceMinor: parseMinorUnits(row.closing_balance, row),
  }
}

const normalizeReconStatus = (value: unknown): GLTBAccount["status"] => {
  const normalized = toStringValue(value).trim().toUpperCase()
  if (
    normalized === "MATCHED" ||
    normalized === "VARIANCE" ||
    normalized === "MISSING_GL" ||
    normalized === "MISSING_TB"
  ) {
    return normalized
  }
  throw new Error(RECONCILIATION_SHAPE_ERROR)
}

const normalizeReconItem = (value: unknown): NormalizedReconItem => {
  const row = toRecord(value)
  return {
    id: toStringValue(row.item_id ?? row.id),
    accountCode: toStringValue(row.account_code),
    accountName: toStringValue(row.account_name),
    glTotalMinor: parseMinorUnits(row.gl_total, row),
    tbClosingBalanceMinor: parseMinorUnits(row.tb_closing_balance, row),
    differenceMinor: parseMinorUnits(row.difference, row),
    status: normalizeReconStatus(row.status),
  }
}

const validateNormalizedGlEntry = (
  value: NormalizedGlEntry,
  rawRow: unknown,
  requestedPeriod: string,
) => {
  if (!value.id || !value.accountCode || !value.accountName) {
    throw new Error(`Invalid GL entry shape: ${JSON.stringify(rawRow)}`)
  }
  if (
    typeof value.debitAmountMinor !== "number" ||
    typeof value.creditAmountMinor !== "number"
  ) {
    throw new Error("Invalid amount in reconciliation data")
  }
  if (value.period) {
    if (value.period !== requestedPeriod) {
      throw new Error("Reconciliation period mismatch")
    }
  } else if (!hasLoggedQueryScopedPeriod && IS_DEBUG_ENABLED) {
    console.debug("Period enforced via query scope", { requestedPeriod })
    hasLoggedQueryScopedPeriod = true
  }
}

const validateNormalizedTbRow = (
  value: NormalizedTbRow,
  rawRow: unknown,
  requestedPeriod: string,
) => {
  if (!value.id || !value.accountCode || !value.accountName) {
    throw new Error(`Invalid TB row shape: ${JSON.stringify(rawRow)}`)
  }
  if (
    typeof value.openingBalanceMinor !== "number" ||
    typeof value.closingBalanceMinor !== "number"
  ) {
    throw new Error("Invalid amount in reconciliation data")
  }
  if (value.period) {
    if (value.period !== requestedPeriod) {
      throw new Error("Reconciliation period mismatch")
    }
  } else if (!hasLoggedQueryScopedPeriod && IS_DEBUG_ENABLED) {
    console.debug("Period enforced via query scope", { requestedPeriod })
    hasLoggedQueryScopedPeriod = true
  }
}

const validateNormalizedReconItem = (value: NormalizedReconItem, rawRow: unknown) => {
  if (!value.id || !value.accountCode || !value.accountName) {
    throw new Error(`Invalid reconciliation item shape: ${JSON.stringify(rawRow)}`)
  }
  if (
    typeof value.glTotalMinor !== "number" ||
    typeof value.tbClosingBalanceMinor !== "number" ||
    typeof value.differenceMinor !== "number"
  ) {
    throw new Error("Invalid amount in reconciliation data")
  }
}

const computeAccountStatus = ({
  hasGl,
  hasTb,
  variance,
}: {
  hasGl: boolean
  hasTb: boolean
  variance: number
}): GLTBAccount["status"] => {
  if (!hasGl) {
    return "MISSING_GL"
  }
  if (!hasTb) {
    return "MISSING_TB"
  }
  return variance === 0 ? "MATCHED" : "VARIANCE"
}

const buildGlTbView = (
  glEntries: NormalizedGlEntry[],
  tbRows: NormalizedTbRow[],
  reconItems: NormalizedReconItem[],
  context: { entityId: string; period: string; runId: string },
): GLTBReconResult => {
  const accountMap = new Map<
    string,
    {
      account_code: string
      period: string
      entity_name: string
      currency: string
      account_name: string
      glBalanceMinor: number
      tbBalanceMinor: number
      hasGl: boolean
      hasTb: boolean
    }
  >()

  for (const entry of glEntries) {
    // NOTE: aggregation key limited by available fields.
    const key = [
      entry.accountCode,
      entry.period || context.period,
      entry.entityName || "",
      entry.currency || "",
    ].join("|")
    const current = accountMap.get(key) ?? {
      account_code: entry.accountCode,
      period: entry.period || context.period,
      entity_name: entry.entityName,
      currency: entry.currency,
      account_name: entry.accountName,
      glBalanceMinor: 0,
      tbBalanceMinor: 0,
      hasGl: false,
      hasTb: false,
    }
    current.account_name = current.account_name || entry.accountName
    current.glBalanceMinor += entry.debitAmountMinor - entry.creditAmountMinor
    current.hasGl = true
    accountMap.set(key, current)
  }

  for (const row of tbRows) {
    // NOTE: aggregation key limited by available fields.
    const key = [
      row.accountCode,
      row.period || context.period,
      row.entityName || "",
      row.currency || "",
    ].join("|")
    const current = accountMap.get(key) ?? {
      account_code: row.accountCode,
      period: row.period || context.period,
      entity_name: row.entityName,
      currency: row.currency,
      account_name: row.accountName,
      glBalanceMinor: 0,
      tbBalanceMinor: 0,
      hasGl: false,
      hasTb: false,
    }
    current.account_name = current.account_name || row.accountName
    current.tbBalanceMinor = row.closingBalanceMinor
    current.hasTb = true
    accountMap.set(key, current)
  }

  const reconItemMap = new Map(
    reconItems.map((item) => [`${item.accountCode}|${context.period}`, item]),
  )
  const accounts = Array.from(accountMap.values())
    .sort((left, right) => {
      if (left.account_code !== right.account_code) {
        return left.account_code.localeCompare(right.account_code)
      }
      return left.period.localeCompare(right.period)
    })
    .map<GLTBAccount>((account) => {
      const varianceMinor = account.glBalanceMinor - account.tbBalanceMinor
      const overlay = reconItemMap.get(`${account.account_code}|${account.period}`)
      const glBalanceMinor = overlay?.glTotalMinor ?? account.glBalanceMinor
      const tbBalanceMinor = overlay?.tbClosingBalanceMinor ?? account.tbBalanceMinor
      const effectiveVarianceMinor = overlay?.differenceMinor ?? varianceMinor
      const status =
        overlay?.status ??
        computeAccountStatus({
          hasGl: account.hasGl,
          hasTb: account.hasTb,
          variance: effectiveVarianceMinor,
        })

      const variancePct =
        tbBalanceMinor === 0
          ? effectiveVarianceMinor === 0
            ? 0
            : 100
          : (Math.abs(effectiveVarianceMinor) * 100) / Math.abs(tbBalanceMinor)

      return {
        account_code: account.account_code,
        account_name: account.account_name,
        account_type: "ASSET",
        tb_balance: formatAmount(tbBalanceMinor),
        gl_balance: formatAmount(glBalanceMinor),
        variance: formatAmount(effectiveVarianceMinor),
        variance_pct: formatAmount(Math.round(variancePct * 100)),
        status,
      }
    })

  const matchedAccounts = accounts.filter((account) => account.status === "MATCHED").length
  const varianceAccounts = accounts.filter((account) => account.status !== "MATCHED").length
  const totalVarianceMinor = accounts.reduce(
    (sum, account) => sum + parseMinorUnits(account.variance, account),
    0,
  )

  return {
    run_id: context.runId,
    entity_id: context.entityId,
    period: context.period,
    total_accounts: accounts.length,
    matched_accounts: matchedAccounts,
    variance_accounts: varianceAccounts,
    total_variance: formatAmount(totalVarianceMinor),
    accounts,
    generated_at: new Date().toISOString(),
  }
}

const fetchAllPages = async (
  path: string,
  params: Record<string, string>,
): Promise<unknown[]> => {
  const rows: unknown[] = []
  let offset = 0
  let pageCount = 0
  let previousCursor: string | null = null
  let lastOffset = -1

  while (true) {
    pageCount += 1
    if (pageCount > 1000) {
      throw new Error("Pagination loop detected")
    }
    if (typeof offset === "number") {
      if (offset === lastOffset) {
        console.warn("Pagination offset not advancing", { offset })
        return rows
      }
      lastOffset = offset
    }

    const query = new URLSearchParams(params)
    query.set("limit", String(PAGE_SIZE))
    query.set("offset", String(offset))
    const resolvedPath = `${path}?${query.toString()}`

    debugReconciliationCall(resolvedPath)
    const response = await apiClient.get<unknown>(resolvedPath)
    debugReconciliationResponse(resolvedPath, response.data)

    const payload = toRecord(response.data)
    const pageRows = extractList(payload)
    rows.push(...pageRows)

    const nextCursor = toStringValue(payload.next_cursor).trim() || null
    if (nextCursor && nextCursor === previousCursor) {
      console.warn("Pagination cursor not advancing")
      return rows
    }
    previousCursor = nextCursor

    if (pageRows.length < PAGE_SIZE) {
      return rows
    }

    offset += PAGE_SIZE
  }
}

export const getGLTBResult = async (
  entityId: string,
  period: string,
  runId: string,
): Promise<GLTBReconResult> => {
  const { periodYear, periodMonth } = parsePeriod(period)
  const entityName = requireEntityQueryName(entityId)
  const params = {
    period_year: String(periodYear),
    period_month: String(periodMonth),
    entity_name: entityName,
  }

  const [glEntryRows, tbRows, reconItemRows] = await Promise.all([
    fetchAllPages("/api/v1/recon/gl-entries", params),
    fetchAllPages("/api/v1/recon/tb-rows", params),
    fetchAllPages("/api/v1/recon/items", params),
  ])

  const glEntries = glEntryRows.map(normalizeGlEntry)
  glEntries.forEach((entry, index) =>
    validateNormalizedGlEntry(entry, glEntryRows[index], period),
  )
  const normalizedTbRows = tbRows.map(normalizeTbRow)
  normalizedTbRows.forEach((row, index) =>
    validateNormalizedTbRow(row, tbRows[index], period),
  )
  const reconItems = reconItemRows.map(normalizeReconItem)
  reconItems.forEach((item, index) =>
    validateNormalizedReconItem(item, reconItemRows[index]),
  )

  const result = buildGlTbView(glEntries, normalizedTbRows, reconItems, {
    entityId,
    period,
    runId,
  })
  if (IS_DEBUG_ENABLED) {
    console.debug("Reconciliation rows processed", {
      glCount: glEntries.length,
      tbCount: normalizedTbRows.length,
      resultCount: result.accounts.length,
    })
  }
  return result
}

export const getGLTBAccountEntries = async (
  entityId: string,
  accountCode: string,
  period: string,
): Promise<JournalEntry[]> => {
  const { periodYear, periodMonth } = parsePeriod(period)
  const entityName = requireEntityQueryName(entityId)
  const glEntryRows = await fetchAllPages("/api/v1/recon/gl-entries", {
    period_year: String(periodYear),
    period_month: String(periodMonth),
    entity_name: entityName,
  })

  const entries = glEntryRows
    .map(normalizeGlEntry)
    .map((entry, index) => {
      validateNormalizedGlEntry(entry, glEntryRows[index], period)
      return entry
    })
    .filter((entry) => entry.accountCode === accountCode)

  if (!entries.length) {
    return []
  }

  // TODO: backend does not expose posting date / description / reference for GL entry detail.
  throw new Error(RECONCILIATION_ENTRY_DETAIL_UNSUPPORTED)
}

export const exportGLTBCSV = async (
  entityId: string,
  period: string,
  runId: string,
): Promise<void> => {
  void entityId
  void period
  void runId
  // TODO: backend export endpoint not implemented for reconciliation.
  throw new Error(RECONCILIATION_EXPORT_UNSUPPORTED)
}

export const getPayrollRecon = async (
  entityId: string,
  period: string,
  runId: string,
): Promise<PayrollReconSummary> => {
  void entityId
  void period
  void runId
  // TODO: backend payroll reconciliation returns run/session primitives, not the summary contract required here.
  throw new Error(PAYROLL_RECONCILIATION_UNSUPPORTED)
}

export const getPayrollCostCentreDetail = async (
  entityId: string,
  costCentreId: string,
  period: string,
): Promise<PayrollCostCentre> => {
  void entityId
  void costCentreId
  void period
  // TODO: backend payroll reconciliation does not expose the cost-centre detail contract required here.
  throw new Error(PAYROLL_RECONCILIATION_UNSUPPORTED)
}

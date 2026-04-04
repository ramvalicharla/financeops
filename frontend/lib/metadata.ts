import type { Metadata } from "next"

const BASE_TITLE = "FinanceOps"
const BASE_DESCRIPTION =
  "Enterprise financial operations platform for 1B+ entities"

export function createMetadata(
  title: string,
  description?: string,
): Metadata {
  return {
    title: `${title} | ${BASE_TITLE}`,
    description: description ?? BASE_DESCRIPTION,
  }
}

export const defaultMetadata: Metadata = {
  title: BASE_TITLE,
  description: BASE_DESCRIPTION,
}

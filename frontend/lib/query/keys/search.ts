// Search — full-page search and command-palette inline search.

export const searchKeys = {
  // Full-page search results (search/PageClient)
  globalPage: (
    query: string,
    module: string,
    page: number,
    pageSize: number,
  ) => ["global-search-page", query, module, page, pageSize] as const,

  // Command-palette typeahead (CommandPalette)
  global: (query: string) => ["global-search", query] as const,
} as const

import { describe, it, expect, vi, beforeEach } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { TeamPageClient } from "../TeamPageClient"

const mockReplace = vi.fn()
const mockPathname = "/settings/team"

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mockReplace }),
  usePathname: () => mockPathname,
  useSearchParams: () => new URLSearchParams(),
}))

vi.mock("../_components/UsersPanel", () => ({
  UsersPanel: () => <div data-testid="users-panel">Users Panel</div>,
}))

vi.mock("../_components/GroupsPanel", () => ({
  GroupsPanel: () => <div data-testid="groups-panel">Groups Panel</div>,
}))

describe("TeamPageClient", () => {
  beforeEach(() => {
    mockReplace.mockClear()
  })

  it("renders both tab triggers", () => {
    render(<TeamPageClient initialTab="users" />)
    expect(screen.getByRole("tab", { name: "Users" })).toBeInTheDocument()
    expect(screen.getByRole("tab", { name: "Groups" })).toBeInTheDocument()
  })

  it("shows UsersPanel when initialTab is users", () => {
    render(<TeamPageClient initialTab="users" />)
    expect(screen.getByTestId("users-panel")).toBeInTheDocument()
  })

  it("shows GroupsPanel when initialTab is groups", () => {
    render(<TeamPageClient initialTab="groups" />)
    expect(screen.getByTestId("groups-panel")).toBeInTheDocument()
  })

  it("calls router.replace with ?tab=groups when Groups tab clicked", async () => {
    render(<TeamPageClient initialTab="users" />)
    await userEvent.click(screen.getByRole("tab", { name: "Groups" }))
    expect(mockReplace).toHaveBeenCalledWith(
      expect.stringContaining("tab=groups"),
      { scroll: false },
    )
  })

  it("calls router.replace with ?tab=users when Users tab clicked from groups", async () => {
    render(<TeamPageClient initialTab="groups" />)
    await userEvent.click(screen.getByRole("tab", { name: "Users" }))
    expect(mockReplace).toHaveBeenCalledWith(
      expect.stringContaining("tab=users"),
      { scroll: false },
    )
  })
})

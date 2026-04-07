import { render, screen } from "@testing-library/react"
import { describe, it, expect } from "vitest"
import { FormField } from "./FormField"

describe("FormField", () => {
  it("renders the label text", () => {
    render(
      <FormField id="email" label="Email Address">
        <input type="text" />
      </FormField>,
    )
    expect(screen.getByText("Email Address")).toBeInTheDocument()
  })

  it("label htmlFor matches field id", () => {
    render(
      <FormField id="username" label="Username">
        <input type="text" />
      </FormField>,
    )
    const label = screen.getByText("Username")
    expect(label).toHaveAttribute("for", "username")
  })

  it("sets id on child input via cloneElement", () => {
    render(
      <FormField id="myfield" label="My Field">
        <input type="text" />
      </FormField>,
    )
    expect(screen.getByRole("textbox")).toHaveAttribute("id", "myfield")
  })

  it("renders children", () => {
    render(
      <FormField id="field" label="Field">
        <input type="text" placeholder="Enter value" />
      </FormField>,
    )
    expect(screen.getByPlaceholderText("Enter value")).toBeInTheDocument()
  })

  it("renders error message when error prop is provided", () => {
    render(
      <FormField id="field" label="Field" error="This field is required">
        <input type="text" />
      </FormField>,
    )
    expect(screen.getByText("This field is required")).toBeInTheDocument()
  })

  it("error message has role=alert", () => {
    render(
      <FormField id="field" label="Field" error="Required">
        <input type="text" />
      </FormField>,
    )
    expect(screen.getByRole("alert")).toBeInTheDocument()
  })

  it("does not render error element when no error", () => {
    render(
      <FormField id="field" label="Field">
        <input type="text" />
      </FormField>,
    )
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("sets aria-invalid=true on input when error present", () => {
    render(
      <FormField id="field" label="Field" error="Bad value">
        <input type="text" />
      </FormField>,
    )
    expect(screen.getByRole("textbox")).toHaveAttribute("aria-invalid", "true")
  })

  it("does not set aria-invalid when no error", () => {
    render(
      <FormField id="field" label="Field">
        <input type="text" />
      </FormField>,
    )
    expect(screen.getByRole("textbox")).not.toHaveAttribute("aria-invalid", "true")
  })

  it("links input to error via aria-describedby", () => {
    render(
      <FormField id="myid" label="Field" error="Oops">
        <input type="text" />
      </FormField>,
    )
    const input = screen.getByRole("textbox")
    expect(input).toHaveAttribute("aria-describedby", expect.stringContaining("myid-error"))
  })

  it("links input to hint via aria-describedby", () => {
    render(
      <FormField id="myid" label="Field" hint="Enter your email">
        <input type="text" />
      </FormField>,
    )
    const input = screen.getByRole("textbox")
    expect(input).toHaveAttribute("aria-describedby", expect.stringContaining("myid-hint"))
  })

  it("hint and error both appear in aria-describedby", () => {
    render(
      <FormField id="myid" label="Field" hint="Hint text" error="Error text">
        <input type="text" />
      </FormField>,
    )
    const input = screen.getByRole("textbox")
    const describedBy = input.getAttribute("aria-describedby") ?? ""
    expect(describedBy).toContain("myid-hint")
    expect(describedBy).toContain("myid-error")
  })

  it("renders hint text when hint prop is provided", () => {
    render(
      <FormField id="field" label="Field" hint="This is a hint">
        <input type="text" />
      </FormField>,
    )
    expect(screen.getByText("This is a hint")).toBeInTheDocument()
  })

  it("shows required asterisk when required=true", () => {
    render(
      <FormField id="field" label="Name" required>
        <input type="text" />
      </FormField>,
    )
    expect(screen.getByText("*")).toBeInTheDocument()
  })

  it("sets aria-required=true on input when required=true", () => {
    render(
      <FormField id="field" label="Name" required>
        <input type="text" />
      </FormField>,
    )
    expect(screen.getByRole("textbox")).toHaveAttribute("aria-required", "true")
  })

  it("does not show asterisk when required=false", () => {
    render(
      <FormField id="field" label="Name">
        <input type="text" />
      </FormField>,
    )
    expect(screen.queryByText("*")).not.toBeInTheDocument()
  })
})

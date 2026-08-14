import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { useState } from "react";
import { SlugField } from "./SlugField";

function ControlledSlugField({ initial = "" }: { initial?: string }) {
  const [value, setValue] = useState(initial);
  return <SlugField value={value} onChange={setValue} />;
}

describe("SlugField", () => {
  it("shows an error for a slug that is too short", () => {
    render(<ControlledSlugField initial="AB" />);
    expect(screen.getByText(/3-60 characters: lowercase letters, numbers/i)).toBeInTheDocument();
    expect(screen.getByLabelText("Portfolio URL")).toHaveAttribute("aria-invalid", "true");
  });

  it("shows an error for a slug with a leading hyphen", () => {
    render(<ControlledSlugField initial="-abc" />);
    expect(screen.getByText(/3-60 characters: lowercase letters, numbers/i)).toBeInTheDocument();
  });

  it("shows an error for a slug typed in uppercase before lowercasing settles", () => {
    render(<ControlledSlugField initial="ABC-def" />);
    expect(screen.getByText(/3-60 characters: lowercase letters, numbers/i)).toBeInTheDocument();
  });

  it("shows no error for a valid slug", () => {
    render(<ControlledSlugField initial="john-doe-42" />);
    expect(
      screen.queryByText(/3-60 characters: lowercase letters, numbers/i),
    ).not.toBeInTheDocument();
    expect(screen.getByLabelText("Portfolio URL")).toHaveAttribute("aria-invalid", "false");
  });

  it("lowercases typed input before calling onChange", () => {
    render(<ControlledSlugField />);
    const input = screen.getByLabelText("Portfolio URL");
    fireEvent.change(input, { target: { value: "John-Doe" } });
    expect(input).toHaveValue("john-doe");
  });
});

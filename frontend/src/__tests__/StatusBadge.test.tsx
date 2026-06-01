import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "../components/StatusBadge";

describe("StatusBadge", () => {
  it("renders without crashing", () => {
    render(<StatusBadge status="ok" />);
    expect(screen.getByTestId("status-badge")).toBeInTheDocument();
  });

  it("displays Operational for ok status", () => {
    render(<StatusBadge status="ok" />);
    expect(screen.getByTestId("status-badge")).toHaveTextContent("Operational");
  });

  it("displays Degraded for degraded status", () => {
    render(<StatusBadge status="degraded" />);
    expect(screen.getByTestId("status-badge")).toHaveTextContent("Degraded");
  });

  it("displays Error for error status", () => {
    render(<StatusBadge status="error" />);
    expect(screen.getByTestId("status-badge")).toHaveTextContent("Error");
  });

  it("renders the status indicator dot", () => {
    render(<StatusBadge status="ok" />);
    expect(screen.getByTestId("status-dot")).toBeInTheDocument();
  });
});

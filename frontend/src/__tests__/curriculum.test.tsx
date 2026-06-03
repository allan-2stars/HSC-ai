import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import * as auth from "@/lib/auth";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => ({}),
  useSearchParams: () => new URLSearchParams(),
}));

vi.mock("@/lib/api", () => ({
  api: {
    getCurriculumDashboard: vi.fn(),
    getFrameworkCoverage: vi.fn(),
    getUnmappedQuestions: vi.fn(),
  },
}));

vi.mock("@/lib/auth", () => ({
  getAccessToken: vi.fn(() => "test-token"),
  clearTokens: vi.fn(),
}));


describe("CurriculumDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    (auth.getAccessToken as any).mockReturnValue("test-token");
  });

  it("renders summary cards and framework table", async () => {
    const mockDash = (await import("@/lib/api")).api.getCurriculumDashboard as any;
    mockDash.mockResolvedValue({
      overall_coverage_pct: 33.3,
      total_frameworks: 2,
      total_outcomes: 9,
      total_mapped: 5,
      total_covered: 3,
      unmapped_question_count: 7,
      all_red_outcome_count: 6,
      frameworks: [
        {
          framework_id: "fw-1",
          framework_name: "OC Mathematics 2026",
          total_outcomes: 5,
          mapped_outcomes: 3,
          covered_outcomes: 2,
          coverage_percentage: 40.0,
          red_count: 3,
          amber_count: 1,
          green_count: 1,
        },
        {
          framework_id: "fw-2",
          framework_name: "Selective Thinking Skills 2026",
          total_outcomes: 4,
          mapped_outcomes: 2,
          covered_outcomes: 1,
          coverage_percentage: 25.0,
          red_count: 3,
          amber_count: 0,
          green_count: 1,
        },
      ],
      top_gaps: [
        {
          framework_name: "OC Mathematics 2026",
          outcome_code: "OC-MATH-DECIMALS",
          outcome_title: "Decimals — multiply and divide",
          outcome_id: "o-1",
        },
        {
          framework_name: "Selective Thinking Skills 2026",
          outcome_code: "SEL-TS-INFERENCE",
          outcome_title: "Reading Inference",
          outcome_id: "o-2",
        },
      ],
    });

    const Page = (await import("@/app/(account)/admin/curriculum/page")).default;
    render(<Page />);

    // Summary cards
    expect(await screen.findByText("2")).toBeDefined(); // frameworks
    expect(screen.getByText("9")).toBeDefined(); // outcomes
    expect(screen.getByText("33.3%")).toBeDefined(); // coverage
    expect(screen.getByText("7")).toBeDefined(); // unmapped

    // Framework table
    // Both frameworks appear in the framework table and top gaps table
    expect(screen.getAllByText("OC Mathematics 2026").length).toBe(2);
    expect(screen.getAllByText("Selective Thinking Skills 2026").length).toBe(2);
    expect(screen.getByText("40%")).toBeDefined();
    expect(screen.getByText("25%")).toBeDefined();

    // Top gaps section
    expect(screen.getByText("Top Content Gaps")).toBeDefined();
    expect(screen.getByText("OC-MATH-DECIMALS")).toBeDefined();
    expect(screen.getByText("SEL-TS-INFERENCE")).toBeDefined();
  });

  it("shows outcome detail when framework is clicked", async () => {
    const mockDash = (await import("@/lib/api")).api.getCurriculumDashboard as any;
    const mockCoverage = (await import("@/lib/api")).api.getFrameworkCoverage as any;

    mockDash.mockResolvedValue({
      overall_coverage_pct: 0,
      total_frameworks: 1,
      total_outcomes: 2,
      total_mapped: 1,
      total_covered: 0,
      unmapped_question_count: 5,
      all_red_outcome_count: 2,
      frameworks: [
        {
          framework_id: "fw-1",
          framework_name: "OC Mathematics 2026",
          total_outcomes: 2,
          mapped_outcomes: 1,
          covered_outcomes: 0,
          coverage_percentage: 0,
          red_count: 2,
          amber_count: 0,
          green_count: 0,
        },
      ],
      top_gaps: [],
    });

    mockCoverage.mockResolvedValue({
      framework_id: "fw-1",
      framework_name: "OC Mathematics 2026",
      total_outcomes: 2,
      mapped_outcomes: 1,
      covered_outcomes: 0,
      coverage_percentage: 0,
      red_count: 2,
      amber_count: 0,
      green_count: 0,
      outcomes: [
        {
          outcome_id: "o-1",
          code: "OC-MATH-FRAC",
          title: "Fractions",
          approved_question_count: 0,
          draft_question_count: 3,
          total_question_count: 3,
          coverage_status: "red",
        },
        {
          outcome_id: "o-2",
          code: "OC-MATH-GEOM",
          title: "Geometry",
          approved_question_count: 0,
          draft_question_count: 0,
          total_question_count: 0,
          coverage_status: "red",
        },
      ],
    });

    const Page = (await import("@/app/(account)/admin/curriculum/page")).default;
    render(<Page />);

    expect(await screen.findByText("OC Mathematics 2026")).toBeDefined();

    // Click on the framework row
    fireEvent.click(screen.getByText("OC Mathematics 2026"));

    // Should now show outcome detail
    await waitFor(() => {
      expect(screen.getByText("OC-MATH-FRAC")).toBeDefined();
    });
    expect(screen.getByText("Geometry")).toBeDefined();
    expect(screen.getAllByText("red").length).toBeGreaterThanOrEqual(1);
  });

  it("shows empty state when no frameworks", async () => {
    const mockDash = (await import("@/lib/api")).api.getCurriculumDashboard as any;
    mockDash.mockResolvedValue({
      overall_coverage_pct: 0,
      total_frameworks: 0,
      total_outcomes: 0,
      total_mapped: 0,
      total_covered: 0,
      unmapped_question_count: 0,
      all_red_outcome_count: 0,
      frameworks: [],
      top_gaps: [],
    });

    const Page = (await import("@/app/(account)/admin/curriculum/page")).default;
    render(<Page />);

    expect(await screen.findByText("Curriculum Coverage Dashboard")).toBeDefined();
    expect(screen.getByText("0%")).toBeDefined(); // coverage = 0
    // Three stat cards show "0" (Frameworks, Outcomes, Unmapped Qs)
    expect(screen.getAllByText("0").length).toBe(3);
  });
});

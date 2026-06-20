import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";

const mockUseParams = vi.fn(() => ({ submissionId: "sub-1" }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => mockUseParams(),
  useSearchParams: () => new URLSearchParams(),
}));

const mockGetMyPortfolio = vi.fn();
const mockGetMyPortfolioItem = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getMyPortfolio: (...args: any[]) => mockGetMyPortfolio(...args),
    getMyPortfolioItem: (...args: any[]) => mockGetMyPortfolioItem(...args),
  },
}));

vi.mock("@/lib/auth", () => ({
  getAccessToken: vi.fn(() => "test-token"),
  clearTokens: vi.fn(),
}));

const mockUseAuth = vi.fn(() => ({
  user: { id: "u1", email: "s@test.com", role: "student", is_active: true },
  loading: false,
  role: "student",
  refresh: vi.fn(),
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => mockUseAuth(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => children,
}));

const mockPortfolioList = {
  count: 2,
  items: [
    {
      submission_id: "sub-1",
      task_id: "task-1",
      task_title: "Persuasive Essay",
      submitted_at: "2026-06-01T00:00:00Z",
      published_at: "2026-06-05T00:00:00Z",
      word_count: 300,
      average_rating: 4.0,
      strongest_dimensions: [{ dimension_name: "Ideas", rating: 4.5 }],
      weakest_dimensions: [{ dimension_name: "Structure", rating: 3.0 }],
      latest_feedback_summary: "Good work on ideas.",
      has_dispute: false,
      was_reopened: false,
    },
    {
      submission_id: "sub-2",
      task_id: "task-2",
      task_title: "Narrative Writing",
      submitted_at: "2026-06-10T00:00:00Z",
      published_at: "2026-06-15T00:00:00Z",
      word_count: 250,
      average_rating: 3.5,
      strongest_dimensions: [],
      weakest_dimensions: [],
      latest_feedback_summary: null,
      has_dispute: true,
      was_reopened: true,
    },
  ],
};

const mockPortfolioDetail = {
  submission_id: "sub-1",
  task_id: "task-1",
  task_title: "Persuasive Essay",
  task_prompt: "Should students wear uniforms?",
  task_instructions: "Use 3 arguments.",
  submitted_content: "My essay content.",
  word_count: 300,
  submitted_at: "2026-06-01T00:00:00Z",
  published_at: "2026-06-05T00:00:00Z",
  publication_version: 1,
  was_reopened: false,
  rubric_title: "Selective Writing Rubric",
  feedback: { overall_comment: "Good work.", version: 1, dimensions: null },
  scores: [{ dimension_id: "d1", name: "Ideas", rating: 4, comment: "Strong" }],
  disputes: [],
  disclaimer: "Writing feedback is educational guidance...",
};


// ── Student Portfolio List ──────────────────────────────────────────────

describe("Student Portfolio", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      user: { id: "u1", email: "s@test.com", role: "student", is_active: true },
      loading: false, role: "student", refresh: vi.fn(),
    });
  });

  it("renders portfolio items", async () => {
    mockGetMyPortfolio.mockResolvedValue(mockPortfolioList);
    const PortfolioPage = (await import("@/app/(account)/me/writing/portfolio/page")).default;
    render(React.createElement(PortfolioPage));
    await waitFor(() => {
      expect(screen.getByText("Persuasive Essay")).toBeTruthy();
      expect(screen.getByText("Narrative Writing")).toBeTruthy();
    });
  });

  it("renders dispute/reopen badges", async () => {
    mockGetMyPortfolio.mockResolvedValue(mockPortfolioList);
    const PortfolioPage = (await import("@/app/(account)/me/writing/portfolio/page")).default;
    render(React.createElement(PortfolioPage));
    await waitFor(() => {
      expect(screen.getByText("Disputed")).toBeTruthy();
      expect(screen.getByText("Revised")).toBeTruthy();
    });
  });

  it("renders empty state", async () => {
    mockGetMyPortfolio.mockResolvedValue({ items: [], count: 0 });
    const PortfolioPage = (await import("@/app/(account)/me/writing/portfolio/page")).default;
    render(React.createElement(PortfolioPage));
    await waitFor(() => {
      expect(screen.getByText(/your portfolio is empty/i)).toBeTruthy();
    });
  });

  it("renders dimension strengths", async () => {
    mockGetMyPortfolio.mockResolvedValue(mockPortfolioList);
    const PortfolioPage = (await import("@/app/(account)/me/writing/portfolio/page")).default;
    render(React.createElement(PortfolioPage));
    await waitFor(() => {
      expect(screen.getByText("Ideas")).toBeTruthy();
    });
  });
});

// ── Student Portfolio Detail ────────────────────────────────────────────

describe("Portfolio Detail", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      user: { id: "u1", email: "s@test.com", role: "student", is_active: true },
      loading: false, role: "student", refresh: vi.fn(),
    });
    mockUseParams.mockReturnValue({ submissionId: "sub-1" });
  });

  it("renders submitted content", async () => {
    mockGetMyPortfolioItem.mockResolvedValue(mockPortfolioDetail);
    const DetailPage = (await import("@/app/(account)/me/writing/portfolio/[submissionId]/page")).default;
    render(React.createElement(DetailPage));
    await waitFor(() => {
      expect(screen.getByText("My essay content.")).toBeTruthy();
    });
  });

  it("renders rubric scores", async () => {
    mockGetMyPortfolioItem.mockResolvedValue(mockPortfolioDetail);
    const DetailPage = (await import("@/app/(account)/me/writing/portfolio/[submissionId]/page")).default;
    render(React.createElement(DetailPage));
    await waitFor(() => {
      expect(screen.getByText("Ideas")).toBeTruthy();
      expect(screen.getByText("4/5 Strong")).toBeTruthy();
    });
  });

  it("renders feedback", async () => {
    mockGetMyPortfolioItem.mockResolvedValue(mockPortfolioDetail);
    const DetailPage = (await import("@/app/(account)/me/writing/portfolio/[submissionId]/page")).default;
    render(React.createElement(DetailPage));
    await waitFor(() => {
      expect(screen.getByText("Good work.")).toBeTruthy();
    });
  });

  it("renders disclaimer", async () => {
    mockGetMyPortfolioItem.mockResolvedValue(mockPortfolioDetail);
    const DetailPage = (await import("@/app/(account)/me/writing/portfolio/[submissionId]/page")).default;
    render(React.createElement(DetailPage));
    await waitFor(() => {
      expect(screen.getByText(/educational guidance/i)).toBeTruthy();
    });
  });

  it("renders task prompt and instructions", async () => {
    mockGetMyPortfolioItem.mockResolvedValue(mockPortfolioDetail);
    const DetailPage = (await import("@/app/(account)/me/writing/portfolio/[submissionId]/page")).default;
    render(React.createElement(DetailPage));
    await waitFor(() => {
      expect(screen.getByText("Should students wear uniforms?")).toBeTruthy();
      expect(screen.getByText("Use 3 arguments.")).toBeTruthy();
    });
  });
});

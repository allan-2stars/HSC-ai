import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import React from "react";

const mockUseParams = vi.fn(() => ({ studentId: "s1" }));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
  useParams: () => mockUseParams(),
  useSearchParams: () => new URLSearchParams(),
}));

const mockGetMyWritingAnalytics = vi.fn();
const mockGetStudentWritingAnalytics = vi.fn();
const mockGetAdminAnalyticsOverview = vi.fn();

vi.mock("@/lib/api", () => ({
  api: {
    getMyWritingAnalytics: (...args: any[]) => mockGetMyWritingAnalytics(...args),
    getStudentWritingAnalytics: (...args: any[]) => mockGetStudentWritingAnalytics(...args),
    getAdminAnalyticsOverview: (...args: any[]) => mockGetAdminAnalyticsOverview(...args),
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

const mockAnalytics = {
  summary: {
    published_reviews: 3,
    average_rating: 3.8,
    average_word_count: 250,
    disputes_count: 0,
    reopened_count: 0,
  },
  dimension_averages: [
    { dimension_name: "Ideas", average_rating: 4.2, attempts: 3 },
    { dimension_name: "Structure", average_rating: 3.5, attempts: 3 },
  ],
  progress_over_time: [
    { published_at: "2026-06-01T00:00:00Z", task_title: "Essay 1", average_rating: 3.5, word_count: 200 },
    { published_at: "2026-06-10T00:00:00Z", task_title: "Essay 2", average_rating: 4.0, word_count: 300 },
  ],
  strengths: [{ dimension_name: "Ideas", average_rating: 4.2 }],
  weaknesses: [{ dimension_name: "Structure", average_rating: 3.5 }],
  latest_feedback: {
    task_title: "Essay 2",
    published_at: "2026-06-10T00:00:00Z",
    overall_comment: "Good improvement on ideas.",
  },
};

const emptyAnalytics = {
  summary: { published_reviews: 0, average_rating: null, average_word_count: null, disputes_count: 0, reopened_count: 0 },
  dimension_averages: [],
  progress_over_time: [],
  strengths: [],
  weaknesses: [],
  latest_feedback: null,
};

// ── Student Analytics ────────────────────────────────────────────────────

describe("Student Writing Analytics", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      user: { id: "u1", email: "s@test.com", role: "student", is_active: true },
      loading: false,
      role: "student",
      refresh: vi.fn(),
    });
  });

  it("renders summary stats", async () => {
    mockGetMyWritingAnalytics.mockResolvedValue(mockAnalytics);
    const WritingAnalyticsPage = (await import("@/app/(account)/me/writing/analytics/page")).default;
    render(React.createElement(WritingAnalyticsPage));
    await waitFor(() => {
      expect(screen.getByText("Writing Analytics")).toBeTruthy();
    });
    expect(screen.getByText("3")).toBeTruthy();
    expect(screen.getByText("3.8")).toBeTruthy();
    expect(screen.getByText("250")).toBeTruthy();
  });

  it("renders dimension breakdown", async () => {
    mockGetMyWritingAnalytics.mockResolvedValue(mockAnalytics);
    const WritingAnalyticsPage = (await import("@/app/(account)/me/writing/analytics/page")).default;
    render(React.createElement(WritingAnalyticsPage));
    await waitFor(() => {
      expect(screen.getByText("Ideas")).toBeTruthy();
      expect(screen.getByText("Structure")).toBeTruthy();
    });
  });

  it("renders strengths and weaknesses", async () => {
    mockGetMyWritingAnalytics.mockResolvedValue(mockAnalytics);
    const WritingAnalyticsPage = (await import("@/app/(account)/me/writing/analytics/page")).default;
    render(React.createElement(WritingAnalyticsPage));
    await waitFor(() => {
      expect(screen.getByText("Strengths")).toBeTruthy();
      expect(screen.getByText("Areas to Improve")).toBeTruthy();
    });
  });

  it("renders latest feedback", async () => {
    mockGetMyWritingAnalytics.mockResolvedValue(mockAnalytics);
    const WritingAnalyticsPage = (await import("@/app/(account)/me/writing/analytics/page")).default;
    render(React.createElement(WritingAnalyticsPage));
    await waitFor(() => {
      expect(screen.getByText("Good improvement on ideas.")).toBeTruthy();
    });
  });

  it("renders progress over time", async () => {
    mockGetMyWritingAnalytics.mockResolvedValue(mockAnalytics);
    const WritingAnalyticsPage = (await import("@/app/(account)/me/writing/analytics/page")).default;
    render(React.createElement(WritingAnalyticsPage));
    await waitFor(() => {
      expect(screen.getByText("Essay 1")).toBeTruthy();
      expect(screen.getByText("Essay 2")).toBeTruthy();
    });
  });

  it("renders empty state safely", async () => {
    mockGetMyWritingAnalytics.mockResolvedValue(emptyAnalytics);
    const WritingAnalyticsPage = (await import("@/app/(account)/me/writing/analytics/page")).default;
    render(React.createElement(WritingAnalyticsPage));
    await waitFor(() => {
      expect(screen.getByText(/No published reviews yet/i)).toBeTruthy();
    });
  });
});

// ── Parent Analytics ─────────────────────────────────────────────────────

describe("Parent Writing Analytics", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      user: { id: "p1", email: "p@test.com", role: "parent", is_active: true },
      loading: false,
      role: "parent",
      refresh: vi.fn(),
    });
    mockUseParams.mockReturnValue({ studentId: "s1" });
  });

  it("renders child analytics summary", async () => {
    mockGetStudentWritingAnalytics.mockResolvedValue(mockAnalytics);
    const ParentPage = (await import("@/app/(account)/parent/writing/analytics/[studentId]/page")).default;
    render(React.createElement(ParentPage));
    await waitFor(() => {
      expect(screen.getByText("Writing Analytics")).toBeTruthy();
      expect(screen.getByText("3")).toBeTruthy();
    });
  });
});

// ── Admin Analytics ──────────────────────────────────────────────────────

describe("Admin Writing Analytics", () => {
  const adminOverview = {
    published_reviews: 12,
    average_rating: 3.9,
    average_word_count: 280,
    disputes_count: 2,
    dimension_averages: [
      { dimension_name: "Ideas", average_rating: 4.0, count: 12 },
      { dimension_name: "Structure", average_rating: 3.2, count: 12 },
    ],
    recent_activity: [
      { task_title: "Essay A", student_name: "Student One", published_at: "2026-06-10T00:00:00Z", word_count: 300 },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      user: { id: "a1", email: "a@test.com", role: "admin", is_active: true },
      loading: false,
      role: "admin",
      refresh: vi.fn(),
    });
  });

  it("renders admin overview stats", async () => {
    mockGetAdminAnalyticsOverview.mockResolvedValue(adminOverview);
    const AdminPage = (await import("@/app/(account)/admin/writing/analytics/page")).default;
    render(React.createElement(AdminPage));
    await waitFor(() => {
      expect(screen.getByText("Writing Analytics")).toBeTruthy();
      expect(screen.getByText("12")).toBeTruthy();
      expect(screen.getByText("3.9")).toBeTruthy();
    });
  });

  it("renders dimension averages", async () => {
    mockGetAdminAnalyticsOverview.mockResolvedValue(adminOverview);
    const AdminPage = (await import("@/app/(account)/admin/writing/analytics/page")).default;
    render(React.createElement(AdminPage));
    await waitFor(() => {
      expect(screen.getByText("Ideas")).toBeTruthy();
      expect(screen.getByText("Structure")).toBeTruthy();
    });
  });

  it("renders recent activity with student names", async () => {
    mockGetAdminAnalyticsOverview.mockResolvedValue(adminOverview);
    const AdminPage = (await import("@/app/(account)/admin/writing/analytics/page")).default;
    render(React.createElement(AdminPage));
    await waitFor(() => {
      expect(screen.getByText("Student One")).toBeTruthy();
      expect(screen.getByText("Essay A")).toBeTruthy();
    });
  });

  it("renders empty state when no reviews", async () => {
    mockGetAdminAnalyticsOverview.mockResolvedValue({
      published_reviews: 0,
      average_rating: null,
      average_word_count: null,
      disputes_count: 0,
      dimension_averages: [],
      recent_activity: [],
    });
    const AdminPage = (await import("@/app/(account)/admin/writing/analytics/page")).default;
    render(React.createElement(AdminPage));
    await waitFor(() => {
      expect(screen.getByText(/No published writing reviews yet/i)).toBeTruthy();
    });
  });
});

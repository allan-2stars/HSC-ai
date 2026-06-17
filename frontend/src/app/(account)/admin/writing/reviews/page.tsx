"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type WritingReviewItem } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

const STATUS_STYLES: Record<string, string> = {
  pending: "bg-amber-400/10 text-amber-400",
  assigned: "bg-interactive/10 text-interactive",
  under_review: "bg-interactive/10 text-interactive",
  reviewed: "bg-success/10 text-success",
  published: "bg-success/10 text-success",
};

export default function AdminWritingReviewsPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <AdminWritingReviews />
    </RoleGuard>
  );
}

function AdminWritingReviews() {
  const [reviews, setReviews] = useState<WritingReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<string>("");

  const token = getAccessToken();

  function load() {
    if (!token) return;
    setLoading(true);
    api.listWritingReviews(token, filter || undefined)
      .then(setReviews)
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load reviews");
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token, filter]);

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Writing Review Queue</h1>
          <p className="text-text-secondary text-sm">Admin · Human review of submitted writing</p>
        </div>
        <Link href="/admin/writing" className="text-interactive hover:underline text-sm">
          Writing Tasks
        </Link>
      </div>

      <div className="flex gap-2 mb-4">
        {["", "pending", "assigned", "under_review", "reviewed", "published"].map((s) => (
          <button
            key={s || "all"}
            onClick={() => setFilter(s)}
            className={`text-xs px-3 py-1 rounded border ${
              filter === s ? "border-interactive text-interactive" : "border-border-subtle text-text-tertiary"
            }`}
          >
            {s === "" ? "All" : s.replace("_", " ")}
          </button>
        ))}
      </div>

      {reviews.length === 0 ? (
        <p className="text-text-tertiary">No reviews in this view.</p>
      ) : (
        <div className="space-y-3">
          {reviews.map((r) => (
            <Link
              key={r.id}
              href={`/admin/writing/reviews/${r.id}`}
              className="block bg-surface border border-border-subtle rounded-lg p-4 hover:border-interactive"
            >
              <div className="flex items-center justify-between mb-1">
                <div>
                  <span className="text-text-primary font-medium">{r.student_name ?? "Student"}</span>
                  <span className="text-text-tertiary text-sm ml-2">— {r.task_title}</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded ${STATUS_STYLES[r.status] ?? ""}`}>
                  {r.status.replace("_", " ")}
                </span>
              </div>
              <div className="flex gap-4 text-xs text-text-tertiary">
                {typeof r.word_count === "number" && <span>{r.word_count} words</span>}
                {r.submitted_at && <span>Submitted: {new Date(r.submitted_at).toLocaleString()}</span>}
                {r.latest_feedback_version && <span>Feedback v{r.latest_feedback_version}</span>}
              </div>
            </Link>
          ))}
        </div>
      )}

      <div className="mt-8 space-x-4">
        <Link href="/admin/writing" className="text-interactive hover:underline text-sm">Writing Tasks</Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}

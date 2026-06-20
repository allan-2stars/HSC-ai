"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type WritingAnalytics } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

export default function WritingAnalyticsPage() {
  return (
    <RoleGuard roles={["student"]}>
      <AnalyticsView />
    </RoleGuard>
  );
}

function AnalyticsView() {
  const [data, setData] = useState<WritingAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const token = getAccessToken();

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    api.getMyWritingAnalytics(token)
      .then(setData)
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load analytics");
      })
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;
  if (!data) return <p className="p-8 text-text-secondary">No data</p>;

  const s = data.summary;

  return (
    <div className="max-w-4xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">Writing Analytics</h1>
      <p className="text-text-secondary text-sm mb-8">Your writing performance over time</p>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-8">
        <Card label="Reviews" value={s.published_reviews} />
        <Card label="Avg Rating" value={s.average_rating?.toFixed(1) ?? "—"} />
        <Card label="Avg Words" value={s.average_word_count?.toFixed(0) ?? "—"} />
        <Card label="Disputes" value={s.disputes_count} color={s.disputes_count > 0 ? "text-amber-400" : "text-text-primary"} />
        <Card label="Reopened" value={s.reopened_count} />
      </div>

      {/* Progress Over Time */}
      {data.progress_over_time.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-3">Progress Over Time</h2>
          <div className="space-y-2">
            {data.progress_over_time.map((p, i) => (
              <div key={i} className="bg-surface border border-border-subtle rounded-lg p-4 flex items-center justify-between">
                <div>
                  <p className="text-text-primary text-sm font-medium">{p.task_title}</p>
                  {p.published_at && <p className="text-text-tertiary text-xs">{new Date(p.published_at).toLocaleDateString()}</p>}
                </div>
                <div className="flex items-center gap-4 text-sm">
                  <span className="text-text-secondary">{p.word_count} words</span>
                  <span className="text-interactive font-medium">{p.average_rating?.toFixed(1) ?? "—"}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Dimensions */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        {data.strengths.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold text-success mb-3">Strengths</h2>
            <div className="space-y-2">
              {data.strengths.map((s, i) => (
                <div key={i} className="bg-surface border border-border-subtle rounded-lg p-3 flex items-center justify-between">
                  <span className="text-text-primary text-sm">{s.dimension_name}</span>
                  <span className="text-success text-sm font-medium">{s.average_rating.toFixed(1)}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {data.weaknesses.length > 0 && (
          <div>
            <h2 className="text-lg font-semibold text-error mb-3">Areas to Improve</h2>
            <div className="space-y-2">
              {data.weaknesses.map((w, i) => (
                <div key={i} className="bg-surface border border-border-subtle rounded-lg p-3 flex items-center justify-between">
                  <span className="text-text-primary text-sm">{w.dimension_name}</span>
                  <span className="text-error text-sm font-medium">{w.average_rating.toFixed(1)}</span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Dimension Averages */}
      {data.dimension_averages.length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-text-primary mb-3">Dimension Breakdown</h2>
          <div className="space-y-2">
            {data.dimension_averages.map((d) => (
              <div key={d.dimension_name} className="bg-surface border border-border-subtle rounded-lg p-3 flex items-center justify-between">
                <span className="text-text-primary text-sm">{d.dimension_name}</span>
                <div className="flex items-center gap-3 text-sm">
                  <span className="text-text-tertiary">{d.attempts} reviews</span>
                  <span className="text-interactive font-medium">{d.average_rating.toFixed(1)}</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Latest Feedback */}
      {data.latest_feedback && (
        <div className="mb-8 bg-surface border border-border-subtle rounded-lg p-4">
          <h2 className="text-lg font-semibold text-text-primary mb-2">Latest Feedback</h2>
          <p className="text-text-tertiary text-xs mb-2">
            {data.latest_feedback.task_title}
            {data.latest_feedback.published_at && ` — ${new Date(data.latest_feedback.published_at).toLocaleDateString()}`}
          </p>
          <p className="text-text-primary text-sm whitespace-pre-wrap">{data.latest_feedback.overall_comment}</p>
        </div>
      )}

      <div className="mt-8 space-x-4">
        <Link href="/me/writing" className="text-interactive hover:underline text-sm">Writing Tasks</Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}

function Card({ label, value, color = "text-text-primary" }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="bg-surface border border-border-subtle rounded-lg p-4 text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-text-tertiary text-xs mt-1">{label}</p>
    </div>
  );
}

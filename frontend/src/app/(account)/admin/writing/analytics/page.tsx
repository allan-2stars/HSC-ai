"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type AdminAnalyticsOverview } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

export default function AdminAnalyticsPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <AdminAnalyticsView />
    </RoleGuard>
  );
}

function AdminAnalyticsView() {
  const [data, setData] = useState<AdminAnalyticsOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const token = getAccessToken();

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    api.getAdminAnalyticsOverview(token)
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

  const empty = data.published_reviews === 0;

  return (
    <div className="max-w-5xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">Writing Analytics</h1>
      <p className="text-text-secondary text-sm mb-8">Admin · Platform-wide writing overview</p>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
        <Card label="Published Reviews" value={data.published_reviews} />
        <Card label="Avg Rating" value={data.average_rating?.toFixed(1) ?? "—"} />
        <Card label="Avg Words" value={data.average_word_count?.toFixed(0) ?? "—"} />
        <Card label="Disputes" value={data.disputes_count} color={data.disputes_count > 0 ? "text-amber-400" : "text-text-primary"} />
      </div>

      {empty && (
        <div className="bg-surface border border-border-subtle rounded-lg p-8 text-center mb-8">
          <p className="text-text-tertiary text-sm">No published writing reviews yet. Published reviews will appear here.</p>
        </div>
      )}

      {!empty && (
        <>
          {/* Dimension Averages */}
          {data.dimension_averages.length > 0 && (
            <div className="mb-8">
              <h2 className="text-lg font-semibold text-text-primary mb-3">Dimensions Across All Students</h2>
              <div className="space-y-2">
                {data.dimension_averages.map((d) => {
                  const pct = Math.min((d.average_rating / 5) * 100, 100);
                  return (
                    <div key={d.dimension_name}>
                      <div className="flex items-center justify-between text-xs mb-1">
                        <span className="text-text-secondary">{d.dimension_name}</span>
                        <span className="text-text-tertiary">{d.average_rating.toFixed(1)} / 5 ({d.count} reviews)</span>
                      </div>
                      <div className="h-3 bg-surface-secondary rounded-full overflow-hidden">
                        <div className={`h-full rounded-full ${d.average_rating >= 4 ? "bg-success" : d.average_rating >= 3 ? "bg-interactive" : "bg-amber-400"}`} style={{ width: `${pct}%` }} />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* Recent Activity */}
          {data.recent_activity.length > 0 && (
            <div className="mb-8">
              <h2 className="text-lg font-semibold text-text-primary mb-3">Recent Activity</h2>
              <div className="space-y-2">
                {data.recent_activity.map((a, i) => (
                  <div key={i} className="bg-surface border border-border-subtle rounded-lg p-4 flex items-center justify-between">
                    <div>
                      <p className="text-text-primary text-sm font-medium">{a.task_title}</p>
                      <p className="text-text-tertiary text-xs">{a.student_name}</p>
                    </div>
                    <div className="flex items-center gap-4 text-sm">
                      <span className="text-text-secondary">{a.word_count} words</span>
                      {a.published_at && <span className="text-text-tertiary text-xs">{new Date(a.published_at).toLocaleDateString()}</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      <div className="mt-8 space-x-4">
        <Link href="/admin/writing" className="text-interactive hover:underline text-sm">Writing Tasks</Link>
        <Link href="/admin/writing/reviews" className="text-interactive hover:underline text-sm">Review Queue</Link>
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

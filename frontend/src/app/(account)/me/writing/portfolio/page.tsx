"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type WritingAnalytics } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

interface PortfolioItem {
  submission_id: string;
  task_id: string;
  task_title: string;
  submitted_at: string | null;
  published_at: string | null;
  word_count: number;
  average_rating: number | null;
  strongest_dimensions: { dimension_name: string; rating: number }[];
  weakest_dimensions: { dimension_name: string; rating: number }[];
  latest_feedback_summary: string | null;
  has_dispute: boolean;
  was_reopened: boolean;
}

interface PortfolioList {
  items: PortfolioItem[];
  count: number;
}

export default function WritingPortfolioPage() {
  return (
    <RoleGuard roles={["student"]}>
      <PortfolioView />
    </RoleGuard>
  );
}

function PortfolioView() {
  const [data, setData] = useState<PortfolioList | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const token = getAccessToken();

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    api.getMyPortfolio(token)
      .then(setData)
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load portfolio");
      })
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;
  if (!data) return <p className="p-8 text-text-secondary">No data</p>;

  return (
    <div className="max-w-4xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">My Writing Portfolio</h1>
      <p className="text-text-secondary text-sm mb-8">{data.count} published work{data.count !== 1 ? "s" : ""}</p>

      {data.count === 0 ? (
        <div className="bg-surface border border-border-subtle rounded-lg p-8 text-center">
          <p className="text-text-tertiary text-sm">Your portfolio is empty. Complete and submit writing tasks to see your work here.</p>
        </div>
      ) : (
        <div className="space-y-4">
          {data.items.map((item) => (
            <Link
              key={item.submission_id}
              href={`/me/writing/portfolio/${item.submission_id}`}
              className="block bg-surface border border-border-subtle rounded-lg p-5 hover:border-interactive/30 transition-colors"
            >
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-text-primary font-medium">{item.task_title}</h2>
                <div className="flex items-center gap-2">
                  {item.has_dispute && <span className="text-xs bg-amber-400/10 text-amber-400 px-2 py-0.5 rounded">Disputed</span>}
                  {item.was_reopened && <span className="text-xs bg-interactive/10 text-interactive px-2 py-0.5 rounded">Revised</span>}
                </div>
              </div>
              <div className="flex items-center gap-4 text-xs text-text-tertiary mb-3">
                <span>{item.word_count} words</span>
                {item.average_rating !== null && <span className="text-interactive font-medium">{item.average_rating.toFixed(1)} / 5 avg</span>}
                {item.published_at && <span>{new Date(item.published_at).toLocaleDateString()}</span>}
              </div>
              {item.latest_feedback_summary && (
                <p className="text-text-secondary text-sm line-clamp-2">{item.latest_feedback_summary}</p>
              )}
              {item.strongest_dimensions.length > 0 && (
                <div className="flex items-center gap-3 mt-2 text-xs">
                  <span className="text-text-tertiary">Best:</span>
                  {item.strongest_dimensions.map((d) => (
                    <span key={d.dimension_name} className="text-success">{d.dimension_name} {d.rating.toFixed(1)}</span>
                  ))}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}

      <div className="mt-8 space-x-4">
        <Link href="/me/writing" className="text-interactive hover:underline text-sm">Writing Tasks</Link>
        <Link href="/me/writing/analytics" className="text-interactive hover:underline text-sm">Analytics</Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}

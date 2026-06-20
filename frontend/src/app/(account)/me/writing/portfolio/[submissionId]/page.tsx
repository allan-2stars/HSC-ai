"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { api } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

const RATING_LABELS: Record<number, string> = {
  1: "Needs Work", 2: "Developing", 3: "Satisfactory", 4: "Strong", 5: "Excellent",
};

export default function PortfolioDetailPage() {
  return (
    <RoleGuard roles={["student"]}>
      <PortfolioDetail />
    </RoleGuard>
  );
}

function PortfolioDetail() {
  const params = useParams();
  const submissionId = params.submissionId as string;
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const token = getAccessToken();

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    api.getMyPortfolioItem(submissionId, token)
      .then(setData)
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load portfolio item");
      })
      .finally(() => setLoading(false));
  }, [submissionId, token]);

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;
  if (!data) return <p className="p-8 text-text-secondary">Not found</p>;

  return (
    <div className="max-w-4xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">{data.task_title}</h1>
      <div className="flex items-center gap-3 text-text-tertiary text-xs mb-8">
        {data.published_at && <span>Published {new Date(data.published_at).toLocaleDateString()}</span>}
        <span>{data.word_count} words</span>
        {data.was_reopened && <span className="text-interactive">Revised (v{data.publication_version})</span>}
      </div>

      {/* Task prompt */}
      <div className="bg-surface border border-border-subtle rounded-lg p-4 mb-6">
        <h2 className="text-sm font-medium text-text-secondary mb-2">Task</h2>
        <p className="text-text-primary text-sm whitespace-pre-wrap">{data.task_prompt}</p>
        {data.task_instructions && (
          <p className="text-text-tertiary text-xs mt-2 whitespace-pre-wrap">{data.task_instructions}</p>
        )}
      </div>

      {/* Submitted content */}
      <div className="bg-surface border border-border-subtle rounded-lg p-4 mb-6">
        <h2 className="text-sm font-medium text-text-secondary mb-2">Your Response</h2>
        <div className="bg-surface-secondary rounded p-4 whitespace-pre-wrap text-text-primary text-sm leading-relaxed max-h-96 overflow-y-auto">
          {data.submitted_content || "(No content)"}
        </div>
      </div>

      {/* Rubric scores */}
      {data.scores && data.scores.length > 0 && (
        <div className="bg-surface border border-border-subtle rounded-lg p-4 mb-6">
          <h2 className="text-sm font-medium text-text-secondary mb-3">
            Rubric Assessment {data.rubric_title && <span className="font-normal">· {data.rubric_title}</span>}
          </h2>
          <div className="space-y-3">
            {data.scores.map((s: any) => (
              <div key={s.dimension_id} className="bg-surface-secondary rounded p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-text-primary text-sm font-medium">{s.name}</span>
                  <span className="text-success text-sm">
                    {s.rating}/5 {RATING_LABELS[s.rating] || ""}
                  </span>
                </div>
                {s.comment && <p className="text-text-primary text-sm whitespace-pre-wrap">{s.comment}</p>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Official feedback */}
      {data.feedback && (
        <div className="bg-surface border border-border-subtle rounded-lg p-4 mb-6">
          <h2 className="text-sm font-medium text-text-secondary mb-2">Reviewer Feedback</h2>
          <div className="bg-surface-secondary rounded p-4 whitespace-pre-wrap text-text-primary text-sm leading-relaxed">
            {data.feedback.overall_comment}
          </div>
          {data.feedback.dimensions && data.feedback.dimensions.length > 0 && (
            <div className="mt-3 space-y-2">
              {data.feedback.dimensions.map((d: any, i: number) => (
                <div key={i} className="text-sm">
                  <span className="text-text-secondary font-medium">{d.name}: </span>
                  <span className="text-text-primary">{d.comment}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Disputes */}
      {data.disputes && data.disputes.length > 0 && (
        <div className="bg-surface border border-border-subtle rounded-lg p-4 mb-6">
          <h2 className="text-sm font-medium text-text-secondary mb-2">Review Requests</h2>
          {data.disputes.map((d: any) => (
            <div key={d.id} className="bg-surface-secondary rounded p-3 mb-2">
              <div className="flex items-center gap-2 mb-1">
                <span className={`text-xs px-1.5 py-0.5 rounded ${d.status === "open" ? "bg-amber-400/10 text-amber-400" : d.status === "resolved" ? "bg-success/10 text-success" : "bg-text-tertiary/10 text-text-tertiary"}`}>{d.status}</span>
              </div>
              <p className="text-text-primary text-sm">{d.reason}</p>
              {d.admin_response && <p className="text-text-tertiary text-xs mt-1">Response: {d.admin_response}</p>}
            </div>
          ))}
        </div>
      )}

      <div className="bg-amber-400/5 border border-amber-400/20 rounded p-3 mb-6">
        <p className="text-amber-400 text-xs">{data.disclaimer}</p>
      </div>

      <div className="mt-8 space-x-4">
        <Link href="/me/writing/portfolio" className="text-interactive hover:underline text-sm">Portfolio</Link>
        <Link href="/me/writing" className="text-interactive hover:underline text-sm">Writing Tasks</Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}

"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { api, type ContentStats } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

const STATUS_COLOR: Record<string, string> = {
  draft: "text-text-tertiary",
  review: "text-blue-400",
  approved: "text-amber-400",
  published: "text-success",
  archived: "text-text-tertiary",
  rejected: "text-error",
};

const STATUS_BG: Record<string, string> = {
  draft: "bg-text-tertiary/10",
  review: "bg-blue-400/10",
  approved: "bg-amber-400/10",
  published: "bg-success/10",
};

interface Question {
  id: string;
  subject_id: string;
  exam_type_id: string;
  difficulty: string;
  question_type: string;
  status: string;
  source_type: string;
  content_ownership: string;
  quality_score: number | null;
  review_notes: string | null;
  current_version: { stem: string; version_number: number } | null;
  created_at: string;
}

export default function ContentReviewPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <ContentReview />
    </RoleGuard>
  );
}

function ContentReview() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [stats, setStats] = useState<ContentStats | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [filters, setFilters] = useState<{
    status?: string; source_type?: string; subject_id?: string; exam_type_id?: string
  }>({});

  const token = getAccessToken();

  const loadData = useCallback(() => {
    if (!token) return;
    setLoading(true);
    Promise.all([
      api.listReviewQueue(filters, token),
      api.getContentStats(token),
    ])
      .then(([qs, st]) => {
        setQuestions(qs);
        setStats(st);
      })
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; }
        setError(e.detail ?? "Failed to load");
      })
      .finally(() => setLoading(false));
  }, [token, JSON.stringify(filters)]);

  useEffect(() => { loadData(); }, [loadData]);

  const handleAction = async (questionId: string, action: string) => {
    if (!token) return;
    const actions: Record<string, (id: string, token: string) => Promise<any>> = {
      "submit-review": (id, t) => api.submitForReview(id, t),
      approve: (id, t) => api.approveQuestion(id, t),
      publish: (id, t) => api.publishQuestion(id, t),
      archive: (id, t) => api.archiveQuestion(id, t),
    };
    try {
      await actions[action]?.(questionId, token);
      loadData();
    } catch (e: any) {
      setError(e.detail ?? "Action failed");
    }
  };

  const handleBulk = async (action: string) => {
    if (!token || selected.size === 0) return;
    try {
      await api.bulkAction(Array.from(selected), action, token);
      setSelected(new Set());
      loadData();
    } catch (e: any) {
      setError(e.detail ?? "Bulk action failed");
    }
  };

  const toggleSelect = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  if (loading && !stats) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;

  return (
    <div className="max-w-6xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">Content Review</h1>
      <p className="text-text-secondary text-sm mb-8">Admin · Question Lifecycle Management</p>

      {/* Stats Cards */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard label="Draft" value={stats.by_status.draft ?? 0} color="text-text-tertiary" />
          <StatCard label="In Review" value={stats.by_status.review ?? 0} color="text-blue-400" />
          <StatCard label="Approved" value={stats.by_status.approved ?? 0} color="text-amber-400" />
          <StatCard label="Published" value={stats.by_status.published ?? 0} color="text-success" />
        </div>
      )}

      {/* Source breakdown */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
          <StatCard label="Published (Week)" value={stats.published_this_week} />
          <StatCard label="Published (Month)" value={stats.published_this_month} />
          <StatCard label="Total Questions" value={stats.total} />
        </div>
      )}

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-4">
        <select
          value={filters.status ?? ""}
          onChange={(e) => setFilters((f) => ({ ...f, status: e.target.value || undefined }))}
          className="bg-canvas border border-border-subtle rounded px-3 py-1.5 text-text-primary text-sm"
        >
          <option value="">All Statuses</option>
          <option value="draft">Draft</option>
          <option value="review">In Review</option>
          <option value="approved">Approved</option>
        </select>
        <select
          value={filters.source_type ?? ""}
          onChange={(e) => setFilters((f) => ({ ...f, source_type: e.target.value || undefined }))}
          className="bg-canvas border border-border-subtle rounded px-3 py-1.5 text-text-primary text-sm"
        >
          <option value="">All Sources</option>
          <option value="manual">Manual</option>
          <option value="ai">AI</option>
          <option value="ocr">OCR</option>
          <option value="imported">Imported</option>
        </select>
      </div>

      {/* Bulk actions */}
      {selected.size > 0 && (
        <div className="flex items-center gap-3 mb-4 p-3 bg-surface border border-cta rounded">
          <span className="text-text-primary text-sm">{selected.size} selected</span>
          <button onClick={() => handleBulk("approve")} className="px-3 py-1 bg-amber-700 text-white text-xs rounded hover:opacity-90">Approve</button>
          <button onClick={() => handleBulk("publish")} className="px-3 py-1 bg-green-700 text-white text-xs rounded hover:opacity-90">Publish</button>
          <button onClick={() => handleBulk("archive")} className="px-3 py-1 bg-canvas text-text-secondary text-xs rounded hover:opacity-90 border border-border-subtle">Archive</button>
          <button onClick={() => setSelected(new Set())} className="px-3 py-1 text-text-tertiary text-xs">Clear</button>
        </div>
      )}

      {/* Question table */}
      <div className="bg-surface border border-border-subtle rounded-lg overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border-subtle">
                <th className="w-8 p-3"><input type="checkbox" onChange={(e) => e.target.checked ? setSelected(new Set(questions.map(q => q.id))) : setSelected(new Set())} /></th>
                <th className="text-left p-3 text-text-tertiary">Question</th>
                <th className="text-center p-3 text-text-tertiary">Source</th>
                <th className="text-center p-3 text-text-tertiary">Status</th>
                <th className="text-center p-3 text-text-tertiary">Quality</th>
                <th className="text-right p-3 text-text-tertiary">Actions</th>
              </tr>
            </thead>
            <tbody>
              {questions.length === 0 ? (
                <tr><td colSpan={6} className="p-8 text-center text-text-tertiary">No questions match filters.</td></tr>
              ) : (
                questions.map((q) => (
                  <tr key={q.id} className={`border-b border-border-subtle last:border-0 ${STATUS_BG[q.status] ?? ""}`}>
                    <td className="p-3">
                      <input type="checkbox" checked={selected.has(q.id)} onChange={() => toggleSelect(q.id)} />
                    </td>
                    <td className="p-3">
                      <p className="text-text-primary font-medium truncate max-w-xs">
                        {q.current_version?.stem?.slice(0, 80) ?? "(no version)"}
                      </p>
                      <p className="text-text-tertiary text-xs mt-0.5">
                        v{q.current_version?.version_number ?? "—"} · {q.difficulty} · {q.question_type}
                      </p>
                    </td>
                    <td className="p-3 text-center text-text-secondary text-xs">{q.source_type}</td>
                    <td className={`p-3 text-center text-xs font-medium capitalize ${STATUS_COLOR[q.status] ?? ""}`}>{q.status}</td>
                    <td className="p-3 text-center text-text-secondary">{q.quality_score ?? "—"}</td>
                    <td className="p-3 text-right">
                      <div className="flex justify-end gap-1">
                        {q.status === "draft" && (
                          <button onClick={() => handleAction(q.id, "submit-review")} className="px-2 py-1 text-blue-400 text-xs hover:bg-blue-400/10 rounded">Review</button>
                        )}
                        {q.status === "review" && (
                          <button onClick={() => handleAction(q.id, "approve")} className="px-2 py-1 text-amber-400 text-xs hover:bg-amber-400/10 rounded">Approve</button>
                        )}
                        {q.status === "approved" && (
                          <button onClick={() => handleAction(q.id, "publish")} className="px-2 py-1 text-green-400 text-xs hover:bg-green-400/10 rounded">Publish</button>
                        )}
                        {(q.status === "published" || q.status === "approved" || q.status === "rejected") && (
                          <button onClick={() => handleAction(q.id, "archive")} className="px-2 py-1 text-text-tertiary text-xs hover:bg-white/5 rounded">Archive</button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      <div className="mt-8 space-x-4">
        <Link href="/admin/curriculum" className="text-interactive hover:underline text-sm">Curriculum Dashboard</Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}

function StatCard({ label, value, color = "text-text-primary" }: { label: string; value: string | number; color?: string }) {
  return (
    <div className="bg-surface border border-border-subtle rounded-lg p-4 text-center">
      <p className={`text-2xl font-bold ${color}`}>{value}</p>
      <p className="text-text-tertiary text-xs mt-1">{label}</p>
    </div>
  );
}

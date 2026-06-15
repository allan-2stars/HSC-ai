"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type WritingSubmissionListItem } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

export default function AdminWritingSubmissionsPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <AdminSubmissions />
    </RoleGuard>
  );
}

function AdminSubmissions() {
  const [submissions, setSubmissions] = useState<WritingSubmissionListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState<string | null>(null);

  const token = getAccessToken();

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    api.listAllWritingSubmissions(token)
      .then(setSubmissions)
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load submissions");
      })
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;

  const submitted = submissions.filter(s => s.status === "submitted");

  return (
    <div className="max-w-5xl mx-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Writing Submissions</h1>
          <p className="text-text-secondary text-sm">Admin · Review student writing ({submitted.length} submitted)</p>
        </div>
        <Link href="/admin/writing" className="text-interactive hover:underline text-sm">
          ← Writing Tasks
        </Link>
      </div>

      {submissions.length === 0 ? (
        <p className="text-text-tertiary">No submissions yet.</p>
      ) : (
        <div className="space-y-3">
          {submissions.map((s) => (
            <div key={s.id} className="bg-surface border border-border-subtle rounded-lg p-4">
              <div className="flex items-center justify-between mb-2">
                <div>
                  <span className="text-text-primary font-medium">{s.student_name ?? s.student_id.slice(0, 8)}</span>
                  <span className="text-text-tertiary text-sm ml-2">— {s.task_title}</span>
                </div>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  s.status === "submitted" ? "bg-success/10 text-success" : "bg-amber-400/10 text-amber-400"
                }`}>{s.status}</span>
              </div>
              <div className="flex gap-4 text-xs text-text-tertiary mb-2">
                <span>{s.word_count} words</span>
                {s.submitted_at && <span>Submitted: {new Date(s.submitted_at).toLocaleString()}</span>}
              </div>
              {expanded === s.id ? (
                <div>
                  <div className="bg-surface-secondary rounded p-3 whitespace-pre-wrap text-text-primary text-sm leading-relaxed max-h-64 overflow-y-auto">
                    {s.content || "(No content)"}
                  </div>
                  <button
                    onClick={() => setExpanded(null)}
                    className="text-interactive hover:underline text-xs mt-2"
                  >
                    Collapse
                  </button>
                </div>
              ) : (
                <button
                  onClick={() => setExpanded(s.id)}
                  className="text-interactive hover:underline text-xs"
                >
                  Read submission →
                </button>
              )}
            </div>
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

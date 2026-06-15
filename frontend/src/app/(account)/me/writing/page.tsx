"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type WritingTaskItem } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

export default function WritingTasksPage() {
  return (
    <RoleGuard roles={["student"]}>
      <WritingTasks />
    </RoleGuard>
  );
}

function WritingTasks() {
  const [tasks, setTasks] = useState<WritingTaskItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const token = getAccessToken();

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    api.listWritingTasks(token)
      .then(setTasks)
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load writing tasks");
      })
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;

  return (
    <div className="max-w-3xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">Writing Tasks</h1>
      <p className="text-text-secondary text-sm mb-8">Select a task to begin writing</p>

      {tasks.length === 0 ? (
        <p className="text-text-tertiary">No writing tasks available yet.</p>
      ) : (
        <div className="space-y-4">
          {tasks.map((t) => (
            <div key={t.id} className="bg-surface border border-border-subtle rounded-lg p-5">
              <h2 className="text-lg font-semibold text-text-primary mb-1">{t.title}</h2>
              <p className="text-text-secondary text-sm mb-3">{t.prompt.slice(0, 200)}{t.prompt.length > 200 ? "..." : ""}</p>
              <div className="flex items-center gap-4 text-xs text-text-tertiary mb-3">
                {t.word_limit && <span>Word limit: {t.word_limit}</span>}
                {t.recommended_time_minutes && <span>~{t.recommended_time_minutes} min</span>}
              </div>
              {t.submission ? (
                <div className="flex items-center gap-3">
                  <span className={`text-xs px-2 py-1 rounded ${t.submission.status === "submitted" ? "bg-success/10 text-success" : "bg-amber-400/10 text-amber-400"}`}>
                    {t.submission.status === "submitted" ? "Submitted" : "Draft"}
                  </span>
                  {t.submission.status === "submitted" ? (
                    <Link href={`/me/writing/${t.submission.id}`} className="text-interactive hover:underline text-sm">
                      View submission →
                    </Link>
                  ) : (
                    <Link href={`/me/writing/${t.submission.id}`} className="text-interactive hover:underline text-sm">
                      Continue writing →
                    </Link>
                  )}
                </div>
              ) : (
                <button
                  onClick={async () => {
                    try {
                      const sub = await api.startWriting(t.id, token!);
                      window.location.href = `/me/writing/${sub.id}`;
                    } catch (e: any) {
                      setError(e.detail ?? "Failed to start");
                    }
                  }}
                  className="text-sm bg-interactive text-white px-4 py-2 rounded hover:opacity-90"
                >
                  Start Writing
                </button>
              )}
            </div>
          ))}
        </div>
      )}

      <div className="mt-8">
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}

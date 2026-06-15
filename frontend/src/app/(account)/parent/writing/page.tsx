"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type StudentResponse, type WritingSubmissionListItem } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

export default function ParentWritingPage() {
  return (
    <RoleGuard roles={["parent"]}>
      <ParentWriting />
    </RoleGuard>
  );
}

function ParentWriting() {
  const [students, setStudents] = useState<StudentResponse[]>([]);
  const [submissionsByStudent, setSubmissionsByStudent] = useState<Record<string, WritingSubmissionListItem[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const token = getAccessToken();

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    api.listStudents(token)
      .then(async (sList) => {
        setStudents(sList);
        const results: Record<string, WritingSubmissionListItem[]> = {};
        for (const s of sList) {
          try {
            results[s.id] = await api.listStudentWriting(s.id, token);
          } catch {
            results[s.id] = [];
          }
        }
        setSubmissionsByStudent(results);
      })
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load");
      })
      .finally(() => setLoading(false));
  }, [token]);

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;

  return (
    <div className="max-w-3xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-2">Student Writing</h1>
      <p className="text-text-secondary text-sm mb-8">View your students&apos; writing submissions</p>

      {students.length === 0 ? (
        <p className="text-text-tertiary">No students registered.</p>
      ) : (
        <div className="space-y-6">
          {students.map((student) => {
            const subs = submissionsByStudent[student.id] || [];
            const submitted = subs.filter(s => s.status === "submitted");
            return (
              <div key={student.id} className="bg-surface border border-border-subtle rounded-lg p-4">
                <h2 className="text-text-primary font-medium mb-2">{student.display_name}</h2>
                {subs.length === 0 ? (
                  <p className="text-text-tertiary text-sm">No writing activity yet.</p>
                ) : (
                  <div className="space-y-2">
                    {subs.map((s) => (
                      <div key={s.id} className="flex items-center justify-between text-sm">
                        <span className="text-text-secondary">{s.task_title}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-text-tertiary text-xs">{s.word_count} words</span>
                          <span className={`text-xs px-2 py-0.5 rounded ${
                            s.status === "submitted" ? "bg-success/10 text-success" : "bg-amber-400/10 text-amber-400"
                          }`}>{s.status}</span>
                          {s.submitted_at && (
                            <span className="text-text-tertiary text-xs">
                              {new Date(s.submitted_at).toLocaleDateString()}
                            </span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}

      <div className="mt-8">
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}

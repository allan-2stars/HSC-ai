"use client";

import { useEffect, useState } from "react";
import { api, type StudentResponse, type StudentSummary } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import Link from "next/link";
import RoleGuard from "@/components/RoleGuard";

export default function ParentProgressPage() {
  return (
    <RoleGuard roles={["parent"]}>
      <ParentProgress />
    </RoleGuard>
  );
}

function ParentProgress() {
  const [students, setStudents] = useState<(StudentResponse & { summary?: StudentSummary })[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) { window.location.href = "/login"; return; }

    api.listStudents(token)
      .then(async (list) => {
        // Fetch summary for each student
        const enriched = await Promise.all(
          list.map(async (s) => {
            try {
              const summary = await api.getStudentSummary(s.id, token);
              return { ...s, summary };
            } catch {
              return s;
            }
          })
        );
        setStudents(enriched);
      })
      .catch((e) => { if (e.status === 401) { clearTokens(); window.location.href = "/login"; } })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="p-8 text-text-secondary">Loading…</p>;

  return (
    <div className="max-w-3xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-6">Student Progress</h1>

      {students.length === 0 ? (
        <p className="text-text-secondary">No students linked to your account.</p>
      ) : (
        <div className="grid gap-4">
          {students.map((s) => (
            <Link
              key={s.id}
              href={`/parent/progress/${s.id}`}
              className="block bg-surface border border-border-subtle rounded-lg p-6 hover:border-cta transition-colors"
            >
              <div className="flex justify-between items-start">
                <div>
                  <h2 className="text-lg font-semibold text-text-primary">{s.display_name}</h2>
                  <p className="text-text-secondary text-sm mt-1">Year {s.year_level ?? "—"}</p>
                </div>
                {s.summary && (
                  <div className="text-right">
                    <p className="text-cta text-xl font-bold">{s.summary.average_score}%</p>
                    <p className="text-text-tertiary text-xs">avg score</p>
                  </div>
                )}
              </div>
              {s.summary && (
                <div className="grid grid-cols-3 gap-4 mt-4 pt-4 border-t border-border-subtle">
                  <MiniStat label="Exams" value={s.summary.total_attempts} />
                  <MiniStat label="Best" value={`${s.summary.best_score}%`} />
                  <MiniStat label="Accuracy" value={`${s.summary.overall_accuracy}%`} />
                </div>
              )}
            </Link>
          ))}
        </div>
      )}

      <div className="mt-8 space-x-4">
        <Link href="/parent" className="text-interactive hover:underline text-sm">&larr; Dashboard</Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
        <Link href="/parent/assignments" className="text-interactive hover:underline text-sm">Assignments</Link>
      </div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="text-center">
      <p className="text-text-primary font-semibold">{value}</p>
      <p className="text-text-tertiary text-xs">{label}</p>
    </div>
  );
}

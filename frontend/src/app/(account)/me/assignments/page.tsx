"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type AssignmentItem } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

const STATUS_COLORS: Record<string, string> = {
  assigned: "text-blue-400",
  started: "text-yellow-400",
  completed: "text-success",
  overdue: "text-error",
  cancelled: "text-text-tertiary",
};

export default function StudentAssignmentsPage() {
  return (
    <RoleGuard roles={["student"]}>
      <StudentAssignments />
    </RoleGuard>
  );
}

function StudentAssignments() {
  const [assignments, setAssignments] = useState<AssignmentItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) { window.location.href = "/login"; return; }

    api.getMyAssignments(token)
      .then(setAssignments)
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; }
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;

  const active = assignments.filter((a) => a.status !== "cancelled");

  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-6">My Assignments</h1>

      {active.length === 0 ? (
        <p className="text-text-secondary mb-4">No active assignments right now.</p>
      ) : (
        <div className="space-y-3 mb-8">
          {active.map((a) => (
            <div
              key={a.id}
              className={`bg-surface border rounded-lg p-4 ${
                a.status === "overdue" ? "border-error" : "border-border-subtle"
              }`}
            >
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-text-primary font-medium">{a.title_snapshot}</p>
                  <p className="text-text-tertiary text-xs mt-1">
                    <span className={`font-medium capitalize ${STATUS_COLORS[a.status]}`}>
                      {a.status}
                    </span>
                    {a.due_at && ` · Due ${new Date(a.due_at).toLocaleDateString()}`}
                  </p>
                </div>
                {(a.status === "assigned" || a.status === "started" || a.status === "overdue") && (
                  <Link
                    href={`/exams/${a.exam_instance_id}?assignment_id=${a.id}`}
                    className="px-4 py-2 bg-cta text-white text-sm rounded-md hover:opacity-90 transition-opacity shrink-0"
                  >
                    {a.status === "started" ? "Continue" : "Start Exam"}
                  </Link>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {assignments.filter((a) => a.status === "completed").length > 0 && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-text-secondary mb-3">Completed</h2>
          <div className="space-y-2">
            {assignments
              .filter((a) => a.status === "completed")
              .map((a) => (
                <div key={a.id} className="bg-surface border border-border-subtle rounded p-3 flex justify-between">
                  <span className="text-text-secondary text-sm">{a.title_snapshot}</span>
                  <span className="text-success text-xs font-medium">Completed</span>
                </div>
              ))}
          </div>
        </div>
      )}

      <div className="space-x-4">
        <Link href="/exams" className="text-interactive hover:underline text-sm">Available Exams</Link>
        <Link href="/me/progress" className="text-interactive hover:underline text-sm">My Progress</Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}

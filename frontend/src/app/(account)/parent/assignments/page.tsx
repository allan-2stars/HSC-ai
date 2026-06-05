"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type AssignmentItem, type StudentResponse } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

const STATUS_COLORS: Record<string, string> = {
  assigned: "text-blue-400",
  started: "text-yellow-400",
  completed: "text-success",
  overdue: "text-error",
  cancelled: "text-text-tertiary",
};

export default function ParentAssignmentsPage() {
  return (
    <RoleGuard roles={["parent"]}>
      <ParentAssignments />
    </RoleGuard>
  );
}

function ParentAssignments() {
  const [assignments, setAssignments] = useState<AssignmentItem[]>([]);
  const [students, setStudents] = useState<StudentResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) { window.location.href = "/login"; return; }

    Promise.all([
      api.listAllAssignments(token),
      api.listStudents(token),
    ])
      .then(([ass, stud]) => {
        setAssignments(ass);
        setStudents(stud);
      })
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; }
      })
      .finally(() => setLoading(false));
  }, []);

  const handleCancel = async (assignmentId: string) => {
    const token = getAccessToken();
    if (!token) return;
    await api.updateAssignment(assignmentId, { status: "cancelled" }, token);
    setAssignments((prev) =>
      prev.map((a) => (a.id === assignmentId ? { ...a, status: "cancelled" } : a))
    );
  };

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;

  const active = assignments.filter((a) => a.status !== "cancelled");
  const getStudentName = (sid: string) => students.find((s) => s.id === sid)?.display_name ?? sid.slice(0, 8);

  return (
    <div className="max-w-3xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-6">Assignments</h1>

      {active.length === 0 && assignments.filter((a) => a.status === "cancelled").length === 0 ? (
        <p className="text-text-secondary mb-4">No assignments yet. Assign exams from a student&apos;s analytics page.</p>
      ) : (
        <div className="space-y-3 mb-8">
          {assignments.map((a) => (
            <div
              key={a.id}
              className={`bg-surface border rounded-lg p-4 flex items-center justify-between ${
                a.status === "overdue" ? "border-error" : "border-border-subtle"
              }`}
            >
              <div>
                <p className="text-text-primary font-medium">{a.title_snapshot}</p>
                <p className="text-text-tertiary text-xs mt-0.5">
                  {getStudentName(a.student_id)}
                  {a.due_at && ` · Due ${new Date(a.due_at).toLocaleDateString()}`}
                </p>
              </div>
              <div className="flex items-center gap-3">
                <span className={`text-xs font-medium capitalize ${STATUS_COLORS[a.status] ?? "text-text-tertiary"}`}>
                  {a.status}
                </span>
                {a.status !== "completed" && a.status !== "cancelled" && (
                  <button
                    onClick={() => handleCancel(a.id)}
                    className="text-xs text-text-tertiary hover:text-error transition-colors"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="space-x-4">
        <Link href="/parent" className="text-interactive hover:underline text-sm">&larr; Dashboard</Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}

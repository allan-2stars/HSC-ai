"use client";

import { useEffect, useState } from "react";
import { api, type StudentSummary, type TopicPerfItem, type SkillPerfItem, type RecommendationsResponse, type StudentResponse } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import Link from "next/link";
import RoleGuard from "@/components/RoleGuard";

export default function ParentDashboardPage() {
  return (
    <RoleGuard roles={["parent"]}>
      <ParentDashboard />
    </RoleGuard>
  );
}

function ParentDashboard() {
  return (
    <div className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl font-bold text-text-primary mb-6">Parent Dashboard</h1>
      <StudentList />
    </div>
  );
}

function StudentList() {
  const [students, setStudents] = useState<StudentResponse[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) { window.location.href = "/login"; return; }

    api.listStudents(token)
      .then(setStudents)
      .catch((e) => { if (e.status === 401) { clearTokens(); window.location.href = "/login"; } })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-text-secondary">Loading...</p>;

  return (
    <div>
      {students.length === 0 ? (
        <p className="text-text-secondary">No students yet.</p>
      ) : (
        <div className="grid gap-4">
          {students.map((s) => (
            <Link
              key={s.id}
              href={`/parent/students/${s.id}`}
              className="block bg-surface border border-border-subtle rounded-lg p-6 hover:border-cta transition-colors"
            >
              <h2 className="text-lg font-semibold text-text-primary">{s.display_name}</h2>
              <p className="text-text-secondary text-sm mt-1">
                Year {s.year_level ?? "—"} &middot; {s.first_login_completed ? "Active" : "Pending setup"}
              </p>
            </Link>
          ))}
        </div>
      )}
      <div className="mt-8">
        <Link href="/me" className="text-interactive hover:underline text-sm">&larr; Back to Account</Link>
      </div>
    </div>
  );
}

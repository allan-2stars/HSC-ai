"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type StudentResponse, type WritingSubmissionListItem, type WritingFeedbackView, type WritingRubricView } from "@/lib/api";

const RATING_LABELS: Record<number, string> = {
  1: "Needs Work",
  2: "Developing",
  3: "Satisfactory",
  4: "Strong",
  5: "Excellent",
};
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
                <h2 className="text-text-primary font-medium mb-2">{student.display_name}
                  <Link href={`/parent/writing/analytics/${student.id}`} className="text-interactive hover:underline text-xs ml-3 font-normal">
                    Analytics →
                  </Link>
                </h2>
                {subs.length === 0 ? (
                  <p className="text-text-tertiary text-sm">No writing activity yet.</p>
                ) : (
                  <div className="space-y-2">
                    {subs.map((s) => (
                      <ParentSubmissionRow key={s.id} studentId={student.id} submission={s} token={token!} />
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

function ParentSubmissionRow({
  studentId,
  submission,
  token,
}: {
  studentId: string;
  submission: WritingSubmissionListItem;
  token: string;
}) {
  const [feedback, setFeedback] = useState<WritingFeedbackView | null>(null);
  const [rubric, setRubric] = useState<WritingRubricView | null>(null);
  const [open, setOpen] = useState(false);
  const [checked, setChecked] = useState(false);

  async function toggle() {
    if (!open && !checked) {
      try {
        setFeedback(await api.getStudentWritingFeedback(studentId, submission.id, token));
      } catch {
        setFeedback(null);
      }
      try {
        setRubric(await api.getStudentSubmissionRubric(studentId, submission.id, token));
      } catch {
        setRubric(null);
      }
      setChecked(true);
    }
    setOpen((o) => !o);
  }

  return (
    <div className="text-sm border-b border-border-subtle/40 pb-2">
      <div className="flex items-center justify-between">
        <span className="text-text-secondary">{submission.task_title}</span>
        <div className="flex items-center gap-3">
          <span className="text-text-tertiary text-xs">{submission.word_count} words</span>
          <span className={`text-xs px-2 py-0.5 rounded ${
            submission.status === "submitted" ? "bg-success/10 text-success" : "bg-amber-400/10 text-amber-400"
          }`}>{submission.status}</span>
          {submission.submitted_at && (
            <span className="text-text-tertiary text-xs">
              {new Date(submission.submitted_at).toLocaleDateString()}
            </span>
          )}
          {submission.status === "submitted" && (
            <button onClick={toggle} className="text-interactive hover:underline text-xs">
              {open ? "Hide feedback" : "Feedback"}
            </button>
          )}
        </div>
      </div>
      {open && (
        <div className="mt-2 space-y-2">
          {feedback ? (
            <div className="bg-surface-secondary rounded p-3">
              <p className="whitespace-pre-wrap text-text-primary text-sm leading-relaxed">
                {feedback.overall_comment}
              </p>
              <p className="text-amber-400 text-xs mt-2">{feedback.disclaimer}</p>
            </div>
          ) : (
            <p className="text-text-tertiary text-xs">No published feedback yet.</p>
          )}
          {rubric && (
            <div className="bg-surface-secondary rounded p-3">
              <p className="text-text-secondary text-xs font-medium mb-2">Rubric · {rubric.rubric_title}</p>
              <div className="space-y-2">
                {rubric.scores.map((s) => (
                  <div key={s.dimension_id}>
                    <div className="flex items-center justify-between">
                      <span className="text-text-primary text-sm">{s.name}</span>
                      <span className="text-success text-xs">
                        {s.rating}/5 {s.rating ? `— ${RATING_LABELS[s.rating]}` : ""}
                      </span>
                    </div>
                    {s.comment && <p className="text-text-tertiary text-xs whitespace-pre-wrap">{s.comment}</p>}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

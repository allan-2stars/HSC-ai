"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { api, type WritingTaskResponse } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import RoleGuard from "@/components/RoleGuard";

export default function AdminWritingPage() {
  return (
    <RoleGuard roles={["admin"]}>
      <AdminWriting />
    </RoleGuard>
  );
}

function AdminWriting() {
  const [tasks, setTasks] = useState<WritingTaskResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const token = getAccessToken();

  function loadTasks() {
    if (!token) return;
    api.listAdminWritingTasks(token)
      .then(setTasks)
      .catch((e) => {
        if (e.status === 401) { clearTokens(); window.location.href = "/login"; return; }
        setError(e.detail ?? "Failed to load tasks");
      })
      .finally(() => setLoading(false));
  }

  useEffect(() => {
    if (!token) { window.location.href = "/login"; return; }
    loadTasks();
  }, [token]);

  if (loading) return <p className="p-8 text-text-secondary">Loading...</p>;
  if (error) return <p className="p-8 text-error">{error}</p>;

  return (
    <div className="max-w-4xl mx-auto p-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-text-primary">Writing Tasks</h1>
          <p className="text-text-secondary text-sm">Admin · Manage writing tasks</p>
        </div>
        <div className="flex gap-3">
          <Link href="/admin/writing/rubrics" className="text-sm text-interactive hover:underline">
            Rubrics →
          </Link>
          <Link href="/admin/writing/reviews" className="text-sm text-interactive hover:underline">
            Review Queue →
          </Link>
          <Link href="/admin/writing/submissions" className="text-sm text-interactive hover:underline">
            View Submissions →
          </Link>
          <button
            onClick={() => setShowCreate(!showCreate)}
            className="text-sm bg-interactive text-white px-4 py-2 rounded hover:opacity-90"
          >
            {showCreate ? "Cancel" : "Create Task"}
          </button>
        </div>
      </div>

      {showCreate && (
        <CreateTaskForm
          token={token!}
          onCreated={() => { setShowCreate(false); loadTasks(); }}
        />
      )}

      {tasks.length === 0 ? (
        <p className="text-text-tertiary">No writing tasks yet.</p>
      ) : (
        <div className="space-y-3">
          {tasks.map((t) => (
            <div key={t.id} className="bg-surface border border-border-subtle rounded-lg p-4">
              <div className="flex items-center justify-between mb-1">
                <h3 className="text-text-primary font-medium">{t.title}</h3>
                <span className={`text-xs px-2 py-0.5 rounded ${
                  t.status === "published" ? "bg-success/10 text-success" :
                  t.status === "archived" ? "bg-text-tertiary/10 text-text-tertiary" :
                  "bg-amber-400/10 text-amber-400"
                }`}>{t.status}</span>
              </div>
              <p className="text-text-secondary text-sm mb-2">{t.prompt.slice(0, 120)}...</p>
              <div className="flex items-center gap-3 text-xs text-text-tertiary">
                {t.word_limit && <span>{t.word_limit} words</span>}
                {t.recommended_time_minutes && <span>{t.recommended_time_minutes} min</span>}
                {t.status === "draft" && (
                  <button
                    onClick={async () => {
                      await api.publishWritingTask(t.id, token!);
                      loadTasks();
                    }}
                    className="text-success hover:underline"
                  >
                    Publish
                  </button>
                )}
                {t.status === "published" && (
                  <button
                    onClick={async () => {
                      await api.archiveWritingTask(t.id, token!);
                      loadTasks();
                    }}
                    className="text-text-tertiary hover:underline"
                  >
                    Archive
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-8 space-x-4">
        <Link href="/admin/system" className="text-interactive hover:underline text-sm">System Dashboard</Link>
        <Link href="/me" className="text-interactive hover:underline text-sm">Account</Link>
      </div>
    </div>
  );
}

function CreateTaskForm({ token, onCreated }: { token: string; onCreated: () => void }) {
  const [title, setTitle] = useState("");
  const [prompt, setPrompt] = useState("");
  const [instructions, setInstructions] = useState("");
  const [wordLimit, setWordLimit] = useState("");
  const [timeMinutes, setTimeMinutes] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState("");
  const [subjects, setSubjects] = useState<{ id: string; code: string; name: string }[]>([]);
  const [examTypes, setExamTypes] = useState<{ id: string; code: string; name: string }[]>([]);
  const [subjectId, setSubjectId] = useState("");
  const [examTypeId, setExamTypeId] = useState("");

  useEffect(() => {
    api.listSubjects(token).then(setSubjects).catch(() => {});
    api.listExamTypes(token).then(setExamTypes).catch(() => {});
  }, [token]);

  async function handleCreate() {
    if (!title || !prompt || !subjectId || !examTypeId) {
      setErr("Title, prompt, subject, and exam type are required.");
      return;
    }
    setSubmitting(true);
    try {
      await api.createWritingTask({
        title,
        prompt,
        instructions: instructions || null,
        word_limit: wordLimit ? parseInt(wordLimit) : null,
        recommended_time_minutes: timeMinutes ? parseInt(timeMinutes) : null,
        subject_id: subjectId,
        exam_type_id: examTypeId,
      }, token);
      onCreated();
    } catch (e: any) {
      setErr(e.detail ?? "Failed to create task");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="bg-surface border border-border-subtle rounded-lg p-4 mb-6 space-y-3">
      <h3 className="text-text-primary font-medium">New Writing Task</h3>
      <input className="w-full bg-surface-secondary border border-border-subtle rounded p-2 text-sm text-text-primary" placeholder="Title" value={title} onChange={e => setTitle(e.target.value)} />
      <textarea className="w-full bg-surface-secondary border border-border-subtle rounded p-2 text-sm text-text-primary h-24" placeholder="Prompt / question" value={prompt} onChange={e => setPrompt(e.target.value)} />
      <textarea className="w-full bg-surface-secondary border border-border-subtle rounded p-2 text-sm text-text-primary h-16" placeholder="Instructions (optional)" value={instructions} onChange={e => setInstructions(e.target.value)} />
      <div className="grid grid-cols-2 gap-3">
        <select className="bg-surface-secondary border border-border-subtle rounded p-2 text-sm text-text-primary" value={subjectId} onChange={e => setSubjectId(e.target.value)}>
          <option value="">Select subject</option>
          {subjects.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
        </select>
        <select className="bg-surface-secondary border border-border-subtle rounded p-2 text-sm text-text-primary" value={examTypeId} onChange={e => setExamTypeId(e.target.value)}>
          <option value="">Select exam type</option>
          {examTypes.map(e => <option key={e.id} value={e.id}>{e.name}</option>)}
        </select>
        <input className="bg-surface-secondary border border-border-subtle rounded p-2 text-sm text-text-primary" placeholder="Word limit (optional)" type="number" value={wordLimit} onChange={e => setWordLimit(e.target.value)} />
        <input className="bg-surface-secondary border border-border-subtle rounded p-2 text-sm text-text-primary" placeholder="Time minutes (optional)" type="number" value={timeMinutes} onChange={e => setTimeMinutes(e.target.value)} />
      </div>
      {err && <p className="text-error text-sm">{err}</p>}
      <button onClick={handleCreate} disabled={submitting} className="text-sm bg-interactive text-white px-4 py-2 rounded hover:opacity-90 disabled:opacity-50">
        {submitting ? "Creating..." : "Create Task"}
      </button>
    </div>
  );
}

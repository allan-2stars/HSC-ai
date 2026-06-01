"use client";

import { useEffect, useState } from "react";
import { api, type StudentResponse } from "@/lib/api";
import { getAccessToken } from "@/lib/auth";

export default function StudentsPage() {
  const [students, setStudents] = useState<StudentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [name, setName] = useState("");
  const [yearLevel, setYearLevel] = useState<number | "">("");
  const [creating, setCreating] = useState(false);
  const [newCreds, setNewCreds] = useState<{ email: string; password: string } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) { window.location.href = "/login"; return; }
    api.listStudents(token).then(setStudents).finally(() => setLoading(false));
  }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    const token = getAccessToken();
    if (!token) return;
    setCreating(true);
    setError(null);
    try {
      const student = await api.createStudent(name, yearLevel ? yearLevel : null, token);
      setStudents((prev) => [...prev, student]);
      setNewCreds({ email: student.login_email!, password: student.temp_password! });
      setName("");
      setYearLevel("");
    } catch (err: unknown) {
      const e = err as { detail?: string };
      setError(e.detail ?? "Failed to create student");
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="min-h-screen p-8 max-w-lg mx-auto">
      <div className="flex items-center gap-4 mb-8">
        <a href="/me" className="text-text-tertiary hover:text-white text-sm">← Account</a>
        <h1 className="text-2xl font-light text-white">Students</h1>
      </div>

      {loading ? (
        <p className="text-text-secondary">Loading…</p>
      ) : (
        <div className="space-y-3 mb-8">
          {students.length === 0 && (
            <p className="text-text-tertiary text-sm">No students yet.</p>
          )}
          {students.map((s) => (
            <div key={s.id} className="bg-surface rounded-lg p-4">
              <p className="text-white font-medium">{s.display_name}</p>
              <p className="text-text-tertiary text-sm">
                Year {s.year_level ?? "—"} ·{" "}
                {s.first_login_completed ? "Active" : "Awaiting first login"}
              </p>
            </div>
          ))}
        </div>
      )}

      {students.length < 3 && (
        <form onSubmit={handleCreate} data-testid="create-student-form" className="space-y-4">
          <h2 className="text-lg font-light text-white">Add student</h2>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Name</label>
            <input
              type="text"
              data-testid="student-name-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full bg-canvas border border-border-subtle rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-interactive"
            />
          </div>
          <div>
            <label className="block text-sm text-text-secondary mb-1">Year level</label>
            <select
              data-testid="year-level-select"
              value={yearLevel}
              onChange={(e) => setYearLevel(e.target.value ? Number(e.target.value) : "")}
              className="w-full bg-canvas border border-border-subtle rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-interactive"
            >
              <option value="">Select…</option>
              <option value={4}>Year 4</option>
              <option value={5}>Year 5</option>
              <option value={6}>Year 6</option>
            </select>
          </div>
          {error && <p className="text-error text-sm">{error}</p>}
          <button
            type="submit"
            disabled={creating}
            className="bg-cta text-white rounded-full px-6 py-2 text-sm hover:bg-interactive disabled:opacity-50 transition-colors"
          >
            {creating ? "Creating…" : "Add student"}
          </button>
        </form>
      )}

      {newCreds && (
        <div className="mt-6 bg-surface border border-interactive rounded-lg p-4">
          <p className="text-white text-sm font-medium mb-2">Student login credentials</p>
          <p className="text-text-secondary text-xs">Share these with your child for their first login.</p>
          <div className="mt-3 space-y-1 font-mono text-sm">
            <p className="text-text-secondary">Email: <span className="text-white">{newCreds.email}</span></p>
            <p className="text-text-secondary">Temp password: <span className="text-white">{newCreds.password}</span></p>
          </div>
          <button onClick={() => setNewCreds(null)} className="mt-3 text-xs text-text-tertiary hover:text-white">Dismiss</button>
        </div>
      )}
    </div>
  );
}

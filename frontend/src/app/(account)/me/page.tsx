"use client";

import { useEffect, useState } from "react";
import { api, type MeResponse } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";
import Link from "next/link";

export default function AccountPage() {
  const [user, setUser] = useState<MeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = getAccessToken();
    if (!token) {
      window.location.href = "/login";
      return;
    }
    api.me(token)
      .then(setUser)
      .catch(() => {
        clearTokens();
        window.location.href = "/login";
      });
  }, []);

  function handleLogout() {
    clearTokens();
    window.location.href = "/login";
  }

  if (error) return <p className="text-error p-8">{error}</p>;
  if (!user) return <p className="text-text-secondary p-8">Loading…</p>;

  return (
    <div className="min-h-screen p-8 max-w-lg mx-auto">
      <div className="flex items-start justify-between mb-8">
        <h1 className="text-2xl font-light text-white">My Account</h1>
        <button
          onClick={handleLogout}
          className="text-sm text-text-secondary hover:text-white"
        >
          Sign out
        </button>
      </div>

      <div className="bg-surface rounded-lg p-6 space-y-3">
        <div>
          <span className="text-xs text-text-tertiary uppercase tracking-wide">Email</span>
          <p data-testid="user-email" className="text-white mt-1">{user.email}</p>
        </div>
        <div>
          <span className="text-xs text-text-tertiary uppercase tracking-wide">Role</span>
          <p data-testid="user-role" className="text-white mt-1 capitalize">{user.role}</p>
        </div>
      </div>

      <div className="mt-8 space-y-6">
        {user.role === "parent" && (
          <>
            <NavSection title="Students">
              <NavLink href="/students" label="Manage Students" />
            </NavSection>
            <NavSection title="Dashboard">
              <NavLink href="/parent" label="View Dashboard" />
              <NavLink href="/parent/progress" label="Student Progress" />
              <NavLink href="/parent/assignments" label="Manage Assignments" />
              <NavLink href="/parent/writing" label="Student Writing" />
            </NavSection>
          </>
        )}

        {user.role === "admin" && (
          <NavSection title="Administration">
            <NavLink href="/admin/system" label="System Dashboard" />
            <NavLink href="/admin/curriculum" label="Curriculum Dashboard" />
            <NavLink href="/admin/content/review" label="Content Review" />
            <NavLink href="/admin/content/ocr" label="OCR Import" />
            <NavLink href="/admin/content/import" label="Bulk Import" />
            <NavLink href="/admin/content/ai-generate" label="AI Generate" />
            <NavLink href="/admin/content/quality" label="Content Quality" />
            <NavLink href="/admin/writing" label="Writing Tasks" />
          </NavSection>
        )}

        {user.role === "student" && (
          <>
            <NavSection title="Exams">
              <NavLink href="/exams" label="Available Exams" />
              <NavLink href="/me/assignments" label="My Assignments" />
              <NavLink href="/me/writing" label="Writing Tasks" />
            </NavSection>
            <NavSection title="Progress">
              <NavLink href="/me/progress" label="My Progress" />
            </NavSection>
          </>
        )}
      </div>
    </div>
  );
}

function NavSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h2 className="text-xs text-text-tertiary uppercase tracking-wider mb-2">{title}</h2>
      <div className="space-y-1">{children}</div>
    </div>
  );
}

function NavLink({ href, label }: { href: string; label: string }) {
  return (
    <Link href={href} className="block text-interactive hover:underline text-sm py-1">
      {label} →
    </Link>
  );
}

"use client";

import { useEffect, useState } from "react";
import { api, type MeResponse } from "@/lib/api";
import { getAccessToken, clearTokens } from "@/lib/auth";

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

      {user.role === "parent" && (
        <div className="mt-6">
          <a href="/students" className="text-interactive hover:underline text-sm">
            Manage students →
          </a>
        </div>
      )}
    </div>
  );
}

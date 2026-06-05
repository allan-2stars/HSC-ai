"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import { saveTokens, saveRole } from "@/lib/auth";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const tokens = await api.register(email, password, displayName);
      saveTokens(tokens.access_token, tokens.refresh_token);
      window.location.href = "/parent";
    } catch (err: unknown) {
      const e = err as { detail?: string };
      setError(e.detail ?? "Registration failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <h1 className="text-2xl font-light text-white mb-6">Create parent account</h1>

        <form onSubmit={handleSubmit} data-testid="register-form" className="space-y-4">
          <div>
            <label className="block text-sm text-text-secondary mb-1">Your name</label>
            <input
              type="text"
              data-testid="display-name-input"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              required
              className="w-full bg-canvas border border-border-subtle rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-interactive"
            />
          </div>

          <div>
            <label className="block text-sm text-text-secondary mb-1">Email</label>
            <input
              type="email"
              data-testid="email-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full bg-canvas border border-border-subtle rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-interactive"
            />
          </div>

          <div>
            <label className="block text-sm text-text-secondary mb-1">Password</label>
            <input
              type="password"
              data-testid="password-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="w-full bg-canvas border border-border-subtle rounded px-3 py-2 text-white text-sm focus:outline-none focus:ring-2 focus:ring-interactive"
            />
            <p className="text-xs text-text-tertiary mt-1">Minimum 8 characters</p>
          </div>

          {error && (
            <p data-testid="error-message" className="text-error text-sm">{error}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-cta text-white rounded-full py-2 text-sm font-medium hover:bg-interactive disabled:opacity-50 transition-colors"
          >
            {loading ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="mt-4 text-sm text-text-tertiary">
          Already have an account?{" "}
          <a href="/login" className="text-interactive hover:underline">
            Sign in
          </a>
        </p>
      </div>
    </div>
  );
}

"use client";

const ACCESS_KEY = "hscai_access";
const REFRESH_KEY = "hscai_refresh";
const COOKIE_TOKEN = "hscai_token";
const COOKIE_ROLE = "hscai_role";

function setCookie(name: string, value: string, days: number = 1) {
  if (typeof document === "undefined") return;
  const expires = new Date(Date.now() + days * 86400000).toUTCString();
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires}; path=/; SameSite=Lax`;
}

function clearCookie(name: string) {
  if (typeof document === "undefined") return;
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/; SameSite=Lax`;
}

export function saveTokens(access: string, refresh: string) {
  if (typeof window === "undefined") return;
  sessionStorage.setItem(ACCESS_KEY, access);
  sessionStorage.setItem(REFRESH_KEY, refresh);
  // Also set the token as a cookie for middleware to read
  setCookie(COOKIE_TOKEN, access);
}

export function saveRole(role: string) {
  if (typeof window === "undefined") return;
  setCookie(COOKIE_ROLE, role);
}

export function getAccessToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(ACCESS_KEY);
}

export function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(REFRESH_KEY);
}

export function clearTokens() {
  if (typeof window === "undefined") return;
  sessionStorage.removeItem(ACCESS_KEY);
  sessionStorage.removeItem(REFRESH_KEY);
  clearCookie(COOKIE_TOKEN);
  clearCookie(COOKIE_ROLE);
}

export function isAuthenticated(): boolean {
  return !!getAccessToken();
}

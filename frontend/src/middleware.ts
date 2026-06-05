import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// ── Route groups ────────────────────────────────────────────────────────────

/** Paths that never require authentication. */
const PUBLIC_PREFIXES = ["/login", "/register", "/_next", "/favicon", "/api"];

/** Role → home page on wrong-role or after login. */
const ROLE_HOME: Record<string, string> = {
  parent: "/parent",
  student: "/me",
  admin: "/admin/curriculum",
};

/** Prefix → allowed role. Order matters: more specific first. */
const ROUTE_ROLE_MAP: [string, string][] = [
  ["/admin", "admin"],
  ["/parent", "parent"],
  ["/me/progress", "student"],
  ["/me/assignments", "student"],
  ["/me", "student"],   // fallback — student's account home
  ["/exams", "student"],
  ["/students", "parent"],
];

const COOKIE_TOKEN = "hscai_token";
const COOKIE_ROLE = "hscai_role";

// ── Helpers ─────────────────────────────────────────────────────────────────

function isPublic(pathname: string): boolean {
  // Root landing page is public
  if (pathname === "/") return true;
  return PUBLIC_PREFIXES.some((p) => pathname.startsWith(p));
}

/**
 * Find the required role for a path.
 * Returns `null` when no specific role is enforced (public or loose pages).
 */
function requiredRole(pathname: string): string | null {
  for (const [prefix, role] of ROUTE_ROLE_MAP) {
    if (pathname.startsWith(prefix)) return role;
  }
  return null;
}

// ── Middleware ──────────────────────────────────────────────────────────────

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // 1. Public paths — let through
  if (isPublic(pathname)) {
    return NextResponse.next();
  }

  const token = request.cookies.get(COOKIE_TOKEN)?.value;
  const role = request.cookies.get(COOKIE_ROLE)?.value;

  // 2. No token → redirect to /login
  if (!token) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("from", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // 3. Token exists but no role cookie — let through (page's API call will enforce)
  if (!role) {
    return NextResponse.next();
  }

  // 4. Check route → role match
  const needed = requiredRole(pathname);
  if (needed && role !== needed) {
    const home = ROLE_HOME[role] ?? "/login";
    return NextResponse.redirect(new URL(home, request.url));
  }

  // 5. All good
  return NextResponse.next();
}

export const config = {
  matcher: [
    /*
     * Match all paths except static files, images, etc.
     * Skip Next.js internals and public assets.
     */
    "/((?!_next/static|_next/image|favicon.ico|.*\\.svg|.*\\.png|.*\\.jpg).*)",
  ],
};

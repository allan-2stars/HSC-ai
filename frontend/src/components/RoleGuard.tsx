"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";

const ROLE_HOME: Record<string, string> = {
  parent: "/parent",
  student: "/me",
  admin: "/admin/curriculum",
};

const NOT_FOUND_PAGE = "/404";

/**
 * Wraps children — only renders them if the authenticated user has one of
 * the required roles.  Otherwise redirects to the role's home page (or a
 * generic 404 when no token / unknown role).
 */
export default function RoleGuard({
  children,
  roles,
  fallback,
}: {
  children: React.ReactNode;
  roles: string[];
  fallback?: React.ReactNode;
}) {
  const { user, loading, role } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (loading) return;

    // Not logged in → /login
    if (!user) {
      router.replace("/login");
      return;
    }

    // User logged in but wrong role → redirect to their home page
    if (role && !roles.includes(role)) {
      router.replace(ROLE_HOME[role] ?? NOT_FOUND_PAGE);
    }
  }, [user, loading, role, roles, router]);

  // Still loading auth state
  if (loading) {
    return <>{fallback ?? <p className="p-8 text-text-secondary">Loading…</p>}</>;
  }

  // Not authenticated
  if (!user) {
    return <>{fallback ?? <p className="p-8 text-text-secondary">Redirecting…</p>}</>;
  }

  // Wrong role — redirect in progress
  if (role && !roles.includes(role)) {
    return <>{fallback ?? <p className="p-8 text-text-secondary">Redirecting…</p>}</>;
  }

  return <>{children}</>;
}

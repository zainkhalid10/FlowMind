import { Navigate, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "@/contexts/AuthContext";
import { hasRole, roleHome } from "@/lib/roles";

interface ProtectedRouteProps {
  children: ReactNode;
  /**
   * If provided, the user's role must be in this list. Otherwise the user
   * is redirected to their role's home (clients -> /client-review,
   * everyone else -> /dashboard). A flash of the wrong page is avoided
   * because this check runs during render, before the children mount.
   */
  allowedRoles?: readonly string[];
}

export function ProtectedRoute({ children, allowedRoles }: ProtectedRouteProps) {
  const { isAuthenticated, user } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname + location.search }}
      />
    );
  }

  if (!hasRole(user?.role, allowedRoles)) {
    // User is signed in but lacks permission — send them to their role's
    // home instead of surfacing a scary 403. This prevents clients from
    // bouncing against manager-only pages from a bookmarked URL.
    return <Navigate to={roleHome(user?.role)} replace />;
  }

  return <>{children}</>;
}

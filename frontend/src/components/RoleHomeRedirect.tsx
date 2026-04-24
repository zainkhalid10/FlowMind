import { Navigate } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { roleHome } from "@/lib/roles";

/**
 * Catch-all redirect target. Sends an authenticated user to their role's
 * home page and an unauthenticated user to the public landing page.
 */
export function RoleHomeRedirect() {
  const { isAuthenticated, user } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/" replace />;
  }
  return <Navigate to={roleHome(user?.role)} replace />;
}

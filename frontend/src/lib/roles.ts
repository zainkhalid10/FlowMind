/**
 * Role model used throughout the app.
 *
 *   - manager     Full access: every page.
 *   - team_head   Work + review pages; no admin.
 *   - member      Work pages scoped to their own uploads; no admin.
 *   - client      ONLY the review portal for their assigned document(s)
 *                 and their own settings. Everything else is hidden and
 *                 routed away at the ProtectedRoute layer.
 */
export type Role = "manager" | "team_head" | "member" | "client";

export const WORK_ROLES: Role[] = ["manager", "team_head", "member"];
export const TEAM_LEAD_ROLES: Role[] = ["manager", "team_head"];
export const MANAGER_ONLY: Role[] = ["manager"];
export const CLIENT_ONLY: Role[] = ["client"];

/**
 * Landing page for a freshly-authenticated user. Clients go straight to
 * the review portal so they never see internal work pages; everyone else
 * lands on the dashboard.
 */
export function roleHome(role: string | undefined | null): string {
  return role === "client" ? "/client-review" : "/dashboard";
}

export function hasRole(
  userRole: string | undefined | null,
  allowed: readonly string[] | undefined,
): boolean {
  if (!allowed || allowed.length === 0) return true;
  if (!userRole) return false;
  return allowed.includes(userRole);
}

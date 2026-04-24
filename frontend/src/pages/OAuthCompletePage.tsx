import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { roleHome } from "@/lib/roles";
import type { AuthResponse } from "@/types/api";

/**
 * Lands the OAuth redirect from /auth/google/callback.
 *
 * The backend passes the session payload in the URL hash fragment
 * (`#data=<urlencoded-json>`), NOT a query string — fragments are never
 * sent to any server or written to access logs.
 *
 * We parse it once, store the session through AuthContext, scrub the
 * fragment with history.replaceState so a page reload can't replay it,
 * and route by role.
 */
export default function OAuthCompletePage() {
  const { setSession } = useAuth();
  const navigate = useNavigate();
  const consumed = useRef(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (consumed.current) return;
    consumed.current = true;

    try {
      const hash = window.location.hash.replace(/^#/, "");
      const params = new URLSearchParams(hash);
      const encoded = params.get("data");
      if (!encoded) {
        setError(
          "Missing sign-in payload. Please try signing in with Google again.",
        );
        return;
      }
      const decoded = decodeURIComponent(encoded);
      const payload = JSON.parse(decoded) as Partial<AuthResponse> &
        Pick<AuthResponse, "access_token" | "user" | "role">;

      if (!payload.access_token || !payload.user) {
        setError("Sign-in response was incomplete.");
        return;
      }

      setSession({
        status: "success",
        message: "Google sign-in complete",
        access_token: payload.access_token,
        token_type: payload.token_type ?? "bearer",
        role: payload.role,
        name: payload.user.username,
        assigned_file_id: payload.assigned_file_id ?? null,
        user: payload.user,
      });

      // Scrub the fragment so the token isn't kept in history / bookmarks.
      window.history.replaceState(
        {},
        "",
        window.location.pathname + window.location.search,
      );

      // Clients with an assigned document go straight into their review;
      // every other role lands on roleHome (which is /dashboard for
      // manager / team_head / member, /client-review for bare clients).
      const destination =
        payload.role === "client" && payload.assigned_file_id
          ? `/client-review?file_id=${payload.assigned_file_id}`
          : roleHome(payload.role);

      navigate(destination, { replace: true });
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not complete Google sign-in.",
      );
    }
  }, [navigate, setSession]);

  return (
    <div className="grid min-h-screen place-items-center bg-slate-50 p-6">
      <div className="w-full max-w-sm rounded-xl border border-slate-200 bg-white p-6 text-center shadow-sm">
        {error ? (
          <>
            <AlertTriangle className="mx-auto h-8 w-8 text-rose-500" />
            <h1 className="mt-3 text-lg font-semibold text-slate-900">
              Sign-in failed
            </h1>
            <p className="mt-1 text-sm text-slate-600">{error}</p>
            <button
              onClick={() => navigate("/login", { replace: true })}
              className="mt-4 inline-flex items-center justify-center rounded-lg bg-brand-600 px-4 py-2 text-sm font-medium text-white hover:bg-brand-700"
            >
              Back to sign in
            </button>
          </>
        ) : (
          <>
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-brand-600" />
            <h1 className="mt-3 text-lg font-semibold text-slate-900">
              Signing you in…
            </h1>
            <p className="mt-1 text-sm text-slate-600">
              Exchanging your Google session for a FlowMind workspace.
            </p>
          </>
        )}
      </div>
    </div>
  );
}

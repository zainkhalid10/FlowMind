import { useEffect, useState, type FormEvent } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Brain, Info, Loader2, MailCheck } from "lucide-react";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import {
  extractApiError,
  login,
  resolveClientInvite,
  signup,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { roleHome } from "@/lib/roles";

type Mode = "login" | "signup";

interface LocationState {
  from?: string;
}

export default function LoginPage() {
  const [searchParams] = useSearchParams();
  const inviteToken = searchParams.get("invite_token") || "";
  const initialMode: Mode =
    inviteToken || searchParams.get("mode") !== "signup" ? "login" : "signup";
  const [mode, setMode] = useState<Mode>(initialMode);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [role, setRole] = useState<"manager" | "client">(
    inviteToken ? "client" : "manager",
  );

  const { setSession } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const requestedRedirect = (location.state as LocationState)?.from;

  // When arriving via the emailed invite link, resolve the token so we can
  // pre-fill the email field, force client role, and show a welcome
  // banner. Client just enters their temp password and signs in.
  const inviteQ = useQuery({
    queryKey: ["client-invite", inviteToken],
    queryFn: () => resolveClientInvite(inviteToken),
    enabled: Boolean(inviteToken),
    retry: false,
  });

  useEffect(() => {
    if (inviteQ.data) {
      setEmail(inviteQ.data.email);
      setRole("client");
      setMode("login");
    }
  }, [inviteQ.data]);

  // Public signup creates a manager account — clients are never
  // self-serve, they're always invited by a manager.
  useEffect(() => {
    if (mode === "signup" && role === "client") {
      setRole("manager");
    }
  }, [mode, role]);

  const clientSignupBlocked = mode === "signup" && role === "client";

  const mutation = useMutation({
    mutationFn: async () => {
      if (mode === "login") {
        return login({ email, password, role });
      }
      return signup({ email, password, name: name || undefined });
    },
    onSuccess: (res) => {
      setSession(res);
      // If the client arrived via an invite link for a specific document,
      // take them straight to that review (not the generic client-review
      // picker). Otherwise fall back to role home / requested redirect.
      let destination: string;
      if (
        inviteQ.data?.assigned_file_id &&
        res.user.role === "client"
      ) {
        destination = `/client-review?file_id=${inviteQ.data.assigned_file_id}`;
      } else if (
        requestedRedirect &&
        !requestedRedirect.startsWith("/login")
      ) {
        destination = requestedRedirect;
      } else {
        destination = roleHome(res.user.role);
      }
      navigate(destination, { replace: true });
    },
  });

  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (clientSignupBlocked) return;
    mutation.mutate();
  };

  const errorMessage = mutation.isError
    ? extractApiError(mutation.error)
    : null;

  return (
    <div className="grid min-h-screen md:grid-cols-2">
      <div className="hidden items-center justify-center bg-gradient-to-br from-brand-600 via-brand-700 to-indigo-900 p-12 text-white md:flex">
        <div className="max-w-md space-y-6">
          <div className="flex items-center gap-2">
            <span className="grid h-10 w-10 place-items-center rounded-lg bg-white/15 backdrop-blur">
              <Brain className="h-6 w-6" />
            </span>
            <span className="text-2xl font-semibold tracking-tight">
              FlowMind
            </span>
          </div>
          <h1 className="text-3xl font-semibold leading-tight">
            AI-powered requirements engineering, end to end.
          </h1>
          <p className="text-brand-100/90">
            Extract, review, and collaborate on software requirements from
            PDFs, Word, PowerPoint, and images — with a pre-model gate that
            rejects empty and non-SRS documents before a single model call.
          </p>
          <ul className="space-y-2 text-sm text-brand-100/80">
            <li>• Hybrid heuristic + semantic extraction</li>
            <li>• Client review portal and manager feedback loop</li>
            <li>• CSV / JSON / Jira / Trello exports</li>
          </ul>
        </div>
      </div>

      <div className="flex items-center justify-center p-6 sm:p-10">
        <div className="w-full max-w-md space-y-6">
          <div className="space-y-1">
            <h2 className="text-2xl font-semibold text-slate-900">
              {inviteQ.data
                ? `Welcome, ${inviteQ.data.name}`
                : mode === "login"
                  ? "Welcome back"
                  : "Create your account"}
            </h2>
            <p className="text-sm text-slate-500">
              {inviteQ.data
                ? "You've been invited to review requirements. Enter your temporary password to sign in."
                : mode === "login"
                  ? "Sign in to continue to your FlowMind workspace."
                  : "New managers can sign up below — takes 10 seconds."}
            </p>
          </div>

          {inviteToken && inviteQ.isLoading && (
            <div className="flex items-start gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs text-slate-700">
              <Loader2 className="mt-0.5 h-4 w-4 shrink-0 animate-spin" />
              <span>Verifying your invite link…</span>
            </div>
          )}

          {inviteToken && inviteQ.isError && (
            <div className="flex items-start gap-2 rounded-md border border-rose-200 bg-rose-50 px-3 py-2.5 text-xs text-rose-800">
              <Info className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="font-medium">This invite link isn't valid.</p>
                <p className="mt-0.5 text-rose-700/90">
                  It may be expired, revoked, or for a different account. Ask
                  your manager to send a fresh invite, or sign in manually
                  with your email and temp password below.
                </p>
              </div>
            </div>
          )}

          {inviteQ.data && (
            <div className="flex items-start gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2.5 text-xs text-emerald-900">
              <MailCheck className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="font-medium">
                  Invite verified. You'll be taken straight to your review.
                </p>
                <p className="mt-0.5 text-emerald-800/90">
                  Signed in as <b>{inviteQ.data.email}</b> — only the temp
                  password from your email is needed.
                </p>
              </div>
            </div>
          )}

          {mode === "signup" && !inviteToken && (
            <div className="flex items-start gap-2 rounded-md border border-sky-200 bg-sky-50 px-3 py-2.5 text-xs text-sky-800">
              <Info className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="font-medium">Signing up creates a manager account.</p>
                <p className="mt-0.5 text-sky-700/90">
                  Clients don't sign up here — a manager invites them and
                  shares a temporary password. If you received an invite
                  link, use the &quot;Sign in&quot; tab with the email and
                  temp password you were sent.
                </p>
              </div>
            </div>
          )}

          <form onSubmit={onSubmit} className="space-y-4">
            {mode === "signup" && (
              <Input
                name="name"
                label="Name"
                placeholder="Your name"
                autoComplete="name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            )}
            <Input
              name="email"
              type="email"
              label="Email"
              placeholder="you@company.com"
              autoComplete="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              readOnly={Boolean(inviteQ.data)}
              hint={
                inviteQ.data
                  ? "Locked to the email that received the invite."
                  : undefined
              }
              className={inviteQ.data ? "bg-slate-50 text-slate-700" : undefined}
            />
            <Input
              name="password"
              type="password"
              label="Password"
              placeholder="••••••••"
              autoComplete={
                mode === "login" ? "current-password" : "new-password"
              }
              minLength={6}
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              hint={mode === "signup" ? "At least 6 characters." : undefined}
            />

            {mode === "login" && !inviteQ.data && (
              <div>
                <label className="field-label">Sign in as</label>
                <div className="mt-1.5 inline-flex rounded-lg border border-slate-200 bg-slate-50 p-1">
                  {(["manager", "client"] as const).map((r) => (
                    <button
                      type="button"
                      key={r}
                      onClick={() => setRole(r)}
                      className={
                        "rounded-md px-4 py-1.5 text-xs font-medium capitalize transition " +
                        (role === r
                          ? "bg-white text-slate-900 shadow-sm"
                          : "text-slate-600 hover:text-slate-800")
                      }
                    >
                      {r}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {errorMessage && (
              <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                {errorMessage}
              </div>
            )}

            <Button
              type="submit"
              size="lg"
              className="w-full"
              loading={mutation.isPending}
            >
              {mutation.isPending ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" /> Please wait…
                </>
              ) : mode === "login" ? (
                "Sign in"
              ) : (
                "Create account"
              )}
            </Button>
          </form>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-slate-200" />
            </div>
            <div className="relative flex justify-center">
              <span className="bg-white px-3 text-[11px] font-medium uppercase tracking-wider text-slate-400">
                or continue with
              </span>
            </div>
          </div>

          <a
            href={`/auth/google/init?role=${role}&redirect_tab=${mode}`}
            className="flex h-11 w-full items-center justify-center gap-3 rounded-lg border border-slate-300 bg-white text-sm font-medium text-slate-800 shadow-sm transition hover:bg-slate-50 hover:shadow focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-500"
          >
            <svg
              aria-hidden="true"
              className="h-5 w-5"
              viewBox="0 0 48 48"
            >
              <path
                fill="#FFC107"
                d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 12.955 4 4 12.955 4 24s8.955 20 20 20 20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z"
              />
              <path
                fill="#FF3D00"
                d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4 16.318 4 9.656 8.337 6.306 14.691z"
              />
              <path
                fill="#4CAF50"
                d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238C29.211 35.091 26.715 36 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z"
              />
              <path
                fill="#1976D2"
                d="M43.611 20.083H42V20H24v8h11.303c-.792 2.237-2.231 4.166-4.087 5.571.001-.001.002-.001.003-.002l6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z"
              />
            </svg>
            Continue with Google
          </a>

          <p className="text-center text-[11px] text-slate-400">
            We use Google only to confirm your identity. Your Google password
            is never seen or stored by FlowMind.
          </p>

          <div className="flex items-center justify-between text-sm text-slate-500">
            {mode === "login" ? (
              <button
                type="button"
                onClick={() => setMode("signup")}
                className="font-medium text-brand-700 hover:text-brand-800"
              >
                Create an account
              </button>
            ) : (
              <button
                type="button"
                onClick={() => setMode("login")}
                className="font-medium text-brand-700 hover:text-brand-800"
              >
                I already have an account
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

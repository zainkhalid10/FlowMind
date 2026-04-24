import { useNavigate } from "react-router-dom";
import { Copy, LogOut, ShieldCheck } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { useAuth } from "@/contexts/AuthContext";
import { getStoredToken } from "@/lib/auth";

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-slate-100 py-3 last:border-0">
      <span className="text-sm text-slate-600">{label}</span>
      <span className="text-sm font-medium text-slate-900">{value}</span>
    </div>
  );
}

export default function SettingsPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const token = getStoredToken();

  const copyToken = async () => {
    if (!token) return;
    try {
      await navigator.clipboard.writeText(token);
    } catch {
      // Clipboard not available; ignore.
    }
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Settings
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Profile and session. Workspace/integration settings live on their
          respective pages.
        </p>
      </header>

      <Card>
        <CardHeader title="Profile" />
        <CardBody className="divide-y divide-slate-100">
          <Row label="Username" value={user?.username ?? "—"} />
          <Row label="Email" value={user?.email ?? "—"} />
          <Row
            label="Role"
            value={<Badge tone="brand">{user?.role ?? "—"}</Badge>}
          />
          <Row label="Team" value={user?.team_name ?? "—"} />
          <Row label="User ID" value={user?.id ?? "—"} />
        </CardBody>
      </Card>

      <Card>
        <CardHeader
          title="Session"
          description="Access token used for API calls."
          action={
            token && (
              <Button variant="secondary" size="sm" onClick={copyToken}>
                <Copy className="h-3.5 w-3.5" /> Copy token
              </Button>
            )
          }
        />
        <CardBody>
          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 font-mono text-xs text-slate-700 break-all">
            {token ? (
              <>
                {token.slice(0, 16)}
                <span className="text-slate-400">…</span>
                {token.slice(-8)}
              </>
            ) : (
              <span className="text-slate-500">Not signed in.</span>
            )}
          </div>
          <div className="mt-3 flex items-center gap-2 text-xs text-slate-500">
            <ShieldCheck className="h-4 w-4" />
            Tokens expire automatically after 30 days.
          </div>
          <div className="mt-4 flex justify-end">
            <Button
              variant="danger"
              onClick={() => {
                logout();
                navigate("/login", { replace: true });
              }}
            >
              <LogOut className="h-4 w-4" /> Log out
            </Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

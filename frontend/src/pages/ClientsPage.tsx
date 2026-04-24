import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Copy, Link2, Briefcase, UserPlus } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { extractApiError, fetchClients } from "@/lib/api";
import { InviteClientModal } from "@/components/InviteClientModal";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleDateString();
  } catch {
    return iso;
  }
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  if (!text || text === "N/A") return <span className="text-xs text-slate-400">—</span>;
  return (
    <button
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text);
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        } catch {
          // Clipboard blocked; ignore silently.
        }
      }}
      className="inline-flex items-center gap-1 rounded border border-slate-200 bg-white px-2 py-1 text-[11px] font-medium text-slate-600 hover:bg-slate-50"
    >
      <Copy className="h-3 w-3" />
      {copied ? "Copied" : label}
    </button>
  );
}

export default function ClientsPage() {
  const clientsQ = useQuery({
    queryKey: ["manager-clients"],
    queryFn: fetchClients,
  });
  const [inviteOpen, setInviteOpen] = useState(false);

  const clients = clientsQ.data?.clients ?? [];

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Clients
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Every client you've invited for review, with their assigned document
            and access credentials.
          </p>
        </div>
        <Button onClick={() => setInviteOpen(true)}>
          <UserPlus className="h-4 w-4" />
          Invite client
        </Button>
      </header>

      <InviteClientModal
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
      />

      {clientsQ.isError && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {extractApiError(clientsQ.error)}
        </div>
      )}

      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <Briefcase className="h-4 w-4" /> Invited clients
            </span>
          }
          description={`${clients.length} assignment${clients.length === 1 ? "" : "s"}`}
        />
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3 text-left font-medium">Client</th>
                  <th className="px-5 py-3 text-left font-medium">Document</th>
                  <th className="px-5 py-3 text-left font-medium">Due</th>
                  <th className="px-5 py-3 text-left font-medium">Status</th>
                  <th className="px-5 py-3 text-left font-medium">Share</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {clientsQ.isLoading ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-8 text-center text-slate-500">
                      Loading clients…
                    </td>
                  </tr>
                ) : clients.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="px-5 py-10 text-center">
                      <p className="text-sm font-medium text-slate-800">
                        You haven't invited any clients yet.
                      </p>
                      <p className="mt-1 text-xs text-slate-500">
                        Invite a client to review your extracted requirements.
                      </p>
                      <div className="mt-3">
                        <Button onClick={() => setInviteOpen(true)}>
                          <UserPlus className="h-4 w-4" /> Invite a client
                        </Button>
                      </div>
                    </td>
                  </tr>
                ) : (
                  clients.map((c) => (
                    <tr key={c.assignment_id} className="bg-white align-top">
                      <td className="px-5 py-3">
                        <p className="font-medium text-slate-900">
                          {c.client_name}
                        </p>
                        <p className="text-xs text-slate-500">{c.client_email}</p>
                      </td>
                      <td className="px-5 py-3 text-slate-700">{c.filename}</td>
                      <td className="px-5 py-3 text-slate-600">
                        {formatDate(c.due_date)}
                      </td>
                      <td className="px-5 py-3">
                        {c.submitted_at ? (
                          <Badge tone="success">Submitted</Badge>
                        ) : (
                          <Badge tone="warning">Pending</Badge>
                        )}
                      </td>
                      <td className="px-5 py-3">
                        <div className="flex flex-wrap items-center gap-2">
                          {c.invite_link && (
                            <Button
                              variant="secondary"
                              size="sm"
                              onClick={() =>
                                window.open(c.invite_link!, "_blank", "noopener")
                              }
                            >
                              <Link2 className="h-3.5 w-3.5" /> Open invite
                            </Button>
                          )}
                          <CopyButton
                            text={c.invite_link ?? ""}
                            label="Copy link"
                          />
                          <CopyButton
                            text={c.temp_password}
                            label="Copy password"
                          />
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

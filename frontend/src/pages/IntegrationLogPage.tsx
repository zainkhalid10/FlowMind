import { useQuery } from "@tanstack/react-query";
import { History } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { extractApiError, fetchIntegrationLog } from "@/lib/api";

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

export default function IntegrationLogPage() {
  const logQ = useQuery({
    queryKey: ["integration-log"],
    queryFn: () => fetchIntegrationLog(100),
  });

  const entries = logQ.data?.entries ?? [];

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Integration log
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Every Jira / Trello push recorded by the server, newest first.
        </p>
      </header>

      {logQ.isError && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {extractApiError(logQ.error)}
        </div>
      )}

      <Card>
        <CardHeader
          title={
            <span className="flex items-center gap-2">
              <History className="h-4 w-4" /> Recent activity
            </span>
          }
          description={`${entries.length} entr${entries.length === 1 ? "y" : "ies"}`}
        />
        <CardBody className="p-0">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                <tr>
                  <th className="px-5 py-3 text-left font-medium">When</th>
                  <th className="px-5 py-3 text-left font-medium">Platform</th>
                  <th className="px-5 py-3 text-left font-medium">User</th>
                  <th className="px-5 py-3 text-left font-medium">Source</th>
                  <th className="px-5 py-3 text-left font-medium">Items</th>
                  <th className="px-5 py-3 text-left font-medium">Message</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {logQ.isLoading ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-8 text-center text-slate-500">
                      Loading log…
                    </td>
                  </tr>
                ) : entries.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="px-5 py-8 text-center text-slate-500">
                      No integration activity yet.
                    </td>
                  </tr>
                ) : (
                  entries.map((e) => {
                    const ok = e.success_count >= e.items_count && e.items_count > 0;
                    return (
                      <tr key={e.id} className="bg-white align-top">
                        <td className="px-5 py-3 text-slate-600">
                          {formatDateTime(e.created_at)}
                        </td>
                        <td className="px-5 py-3">
                          <Badge tone="brand">{e.platform}</Badge>
                        </td>
                        <td className="px-5 py-3 text-slate-600">
                          {e.username ?? "—"}
                        </td>
                        <td className="px-5 py-3 text-slate-600">
                          {e.source ?? "—"}
                          {e.source_id ? (
                            <span className="ml-1 text-xs text-slate-400">
                              {e.source_id}
                            </span>
                          ) : null}
                        </td>
                        <td className="px-5 py-3">
                          <Badge tone={ok ? "success" : "warning"}>
                            {e.success_count}/{e.items_count}
                          </Badge>
                        </td>
                        <td className="px-5 py-3 text-slate-700">
                          {e.message ?? "—"}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

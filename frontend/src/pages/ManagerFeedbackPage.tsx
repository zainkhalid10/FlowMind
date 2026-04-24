import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, MessageSquareMore } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { SkeletonRows } from "@/components/ui/Skeleton";
import {
  extractApiError,
  fetchClients,
  fetchReviewSummary,
  resolveFeedback,
} from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";

function actionTone(action: string) {
  const a = action.toLowerCase();
  if (a === "approve") return "success" as const;
  if (a === "reject") return "danger" as const;
  if (a === "request_modification") return "warning" as const;
  return "neutral" as const;
}

function actionLabel(action: string) {
  const a = action.toLowerCase();
  if (a === "request_modification") return "Modification";
  return a.charAt(0).toUpperCase() + a.slice(1);
}

export default function ManagerFeedbackPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const [fileId, setFileId] = useState<number | undefined>(undefined);

  const clientsQ = useQuery({
    queryKey: ["manager-clients"],
    queryFn: fetchClients,
  });

  const assignments = useMemo(() => {
    return (clientsQ.data?.clients ?? []).filter((c) => c.file_id != null);
  }, [clientsQ.data]);

  const summaryQ = useQuery({
    queryKey: ["review-summary", fileId],
    queryFn: () => fetchReviewSummary(fileId!),
    enabled: fileId != null,
  });

  const resolveMut = useMutation({
    mutationFn: (id: number) => resolveFeedback(id, "resolved"),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["review-summary", fileId] });
      toast.success("Feedback resolved");
    },
    onError: (err) => toast.error("Could not resolve", extractApiError(err)),
  });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Manager feedback
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Inspect client actions on each document and resolve the comments you
          address.
        </p>
      </header>

      <Card>
        <CardHeader title="Pick an assignment" />
        <CardBody>
          <Select
            label="Document"
            value={fileId ?? ""}
            onChange={(e) =>
              setFileId(e.target.value ? Number(e.target.value) : undefined)
            }
          >
            <option value="">Select a reviewed document…</option>
            {assignments.map((a) => (
              <option key={a.assignment_id} value={a.file_id!}>
                {a.filename} — {a.client_name}
              </option>
            ))}
          </Select>
        </CardBody>
      </Card>

      {clientsQ.isError && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {extractApiError(clientsQ.error)}
        </div>
      )}

      {fileId != null && (
        <>
          {summaryQ.isLoading ? (
            <SkeletonRows count={3} />
          ) : summaryQ.isError ? (
            <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
              {extractApiError(summaryQ.error)}
            </div>
          ) : summaryQ.data ? (
            <>
              <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
                {[
                  { label: "Total", value: summaryQ.data.total, tone: "muted" as const },
                  {
                    label: "Approved",
                    value: summaryQ.data.approved,
                    tone: "success" as const,
                  },
                  {
                    label: "Rejected",
                    value: summaryQ.data.rejected,
                    tone: "danger" as const,
                  },
                  {
                    label: "Modification",
                    value: summaryQ.data.modification_requested,
                    tone: "warning" as const,
                  },
                  {
                    label: "Pending",
                    value: summaryQ.data.pending,
                    tone: "info" as const,
                  },
                ].map((s) => (
                  <Card key={s.label}>
                    <CardBody>
                      <Badge tone={s.tone}>{s.label}</Badge>
                      <p className="mt-1 text-2xl font-semibold text-slate-900">
                        {s.value}
                      </p>
                    </CardBody>
                  </Card>
                ))}
              </section>

              <Card>
                <CardHeader
                  title={
                    <span className="flex items-center gap-2">
                      <MessageSquareMore className="h-4 w-4" /> Client comments
                    </span>
                  }
                  description={`${summaryQ.data.client_comments.length} total`}
                />
                <CardBody className="space-y-3">
                  {summaryQ.data.client_comments.length === 0 ? (
                    <p className="py-6 text-center text-sm text-slate-500">
                      The client hasn't left any comments yet.
                    </p>
                  ) : (
                    summaryQ.data.client_comments.map((c) => (
                      <div
                        key={c.feedback_id}
                        className="rounded-lg border border-slate-200 bg-white p-4"
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <Badge tone={actionTone(c.action)}>
                              {actionLabel(c.action)}
                            </Badge>
                            <span className="text-sm font-medium text-slate-900">
                              {c.title}
                            </span>
                            {c.resolved && (
                              <Badge tone="success">Resolved</Badge>
                            )}
                          </div>
                          {!c.resolved && (
                            <Button
                              size="sm"
                              variant="secondary"
                              onClick={() => resolveMut.mutate(c.feedback_id)}
                              loading={
                                resolveMut.isPending &&
                                resolveMut.variables === c.feedback_id
                              }
                            >
                              <CheckCircle2 className="h-3.5 w-3.5" /> Mark resolved
                            </Button>
                          )}
                        </div>
                        {c.comment && (
                          <p className="mt-2 text-sm text-slate-700">
                            “{c.comment}”
                          </p>
                        )}
                        {(c.before_text || c.after_text) && (
                          <div className="mt-3 grid gap-2 text-xs md:grid-cols-2">
                            {c.before_text && (
                              <div className="rounded border border-slate-200 bg-slate-50 p-2">
                                <p className="mb-0.5 font-medium text-slate-500">
                                  Before
                                </p>
                                <p className="text-slate-700">{c.before_text}</p>
                              </div>
                            )}
                            {c.after_text && (
                              <div className="rounded border border-emerald-200 bg-emerald-50 p-2">
                                <p className="mb-0.5 font-medium text-emerald-700">
                                  After
                                </p>
                                <p className="text-emerald-900">
                                  {c.after_text}
                                </p>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))
                  )}
                </CardBody>
              </Card>
            </>
          ) : null}
        </>
      )}
    </div>
  );
}

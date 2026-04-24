import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  CheckCircle2,
  Edit3,
  FileCheck2,
  MessageSquareWarning,
  Sparkles,
  XCircle,
} from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Textarea } from "@/components/ui/Textarea";
import {
  aiRefineRequirement,
  extractApiError,
  fetchReviewDocument,
  submitReview,
  submitReviewAction,
} from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";
import type { ReviewRequirement } from "@/types/api";

type ActionKind = "approve" | "reject" | "request_modification";

function statusTone(status: string) {
  if (status === "approved") return "success" as const;
  if (status === "rejected") return "danger" as const;
  if (status === "modification_requested") return "warning" as const;
  return "muted" as const;
}

function statusLabel(status: string) {
  if (status === "modification_requested") return "Modification requested";
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function RequirementRow({
  fileId,
  req,
}: {
  fileId: number;
  req: ReviewRequirement;
}) {
  const qc = useQueryClient();
  const toast = useToast();
  const [comment, setComment] = useState(req.client_comment || "");
  const [showComment, setShowComment] = useState(
    req.review_status === "modification_requested",
  );
  const [aiSuggestion, setAiSuggestion] = useState<string | null>(null);

  const actMut = useMutation({
    mutationFn: (action: ActionKind) =>
      submitReviewAction(fileId, {
        req_id: req.req_id,
        action,
        comment: comment || undefined,
      }),
    onSuccess: (_data, action) => {
      qc.invalidateQueries({ queryKey: ["review-document", fileId] });
      toast.success(
        action === "approve"
          ? "Approved"
          : action === "reject"
            ? "Rejected"
            : "Change request submitted",
      );
      setAiSuggestion(null);
    },
    onError: (err) => toast.error("Action failed", extractApiError(err)),
  });

  const refineMut = useMutation({
    mutationFn: () => aiRefineRequirement(fileId, req.req_id, comment),
    onSuccess: (res) => {
      setAiSuggestion(res.refined);
    },
    onError: (err) => toast.error("AI refine failed", extractApiError(err)),
  });

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <Badge tone="brand">{req.category || "uncategorized"}</Badge>
        <Badge tone="muted">{req.priority || "Medium"}</Badge>
        <Badge tone={statusTone(req.review_status)}>
          {statusLabel(req.review_status)}
        </Badge>
      </div>
      <p className="text-sm font-medium text-slate-900">{req.title}</p>
      <p className="mt-1 text-sm text-slate-700 leading-relaxed">
        {req.description}
      </p>

      {req.client_comment && (
        <p className="mt-2 rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-700">
          <span className="font-medium text-slate-500">Your previous note: </span>
          {req.client_comment}
        </p>
      )}

      {showComment && (
        <div className="mt-3 space-y-2">
          <Textarea
            rows={2}
            placeholder="Describe the change you want made…"
            value={comment}
            onChange={(e) => setComment(e.target.value)}
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button
              size="sm"
              variant="secondary"
              onClick={() => refineMut.mutate()}
              loading={refineMut.isPending}
              disabled={comment.trim().length < 10}
              title={
                comment.trim().length < 10
                  ? "Type at least a sentence describing the change"
                  : "Let AI rewrite the requirement based on your note"
              }
            >
              <Sparkles className="h-3.5 w-3.5" />
              Suggest with AI
            </Button>
            {comment.trim().length < 10 && (
              <span className="text-[11px] text-slate-400">
                Add a sentence describing the change to enable AI refine
              </span>
            )}
          </div>
          {aiSuggestion && (
            <div className="rounded-lg border border-brand-200 bg-gradient-to-br from-brand-50 to-indigo-50 p-3 text-sm">
              <div className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-brand-700">
                <Sparkles className="h-3.5 w-3.5" />
                AI suggestion
              </div>
              <p className="mt-1 italic text-slate-800">"{aiSuggestion}"</p>
              <div className="mt-2 flex flex-wrap gap-2">
                <Button
                  size="sm"
                  onClick={() => {
                    setComment(aiSuggestion);
                    setAiSuggestion(null);
                    toast.info(
                      "Suggestion applied",
                      "Click 'Submit modification' to send it to your manager.",
                    );
                  }}
                >
                  Use this wording
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setAiSuggestion(null)}
                >
                  Dismiss
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <Button
          size="sm"
          onClick={() => actMut.mutate("approve")}
          loading={actMut.isPending && actMut.variables === "approve"}
        >
          <CheckCircle2 className="h-3.5 w-3.5" /> Approve
        </Button>
        <Button
          size="sm"
          variant="danger"
          onClick={() => actMut.mutate("reject")}
          loading={actMut.isPending && actMut.variables === "reject"}
        >
          <XCircle className="h-3.5 w-3.5" /> Reject
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            if (!showComment) {
              setShowComment(true);
              return;
            }
            actMut.mutate("request_modification");
          }}
          loading={
            actMut.isPending && actMut.variables === "request_modification"
          }
        >
          <Edit3 className="h-3.5 w-3.5" />
          {showComment ? "Submit modification" : "Request change"}
        </Button>
      </div>

      {actMut.isError && (
        <p className="mt-2 text-xs text-rose-600">
          {extractApiError(actMut.error)}
        </p>
      )}
    </div>
  );
}

export default function ClientReviewPage() {
  const [params, setParams] = useSearchParams();
  const fileIdParam = params.get("file_id");
  const [inputFile, setInputFile] = useState(fileIdParam ?? "");
  const fileId = fileIdParam ? Number(fileIdParam) : undefined;

  const qc = useQueryClient();
  const toast = useToast();

  const docQ = useQuery({
    queryKey: ["review-document", fileId],
    queryFn: () => fetchReviewDocument(fileId!),
    enabled: fileId != null,
  });

  const submitMut = useMutation({
    mutationFn: () => submitReview(fileId!),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["review-document", fileId] });
      toast.success("Review submitted — thanks!");
    },
    onError: (err) => toast.error("Submit failed", extractApiError(err)),
  });

  const stats = useMemo(() => {
    const items = docQ.data?.requirements ?? [];
    return {
      total: items.length,
      approved: items.filter((r) => r.review_status === "approved").length,
      rejected: items.filter((r) => r.review_status === "rejected").length,
      mod: items.filter((r) => r.review_status === "modification_requested")
        .length,
      pending: items.filter((r) => r.review_status === "pending").length,
    };
  }, [docQ.data?.requirements]);

  if (fileId == null) {
    return (
      <div className="space-y-6">
        <header>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Client review
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Enter the file ID shared with you to start reviewing requirements.
          </p>
        </header>
        <Card>
          <CardBody className="flex items-center gap-2">
            <input
              type="number"
              placeholder="File ID"
              value={inputFile}
              onChange={(e) => setInputFile(e.target.value)}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
            />
            <Button
              onClick={() => {
                if (inputFile) setParams({ file_id: inputFile });
              }}
            >
              Open review
            </Button>
          </CardBody>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Client review
          </h1>
          {docQ.data && (
            <p className="mt-1 text-sm text-slate-500">
              {docQ.data.filename} · from{" "}
              <span className="font-medium text-slate-700">
                {docQ.data.manager_name}
              </span>
              {docQ.data.due_date && (
                <>
                  {" "}
                  · due{" "}
                  {new Date(docQ.data.due_date).toLocaleDateString()}
                </>
              )}
            </p>
          )}
        </div>
        {docQ.data?.submitted_at ? (
          <Badge tone="success">
            Submitted {new Date(docQ.data.submitted_at).toLocaleString()}
          </Badge>
        ) : (
          <Button
            onClick={() => submitMut.mutate()}
            disabled={!docQ.data || stats.pending > 0}
            loading={submitMut.isPending}
          >
            <FileCheck2 className="h-4 w-4" />
            {stats.pending > 0
              ? `Submit (${stats.pending} pending)`
              : "Submit review"}
          </Button>
        )}
      </header>

      {docQ.isError && (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {extractApiError(docQ.error)}
        </div>
      )}

      {docQ.data && (
        <>
          <section className="grid grid-cols-2 gap-3 md:grid-cols-5">
            {[
              { label: "Total", value: stats.total, tone: "muted" as const },
              {
                label: "Approved",
                value: stats.approved,
                tone: "success" as const,
              },
              {
                label: "Rejected",
                value: stats.rejected,
                tone: "danger" as const,
              },
              {
                label: "Modification",
                value: stats.mod,
                tone: "warning" as const,
              },
              {
                label: "Pending",
                value: stats.pending,
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
                  <MessageSquareWarning className="h-4 w-4" /> Requirements
                </span>
              }
            />
            <CardBody className="space-y-3">
              {docQ.data.requirements.length === 0 ? (
                <p className="py-6 text-center text-sm text-slate-500">
                  This document has no requirements to review.
                </p>
              ) : (
                docQ.data.requirements.map((r) => (
                  <RequirementRow
                    key={r.req_id}
                    fileId={fileId}
                    req={r}
                  />
                ))
              )}
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}

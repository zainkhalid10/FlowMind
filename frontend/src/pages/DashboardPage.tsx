import { useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Clock,
  Eye,
  FileText,
  ImageIcon,
  Loader2,
  MessageCircle,
  Send,
  Trash2,
  UploadCloud,
  UserPlus,
} from "lucide-react";
import { InviteClientModal } from "@/components/InviteClientModal";
import { SendSummaryModal } from "@/components/SendSummaryModal";
import { WhatsappShareButton } from "@/components/WhatsappShareButton";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonRows } from "@/components/ui/Skeleton";
import {
  deleteUpload,
  extractApiError,
  fetchDashboardStats,
} from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/contexts/ToastContext";
import type { DocStatus, RecentDocument } from "@/types/api";

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

function statusBadge(status: DocStatus) {
  const map: Record<
    DocStatus,
    { tone: "warning" | "info" | "success" | "brand" | "muted"; label: string }
  > = {
    processing: { tone: "warning", label: "Processing" },
    pending: { tone: "muted", label: "Pending review" },
    complete: { tone: "success", label: "Complete" },
    "in-review": { tone: "brand", label: "Client reviewing" },
    "client-submitted": { tone: "info", label: "Client submitted" },
  };
  const spec = map[status] ?? { tone: "muted" as const, label: status };
  return <Badge tone={spec.tone}>{spec.label}</Badge>;
}

function StatTile({
  label,
  value,
  hint,
  accent,
  icon,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  accent?: "brand" | "success" | "warning" | "info";
  icon?: React.ReactNode;
}) {
  const accentClass = {
    brand: "from-brand-500 to-indigo-600",
    success: "from-emerald-500 to-teal-600",
    warning: "from-amber-500 to-orange-600",
    info: "from-sky-500 to-cyan-600",
  }[accent ?? "brand"];
  return (
    <Card>
      <CardBody className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
            {label}
          </p>
          {icon && (
            <span
              className={`grid h-8 w-8 place-items-center rounded-lg bg-gradient-to-br text-white shadow-sm ${accentClass}`}
            >
              {icon}
            </span>
          )}
        </div>
        <p className="text-3xl font-semibold tracking-tight text-slate-900">
          {value}
        </p>
        {hint && <p className="text-xs text-slate-500">{hint}</p>}
      </CardBody>
    </Card>
  );
}

function ActivitySparkline({
  data,
}: {
  data: { date: string; uploads: number }[];
}) {
  const max = Math.max(1, ...data.map((d) => d.uploads));
  return (
    <div className="flex h-16 items-end gap-1">
      {data.map((d, i) => {
        const pct = (d.uploads / max) * 100;
        return (
          <div
            key={i}
            className="group relative flex-1 rounded-t bg-brand-200 transition hover:bg-brand-400"
            style={{ height: `${Math.max(4, pct)}%` }}
            title={`${d.date}: ${d.uploads} upload${d.uploads === 1 ? "" : "s"}`}
          >
            <span className="pointer-events-none absolute -top-5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-slate-900 px-1.5 py-0.5 text-[10px] text-white opacity-0 shadow transition group-hover:opacity-100">
              {d.uploads}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function DocumentRow({
  doc,
  onInvite,
  onSendSummary,
}: {
  doc: RecentDocument;
  onInvite: (fileId: number) => void;
  onSendSummary: (fileId: number) => void;
}) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const toast = useToast();
  const [confirmOpen, setConfirmOpen] = useState(false);

  const delMut = useMutation({
    mutationFn: () => deleteUpload(doc.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["dashboard-stats"] });
      toast.success("Document deleted", doc.filename);
      setConfirmOpen(false);
    },
    onError: (err) => {
      toast.error("Delete failed", extractApiError(err));
      setConfirmOpen(false);
    },
  });

  return (
    <>
    <tr className="align-middle">
      <td className="px-5 py-3">
        <div className="flex items-center gap-2 font-medium text-slate-900">
          <FileText className="h-4 w-4 shrink-0 text-brand-600" />
          <span className="truncate max-w-[22ch]">{doc.filename}</span>
        </div>
      </td>
      <td className="px-5 py-3 text-xs text-slate-500">
        <Clock className="mr-1 inline h-3 w-3" />
        {formatDate(doc.created_at)}
      </td>
      <td className="px-5 py-3 text-sm text-slate-700">
        <span className="font-medium">{doc.feature_count}</span>{" "}
        <span className="text-slate-500">extracted</span>
      </td>
      <td className="px-5 py-3">{statusBadge(doc.status)}</td>
      <td className="px-5 py-3">
        <div className="flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/requirements?file_id=${doc.id}`)}
            aria-label="View requirements"
          >
            <Eye className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onInvite(doc.id)}
            aria-label="Invite client for this document"
            title="Invite client to review this document"
          >
            <UserPlus className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onSendSummary(doc.id)}
            aria-label="Send summary via WhatsApp"
            title="Send the requirement summary to a client on WhatsApp"
          >
            <MessageCircle className="h-3.5 w-3.5 text-[#25D366]" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/export?file_id=${doc.id}`)}
            aria-label="Export"
          >
            <Send className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="danger"
            size="sm"
            loading={delMut.isPending}
            onClick={() => setConfirmOpen(true)}
            aria-label="Delete from history"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </td>
    </tr>
    <ConfirmDialog
      open={confirmOpen}
      onClose={() => setConfirmOpen(false)}
      onConfirm={() => delMut.mutate()}
      tone="danger"
      title="Delete this document?"
      description="This removes the file and every extracted requirement permanently. This cannot be undone."
      detail={doc.filename}
      confirmLabel="Delete document"
      loading={delMut.isPending}
    />
    </>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [inviteFileId, setInviteFileId] = useState<number | undefined>(undefined);
  const [summaryOpen, setSummaryOpen] = useState(false);
  const [summaryFileId, setSummaryFileId] = useState<number | null>(null);
  const statsQ = useQuery({
    queryKey: ["dashboard-stats"],
    queryFn: fetchDashboardStats,
    refetchOnWindowFocus: false,
  });

  const openInviteFor = (fid?: number) => {
    setInviteFileId(fid);
    setInviteOpen(true);
  };

  const openSummaryFor = (fid: number) => {
    setSummaryFileId(fid);
    setSummaryOpen(true);
  };

  const s = statsQ.data;
  const byCat = s?.by_category ?? {};
  const functional = byCat["functional"] ?? 0;
  const nonFunctional = byCat["non-functional"] ?? byCat["non_functional"] ?? 0;
  const business = byCat["business"] ?? 0;
  const system = byCat["system"] ?? 0;

  // Internal status is intentionally not surfaced — only the CLIENT
  // decides approve / reject / modification on requirements.

  return (
    <div className="space-y-8">
      <header className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-sm text-slate-500">
            Welcome back,{" "}
            <span className="font-medium text-slate-700">{user?.username}</span>
          </p>
          <h1 className="mt-1 text-2xl font-semibold tracking-tight text-slate-900">
            Portfolio overview
          </h1>
        </div>
        <div className="flex gap-2">
          <Button
            variant="secondary"
            onClick={() => statsQ.refetch()}
            loading={statsQ.isFetching}
          >
            Refresh
          </Button>
          <WhatsappShareButton variant="outline" size="md" label="Share" />
          <Button variant="secondary" onClick={() => openInviteFor()}>
            <UserPlus className="h-4 w-4" />
            Invite client
          </Button>
          <Button onClick={() => navigate("/upload")}>
            <UploadCloud className="h-4 w-4" />
            Upload document
          </Button>
        </div>
      </header>

      <InviteClientModal
        open={inviteOpen}
        onClose={() => setInviteOpen(false)}
        initialFileId={inviteFileId}
      />

      <SendSummaryModal
        open={summaryOpen}
        onClose={() => setSummaryOpen(false)}
        fileId={summaryFileId}
      />

      {statsQ.isError ? (
        <div className="flex items-start gap-3 rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          <AlertCircle className="mt-0.5 h-4 w-4" />
          <div>
            <p className="font-medium">Couldn't load dashboard stats.</p>
            <p className="text-rose-600/90">{extractApiError(statsQ.error)}</p>
          </div>
        </div>
      ) : statsQ.isLoading ? (
        <SkeletonRows count={3} />
      ) : s ? (
        <>
          {/* Top-line KPIs */}
          <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatTile
              label="Documents"
              value={s.totals.documents}
              hint="Processed & in the system"
              accent="brand"
              icon={<FileText className="h-4 w-4" />}
            />
            <StatTile
              label="Requirements"
              value={s.totals.requirements}
              hint={`${functional} FR · ${nonFunctional} NFR`}
              accent="success"
              icon={<CheckCircle2 className="h-4 w-4" />}
            />
            <StatTile
              label="Images parsed"
              value={s.totals.images}
              hint="OCR + VLM understood"
              accent="info"
              icon={<ImageIcon className="h-4 w-4" />}
            />
            <StatTile
              label="Tracker exports"
              value={s.exports.total}
              hint={`Jira ${s.exports.jira} · Trello ${s.exports.trello}`}
              accent="warning"
              icon={<Send className="h-4 w-4" />}
            />
          </section>

          {/* Second row: requirements split + activity */}
          <section className="grid gap-3 md:grid-cols-3">
            <Card className="md:col-span-2">
              <CardHeader
                title="Requirements by category"
                description="Functional vs non-functional vs business vs system"
              />
              <CardBody>
                <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                  <BreakdownTile label="Functional" count={functional} tone="brand" />
                  <BreakdownTile
                    label="Non-functional"
                    count={nonFunctional}
                    tone="info"
                  />
                  <BreakdownTile label="Business" count={business} tone="warning" />
                  <BreakdownTile label="System" count={system} tone="muted" />
                </div>
                <p className="mt-4 border-t border-slate-100 pt-3 text-xs text-slate-500">
                  Approval decisions belong to the client — see the{" "}
                  <span className="font-medium text-slate-700">
                    Client review feedback
                  </span>{" "}
                  section below for yes / no / modification counts.
                </p>
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Uploads · last 14 days"
                description="Daily ingestion volume"
              />
              <CardBody>
                <ActivitySparkline data={s.activity_14d} />
                <p className="mt-2 text-xs text-slate-500">
                  {s.activity_14d.reduce((sum, d) => sum + d.uploads, 0)}{" "}
                  uploads total
                </p>
              </CardBody>
            </Card>
          </section>

          {/* Client feedback */}
          <section>
            <Card>
              <CardHeader
                title="Client review feedback"
                description="Live totals of every approve / reject / modification request submitted by clients."
                action={
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => navigate("/manager-feedback")}
                  >
                    Open review queue
                  </Button>
                }
              />
              <CardBody>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
                  <BreakdownTile
                    label="Total actions"
                    count={s.client_feedback.total}
                    tone="muted"
                  />
                  <BreakdownTile
                    label="Approved"
                    count={s.client_feedback.approved}
                    tone="success"
                  />
                  <BreakdownTile
                    label="Rejected"
                    count={s.client_feedback.rejected}
                    tone="danger"
                  />
                  <BreakdownTile
                    label="Modification"
                    count={s.client_feedback.modification_requested}
                    tone="warning"
                  />
                  <BreakdownTile
                    label="Pending"
                    count={s.client_feedback.pending}
                    tone="info"
                  />
                </div>
              </CardBody>
            </Card>
          </section>

          {/* Recent documents */}
          <section>
            <Card>
              <CardHeader
                title="Recent documents"
                description="Latest uploads with per-document status"
                action={
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => navigate("/requirements")}
                  >
                    All requirements
                  </Button>
                }
              />
              <CardBody className="p-0">
                {s.recent_documents.length === 0 ? (
                  <EmptyState
                    icon={<UploadCloud className="h-5 w-5" />}
                    title="No documents yet"
                    description="Upload your first Software Requirements Specification to get started."
                    action={
                      <Button onClick={() => navigate("/upload")}>
                        <UploadCloud className="h-4 w-4" /> Upload a document
                      </Button>
                    }
                  />
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500">
                        <tr>
                          <th className="px-5 py-3 text-left font-medium">File</th>
                          <th className="px-5 py-3 text-left font-medium">Uploaded</th>
                          <th className="px-5 py-3 text-left font-medium">Requirements</th>
                          <th className="px-5 py-3 text-left font-medium">Status</th>
                          <th className="px-5 py-3 text-left font-medium">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {s.recent_documents.map((d) => (
                          <DocumentRow
                            key={d.id}
                            doc={d}
                            onInvite={openInviteFor}
                            onSendSummary={openSummaryFor}
                          />
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardBody>
            </Card>
          </section>
        </>
      ) : (
        <p className="py-8 text-center text-sm text-slate-500">
          <Loader2 className="mx-auto h-5 w-5 animate-spin" />
        </p>
      )}
    </div>
  );
}

function BreakdownTile({
  label,
  count,
  tone,
}: {
  label: string;
  count: number;
  tone: "brand" | "success" | "warning" | "info" | "muted" | "danger";
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <Badge tone={tone}>{label}</Badge>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900">
        {count}
      </p>
    </div>
  );
}

import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileDown, FileText, Pencil, Save, Trash2, X } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import { EmptyState } from "@/components/ui/EmptyState";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { ConfirmDialog } from "@/components/ui/ConfirmDialog";
import {
  deleteFeature,
  extractApiError,
  fetchFeatures,
  fetchMyUploads,
  updateFeature,
} from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";
import type { Feature } from "@/types/api";

const CATEGORIES = ["", "functional", "non-functional", "business", "system"];
const STATUSES = ["", "pending", "approved", "denied"];

function statusTone(s: string) {
  if (s === "approved") return "success" as const;
  if (s === "denied") return "danger" as const;
  if (s === "pending") return "warning" as const;
  return "neutral" as const;
}

function FeatureCard({ feature }: { feature: Feature }) {
  const qc = useQueryClient();
  const toast = useToast();
  const [isEditing, setIsEditing] = useState(false);
  const [draft, setDraft] = useState(feature.description);
  const [confirmOpen, setConfirmOpen] = useState(false);

  const saveMut = useMutation({
    mutationFn: () => updateFeature(feature.id, { description: draft }),
    onSuccess: () => {
      setIsEditing(false);
      qc.invalidateQueries({ queryKey: ["features"] });
      toast.success("Requirement saved");
    },
    onError: (err) => toast.error("Save failed", extractApiError(err)),
  });

  const delMut = useMutation({
    mutationFn: () => deleteFeature(feature.id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["features"] });
      toast.success("Requirement deleted");
      setConfirmOpen(false);
    },
    onError: (err) => {
      toast.error("Delete failed", extractApiError(err));
      setConfirmOpen(false);
    },
  });

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone="brand">{feature.category || "uncategorized"}</Badge>
          <Badge tone={statusTone(feature.status)}>{feature.status}</Badge>
          {feature.quality_score != null && (
            <Badge tone="muted">
              quality {Math.round((feature.quality_score ?? 0) * 100) / 100}
            </Badge>
          )}
          {feature.assigned_to_username && (
            <Badge tone="info">→ {feature.assigned_to_username}</Badge>
          )}
        </div>
        <div className="flex items-center gap-1">
          {isEditing ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsEditing(false)}
              >
                <X className="h-3.5 w-3.5" /> Cancel
              </Button>
              <Button
                size="sm"
                onClick={() => saveMut.mutate()}
                loading={saveMut.isPending}
              >
                <Save className="h-3.5 w-3.5" /> Save
              </Button>
            </>
          ) : (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setIsEditing(true)}
              >
                <Pencil className="h-3.5 w-3.5" /> Edit
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={() => setConfirmOpen(true)}
                loading={delMut.isPending}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </Button>
            </>
          )}
        </div>
      </div>
      {isEditing ? (
        <Textarea
          rows={3}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
        />
      ) : (
        <p className="text-sm text-slate-800 leading-relaxed">
          {feature.description}
        </p>
      )}
      <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
        <span>📄 {feature.filename}</span>
        {feature.username && <span>👤 {feature.username}</span>}
      </div>
      <ConfirmDialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        onConfirm={() => delMut.mutate()}
        tone="danger"
        title="Delete this requirement?"
        description="This permanently removes the requirement from the document. Exported requirements in Jira / Trello are not affected."
        detail={feature.description.slice(0, 180)}
        confirmLabel="Delete requirement"
        loading={delMut.isPending}
      />
    </div>
  );
}

export default function RequirementsPage() {
  const [params, setParams] = useSearchParams();
  const fileIdParam = params.get("file_id");
  const [status, setStatus] = useState(params.get("status") ?? "");
  const [category, setCategory] = useState(params.get("category") ?? "");
  const [search, setSearch] = useState("");

  const fileId = fileIdParam ? Number(fileIdParam) : undefined;

  const uploadsQ = useQuery({
    queryKey: ["my-uploads"],
    queryFn: fetchMyUploads,
  });

  const featuresQ = useQuery({
    queryKey: ["features", { fileId, status, category }],
    queryFn: () =>
      fetchFeatures({
        file_id: fileId,
        status: status || undefined,
        category: category || undefined,
      }),
  });

  const filtered = useMemo(() => {
    const items = featuresQ.data?.features ?? [];
    if (!search) return items;
    const s = search.toLowerCase();
    return items.filter(
      (f) =>
        f.description.toLowerCase().includes(s) ||
        (f.filename ?? "").toLowerCase().includes(s) ||
        (f.username ?? "").toLowerCase().includes(s),
    );
  }, [featuresQ.data?.features, search]);

  const setFilter = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    setParams(next, { replace: true });
  };

  const selectedFile = (uploadsQ.data?.uploads ?? []).find(
    (u) => u.id === fileId,
  );

  const printPdf = () => {
    // Give the browser a tick to ensure the print-only header is rendered
    // before the print dialog opens.
    window.requestAnimationFrame(() => window.print());
  };

  return (
    <div className="space-y-6">
      {/* Print-only title block (hidden on screen, shown in PDF) */}
      <div className="print-only mb-4 border-b border-slate-300 pb-3">
        <h1 className="text-xl font-bold text-slate-900">
          Requirements export
        </h1>
        <p className="text-sm text-slate-600">
          {selectedFile ? `Document: ${selectedFile.filename}` : "All documents"}
          {status ? ` · Status: ${status}` : ""}
          {category ? ` · Category: ${category}` : ""}
        </p>
        <p className="text-xs text-slate-500">
          Generated by FlowMind · {new Date().toLocaleString()}
        </p>
      </div>

      <header className="flex flex-wrap items-start justify-between gap-3 print-hide">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Requirements
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Browse, edit, and clean up the extracted requirements.
          </p>
        </div>
        <Button variant="secondary" onClick={printPdf}>
          <FileDown className="h-4 w-4" />
          Download PDF
        </Button>
      </header>

      <Card>
        <CardHeader title="Filters" />
        <CardBody>
          <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
            <Select
              label="Document"
              value={fileId ?? ""}
              onChange={(e) => setFilter("file_id", e.target.value)}
            >
              <option value="">All documents</option>
              {(uploadsQ.data?.uploads ?? []).map((u) => (
                <option key={u.id} value={u.id}>
                  {u.filename}
                </option>
              ))}
            </Select>
            <Select
              label="Status"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setFilter("status", e.target.value);
              }}
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s || "All statuses"}
                </option>
              ))}
            </Select>
            <Select
              label="Category"
              value={category}
              onChange={(e) => {
                setCategory(e.target.value);
                setFilter("category", e.target.value);
              }}
            >
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c || "All categories"}
                </option>
              ))}
            </Select>
            <Input
              label="Search text"
              placeholder="Find in description, file, or user"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </CardBody>
      </Card>

      <div className="space-y-3">
        {featuresQ.isLoading ? (
          <SkeletonRows count={4} />
        ) : featuresQ.isError ? (
          <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            {extractApiError(featuresQ.error)}
          </div>
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<FileText className="h-5 w-5" />}
            title="No requirements match these filters"
            description="Try clearing a filter, or pick a different document."
          />
        ) : (
          <>
            <p className="text-xs text-slate-500">
              Showing {filtered.length} of {featuresQ.data?.total ?? 0}
            </p>
            {filtered.map((f) => (
              <FeatureCard key={f.id} feature={f} />
            ))}
          </>
        )}
      </div>
    </div>
  );
}

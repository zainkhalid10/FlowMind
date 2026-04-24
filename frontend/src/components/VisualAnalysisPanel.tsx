import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertCircle,
  Brain,
  Check,
  Copy,
  FileText,
  Images as ImagesIcon,
  Layers,
  Loader2,
  Maximize2,
  Plus,
  RotateCcw,
  Sparkles,
  Workflow,
  X,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { SkeletonRows } from "@/components/ui/Skeleton";
import { Modal } from "@/components/ui/Modal";
import {
  createRequirement,
  explainVisualItem,
  extractApiError,
  fetchVisualAnalysis,
} from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";
import type {
  CreateRequirementPayload,
} from "@/lib/api";
import type {
  VisualAnalysisResponse,
  VisualExplainResponse,
  VisualImage,
} from "@/types/api";

type Category = "functional" | "non-functional" | "business" | "system";

function categorizeRequirement(text: string): {
  cat: Category;
  tone: "brand" | "info" | "warning" | "muted";
} {
  const low = text.toLowerCase();
  if (
    /\b(performance|latency|security|encrypt|scalab|availabilit|reliabilit|usabilit|\d+\s?ms|\d+\s?mb|throughput|uptime|response\s+time)\b/.test(
      low,
    )
  )
    return { cat: "non-functional", tone: "info" };
  if (/\b(compliance|policy|cost|pricing|stakeholder|regulat|gdpr|kpi|audit)\b/.test(low))
    return { cat: "business", tone: "warning" };
  if (/\b(database|server|deployment|hardware|\bos\b|operating system|network|cloud|api gateway|load balancer)\b/.test(low))
    return { cat: "system", tone: "muted" };
  return { cat: "functional", tone: "brand" };
}

function diagramTone(t: string | null | undefined) {
  const k = (t || "unknown").toLowerCase();
  if (k === "unknown" || k === "none") return "muted" as const;
  if (k.includes("class") || k.includes("uml")) return "brand" as const;
  if (k.includes("flow") || k.includes("sequence")) return "info" as const;
  if (k.includes("architect")) return "success" as const;
  if (k.includes("ui") || k.includes("mock")) return "warning" as const;
  return "brand" as const;
}

/* -------------------------------------------------------------------------- */
/* Zoom viewer (full-screen)                                                   */
/* -------------------------------------------------------------------------- */

function ZoomViewer({
  open,
  src,
  caption,
  onClose,
}: {
  open: boolean;
  src: string | null;
  caption?: string;
  onClose: () => void;
}) {
  const [zoom, setZoom] = useState(1);
  const [rot, setRot] = useState(0);
  useEffect(() => {
    if (!open) {
      setZoom(1);
      setRot(0);
      return;
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === "+" || e.key === "=") setZoom((z) => Math.min(4, z + 0.25));
      if (e.key === "-") setZoom((z) => Math.max(0.25, z - 0.25));
      if (e.key.toLowerCase() === "r") setRot((r) => (r + 90) % 360);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open || !src) return null;
  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Image zoom viewer"
      className="fixed inset-0 z-[60] flex flex-col bg-slate-900/95 backdrop-blur"
    >
      <div className="flex items-center justify-between border-b border-slate-800 px-4 py-3 text-slate-200">
        <div className="flex items-center gap-2 text-sm">
          <ImagesIcon className="h-4 w-4" />
          <span className="truncate">{caption ?? "Image viewer"}</span>
          <Badge tone="muted">{Math.round(zoom * 100)}%</Badge>
        </div>
        <div className="flex items-center gap-1">
          <Button variant="ghost" size="sm" onClick={() => setZoom((z) => Math.max(0.25, z - 0.25))} aria-label="Zoom out"><ZoomOut className="h-4 w-4" /></Button>
          <Button variant="ghost" size="sm" onClick={() => setZoom((z) => Math.min(4, z + 0.25))} aria-label="Zoom in"><ZoomIn className="h-4 w-4" /></Button>
          <Button variant="ghost" size="sm" onClick={() => setRot((r) => (r + 90) % 360)} aria-label="Rotate"><RotateCcw className="h-4 w-4" /></Button>
          <Button variant="ghost" size="sm" onClick={() => { setZoom(1); setRot(0); }}>Reset</Button>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></Button>
        </div>
      </div>
      <div
        className="flex flex-1 items-center justify-center overflow-auto p-6"
        onClick={(e) => { if ((e.target as HTMLElement).tagName !== "IMG") onClose(); }}
      >
        <img
          src={src}
          alt={caption ?? ""}
          className="max-h-full max-w-full select-none transition-transform"
          style={{ transform: `scale(${zoom}) rotate(${rot}deg)`, cursor: zoom > 1 ? "grab" : "zoom-in" }}
          onClick={(e) => { e.stopPropagation(); setZoom((z) => (z >= 3 ? 1 : Math.min(4, z + 0.5))); }}
          draggable={false}
        />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Analysis modal (rich, with per-requirement "Add to document")              */
/* -------------------------------------------------------------------------- */

function SectionHeader({
  icon, title, count,
}: { icon: React.ReactNode; title: string; count?: number }) {
  return (
    <div className="mb-2 flex items-center gap-2">
      <span className="grid h-6 w-6 place-items-center rounded-md bg-brand-50 text-brand-700">{icon}</span>
      <h3 className="text-sm font-semibold text-slate-900">{title}</h3>
      {count != null && <Badge tone="muted">{count}</Badge>}
    </div>
  );
}

function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      variant="secondary"
      size="sm"
      onClick={async () => {
        try { await navigator.clipboard.writeText(text); setCopied(true); window.setTimeout(() => setCopied(false), 1500); } catch { /* */ }
      }}
    >
      {copied ? (<><Check className="h-3.5 w-3.5" /> Copied</>) : (<><Copy className="h-3.5 w-3.5" /> {label}</>)}
    </Button>
  );
}

function requirementsAsMarkdown(result: VisualExplainResponse): string {
  const lines: string[] = [];
  lines.push(`# AI image analysis — ${result.image_name}\n\n## Summary\n${result.explanation || "(no summary)"}`);
  if (result.components.length) lines.push(`\n## Components\n${result.components.map((c) => `- ${c}`).join("\n")}`);
  if (result.relationships.length) lines.push(`\n## Relationships\n${result.relationships.map((r) => `- ${r}`).join("\n")}`);
  if (result.process_steps.length) lines.push(`\n## Process steps\n${result.process_steps.map((p, i) => `${i + 1}. ${p}`).join("\n")}`);
  if (result.extracted_requirements.length) {
    lines.push(`\n## Extracted requirements`);
    for (const req of result.extracted_requirements) {
      const { cat } = categorizeRequirement(req);
      lines.push(`- **[${cat}]** ${req}`);
    }
  }
  return lines.join("\n");
}

function AnalysisModal({
  open, result, loading, error, onClose, imageUrl, onZoomImage, fileId,
  onRequirementAdded, onRetry,
}: {
  open: boolean;
  result: VisualExplainResponse | null;
  loading: boolean;
  error: string | null;
  imageUrl: string | null;
  onClose: () => void;
  onZoomImage?: () => void;
  fileId: number | null;
  onRequirementAdded: () => void;
  onRetry?: () => void;
}) {
  const toast = useToast();
  const [addedSet, setAddedSet] = useState<Set<string>>(new Set());
  // Elapsed-seconds counter so the user sees "this is actually progressing"
  // instead of staring at a silent spinner for up to 3 minutes.
  const [elapsed, setElapsed] = useState(0);

  // Reset per-open state when the modal re-opens for a new image.
  useEffect(() => { if (open) setAddedSet(new Set()); }, [open, result?.image_name]);

  // Tick while loading.
  useEffect(() => {
    if (!loading) { setElapsed(0); return; }
    setElapsed(0);
    const t = window.setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => window.clearInterval(t);
  }, [loading]);

  const grouped = useMemo(() => {
    if (!result) return null;
    const out: Record<Category, string[]> = { functional: [], "non-functional": [], business: [], system: [] };
    // Prefer the backend's rule-engine classification when present
    // (IEEE-830-style rules in rag_agent). Fall back to the client-side
    // keyword heuristic only for payloads from older backend versions.
    if (result.categorized_requirements && result.categorized_requirements.length) {
      for (const cr of result.categorized_requirements) {
        const cat: Category =
          cr.category === "non-functional" ||
          cr.category === "business" ||
          cr.category === "system"
            ? cr.category
            : "functional";
        out[cat].push(cr.text);
      }
    } else {
      for (const r of result.extracted_requirements) {
        out[categorizeRequirement(r).cat].push(r);
      }
    }
    return out;
  }, [result]);

  const categorySpecs: Array<{ key: Category; label: string; tone: "brand" | "info" | "warning" | "muted"; dot: string }> = [
    { key: "functional", label: "Functional", tone: "brand", dot: "bg-brand-500" },
    { key: "non-functional", label: "Non-functional", tone: "info", dot: "bg-sky-500" },
    { key: "business", label: "Business", tone: "warning", dot: "bg-amber-500" },
    { key: "system", label: "System", tone: "muted", dot: "bg-slate-500" },
  ];

  const addMut = useMutation({
    mutationFn: (body: CreateRequirementPayload) => createRequirement(body),
  });

  const addRequirement = async (req: string, cat: Category) => {
    if (!fileId) return;
    try {
      const title = req.length > 80 ? req.slice(0, 77) + "…" : req;
      await addMut.mutateAsync({
        file_id: fileId,
        title,
        description: req,
        category: cat,
        priority: "Medium",
        source: "image_analysis",
      });
      setAddedSet((prev) => new Set(prev).add(req));
      onRequirementAdded();
      toast.success("Requirement added", `${cat} → document`);
    } catch (e) {
      toast.error("Couldn't add requirement", extractApiError(e));
    }
  };

  // Map text → backend-classified category (falls back to keyword heuristic
  // if this payload was built before the backend started categorizing).
  const categoryForRequirement = (req: string): Category => {
    if (result?.categorized_requirements) {
      const hit = result.categorized_requirements.find((c) => c.text === req);
      if (hit) {
        const c = hit.category;
        if (c === "non-functional" || c === "business" || c === "system") return c;
        return "functional";
      }
    }
    return categorizeRequirement(req).cat;
  };

  const addAll = async () => {
    if (!grouped || !fileId) return;
    const all = result?.extracted_requirements ?? [];
    let added = 0;
    for (const req of all) {
      if (addedSet.has(req)) continue;
      const cat = categoryForRequirement(req);
      try {
        const title = req.length > 80 ? req.slice(0, 77) + "…" : req;
        await createRequirement({
          file_id: fileId,
          title,
          description: req,
          category: cat,
          priority: "Medium",
          source: "image_analysis",
        });
        setAddedSet((prev) => new Set(prev).add(req));
        added++;
      } catch { /* keep going */ }
    }
    onRequirementAdded();
    toast.success(
      `${added} requirement${added === 1 ? "" : "s"} added`,
      added === all.length ? "All of them." : `${all.length - added} were skipped.`,
    );
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="xl"
      title={<span className="flex items-center gap-2"><Sparkles className="h-4 w-4 text-brand-600" /> AI image analysis</span>}
      description="Qwen 2.5-VL interpreted the visual content plus OCR text. Add the useful extracted requirements directly into this document."
      footer={
        <>
          {result && result.extracted_requirements.length > 0 && (
            <Button
              variant="secondary"
              onClick={addAll}
              disabled={
                !fileId ||
                addedSet.size >= result.extracted_requirements.length
              }
            >
              <Plus className="h-3.5 w-3.5" /> Add all to document
            </Button>
          )}
          {result && (
            <CopyButton
              text={requirementsAsMarkdown(result)}
              label="Copy full summary"
            />
          )}
          <Button onClick={onClose}>Close</Button>
        </>
      }
    >
      {loading ? (
        <div className="space-y-4 py-4">
          <div className="flex items-start gap-3 rounded-lg border border-brand-200 bg-gradient-to-br from-brand-50 to-indigo-50 p-4 text-sm text-brand-800">
            <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-brand-600 text-white shadow-md shadow-brand-500/30">
              <Sparkles className="h-5 w-5 animate-pulse" />
            </span>
            <div className="min-w-0 flex-1 space-y-1">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium">Qwen 2.5-VL is reading the image…</p>
                <span className="inline-flex items-center gap-1 rounded-full bg-white/70 px-2 py-0.5 text-xs font-semibold tabular-nums text-brand-700 ring-1 ring-inset ring-brand-200">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  {Math.floor(elapsed / 60)}:
                  {String(elapsed % 60).padStart(2, "0")}
                </span>
              </div>
              <p className="text-xs text-brand-700/90">
                Detecting components, relationships, process steps, and
                requirements. Local VLM inference can take 1–3 minutes on a
                cold model — subsequent images on the same session finish in
                a few seconds.
              </p>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-brand-100">
                <div
                  className="h-full rounded-full bg-brand-600 transition-all"
                  style={{
                    width: `${Math.min(95, (elapsed / 180) * 100)}%`,
                  }}
                />
              </div>
            </div>
          </div>
          <SkeletonRows count={3} />
        </div>
      ) : error ? (
        <div className="space-y-3 py-2">
          <div className="flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">
            <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
            <div className="space-y-1">
              <p className="font-medium">Couldn't analyze this image.</p>
              <p className="text-rose-700/90">{error}</p>
              <p className="text-xs text-rose-700/80">
                This usually means the local VLM (Qwen 2.5-VL / LLaVA) is
                still loading the model into memory. Retrying often works
                because the model stays hot after the first attempt.
              </p>
            </div>
          </div>
          {onRetry && (
            <div className="flex justify-end">
              <Button onClick={onRetry}>
                <RotateCcw className="h-4 w-4" /> Try again
              </Button>
            </div>
          )}
        </div>
      ) : result ? (
        <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
          <aside className="lg:sticky lg:top-0 lg:self-start">
            {imageUrl && (
              <div className="group relative overflow-hidden rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-2 shadow-sm">
                <img src={imageUrl} alt="" onClick={onZoomImage} className="mx-auto max-h-64 w-auto cursor-zoom-in rounded-md object-contain" />
                {onZoomImage && (
                  <button onClick={onZoomImage} className="absolute right-3 top-3 inline-flex h-8 w-8 items-center justify-center rounded-md bg-slate-900/60 text-white opacity-0 backdrop-blur transition group-hover:opacity-100" aria-label="Open full-size viewer">
                    <Maximize2 className="h-4 w-4" />
                  </button>
                )}
              </div>
            )}
            <p className="mt-2 text-center text-[11px] text-slate-500 break-all">{result.image_name}</p>
            {grouped && (
              <div className="mt-4 grid grid-cols-2 gap-2">
                {categorySpecs.map((spec) => (
                  <div key={spec.key} className="rounded-lg border border-slate-200 bg-white p-2">
                    <div className="flex items-center gap-1.5">
                      <span className={`h-2 w-2 rounded-full ${spec.dot}`} />
                      <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">{spec.label}</span>
                    </div>
                    <p className="mt-0.5 text-xl font-bold tabular-nums text-slate-900">{grouped[spec.key].length}</p>
                  </div>
                ))}
              </div>
            )}
          </aside>

          <div className="space-y-5 min-w-0">
            <section className="rounded-xl border border-brand-100 bg-gradient-to-br from-brand-50/60 to-white p-4">
              <SectionHeader icon={<Sparkles className="h-3.5 w-3.5" />} title="Summary" />
              <p className="whitespace-pre-line text-[15px] leading-relaxed text-slate-800">{result.explanation || "No explanation produced."}</p>
            </section>
            {result.components.length > 0 && (
              <section className="rounded-xl border border-slate-200 bg-white p-4">
                <SectionHeader icon={<Layers className="h-3.5 w-3.5" />} title="Components detected" count={result.components.length} />
                <div className="flex flex-wrap gap-1.5">{result.components.map((c, i) => <Badge key={i} tone="brand">{c}</Badge>)}</div>
              </section>
            )}
            {result.relationships.length > 0 && (
              <section className="rounded-xl border border-slate-200 bg-white p-4">
                <SectionHeader icon={<Workflow className="h-3.5 w-3.5" />} title="Relationships" count={result.relationships.length} />
                <ul className="space-y-1.5 text-sm text-slate-700">
                  {result.relationships.map((r, i) => (
                    <li key={i} className="flex items-start gap-2"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-400" /><span className="leading-relaxed">{r}</span></li>
                  ))}
                </ul>
              </section>
            )}
            {result.process_steps.length > 0 && (
              <section className="rounded-xl border border-slate-200 bg-white p-4">
                <SectionHeader icon={<Workflow className="h-3.5 w-3.5" />} title="Process steps" count={result.process_steps.length} />
                <ol className="relative space-y-2.5 border-l-2 border-brand-100 pl-5">
                  {result.process_steps.map((p, i) => (
                    <li key={i} className="relative text-sm text-slate-700"><span className="absolute -left-[26px] top-0 inline-flex h-6 w-6 items-center justify-center rounded-full bg-brand-600 text-[10px] font-bold text-white ring-4 ring-white">{i + 1}</span><span className="leading-relaxed">{p}</span></li>
                  ))}
                </ol>
              </section>
            )}
            {grouped ? (
              <section className="rounded-xl border border-slate-200 bg-white p-4">
                <SectionHeader icon={<FileText className="h-3.5 w-3.5" />} title="Extracted requirements" count={result.extracted_requirements.length} />
                {result.extracted_requirements.length === 0 ? (
                  <p className="rounded-md border border-dashed border-slate-200 bg-slate-50 p-3 text-xs italic text-slate-500">
                    No concrete requirements could be extracted from this image. Try a different diagram or increase VLM quality.
                  </p>
                ) : (
                  <div className="space-y-4">
                    {categorySpecs.map((spec) => {
                      const items = grouped[spec.key];
                      if (items.length === 0) return null;
                      return (
                        <div key={spec.key}>
                          <div className="mb-2 flex items-center gap-2">
                            <span className={`h-2 w-2 rounded-full ${spec.dot}`} />
                            <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-700">{spec.label}</h4>
                            <Badge tone={spec.tone}>{items.length}</Badge>
                          </div>
                          <ul className="space-y-2">
                            {items.map((req, i) => {
                              const added = addedSet.has(req);
                              return (
                                <li
                                  key={i}
                                  className="flex items-start justify-between gap-3 rounded-lg border border-slate-200 bg-slate-50/60 p-3 text-sm leading-relaxed text-slate-800"
                                >
                                  <span className="flex-1">{req}</span>
                                  <Button
                                    size="sm"
                                    variant={added ? "secondary" : "primary"}
                                    disabled={added || !fileId || addMut.isPending}
                                    onClick={() => addRequirement(req, spec.key)}
                                  >
                                    {added ? (<><Check className="h-3.5 w-3.5" /> Added</>) : (<><Plus className="h-3.5 w-3.5" /> Add</>)}
                                  </Button>
                                </li>
                              );
                            })}
                          </ul>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>
            ) : null}
          </div>
        </div>
      ) : null}
    </Modal>
  );
}

/* -------------------------------------------------------------------------- */
/* Image gallery card                                                         */
/* -------------------------------------------------------------------------- */

function ImageCard({
  img, onZoom, onAnalyze, analyzing,
}: {
  img: VisualImage;
  onZoom: () => void;
  onAnalyze: () => void;
  analyzing: boolean;
}) {
  const ocrPreview = (img.ocr_text || "").replace(/\s+/g, " ").trim().slice(0, 120);
  return (
    <Card className="overflow-hidden">
      <div className="group relative aspect-video overflow-hidden bg-slate-100">
        <img src={img.image_url} alt={img.agent_note || "extracted image"} className="h-full w-full cursor-zoom-in object-contain transition group-hover:scale-[1.02]" onClick={onZoom} loading="lazy" />
        <button onClick={onZoom} aria-label="Open full-size viewer" className="absolute right-2 top-2 inline-flex h-8 w-8 items-center justify-center rounded-md bg-slate-900/60 text-white opacity-0 backdrop-blur transition hover:bg-slate-900/80 group-hover:opacity-100">
          <Maximize2 className="h-4 w-4" />
        </button>
        {img.page_number != null && (
          <span className="absolute left-2 top-2 rounded-full bg-slate-900/60 px-2 py-0.5 text-[10px] font-medium text-white">Page {img.page_number}</span>
        )}
      </div>
      <CardBody className="space-y-2.5">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge tone={diagramTone(img.diagram_type)}>{img.diagram_type || "unknown"}</Badge>
          {img.type_confidence > 0 && <Badge tone="muted">{img.type_confidence}% confidence</Badge>}
        </div>
        {img.agent_note && <p className="text-xs italic text-slate-600">"{img.agent_note}"</p>}
        {ocrPreview && <p className="line-clamp-2 text-xs text-slate-500"><span className="font-medium text-slate-600">OCR: </span>{ocrPreview}</p>}
        <div className="flex items-center justify-end gap-2 pt-1">
          <Button variant="secondary" size="sm" onClick={onZoom}><Maximize2 className="h-3.5 w-3.5" /> View</Button>
          <Button size="sm" onClick={onAnalyze} loading={analyzing}><Brain className="h-3.5 w-3.5" /> Analyze</Button>
        </div>
      </CardBody>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/* Top-level reusable panel                                                   */
/* -------------------------------------------------------------------------- */

interface VisualAnalysisPanelProps {
  fileId: number | null;
  /** Called when a requirement is added, so callers can refresh their own lists. */
  onRequirementAdded?: () => void;
}

export function VisualAnalysisPanel({
  fileId,
  onRequirementAdded,
}: VisualAnalysisPanelProps) {
  const [zoomSrc, setZoomSrc] = useState<string | null>(null);
  const [zoomCaption, setZoomCaption] = useState<string | undefined>(undefined);
  const [analyzing, setAnalyzing] = useState<string | null>(null);
  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<VisualExplainResponse | null>(null);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [analysisImage, setAnalysisImage] = useState<string | null>(null);
  // Remember the image we last tried to analyze so the "Try again" button
  // in the error state can retry without the user having to close, find
  // the card, and click Analyze again.
  const [lastImage, setLastImage] = useState<VisualImage | null>(null);

  const visualQ = useQuery<VisualAnalysisResponse>({
    queryKey: ["visual-analysis", fileId],
    queryFn: () => fetchVisualAnalysis(fileId!),
    enabled: fileId != null,
  });

  const explainMut = useMutation({
    mutationFn: (img: VisualImage) =>
      explainVisualItem(fileId!, {
        image_id: String(img.id),
        image_url: img.image_url,
        ocr_text: img.ocr_text || undefined,
      }),
    onMutate: (img) => {
      setAnalysisResult(null);
      setAnalysisError(null);
      setAnalysisImage(img.image_url);
      setAnalysisOpen(true);
      setAnalyzing(img.image_url);
      setLastImage(img);
    },
    onSuccess: (res) => { setAnalysisResult(res); setAnalyzing(null); },
    onError: (err) => {
      setAnalysisError(extractApiError(err));
      setAnalyzing(null);
    },
  });

  if (fileId == null) return null;

  const images = visualQ.data?.images ?? [];

  return (
    <Card>
      <CardHeader
        title={
          <span className="flex items-center gap-2">
            <ImagesIcon className="h-4 w-4" />
            Images &amp; Patterns with Requirements
          </span>
        }
        description="Every diagram / screenshot / image extracted from this document. Click Analyze to let Qwen 2.5-VL summarize and pull requirements from the visual, then add them straight into this document."
        action={
          visualQ.isFetching ? (
            <span className="inline-flex items-center gap-1.5 text-xs text-slate-500">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading…
            </span>
          ) : (
            <Badge tone="muted">
              {images.length} image{images.length === 1 ? "" : "s"}
            </Badge>
          )
        }
      />
      <CardBody>
        {visualQ.isLoading ? (
          <SkeletonRows count={2} />
        ) : visualQ.isError ? (
          <div className="flex items-start gap-3 rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
            <AlertCircle className="mt-0.5 h-4 w-4" />
            <div>
              <p className="font-medium">Couldn't load visual analysis.</p>
              <p>{extractApiError(visualQ.error)}</p>
            </div>
          </div>
        ) : images.length === 0 ? (
          <div className="rounded-md border border-dashed border-slate-200 bg-slate-50 p-4 text-center text-sm text-slate-500">
            No images were detected in this document.
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {images.map((img) => (
              <ImageCard
                key={String(img.id)}
                img={img}
                onZoom={() => {
                  setZoomSrc(img.image_url);
                  setZoomCaption(img.agent_note || `${img.diagram_type || "image"} — page ${img.page_number ?? "?"}`);
                }}
                onAnalyze={() => explainMut.mutate(img)}
                analyzing={analyzing === img.image_url && explainMut.isPending}
              />
            ))}
          </div>
        )}
      </CardBody>

      <ZoomViewer open={Boolean(zoomSrc)} src={zoomSrc} caption={zoomCaption} onClose={() => setZoomSrc(null)} />

      <AnalysisModal
        open={analysisOpen}
        result={analysisResult}
        loading={explainMut.isPending}
        error={analysisError}
        imageUrl={analysisImage}
        onClose={() => setAnalysisOpen(false)}
        onZoomImage={
          analysisImage
            ? () => { setZoomSrc(analysisImage); setZoomCaption(analysisResult?.image_name ?? "Image preview"); }
            : undefined
        }
        fileId={fileId}
        onRequirementAdded={() => onRequirementAdded?.()}
        onRetry={
          lastImage
            ? () => {
                setAnalysisError(null);
                setAnalysisResult(null);
                explainMut.mutate(lastImage);
              }
            : undefined
        }
      />
    </Card>
  );
}

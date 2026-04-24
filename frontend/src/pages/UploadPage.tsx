import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
} from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import {
  AlertTriangle,
  Brain,
  CheckCircle2,
  Eye,
  FileSearch,
  FileText,
  FileUp,
  ScanSearch,
  Sparkles,
  UploadCloud,
  X,
  ShieldAlert,
  Image as ImageIcon,
  ShieldCheck,
  Zap,
} from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Modal } from "@/components/ui/Modal";
import { PipelineStages, type PipelineStage } from "@/components/PipelineStages";
import {
  extractApiError,
  extractRejectionDetail,
  uploadAgent,
} from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";
import { VisualAnalysisPanel } from "@/components/VisualAnalysisPanel";
import { useQueryClient } from "@tanstack/react-query";
import type { AnalyzeResponse, RejectionDetail } from "@/types/api";

const ACCEPTED_EXTENSIONS = [".pdf", ".doc", ".docx"];

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(2)} MB`;
}

// Maps cleanly onto the backend ProcessingStage enum. Durations are
// client-side estimates used purely to animate the pipeline while the
// synchronous upload request is in flight — the real server progress
// is reflected in the final response (success or rejection).
const PIPELINE: PipelineStage[] = [
  {
    key: "upload",
    label: "Uploading",
    icon: FileUp,
    hint: "Streaming the file to FlowMind…",
  },
  {
    key: "parse",
    label: "Parsing document",
    icon: FileText,
    hint: "Extracting text from every page.",
  },
  {
    key: "validate",
    label: "SRS gate",
    icon: ShieldCheck,
    hint: "Rejecting empty & non-SRS docs before any model runs.",
  },
  {
    key: "vision",
    label: "Vision + OCR (parallel)",
    icon: ImageIcon,
    hint: "Qwen2.5-VL & Tesseract analyze diagrams in parallel workers.",
  },
  {
    key: "extract",
    label: "AI requirement extraction",
    icon: Sparkles,
    hint: "LangChain + LLaMA 3 classify functional / NFR / business.",
  },
  {
    key: "finalize",
    label: "Finalizing",
    icon: CheckCircle2,
    hint: "Deduplicating, scoring, and saving the results.",
  },
];

// Approximate per-stage durations in ms for the client-side animation.
// The pipeline snaps to 100% as soon as the real response arrives.
const STAGE_DURATIONS_MS = [800, 1800, 600, 6000, 5000, 1200];

export default function UploadPage() {
  const navigate = useNavigate();
  const toast = useToast();
  const qc = useQueryClient();

  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [stageIndex, setStageIndex] = useState(0);
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [rejection, setRejection] = useState<RejectionDetail | null>(null);
  const [rejectionOpen, setRejectionOpen] = useState(false);

  const stageTimers = useRef<number[]>([]);

  const clearStageTimers = useCallback(() => {
    for (const id of stageTimers.current) window.clearTimeout(id);
    stageTimers.current = [];
  }, []);

  useEffect(() => () => clearStageTimers(), [clearStageTimers]);

  const startPipelineAnimation = useCallback(() => {
    clearStageTimers();
    setStageIndex(0);
    let cumulative = 0;
    // Advance stage index according to estimated duration. We stop the
    // animation one step short of the final stage so the "Running" state
    // stays visible until the real response snaps it to complete.
    for (let i = 1; i < PIPELINE.length; i++) {
      cumulative += STAGE_DURATIONS_MS[i - 1];
      const id = window.setTimeout(() => setStageIndex(i), cumulative);
      stageTimers.current.push(id);
    }
  }, [clearStageTimers]);

  const mutation = useMutation({
    mutationFn: async (f: File) => uploadAgent(f),
    onMutate: () => {
      setResult(null);
      setRejection(null);
      setRejectionOpen(false);
      setIsRunning(true);
      startPipelineAnimation();
    },
    onSuccess: (res) => {
      clearStageTimers();
      setStageIndex(PIPELINE.length - 1);
      setIsRunning(false);
      setResult(res);
      toast.success(
        "Analysis complete",
        typeof res.images_detected === "number"
          ? `Parsed ${res.images_detected} image${res.images_detected === 1 ? "" : "s"} and extracted requirements.`
          : "Extracted requirements are ready to review.",
      );
    },
    onError: (err) => {
      clearStageTimers();
      setIsRunning(false);
      const rej = extractRejectionDetail(err);
      if (rej) {
        setRejection(rej);
        setRejectionOpen(true);
      } else {
        toast.error("Analysis failed", extractApiError(err));
      }
    },
  });

  const onFileSelected = (f: File | null) => {
    setFile(f);
    setResult(null);
    setRejection(null);
    setRejectionOpen(false);
    setStageIndex(0);
    setIsRunning(false);
    clearStageTimers();
  };

  const onDrop = (e: DragEvent<HTMLLabelElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) onFileSelected(dropped);
  };

  const onFileInput = (e: ChangeEvent<HTMLInputElement>) => {
    const picked = e.target.files?.[0] ?? null;
    onFileSelected(picked);
  };

  const onAnalyze = () => {
    if (!file || isRunning) return;
    mutation.mutate(file);
  };

  /* ---------- derived visuals for the status pane ---------- */

  const showPipeline = isRunning || (result && !isRunning) || mutation.isPending;

  return (
    <div className="space-y-8">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
            Analyze with AI
          </h1>
          <p className="mt-1 text-sm text-slate-500">
            Drop a PDF or Word document. The SRS gate rejects empty &
            non-SRS files in milliseconds, then the extraction pipeline pulls
            functional, non-functional, business, and system requirements —
            including from diagrams inside the document.
          </p>
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[1.35fr_1fr]">
        {/* ---------------- File picker card ---------------- */}
        <Card>
          <CardHeader
            title="1. Choose a document"
            description={`Accepts ${ACCEPTED_EXTENSIONS.join(", ")} · up to 50 MB`}
          />
          <CardBody className="space-y-5">
            <label
              onDragOver={(e) => {
                e.preventDefault();
                setIsDragging(true);
              }}
              onDragLeave={() => setIsDragging(false)}
              onDrop={onDrop}
              className={
                "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed px-6 py-14 text-center transition " +
                (isDragging
                  ? "border-brand-500 bg-brand-50"
                  : "border-slate-300 bg-slate-50 hover:border-brand-400 hover:bg-brand-50/40")
              }
            >
              <span className="grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-indigo-600 text-white shadow-lg shadow-brand-500/30">
                <UploadCloud className="h-7 w-7" />
              </span>
              <p className="mt-4 text-sm font-medium text-slate-800">
                Drag &amp; drop your document, or click to browse
              </p>
              <p className="mt-1 text-xs text-slate-500">
                PDF · DOC · DOCX
              </p>
              <input
                type="file"
                accept={ACCEPTED_EXTENSIONS.join(",")}
                onChange={onFileInput}
                className="hidden"
              />
            </label>

            {file && (
              <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-3 py-2.5 text-sm">
                <div className="flex min-w-0 flex-1 items-center gap-3">
                  <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-50 text-brand-600">
                    <FileText className="h-5 w-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium text-slate-900">
                      {file.name}
                    </p>
                    <p className="text-xs text-slate-500">
                      {formatBytes(file.size)}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => onFileSelected(null)}
                  disabled={isRunning}
                  className="rounded-md p-1 text-slate-400 transition hover:bg-slate-100 hover:text-slate-600 disabled:opacity-40"
                  aria-label="Remove selected file"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            )}

            <div className="flex items-center justify-between gap-3 pt-1">
              <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                <Badge tone="info">
                  <Zap className="mr-1 h-3 w-3" />
                  Gate &lt; 200ms
                </Badge>
                <Badge tone="brand">
                  <ImageIcon className="mr-1 h-3 w-3" />
                  Parallel VLM
                </Badge>
                <Badge tone="muted">
                  <ScanSearch className="mr-1 h-3 w-3" />
                  OCR + NLP
                </Badge>
              </div>
              <Button
                size="lg"
                onClick={onAnalyze}
                disabled={!file || isRunning}
                loading={isRunning}
              >
                <Brain className="h-4 w-4" />
                {isRunning ? "Analyzing…" : "Analyze with AI"}
              </Button>
            </div>
          </CardBody>
        </Card>

        {/* ---------------- Pipeline / Status card ---------------- */}
        <Card>
          <CardHeader
            title="2. Pipeline"
            description="Watch each stage light up as the document flows through."
          />
          <CardBody>
            {showPipeline ? (
              <>
                <PipelineStages
                  stages={PIPELINE}
                  activeIndex={stageIndex}
                  complete={!isRunning && !!result}
                />
                {result && !isRunning && (
                  <div className="mt-4 space-y-3">
                    <div className="flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">
                      <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0" />
                      <div className="space-y-1">
                        <p className="font-medium">Document processed</p>
                        {result.srs_validation && (
                          <div className="flex flex-wrap items-center gap-1.5">
                            <Badge tone="info">
                              SRS score {result.srs_validation.srs_score}
                            </Badge>
                            <Badge tone="brand">
                              {result.srs_validation.confidence}
                            </Badge>
                            {typeof result.images_detected === "number" && (
                              <Badge tone="muted">
                                {result.images_detected} image
                                {result.images_detected === 1 ? "" : "s"}
                              </Badge>
                            )}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                      {result.file_id ? (
                        <Button
                          onClick={() =>
                            navigate(`/requirements?file_id=${result.file_id}`)
                          }
                        >
                          <Eye className="h-4 w-4" />
                          View extracted requirements
                        </Button>
                      ) : (
                        <Button onClick={() => navigate(`/requirements`)}>
                          <Eye className="h-4 w-4" />
                          View extracted requirements
                        </Button>
                      )}
                      <Button
                        variant="secondary"
                        onClick={() => onFileSelected(null)}
                      >
                        Analyze another
                      </Button>
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div className="flex h-full flex-col items-center justify-center py-6 text-center">
                <span className="mb-3 grid h-12 w-12 place-items-center rounded-full bg-slate-100 text-slate-400">
                  <FileSearch className="h-5 w-5" />
                </span>
                <p className="text-sm font-semibold text-slate-800">
                  Ready when you are
                </p>
                <p className="mt-1 max-w-xs text-xs text-slate-500">
                  Pick a document and click{" "}
                  <span className="font-medium text-slate-700">
                    Analyze with AI
                  </span>{" "}
                  — we'll show you every stage as it runs.
                </p>
              </div>
            )}
          </CardBody>
        </Card>
      </div>

      {/* ---- Images & Patterns (appears only after a successful upload) ---- */}
      {result && !isRunning && result.file_id && (
        <>
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-slate-900">
              3. Images &amp; Patterns with Requirements
            </h2>
            <p className="mt-1 text-sm text-slate-500">
              Review the diagrams / screenshots FlowMind extracted from the
              document. Click <span className="font-medium">Analyze</span> on
              any image to summarize it with Qwen 2.5-VL and pull new
              functional / non-functional / business / system requirements —
              each one can be added straight into this document's requirement
              list.
            </p>
          </div>

          <VisualAnalysisPanel
            fileId={result.file_id}
            onRequirementAdded={() => {
              // Invalidate requirement caches so the Requirements page sees
              // newly-added image-derived items on next visit.
              qc.invalidateQueries({ queryKey: ["features"] });
              qc.invalidateQueries({ queryKey: ["dashboard-stats"] });
            }}
          />

          <div className="flex flex-wrap items-center justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => onFileSelected(null)}
            >
              Analyze another document
            </Button>
            <Button
              size="lg"
              onClick={() =>
                navigate(`/requirements?file_id=${result.file_id}`)
              }
            >
              <CheckCircle2 className="h-4 w-4" />
              Done — view the requirements
            </Button>
          </div>
        </>
      )}

      {/* --------------------- Rejection modal --------------------- */}
      <RejectionModal
        open={rejectionOpen && !!rejection}
        rejection={rejection}
        onClose={() => {
          setRejectionOpen(false);
        }}
        onRetry={() => {
          setRejectionOpen(false);
          setRejection(null);
          setFile(null);
        }}
      />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Rejection modal                                                            */
/* -------------------------------------------------------------------------- */

function RejectionModal({
  open,
  rejection,
  onClose,
  onRetry,
}: {
  open: boolean;
  rejection: RejectionDetail | null;
  onClose: () => void;
  onRetry: () => void;
}) {
  if (!rejection) {
    return <Modal open={open} onClose={onClose}>{null}</Modal>;
  }
  const isEmpty = rejection.error === "DOCUMENT_EMPTY";
  const tone = isEmpty
    ? {
        bg: "bg-amber-100",
        text: "text-amber-700",
        ring: "ring-amber-200",
        icon: <AlertTriangle className="h-6 w-6" />,
        title: "This document looks empty",
      }
    : {
        bg: "bg-rose-100",
        text: "text-rose-700",
        ring: "ring-rose-200",
        icon: <ShieldAlert className="h-6 w-6" />,
        title: "Document isn't an SRS",
      };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            Close
          </Button>
          <Button onClick={onRetry}>
            <UploadCloud className="h-4 w-4" />
            Try another document
          </Button>
        </>
      }
    >
      <div className="flex items-start gap-4">
        <span
          className={`grid h-12 w-12 shrink-0 place-items-center rounded-full ring-1 ring-inset ${tone.bg} ${tone.text} ${tone.ring}`}
        >
          {tone.icon}
        </span>
        <div className="min-w-0 flex-1">
          <h3 className="text-lg font-semibold text-slate-900">{tone.title}</h3>
          <p className="mt-1 text-sm text-slate-600">{rejection.message}</p>

          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            <Badge tone={isEmpty ? "warning" : "danger"}>
              {rejection.error}
            </Badge>
            {typeof rejection.score === "number" && (
              <Badge tone="muted">SRS score {rejection.score} / 100</Badge>
            )}
            <Badge tone="info">Blocked before any model ran</Badge>
          </div>

          {rejection.reasons && rejection.reasons.length > 0 && (
            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Why it was flagged
              </p>
              <ul className="mt-2 space-y-1.5">
                {rejection.reasons.slice(0, 6).map((reason, i) => (
                  <li
                    key={i}
                    className="flex items-start gap-2 text-sm text-slate-700"
                  >
                    <span className="mt-1 h-1.5 w-1.5 shrink-0 rounded-full bg-slate-400" />
                    {reason}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {rejection.recommendation && (
            <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
              <span className="font-medium text-slate-500">Recommendation:</span>{" "}
              {rejection.recommendation}
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}

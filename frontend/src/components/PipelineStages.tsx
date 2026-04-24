import { CheckCircle2, Loader2, type LucideIcon } from "lucide-react";
import { cn } from "@/lib/cn";

export interface PipelineStage {
  key: string;
  label: string;
  icon: LucideIcon;
  hint?: string;
}

interface PipelineStagesProps {
  stages: PipelineStage[];
  /** Index of the stage currently in progress. Stages before it are done, after it are pending. */
  activeIndex: number;
  /** When true, every stage before and including activeIndex is marked done. */
  complete?: boolean;
}

export function PipelineStages({
  stages,
  activeIndex,
  complete,
}: PipelineStagesProps) {
  return (
    <ol className="grid gap-2.5">
      {stages.map((stage, i) => {
        const isComplete = complete ? i <= activeIndex : i < activeIndex;
        const isActive = !complete && i === activeIndex;
        const isPending = !complete && i > activeIndex;

        return (
          <li
            key={stage.key}
            className={cn(
              "relative flex items-start gap-3 rounded-lg border p-3 transition",
              isActive &&
                "border-brand-200 bg-brand-50/40 shadow-sm ring-1 ring-brand-100",
              isComplete && "border-emerald-200 bg-emerald-50/40",
              isPending && "border-slate-200 bg-white opacity-70",
            )}
          >
            <span
              className={cn(
                "mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-full transition",
                isActive && "bg-brand-600 text-white shadow-md shadow-brand-500/30",
                isComplete && "bg-emerald-600 text-white",
                isPending && "bg-slate-100 text-slate-400",
              )}
            >
              {isComplete ? (
                <CheckCircle2 className="h-4 w-4" />
              ) : isActive ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <stage.icon className="h-4 w-4" />
              )}
            </span>

            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p
                  className={cn(
                    "text-sm font-medium",
                    isActive && "text-brand-800",
                    isComplete && "text-emerald-800",
                    isPending && "text-slate-700",
                  )}
                >
                  {stage.label}
                </p>
                {isActive && (
                  <span className="inline-flex animate-pulse items-center text-[11px] font-semibold uppercase tracking-wider text-brand-700">
                    Running
                  </span>
                )}
                {isComplete && (
                  <span className="inline-flex items-center text-[11px] font-semibold uppercase tracking-wider text-emerald-700">
                    Done
                  </span>
                )}
              </div>
              {stage.hint && (
                <p
                  className={cn(
                    "mt-0.5 text-xs",
                    isActive && "text-brand-700/90",
                    isComplete && "text-emerald-700/80",
                    isPending && "text-slate-500",
                  )}
                >
                  {stage.hint}
                </p>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

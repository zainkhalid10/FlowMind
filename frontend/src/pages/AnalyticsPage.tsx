import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Chart as ChartJS,
  ArcElement,
  BarElement,
  CategoryScale,
  Legend,
  LinearScale,
  PointElement,
  Tooltip,
  Title,
} from "chart.js";
import { Bar, Doughnut, Pie, Scatter } from "react-chartjs-2";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Select } from "@/components/ui/Select";
import { Badge } from "@/components/ui/Badge";
import { extractApiError, fetchFeatures, fetchMyUploads } from "@/lib/api";
import type { Feature } from "@/types/api";

ChartJS.register(
  ArcElement,
  BarElement,
  CategoryScale,
  LinearScale,
  PointElement,
  Tooltip,
  Legend,
  Title,
);

type Counter = Record<string, number>;

function tally<T>(items: T[], key: (item: T) => string): Counter {
  const out: Counter = {};
  for (const item of items) {
    const k = key(item) || "unknown";
    out[k] = (out[k] || 0) + 1;
  }
  return out;
}

function titleCase(s: string): string {
  return s
    .replace(/[_-]/g, " ")
    .split(" ")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

// Brand-aligned palette, deterministic and color-blind-friendly.
const PALETTE = [
  "#3c6bff",
  "#7c3aed",
  "#0ea5e9",
  "#10b981",
  "#f59e0b",
  "#ef4444",
  "#d946ef",
  "#14b8a6",
  "#6366f1",
];

const CHART_ANIMATION = {
  animation: {
    duration: 800,
    easing: "easeOutQuart" as const,
  },
};

export default function AnalyticsPage() {
  const [fileId, setFileId] = useState<number | undefined>(undefined);

  const uploadsQ = useQuery({
    queryKey: ["my-uploads"],
    queryFn: fetchMyUploads,
  });

  const featuresQ = useQuery({
    queryKey: ["features", { file_id: fileId }],
    queryFn: () => fetchFeatures({ file_id: fileId }),
  });

  const features: Feature[] = featuresQ.data?.features ?? [];

  const { byCategory, byStatus, byPriority, byFile, scatterPoints, avgQuality } =
    useMemo(() => {
      const byCategory = tally(features, (f) =>
        (f.category || "uncategorized").toLowerCase(),
      );
      const byStatus = tally(features, (f) => f.status || "pending");
      const byPriority = tally(
        features,
        (f: Feature) =>
          ((f as unknown as { priority?: string }).priority || "medium").toLowerCase(),
      );
      const byFile = tally(features, (f) => f.filename || "unknown");
      const scatterPoints = features
        .filter((f) => f.quality_score != null && f.created_at)
        .map((f) => ({
          x: new Date(f.created_at!).getTime(),
          y: Number(f.quality_score ?? 0),
          label: f.description.slice(0, 60),
          category: (f.category || "uncategorized").toLowerCase(),
        }));
      const avgQuality =
        features.length === 0
          ? 0
          : features.reduce((s, f) => s + (f.quality_score ?? 0), 0) /
            features.length;
      return {
        byCategory,
        byStatus,
        byPriority,
        byFile,
        scatterPoints,
        avgQuality,
      };
    }, [features]);

  const chartBgPrimary = features.length === 0 ? ["#e2e8f0"] : undefined;

  const categoryDoughnut = {
    labels: Object.keys(byCategory).map(titleCase),
    datasets: [
      {
        label: "Requirements",
        data: Object.values(byCategory),
        backgroundColor:
          chartBgPrimary ?? Object.keys(byCategory).map((_, i) => PALETTE[i % PALETTE.length]),
        borderColor: "#ffffff",
        borderWidth: 2,
      },
    ],
  };

  const statusBar = {
    labels: Object.keys(byStatus).map(titleCase),
    datasets: [
      {
        label: "Requirements",
        data: Object.values(byStatus),
        backgroundColor: Object.keys(byStatus).map((k) => {
          const key = k.toLowerCase();
          if (key === "approved") return "#10b981";
          if (key === "denied" || key === "rejected") return "#ef4444";
          if (key === "pending") return "#f59e0b";
          return "#3c6bff";
        }),
        borderRadius: 6,
      },
    ],
  };

  const priorityPie = {
    labels: Object.keys(byPriority).map(titleCase),
    datasets: [
      {
        label: "Requirements",
        data: Object.values(byPriority),
        backgroundColor: Object.keys(byPriority).map((k) => {
          const key = k.toLowerCase();
          if (key === "high" || key === "critical") return "#ef4444";
          if (key === "medium") return "#f59e0b";
          if (key === "low") return "#10b981";
          return "#3c6bff";
        }),
        borderColor: "#ffffff",
        borderWidth: 2,
      },
    ],
  };

  const scatterData = {
    datasets: [
      {
        label: "Requirement quality over time",
        data: scatterPoints,
        backgroundColor: scatterPoints.map((p) => {
          const c = p.category;
          if (c === "functional") return "#3c6bff";
          if (c === "non-functional" || c === "non_functional") return "#0ea5e9";
          if (c === "business") return "#f59e0b";
          if (c === "system") return "#7c3aed";
          return "#64748b";
        }),
        pointRadius: 5,
        pointHoverRadius: 7,
      },
    ],
  };

  const byFileBar = {
    labels: Object.keys(byFile),
    datasets: [
      {
        label: "Requirements",
        data: Object.values(byFile),
        backgroundColor: Object.keys(byFile).map(
          (_, i) => PALETTE[i % PALETTE.length],
        ),
        borderRadius: 6,
      },
    ],
  };

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Analytics
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Animated breakdowns of every extracted requirement across category,
          status, priority, and quality score.
        </p>
      </header>

      <Card>
        <CardHeader title="Scope" />
        <CardBody>
          <Select
            label="Document"
            value={fileId ?? ""}
            onChange={(e) =>
              setFileId(e.target.value ? Number(e.target.value) : undefined)
            }
          >
            <option value="">All documents</option>
            {(uploadsQ.data?.uploads ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.filename}
              </option>
            ))}
          </Select>
        </CardBody>
      </Card>

      {featuresQ.isError ? (
        <div className="rounded-md border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700">
          {extractApiError(featuresQ.error)}
        </div>
      ) : (
        <>
          <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <StatTile label="Total" value={features.length} />
            <StatTile
              label="Approved"
              value={byStatus["approved"] ?? 0}
              tone="success"
            />
            <StatTile
              label="Pending"
              value={byStatus["pending"] ?? 0}
              tone="warning"
            />
            <StatTile
              label="Avg quality"
              value={avgQuality.toFixed(2)}
              tone="brand"
            />
          </section>

          <div className="grid gap-4 lg:grid-cols-2">
            <Card>
              <CardHeader
                title="By category"
                description="Functional vs non-functional vs business vs system"
              />
              <CardBody>
                <div className="mx-auto h-72 max-w-sm">
                  <Doughnut
                    data={categoryDoughnut}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      cutout: "60%",
                      ...CHART_ANIMATION,
                      plugins: {
                        legend: { position: "bottom" as const },
                        tooltip: { enabled: true },
                      },
                    }}
                  />
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="By status"
                description="Internal review pipeline state"
              />
              <CardBody>
                <div className="h-72">
                  <Bar
                    data={statusBar}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      ...CHART_ANIMATION,
                      plugins: {
                        legend: { display: false },
                      },
                      scales: {
                        y: { beginAtZero: true, ticks: { precision: 0 } },
                      },
                    }}
                  />
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="By priority"
                description="High / medium / low distribution"
              />
              <CardBody>
                <div className="mx-auto h-72 max-w-sm">
                  <Pie
                    data={priorityPie}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      ...CHART_ANIMATION,
                      plugins: {
                        legend: { position: "bottom" as const },
                      },
                    }}
                  />
                </div>
              </CardBody>
            </Card>

            <Card>
              <CardHeader
                title="Quality over time"
                description="Each point is one requirement; colour = category"
              />
              <CardBody>
                <div className="h-72">
                  <Scatter
                    data={scatterData}
                    options={{
                      responsive: true,
                      maintainAspectRatio: false,
                      ...CHART_ANIMATION,
                      plugins: {
                        legend: { display: false },
                        tooltip: {
                          callbacks: {
                            label: (ctx) => {
                              const raw = ctx.raw as {
                                label: string;
                                y: number;
                              };
                              return `${raw.label} — quality ${raw.y.toFixed(2)}`;
                            },
                          },
                        },
                      },
                      scales: {
                        x: {
                          type: "linear",
                          ticks: {
                            callback: (v) => {
                              const d = new Date(Number(v));
                              return `${d.getMonth() + 1}/${d.getDate()}`;
                            },
                          },
                        },
                        y: {
                          beginAtZero: true,
                          title: {
                            display: true,
                            text: "Quality score",
                          },
                        },
                      },
                    }}
                  />
                </div>
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader
              title="By document"
              description="How many requirements each document contributed"
              action={
                <Badge tone="muted">
                  {Object.keys(byFile).length} document
                  {Object.keys(byFile).length === 1 ? "" : "s"}
                </Badge>
              }
            />
            <CardBody>
              <div className="h-80">
                <Bar
                  data={byFileBar}
                  options={{
                    responsive: true,
                    maintainAspectRatio: false,
                    indexAxis: "y" as const,
                    ...CHART_ANIMATION,
                    plugins: { legend: { display: false } },
                    scales: {
                      x: { beginAtZero: true, ticks: { precision: 0 } },
                    },
                  }}
                />
              </div>
            </CardBody>
          </Card>
        </>
      )}
    </div>
  );
}

function StatTile({
  label,
  value,
  tone,
}: {
  label: string;
  value: number | string;
  tone?: "success" | "warning" | "brand";
}) {
  const accent = {
    success: "text-emerald-700",
    warning: "text-amber-700",
    brand: "text-brand-700",
  }[tone ?? "brand"];
  return (
    <Card>
      <CardBody>
        <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
          {label}
        </p>
        <p className={`mt-1 text-2xl font-semibold tabular-nums ${accent}`}>
          {value}
        </p>
      </CardBody>
    </Card>
  );
}

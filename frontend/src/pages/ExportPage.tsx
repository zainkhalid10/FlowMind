import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, FileJson, FileSpreadsheet, Kanban } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Badge } from "@/components/ui/Badge";
import {
  csvDownloadUrl,
  exportToJira,
  exportToTrello,
  extractApiError,
  fetchIntegrationConfig,
  fetchMyUploads,
  jsonDownloadUrl,
} from "@/lib/api";
import { getStoredToken } from "@/lib/auth";
import { useToast } from "@/contexts/ToastContext";

export default function ExportPage() {
  const [fileId, setFileId] = useState<number | undefined>(undefined);

  const uploadsQ = useQuery({
    queryKey: ["my-uploads"],
    queryFn: fetchMyUploads,
  });

  const configQ = useQuery({
    queryKey: ["integration-config"],
    queryFn: fetchIntegrationConfig,
  });

  const toast = useToast();
  const jiraMut = useMutation({
    mutationFn: () => exportToJira(fileId!, []),
    onSuccess: () => toast.success("Pushed to Jira"),
    onError: (err) => toast.error("Jira push failed", extractApiError(err)),
  });
  const trelloMut = useMutation({
    mutationFn: () => exportToTrello(fileId!, []),
    onSuccess: () => toast.success("Pushed to Trello"),
    onError: (err) => toast.error("Trello push failed", extractApiError(err)),
  });

  const token = getStoredToken();
  const downloadWithToken = (url: string) => {
    // Backend accepts ?token= on export routes; safest with blob downloads.
    const withToken = `${url}?token=${encodeURIComponent(token ?? "")}`;
    window.open(withToken, "_blank", "noopener");
  };

  const disabled = !fileId;
  const jiraConnected = Boolean(
    configQ.data?.jira && Object.keys(configQ.data.jira).length > 0,
  );
  const trelloConnected = Boolean(
    configQ.data?.trello && Object.keys(configQ.data.trello).length > 0,
  );

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Export
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Download extracted requirements or push them to your tracker.
        </p>
      </header>

      <Card>
        <CardHeader title="Source document" />
        <CardBody>
          <Select
            label="Document"
            value={fileId ?? ""}
            onChange={(e) =>
              setFileId(e.target.value ? Number(e.target.value) : undefined)
            }
          >
            <option value="">Pick a document…</option>
            {(uploadsQ.data?.uploads ?? []).map((u) => (
              <option key={u.id} value={u.id}>
                {u.filename}
              </option>
            ))}
          </Select>
        </CardBody>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader
            title="Download"
            description="CSV or JSON of the approved requirements."
          />
          <CardBody className="space-y-3">
            <Button
              variant="secondary"
              disabled={disabled}
              onClick={() => downloadWithToken(csvDownloadUrl(fileId!))}
            >
              <FileSpreadsheet className="h-4 w-4" /> Download CSV
            </Button>
            <Button
              variant="secondary"
              disabled={disabled}
              onClick={() => downloadWithToken(jsonDownloadUrl(fileId!))}
            >
              <FileJson className="h-4 w-4" /> Download JSON
            </Button>
          </CardBody>
        </Card>

        <Card>
          <CardHeader
            title="Push to tracker"
            description="One-click export to Jira or Trello."
            action={
              <div className="flex gap-1.5">
                <Badge tone={jiraConnected ? "success" : "muted"}>
                  Jira {jiraConnected ? "on" : "off"}
                </Badge>
                <Badge tone={trelloConnected ? "success" : "muted"}>
                  Trello {trelloConnected ? "on" : "off"}
                </Badge>
              </div>
            }
          />
          <CardBody className="space-y-3">
            <Button
              disabled={disabled || !jiraConnected}
              loading={jiraMut.isPending}
              onClick={() => jiraMut.mutate()}
            >
              <Download className="h-4 w-4" /> Push to Jira
            </Button>
            <Button
              disabled={disabled || !trelloConnected}
              loading={trelloMut.isPending}
              onClick={() => trelloMut.mutate()}
            >
              <Kanban className="h-4 w-4" /> Push to Trello
            </Button>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}

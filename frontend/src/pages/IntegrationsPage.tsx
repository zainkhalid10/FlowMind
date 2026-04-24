import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Save } from "lucide-react";
import { Card, CardBody, CardHeader } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import {
  extractApiError,
  fetchIntegrationConfig,
  saveIntegrationConfig,
  type IntegrationConfig,
} from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";

const JIRA_FIELDS = [
  { key: "jira_url", label: "Jira URL", hint: "https://your-workspace.atlassian.net" },
  { key: "jira_email", label: "Jira email" },
  { key: "jira_token", label: "API token", type: "password" },
  { key: "jira_project_key", label: "Project key", hint: "e.g. PROJ" },
  { key: "jira_issue_type", label: "Issue type", hint: "e.g. Task" },
] as const;

const TRELLO_FIELDS = [
  { key: "trello_key", label: "Trello API key" },
  { key: "trello_token", label: "Trello token", type: "password" },
  { key: "trello_board_id", label: "Board ID" },
  { key: "trello_list_id", label: "List ID" },
] as const;

function useFields(initial: Record<string, string> | null | undefined) {
  const [state, setState] = useState<Record<string, string>>({});
  useEffect(() => {
    setState(initial ?? {});
  }, [initial]);
  return [state, setState] as const;
}

export default function IntegrationsPage() {
  const qc = useQueryClient();
  const toast = useToast();
  const configQ = useQuery({
    queryKey: ["integration-config"],
    queryFn: fetchIntegrationConfig,
  });

  const [jira, setJira] = useFields(configQ.data?.jira);
  const [trello, setTrello] = useFields(configQ.data?.trello);

  const saveMut = useMutation({
    mutationFn: (body: IntegrationConfig) => saveIntegrationConfig(body),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ["integration-config"] });
      toast.success(
        "jira" in (vars ?? {}) ? "Jira settings saved" : "Trello settings saved",
      );
    },
    onError: (err) => toast.error("Save failed", extractApiError(err)),
  });

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">
          Integrations
        </h1>
        <p className="mt-1 text-sm text-slate-500">
          Connect Jira and Trello so approved requirements can be pushed
          directly from the Export page.
        </p>
      </header>

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader title="Jira" description="Atlassian Cloud credentials" />
          <CardBody className="space-y-3">
            {JIRA_FIELDS.map((f) => (
              <Input
                key={f.key}
                label={f.label}
                type={"type" in f ? (f.type as "password") : undefined}
                hint={"hint" in f ? (f.hint as string) : undefined}
                value={jira[f.key] ?? ""}
                onChange={(e) =>
                  setJira((prev) => ({ ...prev, [f.key]: e.target.value }))
                }
              />
            ))}
            <div className="flex justify-end">
              <Button
                onClick={() => saveMut.mutate({ jira })}
                loading={saveMut.isPending && "jira" in (saveMut.variables ?? {})}
              >
                <Save className="h-4 w-4" /> Save Jira
              </Button>
            </div>
          </CardBody>
        </Card>

        <Card>
          <CardHeader title="Trello" description="Trello API credentials" />
          <CardBody className="space-y-3">
            {TRELLO_FIELDS.map((f) => (
              <Input
                key={f.key}
                label={f.label}
                type={"type" in f ? (f.type as "password") : undefined}
                value={trello[f.key] ?? ""}
                onChange={(e) =>
                  setTrello((prev) => ({ ...prev, [f.key]: e.target.value }))
                }
              />
            ))}
            <div className="flex justify-end">
              <Button
                onClick={() => saveMut.mutate({ trello })}
                loading={
                  saveMut.isPending && "trello" in (saveMut.variables ?? {})
                }
              >
                <Save className="h-4 w-4" /> Save Trello
              </Button>
            </div>
          </CardBody>
        </Card>
      </div>

    </div>
  );
}

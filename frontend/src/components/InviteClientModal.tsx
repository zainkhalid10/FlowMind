import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Check,
  Copy,
  KeyRound,
  Mail,
  MailCheck,
  Send,
  UserPlus,
} from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import {
  extractApiError,
  fetchMyUploads,
  inviteClient,
  type InviteClientResponse,
} from "@/lib/api";
import { useToast } from "@/contexts/ToastContext";

interface Props {
  open: boolean;
  onClose: () => void;
  /** Pre-select a document when invoked from a doc row. */
  initialFileId?: number;
}

function CopyInput({
  value,
  label,
  isSecret,
}: {
  value: string;
  label: string;
  isSecret?: boolean;
}) {
  const [copied, setCopied] = useState(false);
  const [reveal, setReveal] = useState(!isSecret);
  const display = !isSecret || reveal ? value : "•".repeat(Math.min(16, value.length));
  return (
    <div>
      <label className="field-label">{label}</label>
      <div className="mt-1 flex gap-2">
        <input
          readOnly
          value={display}
          onClick={(e) => (e.target as HTMLInputElement).select()}
          className="w-full rounded-lg border border-slate-300 bg-slate-50 px-3 py-2 font-mono text-xs text-slate-800"
        />
        {isSecret && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setReveal((v) => !v)}
          >
            {reveal ? "Hide" : "Show"}
          </Button>
        )}
        <Button
          variant="secondary"
          size="sm"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(value);
              setCopied(true);
              window.setTimeout(() => setCopied(false), 1500);
            } catch {
              // clipboard blocked — ignore
            }
          }}
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5" /> Copied
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" /> Copy
            </>
          )}
        </Button>
      </div>
    </div>
  );
}

export function InviteClientModal({ open, onClose, initialFileId }: Props) {
  const qc = useQueryClient();
  const toast = useToast();

  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [dueDate, setDueDate] = useState("");
  const [fileId, setFileId] = useState<number | undefined>(initialFileId);
  const [result, setResult] = useState<InviteClientResponse | null>(null);

  const uploadsQ = useQuery({
    queryKey: ["my-uploads"],
    queryFn: fetchMyUploads,
    enabled: open,
  });

  const inviteMut = useMutation({
    mutationFn: () =>
      inviteClient({
        email,
        name: name || undefined,
        file_id: fileId,
        due_date: dueDate || undefined,
      }),
    onSuccess: (res) => {
      setResult(res);
      qc.invalidateQueries({ queryKey: ["manager-clients"] });
      qc.invalidateQueries({ queryKey: ["dashboard-stats"] });
      if (res.email_delivery_enabled) {
        toast.success("Invitation email sent", res.client.email);
      } else {
        toast.info(
          "Client created — send credentials manually",
          "Email delivery isn't configured (add MAIL_EMAIL + MAIL_PASSWORD to .env).",
        );
      }
    },
    onError: (err) => toast.error("Invite failed", extractApiError(err)),
  });

  const submit = (e: FormEvent) => {
    e.preventDefault();
    inviteMut.mutate();
  };

  const close = () => {
    setResult(null);
    setEmail("");
    setName("");
    setDueDate("");
    setFileId(initialFileId);
    onClose();
  };

  const docs = useMemo(() => uploadsQ.data?.uploads ?? [], [uploadsQ.data]);

  const sendViaSlack = async () => {
    if (!result?.invite_link) return;
    const message =
      `FlowMind invitation for *${result.client.username}* (${result.client.email})\n` +
      `Temporary password: \`${result.temp_password}\`\n` +
      `Invite link: ${result.invite_link}`;
    try {
      await navigator.clipboard.writeText(message);
      toast.success(
        "Slack message copied",
        "Paste it in your Slack channel or DM to the client.",
      );
    } catch {
      toast.info(
        "Clipboard blocked",
        "Manually copy the invite link and temp password from this dialog.",
      );
    }
  };

  return (
    <Modal
      open={open}
      onClose={close}
      size="lg"
      title={result ? "Client invited" : "Invite a client"}
      description={
        result
          ? "Share these credentials with your client — they're valid until a new invite is issued."
          : "Create a client account, bind it to a document, and send an invitation."
      }
      footer={
        result ? (
          <>
            <Button variant="secondary" onClick={sendViaSlack}>
              <Send className="h-4 w-4" /> Copy Slack message
            </Button>
            <Button onClick={close}>Done</Button>
          </>
        ) : (
          <>
            <Button variant="secondary" onClick={close}>
              Cancel
            </Button>
            <Button
              type="submit"
              form="invite-client-form"
              loading={inviteMut.isPending}
              disabled={!email}
            >
              <UserPlus className="h-4 w-4" /> Create invite
            </Button>
          </>
        )
      }
    >
      {result ? (
        <div className="space-y-4">
          <div className="flex items-start gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
            <MailCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-600" />
            <div className="text-sm">
              <p className="font-medium text-emerald-900">
                Client account ready for {result.client.email}
              </p>
              <p className="text-emerald-800/80">
                {result.email_delivery_enabled
                  ? "An invitation email with the login link has been sent automatically."
                  : "Email delivery is OFF. Share the credentials below via Slack / your own email."}
              </p>
            </div>
          </div>

          {!result.email_delivery_enabled && (
            <div className="flex items-start gap-3 rounded-md border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
              <div>
                <p className="font-medium">
                  {result.email_warning || "Email delivery isn't configured."}
                </p>
                <p className="mt-0.5 text-amber-700/90">
                  Add <code className="font-mono">MAIL_EMAIL</code> and{" "}
                  <code className="font-mono">MAIL_PASSWORD</code> (Gmail
                  App Password, 16 chars) to{" "}
                  <code className="font-mono">.env</code> and restart the
                  backend to enable automatic emails.
                </p>
              </div>
            </div>
          )}

          <CopyInput label="Client email" value={result.client.email} />
          <CopyInput
            label="Temporary password"
            value={result.temp_password}
            isSecret
          />
          {result.invite_link && (
            <CopyInput label="One-click invite link" value={result.invite_link} />
          )}

          <div className="rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
            <p className="mb-1 font-medium text-slate-700">
              What the client can do after signing in
            </p>
            <ul className="list-disc space-y-0.5 pl-4">
              <li>See only the requirements you assigned to them</li>
              <li>Approve, reject, or request a modification per requirement</li>
              <li>Use the AI to suggest better wording on modifications</li>
              <li>Submit the full review when finished — you'll see it under Manager feedback</li>
            </ul>
          </div>
        </div>
      ) : (
        <form id="invite-client-form" onSubmit={submit} className="space-y-3">
          <Input
            label="Client email"
            type="email"
            required
            placeholder="client@company.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            autoComplete="off"
          />
          <Input
            label="Client name (optional)"
            placeholder="Jane Doe"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoComplete="off"
          />
          <Select
            label="Attach to document (optional but recommended)"
            value={fileId ?? ""}
            onChange={(e) =>
              setFileId(e.target.value ? Number(e.target.value) : undefined)
            }
          >
            <option value="">— no specific document —</option>
            {docs.map((u) => (
              <option key={u.id} value={u.id}>
                {u.filename}
              </option>
            ))}
          </Select>
          <Input
            label="Review deadline (optional)"
            type="date"
            value={dueDate}
            onChange={(e) => setDueDate(e.target.value)}
          />

          <div className="flex items-start gap-2 rounded-md border border-sky-200 bg-sky-50 px-3 py-2.5 text-xs text-sky-800">
            <KeyRound className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium">
                A secure 14-character password is auto-generated.
              </p>
              <p className="mt-0.5 text-sky-700/90">
                It's shown once on the next screen. The client can't sign up —
                they can only log in with this email + password combination.
              </p>
            </div>
          </div>

          <div className="flex items-start gap-2 rounded-md border border-slate-200 bg-slate-50 px-3 py-2.5 text-xs text-slate-600">
            <Mail className="mt-0.5 h-4 w-4 shrink-0" />
            <div>
              <p className="font-medium text-slate-700">
                Email delivery (optional)
              </p>
              <p className="mt-0.5">
                If Gmail SMTP is configured in <code>.env</code>, the invite
                email sends automatically. Otherwise you'll copy the
                credentials + link and deliver them via Slack or your own mail
                client after creation.
              </p>
            </div>
          </div>

          {inviteMut.isError && (
            <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
              {extractApiError(inviteMut.error)}
            </div>
          )}
        </form>
      )}
    </Modal>
  );
}

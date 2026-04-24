import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Check,
  Copy,
  MessageCircle,
  Phone,
  Send,
} from "lucide-react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Badge } from "@/components/ui/Badge";
import { Textarea } from "@/components/ui/Textarea";
import {
  buildWhatsappShareUrl,
  documentSummaryMessage,
  openWhatsapp,
} from "@/lib/whatsapp";
import { fetchFeatures, fetchMyUploads } from "@/lib/api";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/contexts/ToastContext";

interface Props {
  open: boolean;
  onClose: () => void;
  fileId: number | null;
}

/**
 * "Send summary via WhatsApp" dialog.
 * Fetches feature counts for the selected document, composes a formatted
 * WhatsApp message, and lets the manager either (a) open WhatsApp with the
 * text pre-filled for any recipient, or (b) copy the message to clipboard.
 */
export function SendSummaryModal({ open, onClose, fileId }: Props) {
  const { user } = useAuth();
  const toast = useToast();
  const [phone, setPhone] = useState("");
  const [edited, setEdited] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const uploadsQ = useQuery({
    queryKey: ["my-uploads"],
    queryFn: fetchMyUploads,
    enabled: open,
  });
  const featuresQ = useQuery({
    queryKey: ["features", { file_id: fileId }],
    queryFn: () => fetchFeatures({ file_id: fileId ?? undefined }),
    enabled: open && fileId != null,
  });

  const doc = useMemo(() => {
    return (uploadsQ.data?.uploads ?? []).find((u) => u.id === fileId);
  }, [uploadsQ.data, fileId]);

  const counts = useMemo(() => {
    const list = featuresQ.data?.features ?? [];
    let functional = 0,
      nonFunctional = 0,
      business = 0,
      system = 0;
    for (const f of list) {
      const c = (f.category || "").toLowerCase();
      if (c === "functional") functional++;
      else if (c === "non-functional" || c === "non_functional") nonFunctional++;
      else if (c === "business") business++;
      else if (c === "system") system++;
    }
    return {
      total: list.length,
      functional,
      nonFunctional,
      business,
      system,
    };
  }, [featuresQ.data]);

  const autoMessage = useMemo(() => {
    if (!doc) return "";
    const reviewUrl = `${window.location.origin}/client-review?file_id=${doc.id}`;
    return documentSummaryMessage({
      filename: doc.filename,
      totalRequirements: counts.total,
      functional: counts.functional,
      nonFunctional: counts.nonFunctional,
      business: counts.business,
      system: counts.system,
      reviewUrl,
      managerName: user?.username,
    });
  }, [doc, counts, user]);

  const message = edited ?? autoMessage;

  const sendViaWhatsapp = () => {
    if (!message.trim()) return;
    const url = buildWhatsappShareUrl({ message, phone });
    openWhatsapp(url);
    toast.success(
      "Opening WhatsApp",
      phone
        ? `Message ready for +${phone.replace(/^\+/, "")}.`
        : "Pick a recipient in the WhatsApp window.",
    );
  };

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(message);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      toast.error(
        "Clipboard blocked",
        "Select the text and copy manually.",
      );
    }
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      size="lg"
      title={
        <span className="flex items-center gap-2">
          <MessageCircle className="h-4 w-4 text-[#25D366]" />
          Send summary via WhatsApp
        </span>
      }
      description={
        doc
          ? `Pre-filled message for "${doc.filename}" — edit before sending, or just hit WhatsApp and pick a recipient.`
          : "Pick a document from the dashboard first."
      }
      footer={
        <>
          <Button variant="secondary" onClick={copy}>
            {copied ? (
              <>
                <Check className="h-3.5 w-3.5" /> Copied
              </>
            ) : (
              <>
                <Copy className="h-3.5 w-3.5" /> Copy message
              </>
            )}
          </Button>
          <Button
            onClick={sendViaWhatsapp}
            className="bg-[#25D366] text-white hover:bg-[#1FBA57]"
          >
            <Send className="h-3.5 w-3.5" /> Open WhatsApp
          </Button>
        </>
      }
    >
      {!doc ? (
        <p className="text-sm text-slate-500">Select a document first.</p>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
            <StatPill label="Total" value={counts.total} tone="muted" />
            <StatPill label="Functional" value={counts.functional} tone="brand" />
            <StatPill
              label="Non-functional"
              value={counts.nonFunctional}
              tone="info"
            />
            <StatPill
              label="Business"
              value={counts.business}
              tone="warning"
            />
            <StatPill label="System" value={counts.system} tone="muted" />
          </div>

          <Input
            label="Recipient phone (optional — include country code, digits only)"
            type="tel"
            placeholder="e.g. 12345678901"
            value={phone}
            onChange={(e) => setPhone(e.target.value.replace(/[^\d]/g, ""))}
            hint="Leave blank and WhatsApp will let you pick a contact."
          />

          <Textarea
            label="Message"
            rows={10}
            value={message}
            onChange={(e) => setEdited(e.target.value)}
            className="font-mono text-xs"
          />

          <div className="flex items-start gap-2 rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-800">
            <Phone className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <p>
              This opens WhatsApp Web on desktop or the native app on mobile.
              No data is sent to WhatsApp's servers until you actually tap
              Send in the WhatsApp window.
            </p>
          </div>
        </div>
      )}
    </Modal>
  );
}

function StatPill({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "brand" | "info" | "warning" | "muted";
}) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white px-2 py-1.5">
      <Badge tone={tone} className="mb-0.5">
        {label}
      </Badge>
      <p className="text-lg font-semibold tabular-nums text-slate-900">{value}</p>
    </div>
  );
}

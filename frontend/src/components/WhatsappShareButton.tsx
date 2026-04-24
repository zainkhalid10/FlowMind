import { MessageCircle } from "lucide-react";
import { Button } from "@/components/ui/Button";
import {
  buildWhatsappShareUrl,
  openWhatsapp,
  shareFlowMindMessage,
} from "@/lib/whatsapp";
import { cn } from "@/lib/cn";

interface WhatsappShareButtonProps {
  /** Override the default share message. */
  message?: string;
  /** Button label. */
  label?: string;
  /** Size of the button. */
  size?: "sm" | "md" | "lg";
  /** Visual variant. */
  variant?: "filled" | "outline" | "ghost";
  className?: string;
}

/**
 * Opens WhatsApp (Web or native) with a pre-filled marketing message about
 * FlowMind. The user then picks who to send it to. Works without any
 * WhatsApp Business API credentials.
 */
export function WhatsappShareButton({
  message,
  label = "Share on WhatsApp",
  size = "md",
  variant = "filled",
  className,
}: WhatsappShareButtonProps) {
  const handle = () => {
    const url = buildWhatsappShareUrl({
      message: message || shareFlowMindMessage(window.location.origin),
    });
    openWhatsapp(url);
  };

  if (variant === "filled") {
    return (
      <Button
        size={size}
        onClick={handle}
        className={cn(
          "bg-[#25D366] text-white hover:bg-[#1FBA57] focus-visible:ring-[#25D366]",
          className,
        )}
      >
        <MessageCircle className="h-4 w-4" />
        {label}
      </Button>
    );
  }

  if (variant === "outline") {
    return (
      <Button
        size={size}
        variant="secondary"
        onClick={handle}
        className={cn(
          "border-[#25D366]/40 text-[#128C7E] hover:bg-[#25D366]/10",
          className,
        )}
      >
        <MessageCircle className="h-4 w-4" />
        {label}
      </Button>
    );
  }

  return (
    <Button size={size} variant="ghost" onClick={handle} className={className}>
      <MessageCircle className="h-4 w-4 text-[#25D366]" />
      {label}
    </Button>
  );
}

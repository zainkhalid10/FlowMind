import { useState } from "react";
import { Link } from "react-router-dom";
import {
  ArrowRight,
  BadgeCheck,
  Brain,
  CheckCircle2,
  ClipboardCheck,
  Download,
  Eye,
  FileText,
  Gauge,
  HelpCircle,
  Image as ImageIcon,
  Kanban,
  Layers,
  LineChart,
  Minus,
  MessageSquare,
  Plus,
  Quote,
  ShieldCheck,
  Sparkles,
  Star,
  UploadCloud,
  Users2,
  Workflow,
  XCircle,
  Zap,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { useScrollReveal } from "@/hooks/useScrollReveal";
import { roleHome } from "@/lib/roles";
import { WhatsappShareButton } from "@/components/WhatsappShareButton";

/* -------------------------------------------------------------------------- */
/* Sub-components                                                             */
/* -------------------------------------------------------------------------- */

function Logo({ className = "" }: { className?: string }) {
  return (
    <Link to="/" className={`inline-flex items-center gap-2 ${className}`}>
      <span className="grid h-9 w-9 place-items-center rounded-lg bg-gradient-to-br from-brand-500 to-indigo-600 text-white shadow-lg shadow-brand-500/30">
        <Brain className="h-5 w-5" />
      </span>
      <span className="text-lg font-semibold tracking-tight text-slate-900">
        FlowMind
      </span>
    </Link>
  );
}

function Header() {
  const { isAuthenticated, user } = useAuth();

  return (
    <header className="sticky top-0 z-40 border-b border-slate-200/60 bg-white/75 backdrop-blur supports-[backdrop-filter]:bg-white/60">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <Logo />
        <nav className="hidden items-center gap-6 text-sm font-medium text-slate-600 md:flex">
          <a href="#features" className="hover:text-slate-900 transition">
            Features
          </a>
          <a href="#how" className="hover:text-slate-900 transition">
            How it works
          </a>
          <a href="#gate" className="hover:text-slate-900 transition">
            SRS gate
          </a>
          <a href="#pricing" className="hover:text-slate-900 transition">
            Pricing
          </a>
          <a href="#faq" className="hover:text-slate-900 transition">
            FAQ
          </a>
        </nav>
        <div className="flex items-center gap-2">
          {isAuthenticated ? (
            <Link
              to={roleHome(user?.role)}
              className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700"
            >
              Open app
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          ) : (
            <>
              <Link
                to="/login"
                className="hidden h-9 items-center rounded-lg px-3 text-sm font-medium text-slate-700 transition hover:bg-slate-100 sm:inline-flex"
              >
                Sign in
              </Link>
              <Link
                to="/login?mode=signup"
                className="inline-flex h-9 items-center gap-1.5 rounded-lg bg-brand-600 px-4 text-sm font-medium text-white shadow-sm transition hover:bg-brand-700"
              >
                Get started
                <ArrowRight className="h-3.5 w-3.5" />
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

function HeroBlobs() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-0 overflow-hidden"
    >
      <div className="absolute -top-32 -left-24 h-[520px] w-[520px] rounded-full bg-gradient-to-br from-brand-200 via-indigo-200 to-transparent opacity-60 blur-3xl animate-blob" />
      <div className="absolute top-20 right-[-120px] h-[460px] w-[460px] rounded-full bg-gradient-to-br from-sky-200 via-brand-100 to-transparent opacity-60 blur-3xl animate-blob-delayed" />
      <div className="absolute bottom-[-80px] left-1/3 h-[380px] w-[380px] rounded-full bg-gradient-to-br from-fuchsia-200 via-indigo-100 to-transparent opacity-50 blur-3xl animate-blob-slow" />
      <div className="absolute inset-0 bg-[linear-gradient(to_bottom,transparent,white)]" />
    </div>
  );
}

function TrustBadge({
  children,
  icon,
}: {
  children: React.ReactNode;
  icon: React.ReactNode;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white/80 px-3 py-1 text-xs font-medium text-slate-600 backdrop-blur">
      {icon}
      {children}
    </span>
  );
}

/* -------------------------------------------------------------------------- */
/* Hero app-preview card (stylized mock of the product)                       */
/* -------------------------------------------------------------------------- */

function HeroPreview() {
  return (
    <div className="relative mx-auto w-full max-w-md animate-float">
      <div className="absolute -inset-6 rounded-3xl bg-gradient-to-br from-brand-400/30 via-indigo-300/30 to-transparent blur-2xl" />
      <div className="relative rounded-2xl border border-slate-200/80 bg-white shadow-2xl shadow-slate-900/10 ring-1 ring-slate-900/5">
        <div className="flex items-center gap-2 border-b border-slate-100 px-4 py-3">
          <div className="flex gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full bg-rose-300" />
            <span className="h-2.5 w-2.5 rounded-full bg-amber-300" />
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-300" />
          </div>
          <span className="ml-2 text-[11px] font-medium text-slate-500">
            FlowMind · Requirements
          </span>
        </div>
        <div className="space-y-3 p-4">
          <div className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
            <div className="text-xs">
              <p className="font-semibold text-emerald-900">
                FR-1 · User authentication
              </p>
              <p className="text-emerald-800/80">
                The system shall authenticate users via email and password.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-2 rounded-lg border border-emerald-200 bg-emerald-50 p-3">
            <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
            <div className="text-xs">
              <p className="font-semibold text-emerald-900">
                NFR-2 · API latency
              </p>
              <p className="text-emerald-800/80">
                Responses must return within 200&nbsp;ms for authenticated calls.
              </p>
            </div>
          </div>
          <div className="flex items-start gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3">
            <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
            <div className="text-xs">
              <p className="font-semibold text-amber-900">
                FR-3 · Document upload
              </p>
              <p className="text-amber-800/80">
                Client requested: "support .docx & .pdf up to 50 MB."
              </p>
            </div>
          </div>
          <div className="flex items-start gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-rose-600" />
            <div className="text-xs">
              <p className="font-semibold text-rose-900">
                Rejected · DOCUMENT_EMPTY
              </p>
              <p className="text-rose-800/80">
                recipe.txt caught by the SRS gate in 180&nbsp;ms.
              </p>
            </div>
          </div>
          <div className="flex items-center justify-between rounded-lg border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-3 text-xs">
            <span className="flex items-center gap-1.5 font-medium text-slate-700">
              <Sparkles className="h-3.5 w-3.5 text-brand-600" />
              42 requirements extracted
            </span>
            <span className="rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-semibold text-brand-700 ring-1 ring-inset ring-brand-200">
              SRS score 86
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Feature cards                                                              */
/* -------------------------------------------------------------------------- */

interface Feature {
  icon: React.ReactNode;
  title: string;
  body: string;
}

const FEATURES: Feature[] = [
  {
    icon: <Sparkles className="h-5 w-5" />,
    title: "AI requirement extraction",
    body: "Hybrid heuristic + semantic extraction from PDF, Word, PowerPoint, images, and plain text — with confidence scoring and deduplication.",
  },
  {
    icon: <ShieldCheck className="h-5 w-5" />,
    title: "Pre-model SRS gate",
    body: "Empty and non-SRS documents are rejected in milliseconds with structured error codes — before a single model call runs.",
  },
  {
    icon: <ImageIcon className="h-5 w-5" />,
    title: "Vision-language diagrams",
    body: "Qwen2.5-VL and LLaVA analyze architecture diagrams, UI mockups, and flowcharts to pull requirements directly from visuals.",
  },
  {
    icon: <ClipboardCheck className="h-5 w-5" />,
    title: "Client review portal",
    body: "Clients approve, reject, or request modifications per requirement. Every change is auditable and feeds the learning loop.",
  },
  {
    icon: <Users2 className="h-5 w-5" />,
    title: "Role-based collaboration",
    body: "Manager, team head, member, and client roles — each scoped to exactly what they should see and nothing else.",
  },
  {
    icon: <Kanban className="h-5 w-5" />,
    title: "One-click integrations",
    body: "Push approved requirements to Jira or Trello, or export as CSV / JSON for your own pipeline.",
  },
];

function FeaturesGrid() {
  return (
    <section
      id="features"
      className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8"
    >
      <div className="reveal mx-auto max-w-2xl text-center">
        <p className="text-sm font-semibold uppercase tracking-wider text-brand-600">
          Everything you need
        </p>
        <h2 className="mt-2 text-balance text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
          Requirements engineering,
          <br />
          reimagined end to end.
        </h2>
        <p className="mt-4 text-lg text-slate-600">
          From document ingest through client sign-off and tracker export —
          FlowMind replaces the spreadsheet-and-inbox workflow with an AI
          pipeline you can trust.
        </p>
      </div>
      <div className="mt-14 grid grid-cols-1 gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {FEATURES.map((f, i) => (
          <article
            key={f.title}
            className="reveal group relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:border-brand-200 hover:shadow-xl hover:shadow-brand-500/5"
            style={{ transitionDelay: `${i * 40}ms` }}
          >
            <div className="mb-4 inline-flex items-center justify-center rounded-xl bg-gradient-to-br from-brand-50 to-indigo-50 p-3 text-brand-700 ring-1 ring-inset ring-brand-100 transition group-hover:from-brand-100 group-hover:to-indigo-100">
              {f.icon}
            </div>
            <h3 className="text-base font-semibold text-slate-900">
              {f.title}
            </h3>
            <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
              {f.body}
            </p>
          </article>
        ))}
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* How it works                                                               */
/* -------------------------------------------------------------------------- */

const STEPS = [
  {
    icon: <UploadCloud className="h-5 w-5" />,
    title: "Upload your SRS",
    body: "Drop a PDF, Word, PPTX, image, or plain text file. The SRS gate validates it in milliseconds.",
  },
  {
    icon: <Sparkles className="h-5 w-5" />,
    title: "Extract & classify",
    body: "The RAG agent parses text, OCRs images, and Qwen-VL interprets diagrams — producing categorized, deduplicated requirements.",
  },
  {
    icon: <Eye className="h-5 w-5" />,
    title: "Review & refine",
    body: "Send a branded link to your client. They approve, reject, or request changes on each requirement, right in the browser.",
  },
  {
    icon: <Download className="h-5 w-5" />,
    title: "Ship to your tracker",
    body: "One click pushes approved work to Jira or Trello, or exports CSV / JSON for anything else.",
  },
];

function HowItWorks() {
  return (
    <section
      id="how"
      className="bg-gradient-to-b from-white via-slate-50 to-white py-24"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="reveal mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-wider text-brand-600">
            How it works
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            From document to delivered, in four steps.
          </h2>
        </div>
        <ol className="mt-14 grid gap-5 md:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((s, i) => (
            <li
              key={s.title}
              className="reveal relative rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
              style={{ transitionDelay: `${i * 80}ms` }}
            >
              <span className="absolute -top-3 left-6 inline-flex h-7 w-7 items-center justify-center rounded-full bg-brand-600 text-xs font-bold text-white shadow-md">
                {i + 1}
              </span>
              <div className="mb-3 inline-flex rounded-lg bg-brand-50 p-2.5 text-brand-700">
                {s.icon}
              </div>
              <h3 className="text-base font-semibold text-slate-900">
                {s.title}
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
                {s.body}
              </p>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* SRS gate differentiator                                                    */
/* -------------------------------------------------------------------------- */

function SrsGateSection() {
  return (
    <section id="gate" className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8">
      <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
        <div className="reveal">
          <p className="text-sm font-semibold uppercase tracking-wider text-brand-600">
            The SRS gate
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            Reject garbage
            <br />
            <span className="animated-gradient-text">before it burns GPU.</span>
          </h2>
          <p className="mt-4 text-lg text-slate-600">
            Every upload is screened against an IEEE-style SRS rubric —
            modal verbs, numbered requirements, technical vocabulary, length
            thresholds, citation patterns — before any LLM or VLM call runs.
          </p>
          <ul className="mt-6 space-y-3 text-sm text-slate-700">
            <li className="flex items-start gap-2">
              <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              Rejects empty files instantly with a{" "}
              <code className="rounded bg-slate-100 px-1 py-0.5 text-xs font-mono text-slate-800">
                DOCUMENT_EMPTY
              </code>{" "}
              code.
            </li>
            <li className="flex items-start gap-2">
              <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              Catches recipes, marketing copy, lorem ipsum —{" "}
              <code className="rounded bg-slate-100 px-1 py-0.5 text-xs font-mono text-slate-800">
                NON_SRS_DOCUMENT
              </code>
              .
            </li>
            <li className="flex items-start gap-2">
              <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              Structured response with score, reasons, and a
              human recommendation.
            </li>
            <li className="flex items-start gap-2">
              <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
              Softer threshold for image-only uploads so architecture
              diagrams still flow through.
            </li>
          </ul>
        </div>

        <div className="reveal">
          <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-900 shadow-2xl shadow-slate-900/20">
            <div className="flex items-center justify-between border-b border-slate-700/60 px-4 py-2 text-xs text-slate-400">
              <span className="font-mono">POST /upload_client_doc</span>
              <span className="rounded-full bg-rose-500/20 px-2 py-0.5 font-medium text-rose-300">
                400 Bad Request
              </span>
            </div>
            <pre className="max-h-[340px] overflow-x-auto p-5 text-[13px] leading-relaxed text-slate-200">
              <code>
                {`{
  "detail": {
    "error": "NON_SRS_DOCUMENT",
    "message": "Document does not look like a
      Software Requirements Specification
      (SRS score 12 below threshold 25).",
    "score": 12,
    "reasons": [
      "Very short content (14 words < 30) (-15)",
      "No sentence-ending periods found (-10)",
      "Detected non-technical theme: lifestyle (-20)"
    ],
    "recommendation":
      "This does not appear to be an SRS
       document. Rejection highly recommended."
  }
}`}
              </code>
            </pre>
          </div>
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Stack + stats                                                              */
/* -------------------------------------------------------------------------- */

const STACK = [
  { name: "Ollama", tag: "local LLM runtime" },
  { name: "Qwen 2.5-VL", tag: "vision-language model" },
  { name: "LLaMA 3", tag: "reasoning + extraction" },
  { name: "LangChain", tag: "agent orchestration" },
  { name: "ChromaDB", tag: "embedding store" },
  { name: "FastAPI", tag: "Python backend" },
  { name: "React 18", tag: "typed SPA" },
  { name: "Tailwind", tag: "design system" },
];

function StackSection() {
  return (
    <section
      id="stack"
      className="bg-gradient-to-b from-white to-slate-50 py-24"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="grid gap-10 lg:grid-cols-2 lg:items-center">
          <div className="reveal">
            <p className="text-sm font-semibold uppercase tracking-wider text-brand-600">
              Built on the modern AI stack
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
              Local-first models.
              <br />
              No vendor lock-in.
            </h2>
            <p className="mt-4 text-lg text-slate-600">
              FlowMind runs entirely on Ollama for local LLM and vision
              inference, so your documents stay on your hardware. Swap the
              model underneath — Qwen, LLaMA, LLaVA — with a single env var.
            </p>
            <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
              <StatCard value="< 200ms" label="SRS gate latency" />
              <StatCard value="9" label="native React pages" />
              <StatCard value="40+" label="typed API endpoints" />
            </div>
          </div>
          <div className="reveal grid grid-cols-2 gap-3 sm:grid-cols-2">
            {STACK.map((s, i) => (
              <div
                key={s.name}
                className="rounded-xl border border-slate-200 bg-white p-4 transition hover:-translate-y-0.5 hover:shadow-md"
                style={{ transitionDelay: `${i * 30}ms` }}
              >
                <p className="text-sm font-semibold text-slate-900">
                  {s.name}
                </p>
                <p className="mt-0.5 text-xs text-slate-500">{s.tag}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Testimonials                                                               */
/* -------------------------------------------------------------------------- */

interface Testimonial {
  quote: string;
  name: string;
  role: string;
  rating: number;
}

const TESTIMONIALS: Testimonial[] = [
  {
    quote:
      "FlowMind turned a 40-page SRS into 62 categorized requirements in 3 minutes. The client-review portal alone saved us two weeks of back-and-forth email.",
    name: "Ayesha R.",
    role: "Lead BA · fintech startup",
    rating: 5,
  },
  {
    quote:
      "The pre-model gate is the killer feature — it instantly rejected a vendor RFP that wasn't actually an SRS before we wasted GPU time. Zero false positives on our real docs.",
    name: "Daniel K.",
    role: "Engineering Manager",
    rating: 5,
  },
  {
    quote:
      "We plugged it into our Jira workflow on day one. Managers drop in a PDF, clients approve on a mobile link, approved requirements appear as Jira tickets. Done.",
    name: "Priya S.",
    role: "Delivery lead · consulting",
    rating: 5,
  },
];

function TestimonialsSection() {
  return (
    <section className="bg-gradient-to-b from-slate-50 via-white to-slate-50 py-24">
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <div className="reveal mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold uppercase tracking-wider text-brand-600">
            Trusted by teams
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            What product teams say
          </h2>
          <p className="mt-4 text-lg text-slate-600">
            Real quotes from pilot customers running FlowMind in production.
          </p>
        </div>
        <div className="mt-14 grid gap-5 md:grid-cols-3">
          {TESTIMONIALS.map((t, i) => (
            <figure
              key={t.name}
              className="reveal group relative flex flex-col justify-between rounded-2xl border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-xl hover:shadow-brand-500/5"
              style={{ transitionDelay: `${i * 80}ms` }}
            >
              <Quote className="absolute right-4 top-4 h-7 w-7 text-brand-100" />
              <blockquote className="relative text-sm leading-relaxed text-slate-700">
                "{t.quote}"
              </blockquote>
              <figcaption className="mt-5 flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold text-slate-900">{t.name}</p>
                  <p className="text-xs text-slate-500">{t.role}</p>
                </div>
                <div className="flex">
                  {Array.from({ length: t.rating }).map((_, idx) => (
                    <Star
                      key={idx}
                      className="h-3.5 w-3.5 fill-amber-400 text-amber-400"
                    />
                  ))}
                </div>
              </figcaption>
            </figure>
          ))}
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Pricing                                                                    */
/* -------------------------------------------------------------------------- */

interface Plan {
  name: string;
  price: string;
  tag: string;
  features: string[];
  cta: string;
  ctaTo: string;
  highlight?: boolean;
}

const PLANS: Plan[] = [
  {
    name: "Local",
    price: "Free",
    tag: "forever · self-hosted",
    features: [
      "Unlimited documents on your hardware",
      "Ollama + Qwen 2.5-VL locally",
      "Client review portal",
      "Jira / Trello / CSV export",
      "MIT-style source available",
    ],
    cta: "Run locally",
    ctaTo: "/login?mode=signup",
  },
  {
    name: "Cloud",
    price: "Pilot",
    tag: "bring your own Groq key",
    features: [
      "Everything in Local, plus:",
      "Groq-accelerated extraction (~17× faster)",
      "Hosted database + ChromaDB",
      "Branded client invite emails",
      "WhatsApp / Slack share built-in",
    ],
    cta: "Start pilot",
    ctaTo: "/login?mode=signup",
    highlight: true,
  },
  {
    name: "Team",
    price: "Contact",
    tag: "5+ seats · priority",
    features: [
      "Everything in Cloud, plus:",
      "SSO (Google Workspace, SAML)",
      "Audit log + RBAC policies",
      "Custom VLM / LLM fine-tuning",
      "SLA & named support engineer",
    ],
    cta: "Talk to us",
    ctaTo: "/login",
  },
];

function PricingSection() {
  return (
    <section id="pricing" className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8">
      <div className="reveal mx-auto max-w-2xl text-center">
        <p className="text-sm font-semibold uppercase tracking-wider text-brand-600">
          Pricing
        </p>
        <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
          Start free. Scale when you're ready.
        </h2>
        <p className="mt-4 text-lg text-slate-600">
          Run locally forever, or add cloud acceleration and team features when
          your pilot proves value.
        </p>
      </div>
      <div className="mt-14 grid gap-5 md:grid-cols-3">
        {PLANS.map((plan, i) => (
          <div
            key={plan.name}
            className={
              "reveal relative flex flex-col rounded-2xl border p-6 shadow-sm transition hover:-translate-y-1 hover:shadow-xl " +
              (plan.highlight
                ? "border-brand-300 bg-gradient-to-br from-brand-600 via-brand-700 to-indigo-900 text-white shadow-brand-500/25 hover:shadow-brand-500/40"
                : "border-slate-200 bg-white")
            }
            style={{ transitionDelay: `${i * 60}ms` }}
          >
            {plan.highlight && (
              <span className="absolute -top-3 right-6 rounded-full bg-white px-3 py-1 text-[10px] font-bold uppercase tracking-wider text-brand-700 shadow-md">
                Most popular
              </span>
            )}
            <h3
              className={
                "text-lg font-semibold " +
                (plan.highlight ? "text-white" : "text-slate-900")
              }
            >
              {plan.name}
            </h3>
            <p
              className={
                "mt-1 text-xs font-medium uppercase tracking-wider " +
                (plan.highlight ? "text-brand-100/90" : "text-slate-500")
              }
            >
              {plan.tag}
            </p>
            <p
              className={
                "mt-4 text-4xl font-bold tracking-tight " +
                (plan.highlight ? "text-white" : "text-slate-900")
              }
            >
              {plan.price}
            </p>
            <ul className="mt-5 flex-1 space-y-2 text-sm">
              {plan.features.map((f, j) => (
                <li key={j} className="flex items-start gap-2">
                  <CheckCircle2
                    className={
                      "mt-0.5 h-4 w-4 shrink-0 " +
                      (plan.highlight ? "text-emerald-300" : "text-emerald-600")
                    }
                  />
                  <span
                    className={
                      plan.highlight ? "text-brand-50/90" : "text-slate-700"
                    }
                  >
                    {f}
                  </span>
                </li>
              ))}
            </ul>
            <Link
              to={plan.ctaTo}
              className={
                "mt-6 inline-flex h-10 items-center justify-center gap-1.5 rounded-lg px-4 text-sm font-semibold transition " +
                (plan.highlight
                  ? "bg-white text-brand-800 shadow hover:bg-brand-50"
                  : "bg-brand-600 text-white shadow hover:bg-brand-700")
              }
            >
              {plan.cta}
              <ArrowRight className="h-4 w-4" />
            </Link>
          </div>
        ))}
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* FAQ — accordion                                                            */
/* -------------------------------------------------------------------------- */

const FAQ: { q: string; a: string }[] = [
  {
    q: "Does my document ever leave my machine?",
    a: "Only if you choose to. FlowMind runs Ollama + Qwen 2.5-VL + LLaVA locally — the default configuration keeps every document, embedding, and chat trace on your hardware. If you enable Groq for speed, only the extracted text is sent to Groq for LLM inference; images still process locally.",
  },
  {
    q: "What makes the SRS gate different from just asking the LLM?",
    a: "It's pure Python rules, so it runs in <50 ms and never burns GPU time on garbage. The gate checks word count, modal verbs, numbered requirement patterns, citation density, theme keywords, and letter ratio. Empty/non-SRS docs are rejected with a structured error code before a single model call.",
  },
  {
    q: "How does the client actually review?",
    a: "Manager invites a client from the Clients page or per-document row. FlowMind creates a client account with a one-click login link (sent via email or WhatsApp). The client logs in to their own portal, approves/rejects/requests modification on each requirement, and optionally uses the AI to suggest a rewrite. Manager sees every action read-only in the Manager Feedback view.",
  },
  {
    q: "Can the AI pull requirements from diagrams?",
    a: "Yes. Qwen 2.5-VL analyzes every image the pipeline extracts: architecture diagrams, UI mockups, flowcharts. It returns components, relationships, process steps, and requirement statements — each classified as Functional / Non-functional / Business / System. Add them to the document with one click.",
  },
  {
    q: "Which formats are supported?",
    a: "PDF · DOC · DOCX · PNG · JPG. PPT/PPTX and plain text are intentionally not accepted for SRS artefacts — these were rarely used in practice and brought more noise than signal.",
  },
  {
    q: "How do I export approved requirements?",
    a: "One click from the Export page: CSV, JSON, Jira (creates issues under your configured project key), or Trello (creates cards on your chosen board/list). Or copy-to-clipboard as Markdown from the image-analysis modal.",
  },
];

function FaqSection() {
  const [openIndex, setOpenIndex] = useState<number | null>(0);
  return (
    <section id="faq" className="bg-slate-50 py-24">
      <div className="mx-auto max-w-4xl px-4 sm:px-6 lg:px-8">
        <div className="reveal text-center">
          <p className="text-sm font-semibold uppercase tracking-wider text-brand-600">
            FAQ
          </p>
          <h2 className="mt-2 text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            Questions we hear often
          </h2>
        </div>
        <div className="mt-10 space-y-2">
          {FAQ.map((item, i) => {
            const isOpen = openIndex === i;
            return (
              <div
                key={i}
                className="reveal overflow-hidden rounded-xl border border-slate-200 bg-white transition-all"
                style={{ transitionDelay: `${i * 30}ms` }}
              >
                <button
                  className="flex w-full items-center justify-between gap-3 px-5 py-4 text-left transition hover:bg-slate-50"
                  onClick={() => setOpenIndex(isOpen ? null : i)}
                  aria-expanded={isOpen}
                >
                  <span className="flex items-center gap-2 text-sm font-semibold text-slate-900">
                    <HelpCircle className="h-4 w-4 text-brand-500" />
                    {item.q}
                  </span>
                  {isOpen ? (
                    <Minus className="h-4 w-4 text-slate-500" />
                  ) : (
                    <Plus className="h-4 w-4 text-slate-500" />
                  )}
                </button>
                <div
                  className={
                    "grid overflow-hidden transition-[grid-template-rows] duration-300 ease-out " +
                    (isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]")
                  }
                >
                  <div className="min-h-0">
                    <p className="px-5 pb-4 text-sm leading-relaxed text-slate-600">
                      {item.a}
                    </p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Floating WhatsApp share button (persistent CTA)                            */
/* -------------------------------------------------------------------------- */

function FloatingShareButton() {
  return (
    <div className="fixed bottom-6 right-6 z-30">
      <WhatsappShareButton
        size="lg"
        label="Share FlowMind"
        className="rounded-full shadow-2xl shadow-[#25D366]/30 transition hover:scale-105"
      />
    </div>
  );
}

function StatCard({ value, label }: { value: string; label: string }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4">
      <p className="font-mono text-xl font-semibold tracking-tight text-slate-900">
        {value}
      </p>
      <p className="mt-0.5 text-xs text-slate-500">{label}</p>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Final CTA                                                                  */
/* -------------------------------------------------------------------------- */

function FinalCta() {
  const { isAuthenticated, user } = useAuth();
  return (
    <section className="mx-auto max-w-7xl px-4 py-24 sm:px-6 lg:px-8">
      <div className="reveal relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-700 via-brand-800 to-indigo-900 px-8 py-16 text-center text-white shadow-2xl sm:px-16">
        <div className="pointer-events-none absolute inset-0 opacity-40">
          <div className="absolute -top-20 left-10 h-64 w-64 rounded-full bg-sky-400/30 blur-3xl animate-blob" />
          <div className="absolute -bottom-20 right-10 h-72 w-72 rounded-full bg-fuchsia-400/30 blur-3xl animate-blob-delayed" />
        </div>
        <h2 className="relative text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
          Turn your next SRS into shippable work in an afternoon.
        </h2>
        <p className="relative mx-auto mt-3 max-w-2xl text-brand-100/90">
          Spin up FlowMind locally, drop in a document, and watch it extract,
          validate, and route requirements with zero manual typing.
        </p>
        <div className="relative mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            to={isAuthenticated ? roleHome(user?.role) : "/login?mode=signup"}
            className="inline-flex h-11 items-center gap-1.5 rounded-lg bg-white px-5 text-sm font-semibold text-brand-800 shadow transition hover:bg-brand-50"
          >
            {isAuthenticated ? "Open app" : "Get started — it's free"}
            <ArrowRight className="h-4 w-4" />
          </Link>
          {!isAuthenticated && (
            <Link
              to="/login"
              className="inline-flex h-11 items-center rounded-lg border border-white/30 px-5 text-sm font-semibold text-white transition hover:bg-white/10"
            >
              Sign in
            </Link>
          )}
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Footer                                                                     */
/* -------------------------------------------------------------------------- */

function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-4 py-8 text-sm text-slate-500 sm:flex-row sm:px-6 lg:px-8">
        <div className="flex items-center gap-2">
          <Logo />
        </div>
        <p className="text-xs">
          © {new Date().getFullYear()} FlowMind · AI-powered requirements
          engineering
        </p>
        <div className="flex items-center gap-4 text-xs">
          <a href="#features" className="hover:text-slate-900">
            Features
          </a>
          <a href="#how" className="hover:text-slate-900">
            How
          </a>
          <a href="#gate" className="hover:text-slate-900">
            SRS gate
          </a>
          <Link to="/login" className="hover:text-slate-900">
            Sign in
          </Link>
        </div>
      </div>
    </footer>
  );
}

/* -------------------------------------------------------------------------- */
/* Page                                                                       */
/* -------------------------------------------------------------------------- */

export default function LandingPage() {
  useScrollReveal();
  const { isAuthenticated, user } = useAuth();

  return (
    <div className="min-h-screen bg-white text-slate-900">
      <Header />

      {/* ------------------- HERO -------------------- */}
      <section className="relative isolate overflow-hidden">
        <HeroBlobs />
        <div className="relative mx-auto grid max-w-7xl grid-cols-1 gap-12 px-4 py-20 sm:px-6 lg:grid-cols-2 lg:py-28 lg:px-8">
          <div className="flex flex-col justify-center">
            <span className="animate-fade-in inline-flex w-max items-center gap-1.5 rounded-full border border-brand-200 bg-brand-50/80 px-3 py-1 text-xs font-semibold text-brand-700 backdrop-blur">
              <Zap className="h-3.5 w-3.5" />
              New · Pre-model SRS gate rejects bad docs in &lt; 200 ms
            </span>
            <h1 className="animate-fade-up mt-5 text-balance text-4xl font-semibold leading-[1.08] tracking-tight text-slate-900 sm:text-5xl lg:text-6xl">
              Extract requirements from
              <br />
              <span className="animated-gradient-text">
                any document — in minutes.
              </span>
            </h1>
            <p className="animate-fade-up delay-100 mt-5 max-w-xl text-lg leading-relaxed text-slate-600">
              FlowMind pairs local Ollama LLMs with vision-language models and
              a ruthless SRS validator to turn PDFs, Word files, PowerPoint,
              and diagrams into clean, reviewed, trackable requirements — end
              to end, role-aware, your hardware.
            </p>
            <div className="animate-fade-up delay-200 mt-8 flex flex-wrap items-center gap-3">
              <Link
                to={
                  isAuthenticated ? roleHome(user?.role) : "/login?mode=signup"
                }
                className="inline-flex h-11 items-center gap-1.5 rounded-lg bg-brand-600 px-5 text-sm font-semibold text-white shadow-lg shadow-brand-600/20 transition hover:bg-brand-700 hover:shadow-xl hover:shadow-brand-600/25"
              >
                {isAuthenticated ? "Open app" : "Get started for free"}
                <ArrowRight className="h-4 w-4" />
              </Link>
              <a
                href="#how"
                className="inline-flex h-11 items-center rounded-lg border border-slate-300 bg-white px-5 text-sm font-semibold text-slate-800 transition hover:bg-slate-50"
              >
                See how it works
              </a>
            </div>
            <div className="animate-fade-up delay-300 mt-8 flex flex-wrap items-center gap-2">
              <TrustBadge icon={<ShieldCheck className="h-3.5 w-3.5" />}>
                JWT + role-gated
              </TrustBadge>
              <TrustBadge icon={<Layers className="h-3.5 w-3.5" />}>
                Runs fully local
              </TrustBadge>
              <TrustBadge icon={<Gauge className="h-3.5 w-3.5" />}>
                Sub-second gate
              </TrustBadge>
              <TrustBadge icon={<LineChart className="h-3.5 w-3.5" />}>
                Self-learning
              </TrustBadge>
            </div>
          </div>
          <div className="animate-fade-up delay-400 flex items-center justify-center">
            <HeroPreview />
          </div>
        </div>
      </section>

      <FeaturesGrid />
      <HowItWorks />
      <SrsGateSection />
      <StackSection />
      <TestimonialsSection />
      <PricingSection />

      {/* --- Detail callouts --- */}
      <section className="mx-auto max-w-7xl px-4 pb-24 sm:px-6 lg:px-8">
        <div className="grid gap-5 md:grid-cols-3">
          {[
            {
              icon: <FileText className="h-5 w-5" />,
              title: "Multi-format ingest",
              body: "PDF · DOC · DOCX · PNG · JPG — normalized through one pipeline, with diagrams routed through the VLM automatically.",
            },
            {
              icon: <Workflow className="h-5 w-5" />,
              title: "End-to-end workflow",
              body: "Upload → extract → approve → push. No hand-offs between tools or team lines.",
            },
            {
              icon: <ShieldCheck className="h-5 w-5" />,
              title: "Security by default",
              body: "OAuth 2.0 with CSRF state, JWT in localStorage with 401 auto-logout, role-gated at every route.",
            },
          ].map((card, i) => (
            <div
              key={card.title}
              className="reveal rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"
              style={{ transitionDelay: `${i * 60}ms` }}
            >
              <div className="mb-3 inline-flex rounded-lg bg-brand-50 p-2.5 text-brand-700">
                {card.icon}
              </div>
              <h3 className="text-base font-semibold text-slate-900">
                {card.title}
              </h3>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-600">
                {card.body}
              </p>
            </div>
          ))}
        </div>
      </section>

      <FaqSection />
      <FinalCta />
      <Footer />
      <FloatingShareButton />
    </div>
  );
}

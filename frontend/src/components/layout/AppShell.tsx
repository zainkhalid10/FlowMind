import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  Brain,
  Briefcase,
  Download,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  PieChart,
  Plug,
  Settings,
  UploadCloud,
  Users2,
  History,
  ShieldCheck,
  MessageSquare,
  X,
} from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { cn } from "@/lib/cn";

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  roles?: string[];
}

interface NavSection {
  heading: string;
  items: NavItem[];
}

const INTERNAL_NAV_SECTIONS: NavSection[] = [
  {
    heading: "Work",
    items: [
      { to: "/dashboard", label: "Dashboard", icon: <LayoutDashboard className="h-4 w-4" /> },
      { to: "/upload", label: "Upload", icon: <UploadCloud className="h-4 w-4" /> },
      { to: "/requirements", label: "Requirements", icon: <FileText className="h-4 w-4" /> },
      { to: "/analytics", label: "Analytics", icon: <PieChart className="h-4 w-4" /> },
      { to: "/export", label: "Export", icon: <Download className="h-4 w-4" /> },
    ],
  },
  {
    heading: "Review",
    items: [
      {
        to: "/manager-feedback",
        label: "Manager feedback",
        icon: <MessageSquare className="h-4 w-4" />,
        roles: ["manager", "team_head"],
      },
    ],
  },
  {
    heading: "Admin",
    items: [
      { to: "/members", label: "Members", icon: <Users2 className="h-4 w-4" />, roles: ["manager"] },
      { to: "/clients", label: "Clients", icon: <Briefcase className="h-4 w-4" />, roles: ["manager"] },
      { to: "/integrations", label: "Integrations", icon: <Plug className="h-4 w-4" />, roles: ["manager"] },
      {
        to: "/integration-log",
        label: "Integration log",
        icon: <History className="h-4 w-4" />,
        roles: ["manager", "team_head"],
      },
    ],
  },
  {
    heading: "Account",
    items: [
      { to: "/settings", label: "Settings", icon: <Settings className="h-4 w-4" /> },
    ],
  },
];

const CLIENT_NAV_SECTIONS: NavSection[] = [
  {
    heading: "Review",
    items: [
      {
        to: "/client-review",
        label: "Review requirements",
        icon: <ShieldCheck className="h-4 w-4" />,
      },
    ],
  },
  {
    heading: "Account",
    items: [
      { to: "/settings", label: "Settings", icon: <Settings className="h-4 w-4" /> },
    ],
  },
];

function canSee(item: NavItem, role?: string | null): boolean {
  if (!item.roles || item.roles.length === 0) return true;
  if (!role) return false;
  return item.roles.includes(role);
}

function initialOf(text: string | null | undefined) {
  return (text ?? "?").slice(0, 1).toUpperCase();
}

/* -------------------- Sidebar (shared between desktop and mobile drawer) */

interface SidebarProps {
  sections: NavSection[];
  role: string | null | undefined;
  onNavItemClick?: () => void;
}

function SidebarNav({ sections, role, onNavItemClick }: SidebarProps) {
  return (
    <nav className="flex-1 space-y-4 overflow-y-auto px-3">
      {sections.map((section) => {
        const items = section.items.filter((i) => canSee(i, role));
        if (items.length === 0) return null;
        return (
          <div key={section.heading}>
            <p className="mb-1 px-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              {section.heading}
            </p>
            <div className="space-y-0.5">
              {items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={onNavItemClick}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition",
                      isActive
                        ? "bg-brand-50 text-brand-700"
                        : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
                    )
                  }
                >
                  {item.icon}
                  {item.label}
                </NavLink>
              ))}
            </div>
          </div>
        );
      })}
    </nav>
  );
}

function UserFooter({
  avatarUrl,
  username,
  email,
  role,
  onLogout,
}: {
  avatarUrl?: string | null;
  username?: string | null;
  email?: string | null;
  role?: string | null;
  onLogout: () => void;
}) {
  return (
    <div className="border-t border-slate-200 p-3">
      <div className="mb-2 flex items-start gap-2 rounded-md px-2 py-2 text-xs text-slate-500">
        {avatarUrl ? (
          <img
            src={avatarUrl}
            alt=""
            referrerPolicy="no-referrer"
            className="h-8 w-8 shrink-0 rounded-full object-cover ring-1 ring-slate-200"
          />
        ) : (
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700">
            {initialOf(username ?? email)}
          </span>
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate font-medium text-slate-800">
            {username ?? "—"}
          </p>
          <p className="truncate">{email ?? ""}</p>
          <p className="mt-1 inline-flex rounded bg-slate-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-slate-600">
            {role ?? "user"}
          </p>
        </div>
      </div>
      <button
        onClick={onLogout}
        className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
      >
        <LogOut className="h-4 w-4" />
        Log out
      </button>
    </div>
  );
}

/* -------------------- Shell -------------------------------------------- */

export function AppShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [drawerOpen, setDrawerOpen] = useState(false);

  const sections =
    user?.role === "client" ? CLIENT_NAV_SECTIONS : INTERNAL_NAV_SECTIONS;

  // Close the mobile drawer on route change — otherwise users tap a link
  // and get stuck staring at the underlay.
  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  // Close on Escape so power users can dismiss without reaching for the X.
  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setDrawerOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [drawerOpen]);

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  const logoLink = (
    <Link
      to={user?.role === "client" ? "/client-review" : "/dashboard"}
      className="flex items-center gap-2 text-slate-900"
    >
      <span className="grid h-9 w-9 place-items-center rounded-lg bg-gradient-to-br from-brand-500 to-indigo-600 text-white shadow-md shadow-brand-500/20">
        <Brain className="h-5 w-5" />
      </span>
      <span className="text-lg font-semibold tracking-tight">FlowMind</span>
    </Link>
  );

  return (
    <div className="flex min-h-screen bg-slate-50">
      {/* Desktop sidebar */}
      <aside className="hidden w-60 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
        <div className="px-5 py-5">{logoLink}</div>
        <SidebarNav sections={sections} role={user?.role} />
        <UserFooter
          avatarUrl={user?.avatar_url}
          username={user?.username}
          email={user?.email}
          role={user?.role}
          onLogout={handleLogout}
        />
      </aside>

      {/* Mobile top bar — only visible below md */}
      <div className="fixed inset-x-0 top-0 z-30 flex h-14 items-center justify-between border-b border-slate-200 bg-white/90 px-4 backdrop-blur md:hidden">
        {logoLink}
        <button
          onClick={() => setDrawerOpen(true)}
          aria-label="Open navigation"
          aria-expanded={drawerOpen}
          className="inline-flex h-9 w-9 items-center justify-center rounded-md text-slate-600 transition hover:bg-slate-100 hover:text-slate-900"
        >
          <Menu className="h-5 w-5" />
        </button>
      </div>

      {/* Mobile drawer */}
      {drawerOpen && (
        <div className="fixed inset-0 z-40 md:hidden">
          <div
            className="absolute inset-0 animate-[fade-in_0.15s_ease-out] bg-slate-900/45"
            onClick={() => setDrawerOpen(false)}
            aria-hidden="true"
          />
          <aside
            role="dialog"
            aria-modal="true"
            aria-label="Main navigation"
            className="absolute inset-y-0 left-0 flex w-72 max-w-[85%] flex-col border-r border-slate-200 bg-white shadow-2xl animate-[fade-up_0.2s_ease-out]"
          >
            <div className="flex items-center justify-between px-5 py-5">
              {logoLink}
              <button
                onClick={() => setDrawerOpen(false)}
                aria-label="Close navigation"
                className="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-500 transition hover:bg-slate-100 hover:text-slate-700"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <SidebarNav
              sections={sections}
              role={user?.role}
              onNavItemClick={() => setDrawerOpen(false)}
            />
            <UserFooter
              avatarUrl={user?.avatar_url}
              username={user?.username}
              email={user?.email}
              role={user?.role}
              onLogout={handleLogout}
            />
          </aside>
        </div>
      )}

      <main className="flex-1">
        <div className="mx-auto max-w-7xl px-4 pb-8 pt-20 sm:px-6 md:pt-8 lg:px-8">
          {children}
        </div>
      </main>
    </div>
  );
}

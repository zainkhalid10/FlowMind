import { Route, Routes } from "react-router-dom";
import { AuthProvider } from "@/contexts/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { RoleHomeRedirect } from "@/components/RoleHomeRedirect";
import { AppShell } from "@/components/layout/AppShell";
import {
  CLIENT_ONLY,
  MANAGER_ONLY,
  TEAM_LEAD_ROLES,
  WORK_ROLES,
} from "@/lib/roles";
// NOTE: /approve route intentionally removed — ONLY the client decides
// approve / reject / modification on requirements. The manager reviews
// the client's decisions read-only on /manager-feedback.
import LandingPage from "@/pages/LandingPage";
import LoginPage from "@/pages/LoginPage";
import OAuthCompletePage from "@/pages/OAuthCompletePage";
import DashboardPage from "@/pages/DashboardPage";
import UploadPage from "@/pages/UploadPage";
import RequirementsPage from "@/pages/RequirementsPage";
import SettingsPage from "@/pages/SettingsPage";
import ExportPage from "@/pages/ExportPage";
import MembersPage from "@/pages/MembersPage";
import IntegrationsPage from "@/pages/IntegrationsPage";
import AnalyticsPage from "@/pages/AnalyticsPage";
import ClientsPage from "@/pages/ClientsPage";
import IntegrationLogPage from "@/pages/IntegrationLogPage";
import ManagerFeedbackPage from "@/pages/ManagerFeedbackPage";
import ClientReviewPage from "@/pages/ClientReviewPage";

/**
 * Wraps a page in the standard shell + role gate. If `allowedRoles` is
 * omitted, any authenticated user can reach the page.
 */
function shell(node: React.ReactNode, allowedRoles?: readonly string[]) {
  return (
    <ProtectedRoute allowedRoles={allowedRoles}>
      <AppShell>{node}</AppShell>
    </ProtectedRoute>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/oauth/complete" element={<OAuthCompletePage />} />

        {/* Settings is fine for any signed-in user, including clients. */}
        <Route path="/settings" element={shell(<SettingsPage />)} />

        {/* --- Work pages: manager / team_head / member ------------- */}
        <Route path="/dashboard" element={shell(<DashboardPage />, WORK_ROLES)} />
        <Route path="/upload" element={shell(<UploadPage />, WORK_ROLES)} />
        <Route
          path="/requirements"
          element={shell(<RequirementsPage />, WORK_ROLES)}
        />
        {/* /images route removed — image analysis now lives inline in the
            upload flow (step 3 of /upload) so extracted image requirements
            merge into the same document's list immediately. */}
        <Route path="/analytics" element={shell(<AnalyticsPage />, WORK_ROLES)} />
        <Route path="/export" element={shell(<ExportPage />, WORK_ROLES)} />

        {/* --- Team-lead pages: manager + team_head ----------------- */}
        <Route
          path="/manager-feedback"
          element={shell(<ManagerFeedbackPage />, TEAM_LEAD_ROLES)}
        />
        <Route
          path="/integration-log"
          element={shell(<IntegrationLogPage />, TEAM_LEAD_ROLES)}
        />

        {/* --- Manager-only admin pages ----------------------------- */}
        <Route path="/members" element={shell(<MembersPage />, MANAGER_ONLY)} />
        <Route path="/clients" element={shell(<ClientsPage />, MANAGER_ONLY)} />
        <Route
          path="/integrations"
          element={shell(<IntegrationsPage />, MANAGER_ONLY)}
        />

        {/* --- Client portal ---------------------------------------- */}
        <Route
          path="/client-review"
          element={shell(<ClientReviewPage />, CLIENT_ONLY)}
        />

        {/* Marketing homepage — shown to everyone. Authenticated visitors
            still see it but the header flips CTAs to "Open app". */}
        <Route path="/" element={<LandingPage />} />

        {/* Unknown paths: send auth'd users to their role's home, guests
            back to the landing page. */}
        <Route path="*" element={<RoleHomeRedirect />} />
      </Routes>
    </AuthProvider>
  );
}

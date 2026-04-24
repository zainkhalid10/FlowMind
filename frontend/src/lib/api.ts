import axios, { AxiosError, type AxiosInstance } from "axios";
import { clearSession, getStoredToken } from "./auth";
import type {
  AnalyzeResponse,
  AssignmentRow,
  AuthResponse,
  ClientsResponse,
  DashboardStats,
  FeatureStats,
  FeaturesResponse,
  IntegrationLogEntry,
  LoginRequest,
  MembersResponse,
  ProgressStage,
  RejectionDetail,
  ReviewDocument,
  ReviewSummary,
  SignupRequest,
  UploadsResponse,
  VisualAnalysisResponse,
  VisualExplainResponse,
} from "@/types/api";

// In `vite dev`, empty baseURL routes through the dev-server proxy to FastAPI.
// In production, the FastAPI host serves the built SPA from the same origin.
//
// 60-second default timeout protects the UI from hanging forever when the
// backend stalls on a slow Ollama / RAG request. Endpoints that legitimately
// take longer (file upload / analyze) override the timeout explicitly.
const api: AxiosInstance = axios.create({
  baseURL: "",
  timeout: 60_000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (r) => r,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      clearSession();
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    }
    return Promise.reject(error);
  },
);

export function extractApiError(err: unknown): string {
  if (axios.isAxiosError(err)) {
    if (err.code === "ECONNABORTED" || err.message?.includes("timeout")) {
      return "The server took too long to respond. Please try again in a moment.";
    }
    if (err.code === "ERR_NETWORK") {
      return "Cannot reach the server. Is the backend running?";
    }
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (detail && typeof detail === "object" && "message" in detail) {
      return String((detail as { message: unknown }).message);
    }
    return err.message;
  }
  if (err instanceof Error) return err.message;
  return "Unexpected error";
}

export function extractRejectionDetail(err: unknown): RejectionDetail | null {
  if (!axios.isAxiosError(err)) return null;
  const detail = err.response?.data?.detail;
  if (detail && typeof detail === "object" && "error" in detail) {
    return detail as RejectionDetail;
  }
  return null;
}

// ========== Auth ==========
export async function login(payload: LoginRequest): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>("/api/login", payload);
  return data;
}

export async function signup(payload: SignupRequest): Promise<AuthResponse> {
  const { data } = await api.post<AuthResponse>("/api/signup", payload);
  return data;
}

export interface ClientInviteInfo {
  email: string;
  name: string;
  role: "client";
  assigned_file_id: number;
}

export async function resolveClientInvite(
  token: string,
): Promise<ClientInviteInfo> {
  const { data } = await api.get<ClientInviteInfo>(
    "/auth/client-invite/resolve",
    { params: { token } },
  );
  return data;
}

// ========== Uploads ==========
export async function fetchMyUploads(): Promise<UploadsResponse> {
  const { data } = await api.get<UploadsResponse>("/api/my-uploads");
  return data;
}

export async function deleteUpload(fileId: number): Promise<{ status: string }> {
  const { data } = await api.delete<{ status: string }>(`/api/files/${fileId}`);
  return data;
}

// Document analysis can legitimately take minutes (OCR + VLM + RAG), so
// give the upload endpoints a 10-minute ceiling instead of the default 60 s.
const UPLOAD_TIMEOUT_MS = 10 * 60 * 1000;

export async function uploadBasic(
  file: File,
  projectId?: number,
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  if (projectId != null) form.append("project_id", String(projectId));
  const { data } = await api.post<AnalyzeResponse>("/upload_client_doc", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: UPLOAD_TIMEOUT_MS,
  });
  return data;
}

export async function uploadAgent(
  file: File,
  projectId?: number,
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("file", file);
  if (projectId != null) form.append("project_id", String(projectId));
  const { data } = await api.post<AnalyzeResponse>("/upload_agent_doc", form, {
    headers: { "Content-Type": "multipart/form-data" },
    timeout: UPLOAD_TIMEOUT_MS,
  });
  return data;
}

export async function getProgress(trackerId: string): Promise<ProgressStage> {
  const { data } = await api.get<ProgressStage>(`/api/progress/${trackerId}`);
  return data;
}

// ========== Features (requirements) ==========
export interface FeatureFilters {
  status?: string;
  category?: string;
  file_id?: number;
  project_id?: number;
}

export async function fetchFeatures(
  filters: FeatureFilters = {},
): Promise<FeaturesResponse> {
  const { data } = await api.get<FeaturesResponse>("/api/features", {
    params: filters,
  });
  return data;
}

export async function fetchFeatureStats(
  filters: Pick<FeatureFilters, "file_id" | "project_id"> = {},
): Promise<FeatureStats> {
  const { data } = await api.get<FeatureStats>("/api/features/stats", {
    params: filters,
  });
  return data;
}

export async function updateFeature(
  featureId: number,
  body: { status?: string; feedback?: string; description?: string },
): Promise<{ ok: boolean }> {
  const { data } = await api.put<{ ok: boolean }>(
    `/api/features/${featureId}`,
    body,
  );
  return data;
}

export async function deleteFeature(
  featureId: number,
): Promise<{ status: string }> {
  const { data } = await api.delete<{ status: string }>(
    `/api/features/${featureId}`,
  );
  return data;
}

export async function bulkUpdateFeatures(
  featureIds: number[],
  status: string,
): Promise<{ ok: boolean }> {
  const { data } = await api.put<{ ok: boolean }>(
    "/api/features/bulk-update",
    { feature_ids: featureIds, status },
  );
  return data;
}

// ========== Members / Teams ==========
export async function fetchMembers(): Promise<MembersResponse> {
  const { data } = await api.get<MembersResponse>("/api/members");
  return data;
}

export async function updateMember(
  userId: number,
  body: { role?: string; team_id?: number | null },
): Promise<{ ok: boolean; user_id: number }> {
  const { data } = await api.patch<{ ok: boolean; user_id: number }>(
    `/api/users/${userId}`,
    body,
  );
  return data;
}

// ========== Integration config ==========
export interface IntegrationConfig {
  jira?: Record<string, string> | null;
  trello?: Record<string, string> | null;
}

export async function fetchIntegrationConfig(): Promise<IntegrationConfig> {
  const { data } = await api.get<IntegrationConfig>("/api/integration/config");
  return data;
}

export async function saveIntegrationConfig(
  body: IntegrationConfig,
): Promise<{ ok: boolean }> {
  const { data } = await api.put<{ ok: boolean }>(
    "/api/integration/config",
    body,
  );
  return data;
}

// ========== Exports ==========
export function csvDownloadUrl(fileId: number): string {
  return `/export/csv/${fileId}`;
}

export function jsonDownloadUrl(fileId: number): string {
  return `/export/json/${fileId}`;
}

export async function exportToJira(
  fileId: number,
  types: string[] = [],
): Promise<{ results: unknown[] }> {
  const { data } = await api.post<{ results: unknown[] }>(
    `/export/jira/${fileId}`,
    { types },
  );
  return data;
}

export async function exportToTrello(
  fileId: number,
  types: string[] = [],
): Promise<{ results: unknown[] }> {
  const { data } = await api.post<{ results: unknown[] }>(
    `/export/trello/${fileId}`,
    { types },
  );
  return data;
}

// ========== Manager: dashboard stats ==========
export async function fetchDashboardStats(): Promise<DashboardStats> {
  const { data } = await api.get<DashboardStats>("/api/manager/stats");
  return data;
}

// ========== Manager: clients ==========
export async function fetchClients(): Promise<ClientsResponse> {
  const { data } = await api.get<ClientsResponse>("/api/manager/clients");
  return data;
}

export interface InviteClientPayload {
  email: string;
  name?: string;
  file_id?: number;
  due_date?: string; // ISO date
}

export interface InviteClientResponse {
  status: string;
  message: string;
  email_warning: string | null;
  email_delivery_enabled: boolean;
  client: {
    id: number;
    email: string;
    username: string;
    role: string;
  };
  client_id: number;
  temp_password: string;
  assigned_file_id: number | null;
  invite_link: string | null;
}

export async function inviteClient(
  payload: InviteClientPayload,
): Promise<InviteClientResponse> {
  const { data } = await api.post<InviteClientResponse>(
    "/api/manager/invite-client",
    payload,
  );
  return data;
}

// ========== Integration log ==========
export async function fetchIntegrationLog(
  limit = 100,
): Promise<{ entries: IntegrationLogEntry[] }> {
  const { data } = await api.get<{ entries: IntegrationLogEntry[] }>(
    "/api/integration/log",
    { params: { limit } },
  );
  return data;
}

// ========== Manager: review / feedback ==========
export async function fetchAssignments(): Promise<{
  assignments: AssignmentRow[];
}> {
  const { data } = await api.get<{ assignments: AssignmentRow[] }>(
    "/api/assignments",
  );
  return data;
}

export async function fetchReviewSummary(
  fileId: number,
): Promise<ReviewSummary> {
  const { data } = await api.get<ReviewSummary>(`/review/${fileId}/summary`);
  return data;
}

export async function resolveFeedback(
  feedbackId: number,
  resolution: string,
): Promise<{ ok: boolean }> {
  const { data } = await api.put<{ ok: boolean }>(
    `/review/feedback/${feedbackId}/resolve`,
    { resolution },
  );
  return data;
}

// ========== Client: review ==========
export async function fetchReviewDocument(
  fileId: number,
): Promise<ReviewDocument> {
  const { data } = await api.get<ReviewDocument>(`/review/${fileId}`);
  return data;
}

export async function submitReviewAction(
  fileId: number,
  body: { req_id: number; action: string; comment?: string },
): Promise<unknown> {
  const { data } = await api.post(`/review/${fileId}/action`, body);
  return data;
}

export interface CreateRequirementPayload {
  file_id: number;
  title: string;
  description?: string;
  category?: "functional" | "non-functional" | "business" | "system";
  priority?: "High" | "Medium" | "Low";
  source?: string;
}

export async function createRequirement(
  body: CreateRequirementPayload,
): Promise<{
  req_id: number;
  title: string;
  description: string;
  category: string;
  priority: string;
  source: string;
}> {
  const { data } = await api.post("/requirements", body);
  return data;
}

// ========== Visual analysis (images + patterns) ==========
export async function fetchVisualAnalysis(
  fileId: number,
): Promise<VisualAnalysisResponse> {
  const { data } = await api.get<VisualAnalysisResponse>(
    `/api/files/${fileId}/visual-analysis`,
  );
  return data;
}

export async function explainVisualItem(
  fileId: number,
  body: {
    image_id?: string | number;
    image_url?: string;
    ocr_text?: string;
  },
): Promise<VisualExplainResponse> {
  // VLM image analysis (Qwen 2.5-VL / LLaVA) can take 2-5 minutes on CPU
  // or on a cold model. 5-minute ceiling keeps us from hanging forever
  // while giving the vision model realistic time to respond.
  const { data } = await api.post<VisualExplainResponse>(
    `/api/files/${fileId}/visual-analysis/explain`,
    body,
    { timeout: 5 * 60 * 1000 },
  );
  return data;
}

export interface AiRefineResponse {
  req_id: number;
  file_id: number;
  original: string;
  refined: string;
  instruction: string;
}

export async function aiRefineRequirement(
  fileId: number,
  reqId: number,
  instruction: string,
): Promise<AiRefineResponse> {
  const { data } = await api.post<AiRefineResponse>(
    `/review/${fileId}/requirements/${reqId}/ai-refine`,
    { instruction },
    { timeout: 60_000 },
  );
  return data;
}

export async function submitReview(
  fileId: number,
): Promise<{ submitted_at: string | null }> {
  const { data } = await api.post<{ submitted_at: string | null }>(
    `/review/${fileId}/submit`,
  );
  return data;
}

export default api;

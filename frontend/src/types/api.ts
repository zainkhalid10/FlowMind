export interface AuthUser {
  id: number;
  email: string;
  username: string;
  role: string;
  team_id: number | null;
  team_name: string | null;
  avatar_url?: string | null;
}

export interface AuthResponse {
  status: string;
  message: string;
  access_token: string;
  token_type: string;
  role: string;
  name: string;
  assigned_file_id: number | null;
  user: AuthUser;
}

export interface LoginRequest {
  email: string;
  password: string;
  role?: "manager" | "client";
}

export interface SignupRequest {
  email: string;
  password: string;
  name?: string;
  username?: string;
}

export interface Upload {
  id: number;
  filename: string;
  summary: string | null;
  extracted_text: string | null;
  detected_shapes: number;
  created_at: string | null;
  view_id: string | null;
  user_id: number;
  username: string | null;
  project_id: number | null;
}

export interface UploadsResponse {
  uploads: Upload[];
}

export type FeatureStatus = "pending" | "approved" | "denied" | string;

export interface Feature {
  id: number;
  category: string;
  description: string;
  status: FeatureStatus;
  quality_score: number | null;
  file_id: number;
  filename: string;
  feedback: string;
  created_at: string | null;
  user_id: number;
  username: string | null;
  assigned_to_user_id: number | null;
  assigned_to_username: string | null;
}

export interface FeaturesResponse {
  features: Feature[];
  total: number;
}

export interface FeatureStats {
  total: number;
  pending: number;
  approved: number;
  denied: number;
}

export interface ProgressStage {
  stage: string;
  description: string;
  progress: number;
  message: string;
  estimated_remaining_seconds?: number;
  total_pages?: number;
  current_page?: number;
  total_images?: number;
  current_image?: number;
}

export type RejectionErrorCode =
  | "DOCUMENT_EMPTY"
  | "NON_SRS_DOCUMENT"
  | "DOCUMENT_REJECTED";

export interface RejectionDetail {
  error: RejectionErrorCode;
  message: string;
  score?: number;
  reasons?: string[];
  recommendation?: string;
}

export interface AnalyzeResponse {
  filename?: string;
  status?: string;
  progress_tracker_id?: string;
  view_id?: string;
  file_id?: number;
  extracted_text?: string;
  images_detected?: number;
  summary?: string;
  srs_validation?: {
    srs_score: number;
    confidence: string;
    is_srs: boolean;
    reasons?: string[];
    recommendation?: string;
  };
  [key: string]: unknown;
}

export interface MemberRow {
  id: number;
  username: string;
  email: string;
  role: string;
  team_id: number | null;
  team_name: string | null;
}

export interface TeamRow {
  id: number;
  name: string;
}

export interface MembersResponse {
  members: MemberRow[];
  teams: TeamRow[];
}

export interface ClientRow {
  assignment_id: number;
  client_id: number;
  client_email: string;
  client_name: string;
  temp_password: string;
  invite_link: string | null;
  created_at: string | null;
  file_id: number | null;
  filename: string;
  due_date: string | null;
  submitted_at: string | null;
}

export interface ClientsResponse {
  status: string;
  clients: ClientRow[];
  total: number;
}

export interface IntegrationLogEntry {
  id: number;
  created_at: string | null;
  user_id: number | null;
  username: string | null;
  platform: string;
  source: string | null;
  source_id: string | null;
  items_count: number;
  success_count: number;
  message: string | null;
  details: string | null;
}

export type ClientReviewStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "modification_requested";

export interface ReviewRequirement {
  req_id: number;
  category: string;
  title: string;
  description: string;
  priority: string;
  review_status: ClientReviewStatus;
  client_comment: string;
  source: string;
  suggested_revision: string | null;
  auto_resolved: boolean;
  feedback_date: string | null;
  classification_reason: string | null;
  classification_method: string | null;
  classification_confidence_label: string | null;
}

export interface ReviewDocument {
  file_id: number;
  filename: string;
  manager_name: string;
  due_date: string | null;
  submitted_at: string | null;
  requirements: ReviewRequirement[];
}

export interface ReviewComment {
  feedback_id: number;
  req_id: number;
  title: string;
  action: string;
  comment: string | null;
  resolved: boolean;
  created_at: string | null;
  before_text: string | null;
  after_text: string | null;
}

export interface ReviewSummary {
  file_id: number;
  total: number;
  approved: number;
  rejected: number;
  modification_requested: number;
  pending: number;
  submitted: boolean;
  submitted_at: string | null;
  client_id: number;
  client_comments: ReviewComment[];
}

export type DocStatus =
  | "processing"
  | "pending"
  | "complete"
  | "in-review"
  | "client-submitted";

export interface RecentDocument {
  id: number;
  filename: string;
  created_at: string | null;
  view_id: string | null;
  user_id: number;
  feature_count: number;
  approved_count: number;
  status: DocStatus;
}

export interface DashboardStats {
  totals: {
    documents: number;
    requirements: number;
    images: number;
  };
  by_status: Record<string, number>;
  by_category: Record<string, number>;
  exports: {
    jira: number;
    trello: number;
    csv: number;
    json: number;
    total: number;
  };
  client_feedback: {
    total: number;
    approved: number;
    rejected: number;
    modification_requested: number;
    pending: number;
  };
  recent_documents: RecentDocument[];
  activity_14d: { date: string; uploads: number }[];
}

export interface VisualImage {
  id: number | string;
  page_number: number | null;
  image_url: string;
  ocr_text: string;
  agent_note: string;
  diagram_type: string;
  type_confidence: number;
  detected_features: string[];
  vlm_analysis: string;
  extracted_requirements_count: number;
}

export interface VisualAnalysisResponse {
  file_id: number;
  filename: string;
  detected_patterns: number;
  images_detected: number;
  images: VisualImage[];
}

export type RequirementCategory =
  | "functional"
  | "non-functional"
  | "business"
  | "system";

export interface CategorizedRequirement {
  text: string;
  category: RequirementCategory;
  reason: string;
}

export interface VisualExplainResponse {
  status: string;
  file_id: number;
  image_name: string;
  explanation: string;
  /** Flat list, same ordering as categorized_requirements. */
  extracted_requirements: string[];
  /** Pre-categorized by the rag_agent rule engine (IEEE-830 style). */
  categorized_requirements: CategorizedRequirement[];
  components: string[];
  relationships: string[];
  process_steps: string[];
  learning_hint: string;
}

export interface AssignmentRow {
  id: number;
  file_id: number;
  filename: string;
  client_id: number;
  client_email: string | null;
  client_name: string | null;
  manager_id: number;
  due_date: string | null;
  submitted_at: string | null;
  created_at: string | null;
  status: string;
}

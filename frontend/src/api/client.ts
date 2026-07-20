// Typed client for specs/001-survey-ingest/contracts/rest-api.md.
// Session cookie + CSRF; all errors carry a machine code + i18n message key.

export interface ApiUser {
  id: number;
  username: string;
}

export interface CrsEntry {
  id: number;
  code: string;
  label_key: string;
}

export interface ProjectSummary {
  id: string;
  name: string;
  crs: { code: string; label_key: string };
  survey_count: number;
  created_at: string;
  is_owner: boolean;
}

export interface DeletedProject {
  id: string;
  name: string;
  crs: { code: string; label_key: string };
  survey_count: number;
  deleted_at: string;
  purge_at: string;
}

export interface DeletedSurvey {
  id: string;
  name: string;
  capture_date: string;
  project: { id: string; name: string };
  deleted_at: string;
  purge_at: string;
}

export interface DeletedItems {
  projects: DeletedProject[];
  surveys: DeletedSurvey[];
}

export type SurveyStatus = "queued" | "processing" | "completed" | "failed";
export type Stage = "validation" | "reprojection" | "surface_generation";
export type TargetView = "map2d" | "view3d";
export type OptionState = "pending" | "running" | "completed" | "failed" | "skipped" | "reused";

export interface ProcessingOption {
  id: string;
  label_key: string;
  description_key: string;
  target_view: TargetView;
  required: boolean;
  default_selected: boolean;
  prerequisites: string[];
}

export interface ProcessingOptionsCatalog {
  input_type: string;
  options: ProcessingOption[];
}

export interface RunOptionStatus {
  option_id: string;
  state: OptionState;
  failure_code: string | null;
  failure_message_key: string | null;
  started_at: string | null;
  finished_at: string | null;
  reused_from_run_id: string | null;
}

export interface RunStatus {
  id: string;
  number: number;
  stage: Stage;
  state: "queued" | "running" | "completed" | "failed";
  input_type: string;
  failure_code: string | null;
  failure_message_key: string | null;
  started_at: string | null;
  finished_at: string | null;
  options: RunOptionStatus[];
}

export interface SurveySummary {
  id: string;
  name: string;
  capture_date: string;
  source_format: string | null;
  source_size_bytes: number;
  status: SurveyStatus;
  current_stage: Stage | null;
  input_type: string;
}

export interface SurveyDetail extends SurveySummary {
  runs: RunStatus[];
  latest_run: RunStatus | null;
}

export interface UploadInitiation {
  upload_session_id: string;
  tus_endpoint: string;
  tus_metadata: Record<string, string>;
  effective_options: string[];
}

export interface PendingUpload {
  upload_session_id: string;
  declared_filename: string;
  state: string;
  received_bytes: number | null;
  declared_size_bytes: number;
}

export type MemberRole = "owner" | "member";

export interface ProjectMember {
  username: string;
  role: MemberRole;
  granted_by: string | null; // null = granted by the system (002 backfill)
  granted_at: string;
}

// Keyed by option id (e.g. "elevation", "hillshade", "point_cloud_3d"); shape
// per artifact varies with its file kind (dem/hillshade/copc), not the option
// itself (FR-016, contracts/rest-api.md — breaking change over 001's
// top-level dem/copc/hillshade keys).
export interface ProductArtifact {
  run_id: string;
  kind: string;
  sha256: string;
  expires_in: number;
  url?: string;
  tilejson_url?: string;
  statistics_url?: string;
  tile_url_template?: string;
  cog_url?: string;
  size_bytes?: number;
  resolution_m?: string;
}

export interface ArtifactProducts {
  input_type: string;
  products: Record<string, ProductArtifact>;
}

export class ApiError extends Error {
  constructor(
    public code: string,
    public messageKey: string,
    public status: number,
  ) {
    super(code);
  }
}

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp(`(?:^|; )${name}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = { ...(options.headers as Record<string, string>) };
  if (options.method && options.method !== "GET") {
    headers["Content-Type"] = "application/json";
    const csrf = getCookie("csrftoken");
    if (csrf) headers["X-CSRFToken"] = csrf;
  }
  const response = await fetch(`/api/v1${path}`, { credentials: "same-origin", ...options, headers });
  const body = response.status === 204 ? {} : await response.json().catch(() => ({}));
  if (!response.ok) {
    const err = (body as { error?: { code?: string; message_key?: string } }).error ?? {};
    throw new ApiError(
      err.code ?? "invalid_request",
      err.message_key ?? "errors.invalid_request",
      response.status,
    );
  }
  return body as T;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ user: ApiUser }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password }),
    }),
  logout: () => request<object>("/auth/logout", { method: "POST" }),
  me: () => request<{ user: ApiUser }>("/auth/me"),

  listCrs: () => request<CrsEntry[]>("/crs-catalog"),
  listProjects: () => request<ProjectSummary[]>("/projects"),
  createProject: (name: string, crsId: number) =>
    request<ProjectSummary>("/projects", {
      method: "POST",
      body: JSON.stringify({ name, crs_id: crsId }),
    }),

  getProcessingOptions: (inputType = "point_cloud") =>
    request<ProcessingOptionsCatalog>(
      `/processing-options?input_type=${encodeURIComponent(inputType)}`,
    ),

  initiateUpload: (
    projectId: string,
    body: {
      filename: string;
      size_bytes: number;
      capture_date: string;
      name?: string;
      selected_options?: string[];
    },
  ) =>
    request<UploadInitiation>(`/projects/${projectId}/uploads`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  listPendingUploads: (projectId: string) =>
    request<PendingUpload[]>(`/projects/${projectId}/uploads`),
  deleteUpload: (projectId: string, uploadSessionId: string) =>
    request<object>(`/projects/${projectId}/uploads/${uploadSessionId}`, { method: "DELETE" }),

  listMembers: (projectId: string) => request<ProjectMember[]>(`/projects/${projectId}/members`),
  addMember: (projectId: string, username: string, role: MemberRole) =>
    request<ProjectMember>(`/projects/${projectId}/members`, {
      method: "POST",
      body: JSON.stringify({ username, role }),
    }),
  updateMemberRole: (projectId: string, username: string, role: MemberRole) =>
    request<ProjectMember>(`/projects/${projectId}/members/${encodeURIComponent(username)}`, {
      method: "PATCH",
      body: JSON.stringify({ role }),
    }),
  removeMember: (projectId: string, username: string) =>
    request<object>(`/projects/${projectId}/members/${encodeURIComponent(username)}`, {
      method: "DELETE",
    }),

  listSurveys: (projectId: string) => request<SurveySummary[]>(`/projects/${projectId}/surveys`),
  getSurvey: (surveyId: string) => request<SurveyDetail>(`/surveys/${surveyId}`),
  retrySurvey: (surveyId: string) =>
    request<{ run: RunStatus }>(`/surveys/${surveyId}/retry`, { method: "POST" }),
  processSurvey: (surveyId: string, selectedOptions: string[]) =>
    request<{ run: RunStatus }>(`/surveys/${surveyId}/process`, {
      method: "POST",
      body: JSON.stringify({ selected_options: selectedOptions }),
    }),
  getArtifacts: (surveyId: string) =>
    request<ArtifactProducts>(`/surveys/${surveyId}/artifacts`),
  deleteSurvey: (surveyId: string) => request<object>(`/surveys/${surveyId}`, { method: "DELETE" }),
  restoreSurvey: (surveyId: string) =>
    request<SurveySummary>(`/surveys/${surveyId}/restore`, { method: "POST" }),

  deleteProject: (projectId: string) =>
    request<object>(`/projects/${projectId}`, { method: "DELETE" }),
  restoreProject: (projectId: string) =>
    request<ProjectSummary>(`/projects/${projectId}/restore`, { method: "POST" }),
  listDeleted: () => request<DeletedItems>("/deleted"),
};

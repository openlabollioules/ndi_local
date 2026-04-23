const DEFAULT_API_URL = "http://localhost:8000/api";

function getApiBase() {
  return process.env.NEXT_PUBLIC_API_URL ?? DEFAULT_API_URL;
}

async function fetchWithRetry(
  input: RequestInfo | URL,
  init?: RequestInit,
  retries = 2,
  delayMs = 800,
): Promise<Response> {
  for (let i = 0; i <= retries; i++) {
    try {
      const res = await fetch(input, init);
      return res;
    } catch (err) {
      if (i === retries) throw err;
      await new Promise((r) => setTimeout(r, delayMs * (i + 1)));
    }
  }
  throw new Error("fetchWithRetry: unreachable");
}

// Récupère la clé API depuis les variables d'environnement ou localStorage
function getApiKey(): string | undefined {
  // Priorité : variable d'environnement > localStorage
  const envKey = process.env.NEXT_PUBLIC_API_KEY;
  if (envKey) return envKey;
  
  if (typeof window !== "undefined") {
    return localStorage.getItem("ndi_api_key") ?? undefined;
  }
  return undefined;
}

// Construit les headers avec la clé API si disponible
function buildHeaders(contentType = true): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: "application/json, text/event-stream",
  };
  if (contentType) {
    headers["Content-Type"] = "application/json";
  }
  const apiKey = getApiKey();
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  return headers;
}

export async function getSchema() {
  const response = await fetch(`${getApiBase()}/schema`, {
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    throw new Error("Erreur lors du chargement du schéma.");
  }
  return response.json() as Promise<
    { name: string; columns: { name: string; type: string }[] }[]
  >;
}

export async function getPreview(
  table: string,
  limit = 50,
  offset = 0,
): Promise<{
  columns: string[];
  rows: Record<string, unknown>[];
  total_count: number;
  limit: number;
  offset: number;
  has_next: boolean;
  has_previous: boolean;
}> {
  const params = new URLSearchParams({
    table,
    limit: String(limit),
    offset: String(offset),
  });
  const response = await fetch(`${getApiBase()}/data/preview?${params}`, {
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    throw new Error("Erreur lors du chargement de l'aperçu.");
  }
  return response.json();
}

export async function getIndexStatus(): Promise<{
  indexed: number;
}> {
  const response = await fetch(`${getApiBase()}/index/status`, {
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    throw new Error("Erreur lors du chargement du statut d'indexation.");
  }
  return response.json();
}

export async function uploadFiles(files: File[], asyncProcess = false): Promise<{
  files_received: number;
  tables_created: string[];
  message: string;
  job_id?: string;
  status?: string;
}> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  
  const url = new URL(`${getApiBase()}/ingest/upload`);
  if (asyncProcess) {
    url.searchParams.append("async_process", "true");
  }
  
  const response = await fetch(url.toString(), {
    method: "POST",
    headers: buildHeaders(false), // Note: Don't set Content-Type for FormData, browser will set it with boundary
    body: formData,
  });

  if (!response.ok) {
    let detail = "Erreur lors de l'upload.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") {
        detail = data.detail;
      }
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }

  return response.json();
}

// ============================================================================
// Excel Sheet Preview and Selective Upload
// ============================================================================

export interface ExcelSheetInfo {
  index: number;
  name: string;
  row_count: number;
  column_count: number;
  columns: string[];
  preview_rows: Record<string, unknown>[];
  error?: string;
}

export interface ExcelSheetsResponse {
  filename: string;
  sheets: ExcelSheetInfo[];
  total_sheets: number;
}

export async function previewExcelSheets(file: File): Promise<ExcelSheetsResponse> {
  const formData = new FormData();
  formData.append("file", file);
  
  const headers: Record<string, string> = {};
  const apiKey = getApiKey();
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  
  const response = await fetch(`${getApiBase()}/ingest/excel/sheets`, {
    method: "POST",
    headers,
    body: formData,
  });
  
  if (!response.ok) {
    let detail = "Erreur lors de la prévisualisation des feuillets.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") {
        detail = data.detail;
      }
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  
  return response.json();
}

export async function uploadExcelWithSheetSelection(
  files: File[],
  selections: Record<string, string[]>, // filename -> selected sheet names
  asyncProcess = false
): Promise<{
  files_received: number;
  tables_created: number;
  message: string;
  job_id?: string;
  status?: string;
}> {
  const formData = new FormData();
  files.forEach((file) => formData.append("files", file));
  formData.append("selections", JSON.stringify(selections));
  
  const url = new URL(`${getApiBase()}/ingest/excel/upload`);
  if (asyncProcess) {
    url.searchParams.append("async_process", "true");
  }
  
  const headers: Record<string, string> = {};
  const apiKey = getApiKey();
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  
  const response = await fetch(url.toString(), {
    method: "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    let detail = "Erreur lors de l'upload.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") {
        detail = data.detail;
      }
    } catch {
      // ignore
    }
    throw new Error(detail);
  }

  return response.json();
}

export function getIngestStreamUrl(jobId: string, cursor?: string): string {
  const params = new URLSearchParams({ job_id: jobId });
  if (cursor) params.append("cursor", cursor);
  // EventSource can't send headers — pass API key as query param
  const apiKey = getApiKey();
  if (apiKey) params.append("api_key", apiKey);
  return `${getApiBase()}/ingest/stream?${params}`;
}

export async function purgeData() {
  const response = await fetch(`${getApiBase()}/ingest/purge`, {
    method: "POST",
    headers: buildHeaders(false),
  });

  if (!response.ok) {
    let detail = "Erreur lors de la purge.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") {
        detail = data.detail;
      }
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }

  return response.json() as Promise<{
    duckdb_cleared: boolean;
    chroma_cleared: boolean;
    message: string;
  }>;
}

export async function invalidateCache() {
  const response = await fetch(`${getApiBase()}/health/cache/invalidate`, {
    method: "POST",
    headers: buildHeaders(false),
  });

  if (!response.ok) {
    let detail = "Erreur lors de l'invalidation du cache.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") {
        detail = data.detail;
      }
    } catch {
      // ignore parse errors
    }
    throw new Error(detail);
  }

  return response.json() as Promise<{
    message: string;
    caches_cleared: string[];
  }>;
}

export async function getRelations() {
  const response = await fetch(`${getApiBase()}/relations`, {
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    throw new Error("Erreur lors du chargement des relations.");
  }
  return response.json() as Promise<
    {
      from_table: string;
      from_column: string;
      to_table: string;
      to_column: string;
      relation_type: string;
    }[]
  >;
}

export async function createRelation(payload: {
  from_table: string;
  from_column: string;
  to_table: string;
  to_column: string;
  relation_type?: string;
}) {
  const response = await fetch(`${getApiBase()}/relations`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error("Erreur lors de la création de la relation.");
  }
  return response.json();
}

export async function getConfig() {
  const response = await fetch(`${getApiBase()}/health/config`, {
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    throw new Error("Erreur lors du chargement de la configuration.");
  }
  return response.json() as Promise<{
    llm_model: string;
    indexing_llm_model: string;
    embedding_model: string;
    llm_base_url: string;
    llm_native_base_url: string;
    llm_provider: string;
    auth_enabled: boolean;
    auth_required: boolean;
    database_mode: string;
  }>;
}

export async function getDatabaseMode() {
  const response = await fetch(`${getApiBase()}/health/database/mode`, {
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    throw new Error("Erreur lors du chargement du mode de base de données.");
  }
  return response.json() as Promise<{
    current_mode: string;
    active_plugin_mode: string;
    available_plugins: string[];
    supports_relations: boolean;
  }>;
}

export async function setDatabaseMode(mode: string): Promise<{
  message: string;
  current_mode: string;
  plugin: string;
  supports_relations: boolean;
}> {
  const response = await fetch(`${getApiBase()}/health/database/mode`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({ mode }),
  });
  if (!response.ok) {
    let detail = "Erreur lors du changement de mode.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") {
        detail = data.detail;
      }
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  return response.json();
}

export async function getAvailableModels() {
  const response = await fetch(`${getApiBase()}/health/models`, {
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    throw new Error("Erreur lors du chargement des modèles.");
  }
  return response.json() as Promise<{
    models: string[];
    current: string;
  }>;
}

export async function setCurrentModel(model: string) {
  const response = await fetch(`${getApiBase()}/health/model`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({ model }),
  });
  if (!response.ok) {
    throw new Error("Erreur lors du changement de modèle.");
  }
  return response.json();
}

export type CollectionInfo = {
  name: string;
  count: number;
};

export type VectorStoreDocument = {
  id: string;
  content: string;
  metadata?: Record<string, unknown>;
  distance?: number;
};

export type VectorStoreHealth = {
  status: string;
  total_collections: number;
  total_vectors: number;
  collections: Array<{ name: string; count: number }>;
  error?: string;
};

export async function getVectorStoreCollections(): Promise<CollectionInfo[]> {
  const response = await fetch(`${getApiBase()}/vectorstore/collections`, {
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    throw new Error("Erreur lors du chargement des collections.");
  }
  const data = await response.json();
  // Backend returns paginated { collections: [...], total, ... }
  return Array.isArray(data) ? data : (data.collections ?? []);
}

export async function getVectorStoreCollectionPeek(
  name: string,
  limit = 20,
  offset = 0,
): Promise<{
  documents: VectorStoreDocument[];
  total: number;
  has_more: boolean;
}> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
  });
  const response = await fetch(
    `${getApiBase()}/vectorstore/collections/${encodeURIComponent(name)}/peek?${params}`,
    {
      headers: buildHeaders(false),
    },
  );
  if (!response.ok) {
    throw new Error("Erreur lors du chargement des documents.");
  }
  return response.json();
}

export async function queryVectorStore(
  query: string,
  collectionName?: string | null,
  nResults = 5,
): Promise<VectorStoreDocument[]> {
  if (!collectionName) {
    throw new Error("Sélectionnez une collection avant de lancer une recherche.");
  }
  const response = await fetch(`${getApiBase()}/vectorstore/query`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({ query, collection_name: collectionName, n_results: nResults }),
  });
  if (!response.ok) {
    let detail = "Erreur lors de la requête vectorielle.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  const data = await response.json() as {
    results?: Array<{
      id: string;
      document?: string | null;
      metadata?: Record<string, unknown> | null;
      distance?: number | null;
    }>;
  };
  const results = data.results ?? [];
  return results.map((r) => ({
    id: r.id,
    content: r.document ?? "",
    metadata: r.metadata ?? undefined,
    distance: r.distance ?? undefined,
  }));
}

export async function getVectorStoreHealth(): Promise<VectorStoreHealth> {
  const response = await fetch(`${getApiBase()}/vectorstore/health`, {
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    throw new Error("Erreur lors du chargement du statut.");
  }
  return response.json();
}

export async function purgeVectorStore(): Promise<{
  message: string;
  collections_deleted: string[];
  disk_cleared: boolean;
}> {
  const response = await fetch(`${getApiBase()}/vectorstore/purge`, {
    method: "POST",
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    let detail = "Erreur lors de la purge du vector store.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return response.json();
}

export async function reindexSchema(): Promise<{
  success: boolean;
  indexed: number;
  message: string;
}> {
  const response = await fetch(`${getApiBase()}/index/reindex`, {
    method: "POST",
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    throw new Error("Erreur lors de la réindexation.");
  }
  return response.json();
}

// ============================================================================
// Conversation API (with memory and open analysis)
// ============================================================================

export interface ConversationMessage {
  role: "user" | "assistant" | "system";
  content: string;
  thinking?: string;
  timestamp?: string;
  query?: string;
  query_type?: "sql" | "nosql";
  results_count?: number;
  analysis?: string;
  intent?: string;
}

export interface ConversationQueryRequest {
  question: string;
  conversation_id?: string;
}

export interface ChartConfig {
  type: "bar" | "line" | "pie" | "area" | "scatter" | "radar";
  xKey: string;
  yKeys: string[];
  title?: string;
}

export interface ConversationQueryResponse {
  answer: string;
  conversation_id: string;
  question_type: "query" | "follow_up" | "analysis" | "explanation";
  confidence: number;
  thinking?: string;
  query?: string;
  query_type?: "sql" | "nosql";
  rows?: Record<string, unknown>[];
  row_count?: number;
  analysis_type?: string;
  sample_size?: number;
  chart_suggestion?: ChartConfig;
}

export interface ConversationHistoryResponse {
  conversation_id: string;
  messages: ConversationMessage[];
  message_count: number;
}

export interface StreamCallbacks {
  onThinking?: (chunk: string) => void;
  onContent?: (chunk: string) => void;
  onStatus?: (status: string) => void;
  onAnswer?: (result: ConversationQueryResponse) => void;
  onError?: (error: string) => void;
}

export async function conversationQueryStream(
  request: ConversationQueryRequest,
  callbacks: StreamCallbacks,
): Promise<void> {
  const response = await fetch(`${getApiBase()}/conversation/query/stream`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify(request),
  });

  if (!response.ok) {
    const detail = "Erreur lors de la requête streaming.";
    callbacks.onError?.(detail);
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) return;

  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    let currentEvent = "";
    for (const line of lines) {
      if (line.startsWith("event: ")) {
        currentEvent = line.slice(7).trim();
      } else if (line.startsWith("data: ") && currentEvent) {
        const data = line.slice(6);
        switch (currentEvent) {
          case "thinking":
            callbacks.onThinking?.(data.replace(/\\n/g, "\n"));
            break;
          case "content":
            callbacks.onContent?.(data.replace(/\\n/g, "\n"));
            break;
          case "status":
            callbacks.onStatus?.(data.replace(/\\n/g, "\n"));
            break;
          case "answer":
            try {
              callbacks.onAnswer?.(JSON.parse(data));
            } catch {
              callbacks.onContent?.(data);
            }
            break;
          case "error":
            callbacks.onError?.(data);
            break;
        }
        currentEvent = "";
      }
    }
  }
}

export async function getConversationHistory(
  conversationId: string
): Promise<ConversationHistoryResponse> {
  const response = await fetch(
    `${getApiBase()}/conversation/${encodeURIComponent(conversationId)}/history`,
    {
      headers: buildHeaders(false),
    }
  );

  if (!response.ok) {
    throw new Error("Erreur lors du chargement de l'historique.");
  }

  return response.json();
}

export async function deleteConversation(conversationId: string): Promise<void> {
  const response = await fetch(
    `${getApiBase()}/conversation/${encodeURIComponent(conversationId)}`,
    {
      method: "DELETE",
      headers: buildHeaders(false),
    }
  );

  if (!response.ok) {
    throw new Error("Erreur lors de la suppression de la conversation.");
  }
}

// ============================================================================
// Skills API (generate, inject, refine, rollback, export, history)
// ============================================================================

export interface SkillData {
  name: string;
  content: string;
  source: string;
  active: boolean;
  version: number;
  warnings: string[];
  triggers: string[];
}

export interface ActiveSkillResponse {
  active: boolean;
  skill: {
    name: string;
    content: string;
    source: string;
    version: number;
    created_at: number;
    triggers: string[];
    description: string;
  } | null;
}

export interface SkillHistoryEntry {
  version: number;
  name: string;
  source: string;
  created_at: number;
  content_length: number;
}

export async function generateSkill(
  input: string,
  name?: string,
  conversationId?: string,
): Promise<SkillData> {
  const response = await fetchWithRetry(
    `${getApiBase()}/skills/generate`,
    {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify({
        input,
        name: name || undefined,
        conversation_id: conversationId || undefined,
      }),
    },
    1,
  );
  if (!response.ok) {
    let detail = "Erreur lors de la génération du skill.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return response.json();
}

export async function injectSkill(
  name: string,
  content: string,
  conversationId?: string,
): Promise<SkillData> {
  const response = await fetch(`${getApiBase()}/skills/inject`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({ name, content, conversation_id: conversationId || undefined }),
  });
  if (!response.ok) {
    let detail = "Erreur lors de l'injection du skill.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return response.json();
}

export async function getActiveSkill(conversationId?: string): Promise<ActiveSkillResponse> {
  const params = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : "";
  const response = await fetch(`${getApiBase()}/skills/active${params}`, {
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    throw new Error("Erreur lors du chargement du skill actif.");
  }
  return response.json();
}

export interface RefineSkillResponse {
  questions: string[];
}

export async function refineSkill(content: string): Promise<RefineSkillResponse> {
  const response = await fetchWithRetry(
    `${getApiBase()}/skills/refine`,
    {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify({ content }),
    },
    1,
  );
  if (!response.ok) {
    let detail = "Erreur lors de l'analyse du skill.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return response.json();
}

export async function regenerateSkill(
  originalInput: string,
  skillContent: string,
  refinements: { question: string; answer: string }[],
  name?: string,
  conversationId?: string,
): Promise<SkillData> {
  const response = await fetchWithRetry(
    `${getApiBase()}/skills/regenerate`,
    {
      method: "POST",
      headers: buildHeaders(),
      body: JSON.stringify({
        original_input: originalInput,
        skill_content: skillContent,
        refinements,
        name: name || undefined,
        conversation_id: conversationId || undefined,
      }),
    },
    1,
  );
  if (!response.ok) {
    let detail = "Erreur lors de la régénération du skill.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return response.json();
}

export async function deactivateSkill(conversationId?: string): Promise<{ removed: boolean; message: string }> {
  const params = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : "";
  const response = await fetch(`${getApiBase()}/skills/active${params}`, {
    method: "DELETE",
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    throw new Error("Erreur lors de la désactivation du skill.");
  }
  return response.json();
}

export async function rollbackSkill(conversationId?: string): Promise<ActiveSkillResponse> {
  const params = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : "";
  const response = await fetch(`${getApiBase()}/skills/rollback${params}`, {
    method: "POST",
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    let detail = "Impossible de revenir en arrière.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return response.json();
}

export async function getSkillHistory(conversationId?: string): Promise<SkillHistoryEntry[]> {
  const params = conversationId ? `?conversation_id=${encodeURIComponent(conversationId)}` : "";
  const response = await fetch(`${getApiBase()}/skills/history${params}`, {
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    throw new Error("Erreur lors du chargement de l'historique.");
  }
  return response.json();
}

export async function exportSkillToServer(conversationId?: string): Promise<{ message: string; path: string }> {
  const response = await fetch(`${getApiBase()}/skills/export`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({ conversation_id: conversationId || undefined }),
  });
  if (!response.ok) {
    let detail = "Erreur lors de l'export.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return response.json();
}

export interface PromoteResult {
  message: string;
  name: string;
  python_name: string;
  class_name: string;
  module_path: string;
  files: string[];
  triggers: string[];
}

export async function promoteSkill(conversationId?: string): Promise<PromoteResult> {
  const response = await fetch(`${getApiBase()}/skills/promote`, {
    method: "POST",
    headers: buildHeaders(),
    body: JSON.stringify({ conversation_id: conversationId || undefined }),
  });
  if (!response.ok) {
    let detail = "Erreur lors de la promotion.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") detail = data.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  return response.json();
}

export interface RegisteredSkill {
  name: string;
  description: string;
  version: string;
  tags: string[];
  triggers: string[];
  depends_on: string[];
  is_post_processor: boolean;
  has_tools: boolean;
  tools: string[];
}

export async function getSkillRegistry(): Promise<{ skills: RegisteredSkill[]; count: number }> {
  const response = await fetch(`${getApiBase()}/skills/registry`, {
    headers: buildHeaders(false),
  });
  if (!response.ok) {
    throw new Error("Erreur lors du chargement du registre de skills.");
  }
  return response.json();
}

// ============================================================================
// Conversations API
// ============================================================================

export async function listConversations(): Promise<{
  conversations: Array<{
    id: string;
    message_count: number;
    created_at: string;
    last_activity: string;
  }>;
  count: number;
}> {
  const response = await fetch(`${getApiBase()}/conversation/list`, {
    headers: buildHeaders(false),
  });

  if (!response.ok) {
    throw new Error("Erreur lors du chargement des conversations.");
  }

  return response.json();
}

// ============================================================================
// Image Chat API
// ============================================================================

export interface ImageChatRequest {
  file: File;
  message?: string;
  conversation_id?: string;
  table_name?: string;
}

export interface ImageChatResponse {
  answer: string;
  conversation_id: string;
  action_taken: "describe" | "ocr" | "extract_table" | "ingest_table" | "chart";
  success: boolean;
  table_name?: string;
  rows_ingested?: number;
  columns?: string[];
  data_preview?: Record<string, unknown>[];
}

export async function imageChat(request: ImageChatRequest): Promise<ImageChatResponse> {
  const formData = new FormData();
  formData.append("file", request.file);
  
  if (request.message) {
    formData.append("message", request.message);
  }
  if (request.conversation_id) {
    formData.append("conversation_id", request.conversation_id);
  }
  if (request.table_name) {
    formData.append("table_name", request.table_name);
  }

  const headers: Record<string, string> = {};
  const apiKey = getApiKey();
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  const response = await fetch(`${getApiBase()}/conversation/image-chat`, {
    method: "POST",
    headers,
    body: formData,
  });

  if (!response.ok) {
    let detail = "Erreur lors du traitement de l'image.";
    try {
      const data = await response.json();
      if (typeof data?.detail === "string") {
        detail = data.detail;
      }
    } catch {
      // ignore
    }
    throw new Error(detail);
  }

  return response.json();
}

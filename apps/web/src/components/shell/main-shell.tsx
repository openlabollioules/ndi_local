"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ERDiagram } from "@/components/er-diagram";
import { ApiKeyDialog } from "@/components/api-key-dialog";
import { ChatInterface, type ConversationItem } from "@/components/chat/chat-interface";
import { SkillManager } from "@/components/skill-manager";
import { ExcelSheetPreview } from "@/components/excel-sheet-preview";
import {
  getIngestStreamUrl,
  getIndexStatus,
  getRelations,
  getPreview,
  getSchema,
  createRelation,
  purgeData,
  invalidateCache,
  uploadFiles,
  uploadExcelWithSheetSelection,
  getConfig,
  getAvailableModels,
  setCurrentModel,
  getVectorStoreCollections,
  getVectorStoreCollectionPeek,
  queryVectorStore,
  getVectorStoreHealth,
  purgeVectorStore,
  reindexSchema,
  getDatabaseMode,
  setDatabaseMode as apiSetDatabaseMode,
  type CollectionInfo,
  type VectorStoreDocument,
  type VectorStoreHealth,
} from "@/lib/api";
import { exportToCSV, exportToXLSX, exportToParquet } from "@/lib/export";

type TabKey = "chat" | "data" | "modeling" | "vectorstore" | "skills";

const allTabs: { key: TabKey; label: string }[] = [
  { key: "chat", label: "Chat" },
  { key: "data", label: "Données" },
  { key: "modeling", label: "Modélisation" },
  { key: "vectorstore", label: "Vector Store" },
  { key: "skills", label: "Skills" },
];

export function MainShell() {
  const [activeTab, setActiveTab] = useState<TabKey>("chat");
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [showExcelPreview, setShowExcelPreview] = useState(false);
  const [schema, setSchema] = useState<{ name: string; columns: { name: string; type: string }[] }[]>([]);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [schemaFetched, setSchemaFetched] = useState(false);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [previewColumns, setPreviewColumns] = useState<string[]>([]);
  const [previewRows, setPreviewRows] = useState<Record<string, unknown>[]>([]);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewPageSize, setPreviewPageSize] = useState(50);
  const [previewCurrentPage, setPreviewCurrentPage] = useState(0);
  const [previewTotalCount, setPreviewTotalCount] = useState(0);
  const [previewHasNext, setPreviewHasNext] = useState(false);
  const [previewHasPrevious, setPreviewHasPrevious] = useState(false);
  const [previewContainerWidth, setPreviewContainerWidth] = useState(800);
  const [previewContainerHeight, setPreviewContainerHeight] = useState(600);
  const [isResizingWidth, setIsResizingWidth] = useState(false);
  const [isResizingHeight, setIsResizingHeight] = useState(false);
  const resizeWidthRef = useRef<HTMLDivElement>(null);
  const resizeHeightRef = useRef<HTMLDivElement>(null);
  const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const verticalScrollbarRef = useRef<HTMLDivElement>(null);
  const horizontalScrollbarRef = useRef<HTMLDivElement>(null);
  const [chatHistory, setChatHistory] = useState<ConversationItem[]>([]);
  const [selectedChatId, setSelectedChatId] = useState<string | null>(null);
  const [purging, setPurging] = useState(false);
  const [purgeMessage, setPurgeMessage] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [reindexMessage, setReindexMessage] = useState<string | null>(null);
  const [clearingCache, setClearingCache] = useState(false);
  const [cacheMessage, setCacheMessage] = useState<string | null>(null);
  const [ingestEvents, setIngestEvents] = useState<string[]>([]);
  const [ingestCurrentStep, setIngestCurrentStep] = useState<string | null>(null);
  const [ingestProgress, setIngestProgress] = useState(0);
  const [showIngestHistory, setShowIngestHistory] = useState(false);
  const ingestStreamRef = useRef<EventSource | null>(null);
  const [indexCount, setIndexCount] = useState(0);
  const [lastIngestion, setLastIngestion] = useState<string | null>(null);
  const [llmModel, setLlmModel] = useState<string>("Chargement...");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelChanging, setModelChanging] = useState(false);
  const [relations, setRelations] = useState<
    {
      from_table: string;
      from_column: string;
      to_table: string;
      to_column: string;
      relation_type: string;
    }[]
  >([]);
  
  // Vector Store states
  const [vsCollections, setVsCollections] = useState<CollectionInfo[]>([]);
  const [vsSelectedCollection, setVsSelectedCollection] = useState<string | null>(null);
  const [vsDocuments, setVsDocuments] = useState<VectorStoreDocument[]>([]);
  const [vsDocsLoading, setVsDocsLoading] = useState(false);
  const [vsDocsTotal, setVsDocsTotal] = useState(0);
  const [vsDocsOffset, setVsDocsOffset] = useState(0);
  const [vsDocsLimit, setVsDocsLimit] = useState(20);
  const [vsDocsHasNext, setVsDocsHasNext] = useState(false);
  const [vsDocsHasPrevious, setVsDocsHasPrevious] = useState(false);
  const [vsHealth, setVsHealth] = useState<VectorStoreHealth | null>(null);
  const [vsQuery, setVsQuery] = useState("");
  const [vsQueryResults, setVsQueryResults] = useState<VectorStoreDocument[]>([]);
  const [vsQueryLoading, setVsQueryLoading] = useState(false);
  const [vsActiveView, setVsActiveView] = useState<"content" | "debug" | "health">("content");
  const [vsPurging, setVsPurging] = useState(false);
  const [vsPurgeMessage, setVsPurgeMessage] = useState<string | null>(null);
  
  const [relationForm, setRelationForm] = useState({
    from_table: "",
    from_column: "",
    to_table: "",
    to_column: "",
    relation_type: "foreign_key",
  });
  const [relationMessage, setRelationMessage] = useState<string | null>(null);
  
  // Database mode state
  const [databaseMode, setDatabaseMode] = useState<string>("sql");
  const [databaseModeLoading, setDatabaseModeLoading] = useState(false);
  
  // Filter tabs based on database mode (NoSQL doesn't support modeling)
  const visibleTabs = useMemo(() => {
    if (databaseMode === "nosql") {
      return allTabs.filter((tab) => tab.key !== "modeling");
    }
    return allTabs;
  }, [databaseMode]);
  
  // Labels adapted to database mode
  const entityLabel = databaseMode === "nosql" ? "Collection" : "Table";
  const entitiesLabel = databaseMode === "nosql" ? "Collections" : "Tables";
  const fieldLabel = databaseMode === "nosql" ? "Champ" : "Colonne";
  const fieldsLabel = databaseMode === "nosql" ? "Champs" : "Colonnes";
  
  const activeLabel = useMemo(
    () => visibleTabs.find((tab) => tab.key === activeTab)?.label ?? "Chat",
    [activeTab, visibleTabs]
  );
  const tableCount = useMemo(() => schema.length, [schema]);
  const columnCount = useMemo(
    () => schema.reduce((acc, item) => acc + item.columns.length, 0),
    [schema]
  );

  const loadSchema = async () => {
    try {
      setSchemaLoading(true);
      setSchemaError(null);
      const data = await getSchema();
      setSchema(data);
      const preferred =
        data.find((item) => item.name === selectedTable)?.name ??
        data[0]?.name ??
        null;
      setSelectedTable(preferred);
    } catch (error) {
      setSchemaError(
        error instanceof Error
          ? error.message
          : "Erreur lors du chargement du schéma."
      );
    } finally {
      setSchemaLoading(false);
      setSchemaFetched(true);
    }
  };

  const loadIndexStatus = async () => {
    try {
      const status = await getIndexStatus();
      setIndexCount(status.indexed);
    } catch {
      setIndexCount(0);
    }
  };

  const loadConfig = async () => {
    try {
      const config = await getConfig();
      setLlmModel(config.llm_model);
      setSelectedModel(config.llm_model);
      if (config.database_mode) {
        setDatabaseMode(config.database_mode);
      }
    } catch {
      setLlmModel("Non disponible");
    }
  };
  
  const loadDatabaseMode = async () => {
    try {
      setDatabaseModeLoading(true);
      const data = await getDatabaseMode();
      const mode = data.current_mode || "sql";
      setDatabaseMode(mode);
      // Synchroniser le backend avec le mode affiché (évite SQL/NoSQL créant des collections par erreur)
      await apiSetDatabaseMode(mode);
    } catch (error) {
      console.error("Erreur lors du chargement du mode database:", error);
    } finally {
      setDatabaseModeLoading(false);
    }
  };
  
  const handleSwitchMode = async (mode: string) => {
    if (mode === databaseMode) return;
    try {
      setDatabaseModeLoading(true);
      const result = await apiSetDatabaseMode(mode);
      setDatabaseMode(result.current_mode);
      // Refresh schema after mode switch
      setSchemaFetched(false);
      setActiveTab("chat");
      alert(`Mode changé en: ${result.current_mode}`);
    } catch (error) {
      alert(error instanceof Error ? error.message : "Erreur lors du changement de mode.");
    } finally {
      setDatabaseModeLoading(false);
    }
  };

  const loadAvailableModels = async () => {
    try {
      setModelsLoading(true);
      const data = await getAvailableModels();
      setAvailableModels(data.models);
      setLlmModel(data.current);
      setSelectedModel(data.current);
    } catch (error) {
      console.error("Erreur lors du chargement des modèles:", error);
    } finally {
      setModelsLoading(false);
    }
  };

  const handleLoadModel = async () => {
    if (!selectedModel || selectedModel === llmModel) return;
    try {
      setModelChanging(true);
      const result = await setCurrentModel(selectedModel);
      setLlmModel(result.current);
    } catch (error) {
      alert(error instanceof Error ? error.message : "Erreur lors du changement de modèle.");
    } finally {
      setModelChanging(false);
    }
  };

  const refreshContext = async () => {
    await Promise.all([loadSchema(), loadIndexStatus()]);
  };

  const loadRelations = async () => {
    try {
      const data = await getRelations();
      setRelations(data);
    } catch (error) {
      setRelationMessage(
        error instanceof Error
          ? error.message
          : "Erreur lors du chargement des relations."
      );
    }
  };

  // Vector Store functions
  const loadVsCollections = async () => {
    try {
      const data = await getVectorStoreCollections();
      setVsCollections(data);
      if (data.length > 0 && !vsSelectedCollection) {
        setVsSelectedCollection(data[0].name);
      }
    } catch (error) {
      console.error("Erreur chargement collections:", error);
    }
  };

  const loadVsDocuments = async (collection: string, offset = 0) => {
    try {
      setVsDocsLoading(true);
      const data = await getVectorStoreCollectionPeek(collection, vsDocsLimit, offset);
      setVsDocuments(data.documents);
      setVsDocsTotal(data.total);
      setVsDocsOffset(offset);
      setVsDocsHasNext(data.has_more);
      setVsDocsHasPrevious(offset > 0);
    } catch (error) {
      console.error("Erreur chargement documents:", error);
    } finally {
      setVsDocsLoading(false);
    }
  };

  const loadVsHealth = async () => {
    try {
      const data = await getVectorStoreHealth();
      setVsHealth(data);
    } catch (error) {
      console.error("Erreur health check:", error);
    }
  };

  const handleVsQuery = async () => {
    if (!vsQuery.trim() || !vsSelectedCollection) return;
    try {
      setVsQueryLoading(true);
      const data = await queryVectorStore(vsQuery, vsSelectedCollection, 5);
      setVsQueryResults(data);
    } catch (error) {
      console.error("Erreur recherche:", error);
    } finally {
      setVsQueryLoading(false);
    }
  };

  const refreshModeling = async () => {
    await Promise.all([loadSchema(), loadRelations()]);
  };

  useEffect(() => {
    void loadConfig();
    void loadDatabaseMode();
    void loadAvailableModels();
    // Charger l'historique depuis localStorage
    const savedHistory = localStorage.getItem("ndi_chat_history");
    if (savedHistory) {
      try {
        const parsed: ConversationItem[] = JSON.parse(savedHistory);
        const migrated = parsed.map(c => ({
          ...c,
          messages: c.messages ?? [
            { id: `user-${c.id}`, role: "user" as const, content: c.question, timestamp: c.timestamp },
            { id: `asst-${c.id}`, role: "assistant" as const, content: c.answer, query: c.sql ?? undefined, timestamp: c.timestamp },
          ],
        }));
        setChatHistory(migrated);
      } catch {
        // Ignore parsing errors
      }
    }
  }, []);

  useEffect(() => {
    if (activeTab !== "data") {
      return;
    }
    if (!schemaFetched && !schemaLoading) {
      void loadSchema();
    }
  }, [activeTab, schemaFetched, schemaLoading]);

  useEffect(() => {
    if (activeTab !== "modeling") {
      return;
    }
    void refreshModeling();
  }, [activeTab]);

  useEffect(() => {
    if (activeTab !== "vectorstore") {
      return;
    }
    void loadVsCollections();
    void loadVsHealth();
  }, [activeTab]);

  useEffect(() => {
    if (vsSelectedCollection) {
      void loadVsDocuments(vsSelectedCollection, 0);
      setVsQueryResults([]);
    }
  }, [vsSelectedCollection, vsDocsLimit]);

  useEffect(() => {
    if (!selectedTable) {
      setPreviewColumns([]);
      setPreviewRows([]);
      setPreviewTotalCount(0);
      setPreviewCurrentPage(0);
      return;
    }

    const run = async () => {
      try {
        setPreviewLoading(true);
        setPreviewError(null);
        const offset = previewCurrentPage * previewPageSize;
        const data = await getPreview(selectedTable, previewPageSize, offset);
        setPreviewColumns(data.columns);
        setPreviewRows(data.rows);
        setPreviewTotalCount(data.total_count);
        setPreviewHasNext(data.has_next);
        setPreviewHasPrevious(data.has_previous);
      } catch (error) {
        setPreviewError(
          error instanceof Error
            ? error.message
            : "Erreur lors du chargement des données."
        );
      } finally {
        setPreviewLoading(false);
      }
    };

    void run();
  }, [selectedTable, previewCurrentPage, previewPageSize]);

  const startIngestStream = (jobId: string) => {
    if (ingestStreamRef.current) {
      ingestStreamRef.current.close();
    }

    const url = getIngestStreamUrl(jobId);
    console.log("[NDI] SSE connecting:", url);
    const source = new EventSource(url);
    ingestStreamRef.current = source;

    source.addEventListener("progress", (event) => {
      console.log("[NDI] SSE progress:", event.data);
      try {
        const payload = JSON.parse(event.data);
        if (payload?.message) {
          const ts = new Date().toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
          setIngestEvents((prev) => [...prev, `${ts} — ${payload.message}`]);
          setIngestCurrentStep(payload.message);
        }
        if (payload?.step) {
          const stepMap: Record<string, number> = {
            start: 5,
            read_file: 15,
            normalize_columns: 30,
            normalize_values: 40,
            normalize_dates: 50,
            write_duckdb: 60,
            table_created: 65,
            indexing: 70,
            dictionary: 80,
            vector_index: 90,
            vector_index_error: 90,
            done: 100,
          };
          if (stepMap[payload.step] !== undefined) {
            setIngestProgress(stepMap[payload.step]);
          }
        }
      } catch {
        // ignore parse errors
      }
    });

    source.addEventListener("done", () => {
      console.log("[NDI] SSE done");
      source.close();
      ingestStreamRef.current = null;
      setUploadMessage("Ingestion terminée.");
      setIngestCurrentStep("Ingestion terminée.");
      setIngestProgress(100);
      setSchemaFetched(false);
      setLastIngestion(new Date().toLocaleString("fr-FR"));
      void refreshContext();
    });

    source.onerror = (err) => {
      console.error("[NDI] SSE error:", err);
      source.close();
      ingestStreamRef.current = null;
      setUploadMessage("Erreur lors du streaming.");
    };
  };

  useEffect(() => {
    return () => {
      if (ingestStreamRef.current) {
        ingestStreamRef.current.close();
      }
    };
  }, []);

  // Gestion du redimensionnement horizontal (largeur)
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizingWidth || !resizeWidthRef.current) return;
      const container = resizeWidthRef.current.parentElement?.parentElement;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const sidebarWidth = 260;
      const gap = 16;
      const handleWidth = 8;
      const newWidth = e.clientX - rect.left - sidebarWidth - gap - handleWidth;
      const minWidth = 400;
      const maxWidth = Math.min(window.innerWidth - 500, 1400);
      setPreviewContainerWidth(Math.max(minWidth, Math.min(maxWidth, newWidth)));
    };

    const handleMouseUp = () => {
      setIsResizingWidth(false);
    };

    if (isResizingWidth) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      if (!isResizingHeight) {
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    };
  }, [isResizingWidth, isResizingHeight]);

  // Gestion du redimensionnement vertical (hauteur)
  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (!isResizingHeight || !resizeHeightRef.current) return;
      const container = resizeHeightRef.current.parentElement;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const newHeight = e.clientY - rect.top;
      const minHeight = 300;
      const maxHeight = Math.min(window.innerHeight - 200, 1200);
      setPreviewContainerHeight(Math.max(minHeight, Math.min(maxHeight, newHeight)));
    };

    const handleMouseUp = () => {
      setIsResizingHeight(false);
    };

    if (isResizingHeight) {
      document.addEventListener("mousemove", handleMouseMove);
      document.addEventListener("mouseup", handleMouseUp);
      document.body.style.cursor = "row-resize";
      document.body.style.userSelect = "none";
    }

    return () => {
      document.removeEventListener("mousemove", handleMouseMove);
      document.removeEventListener("mouseup", handleMouseUp);
      if (!isResizingWidth) {
        document.body.style.cursor = "";
        document.body.style.userSelect = "";
      }
    };
  }, [isResizingHeight, isResizingWidth]);

  // Synchronisation des scrollbars personnalisées
  useEffect(() => {
    const container = scrollContainerRef.current;
    const verticalScrollbar = verticalScrollbarRef.current;
    const horizontalScrollbar = horizontalScrollbarRef.current;

    if (!container) return;

    const updateScrollbars = () => {
      const maxScrollTop = container.scrollHeight - container.clientHeight;
      const maxScrollLeft = container.scrollWidth - container.clientWidth;

      // Afficher/masquer la scrollbar verticale selon le besoin
      if (verticalScrollbar) {
        if (maxScrollTop > 0) {
          verticalScrollbar.style.display = "block";
          const scrollRatio = container.scrollTop / maxScrollTop;
          const thumbHeight = Math.max(20, (container.clientHeight / container.scrollHeight) * 100);
          const trackHeight = 100;
          const thumbTop = scrollRatio * (trackHeight - thumbHeight);
          const thumb = verticalScrollbar.querySelector(".custom-scrollbar-thumb-vertical") as HTMLElement;
          if (thumb) {
            thumb.style.top = `${thumbTop}%`;
            thumb.style.height = `${thumbHeight}%`;
          }
        } else {
          verticalScrollbar.style.display = "none";
        }
      }

      // Afficher/masquer la scrollbar horizontale selon le besoin
      if (horizontalScrollbar) {
        if (maxScrollLeft > 0) {
          horizontalScrollbar.style.display = "block";
          const scrollRatio = container.scrollLeft / maxScrollLeft;
          const thumbWidth = Math.max(20, (container.clientWidth / container.scrollWidth) * 100);
          const trackWidth = 100;
          const thumbLeft = scrollRatio * (trackWidth - thumbWidth);
          const thumb = horizontalScrollbar.querySelector(".custom-scrollbar-thumb-horizontal") as HTMLElement;
          if (thumb) {
            thumb.style.left = `${thumbLeft}%`;
            thumb.style.width = `${thumbWidth}%`;
          }
        } else {
          horizontalScrollbar.style.display = "none";
        }
      }
    };

    const handleScroll = () => {
      updateScrollbars();
    };

    const resizeObserver = new ResizeObserver(() => {
      updateScrollbars();
    });

    container.addEventListener("scroll", handleScroll);
    resizeObserver.observe(container);

    // Mettre à jour après un court délai pour s'assurer que le DOM est prêt
    setTimeout(updateScrollbars, 100);

    return () => {
      container.removeEventListener("scroll", handleScroll);
      resizeObserver.disconnect();
    };
  }, [previewRows, previewColumns, previewContainerHeight, previewContainerWidth, selectedTable]);

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="hidden w-64 flex-col border-r border-border bg-card/40 md:flex">
        <div className="p-6 border-b border-border">
          <div className="mb-6">
            <img
              src="/logo-ndi.png"
              alt="Naval Data Intelligence"
              className="h-24 w-auto object-contain"
            />
          </div>
          <div className="text-lg font-semibold">Naval Data Intelligence</div>
          <div className="mt-6 space-y-3 text-sm text-muted-foreground">
            <div className="rounded-md bg-muted/60 px-3 py-2 flex items-center gap-2">
              <img src="/Local_Mode.png" alt="" className="h-5 w-5" />
              Local Mode
            </div>
            
            {/* Mode Database Indicator */}
            <div className="rounded-md border border-primary/30 bg-primary/5 px-3 py-2">
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">Mode:</span>
                <span className="text-xs font-medium text-foreground uppercase">
                  {databaseMode === "nosql" ? "NoSQL" : "SQL"}
                </span>
              </div>
              {databaseMode === "nosql" && (
                <p className="text-[10px] text-muted-foreground mt-1">
                  Documents JSON (sans JOINs)
                </p>
              )}
              {databaseMode === "sql" && (
                <p className="text-[10px] text-muted-foreground mt-1">
                  DuckDB (avec relations)
                </p>
              )}
            </div>
            
            {/* Sélecteur de mode Database */}
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Mode Database</label>
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={() => handleSwitchMode("sql")}
                  disabled={databaseModeLoading || databaseMode === "sql"}
                  className={`flex-1 rounded-md px-3 py-2 text-xs font-medium transition-colors ${
                    databaseMode === "sql"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted/60 text-muted-foreground hover:bg-muted"
                  } disabled:opacity-50`}
                >
                  SQL
                </button>
                <button
                  type="button"
                  onClick={() => handleSwitchMode("nosql")}
                  disabled={databaseModeLoading || databaseMode === "nosql"}
                  className={`flex-1 rounded-md px-3 py-2 text-xs font-medium transition-colors ${
                    databaseMode === "nosql"
                      ? "bg-primary text-primary-foreground"
                      : "bg-muted/60 text-muted-foreground hover:bg-muted"
                  } disabled:opacity-50`}
                >
                  NoSQL
                </button>
              </div>
              {databaseModeLoading && (
                <p className="text-[10px] text-muted-foreground">Changement en cours...</p>
              )}
            </div>
            
            {/* Sélecteur de modèle LLM */}
            <div className="space-y-2">
              <label className="text-xs text-muted-foreground">Modèle LLM</label>
              <div className="relative">
                <select
                  className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground cursor-pointer appearance-none pr-8 focus:outline-none focus:ring-2 focus:ring-primary/50"
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  disabled={modelsLoading}
                >
                  {modelsLoading ? (
                    <option value="">Chargement...</option>
                  ) : availableModels.length === 0 ? (
                    <option value={llmModel}>{llmModel}</option>
                  ) : (
                    availableModels.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))
                  )}
                </select>
                <div className="absolute right-2 top-1/2 -translate-y-1/2 pointer-events-none">
                  <svg
                    className="w-4 h-4 text-muted-foreground"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M19 9l-7 7-7-7"
                    />
                  </svg>
                </div>
              </div>
              {selectedModel !== llmModel && (
                <p className="text-xs text-amber-500">
                  Modèle sélectionné différent du modèle actif
                </p>
              )}
            </div>
            
            {/* Bouton pour charger le modèle */}
            <Button
              variant="default"
              size="sm"
              className="w-full"
              disabled={modelsLoading || modelChanging || selectedModel === llmModel || !selectedModel}
              onClick={() => void handleLoadModel()}
            >
              {modelChanging ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Chargement...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <img src="/Load.png" alt="" className="h-5 w-5" />
                  Charger le modèle
                </span>
              )}
            </Button>
            
            {/* Indicateur du modèle actif */}
            <div className="rounded-md border border-primary/30 bg-primary/5 px-3 py-2 text-xs">
              <span className="text-muted-foreground">Actif: </span>
              <span className="text-foreground font-medium">{llmModel}</span>
            </div>
          </div>
        </div>
        
        {/* Historique des conversations */}
        <div className="flex-1 overflow-hidden flex flex-col">
          <div className="p-4 border-b border-border">
            <Button
              variant="outline"
              size="sm"
              className="w-full"
              onClick={() => {
                setSelectedChatId(null);
              }}
            >
              + Nouvelle conversation
            </Button>
          </div>
          
          <div className="flex-1 overflow-y-auto custom-scrollbar p-2">
            {chatHistory.length === 0 ? (
              <div className="text-xs text-muted-foreground text-center py-8 px-4">
                Aucune conversation
              </div>
            ) : (
              <div className="space-y-1">
                {chatHistory.map((chat) => {
                  const title = chat.question.length > 40 
                    ? chat.question.substring(0, 40) + "..." 
                    : chat.question;
                  return (
                    <button
                      key={chat.id}
                      type="button"
                      onClick={() => {
                        setSelectedChatId(chat.id);
                      }}
                      className={`w-full rounded-lg px-3 py-2.5 text-left text-sm transition-colors ${
                        selectedChatId === chat.id
                          ? "bg-primary/10 text-foreground border border-primary/20"
                          : "text-muted-foreground hover:bg-muted/40 border border-transparent"
                      }`}
                    >
                      <div className="truncate font-medium">{title}</div>
                      <div className="mt-1 text-xs text-muted-foreground/70">
                        {new Date(chat.timestamp).toLocaleDateString("fr-FR", {
                          day: "2-digit",
                          month: "2-digit",
                          hour: "2-digit",
                          minute: "2-digit",
                        })}
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
          
          {chatHistory.length > 0 && (
            <div className="p-4 border-t border-border">
              <Button
                variant="outline"
                size="sm"
                className="w-full text-destructive hover:text-destructive hover:bg-destructive/10"
                onClick={() => {
                  if (window.confirm("Supprimer tout l'historique des conversations ?")) {
                    setChatHistory([]);
                    setSelectedChatId(null);
                    localStorage.removeItem("ndi_chat_history");
                  }
                }}
              >
                <img src="/Trash.png" alt="" className="h-4 w-4 mr-2" />
                Effacer l'historique
              </Button>
            </div>
          )}
        </div>
      </aside>

      <main className="flex flex-1 flex-col">
        <header className="flex flex-col gap-3 border-b border-border p-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm uppercase tracking-wide text-muted-foreground">
              Tableau de bord
            </p>
            <h1 className="text-2xl font-semibold">{activeLabel}</h1>
          </div>
          
          {/* Logo Naval Group avec effet glow */}
          <div className="hidden sm:flex flex-1 items-center justify-center">
            <img 
              src="/logo_navalgroup.png" 
              alt="Naval Group" 
              className="h-14 w-auto logo-glow"
            />
          </div>
          
          <div className="flex flex-wrap gap-2">
            <ApiKeyDialog />
            <Button variant="outline" onClick={() => void refreshContext()}>
              <img src="/Refresh.png" alt="" className="h-4 w-4 mr-2" />
              Rafraîchir contexte
            </Button>
          </div>
        </header>

        <div className="flex flex-col gap-6 p-6">
          <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as TabKey)}>
            <TabsList>
              {visibleTabs.map((tab) => (
                <TabsTrigger key={tab.key} value={tab.key}>
                  {tab.label}
                </TabsTrigger>
              ))}
            </TabsList>

            <TabsContent value="chat" className="h-[calc(100vh-180px)] min-h-[500px]">
              <ChatInterface 
                databaseMode={databaseMode}
                selectedConversationId={selectedChatId}
                conversations={chatHistory}
                onConversationUpdate={(item: ConversationItem) => {
                  setChatHistory(prev => {
                    const exists = prev.some(c => c.id === item.id);
                    let updated: ConversationItem[];
                    if (exists) {
                      updated = prev.map(c => c.id === item.id ? item : c);
                    } else {
                      updated = [item, ...prev].slice(0, 50);
                      setSelectedChatId(item.id);
                    }
                    localStorage.setItem("ndi_chat_history", JSON.stringify(updated));
                    return updated;
                  });
                }}
                onConversationSelect={setSelectedChatId}
              />
            </TabsContent>

          <TabsContent value="data">
            <Card>
              <CardHeader>
                <CardTitle>Données</CardTitle>
                <CardDescription>
                  `Vue en lecture seule des ${entitiesLabel.toLowerCase()}` avec pagination.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap items-center gap-3">
                  <Button
                    variant="outline"
                    disabled={schemaLoading}
                    onClick={() => void loadSchema()}
                  >
                    <img src="/Refresh.png" alt="" className="h-4 w-4 mr-2" />
                    {schemaLoading ? "Chargement..." : "Actualiser le schéma"}
                  </Button>
                  <Button
                    variant="outline"
                    className="border-destructive/60 text-destructive hover:bg-destructive/10"
                    disabled={purging}
                    onClick={async () => {
                      if (!window.confirm("Purger toutes les données ingérées et vider le cache ?")) {
                        return;
                      }
                      try {
                        setPurging(true);
                        setPurgeMessage("Purge et vidage du cache...");
                        const result = await purgeData();
                        await invalidateCache();
                        setPurgeMessage("Données purgées et cache vidé.");
                        setSchema([]);
                        setSelectedTable(null);
                        setPreviewColumns([]);
                        setPreviewRows([]);
                        setSchemaFetched(false);
                        setIndexCount(0);
                        setLastIngestion(null);
                      } catch (error) {
                        setPurgeMessage(
                          error instanceof Error
                            ? error.message
                            : "Erreur lors de la purge."
                        );
                      } finally {
                        setPurging(false);
                      }
                    }}
                  >
                    <img src="/Trash.png" alt="" className="h-4 w-4 mr-2" />
                    {purging ? "Purge..." : "Purger les données"}
                  </Button>
                  <Button
                    variant="outline"
                    disabled={reindexing || schema.length === 0}
                    onClick={async () => {
                      try {
                        setReindexing(true);
                        setReindexMessage("Réindexation en cours...");
                        const result = await reindexSchema();
                        setReindexMessage(result.message);
                        await loadIndexStatus();
                      } catch (error) {
                        setReindexMessage(
                          error instanceof Error
                            ? error.message
                            : "Erreur lors de la réindexation."
                        );
                      } finally {
                        setReindexing(false);
                      }
                    }}
                  >
                    <img src="/Refresh.png" alt="" className="h-4 w-4 mr-2" />
                    {reindexing ? "Indexation..." : "Réindexer"}
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-muted-foreground hover:text-foreground"
                    disabled={clearingCache}
                    onClick={async () => {
                      try {
                        setClearingCache(true);
                        setCacheMessage("Vidage du cache...");
                        const result = await invalidateCache();
                        setCacheMessage(result.message);
                        // Auto-clear message after 3 seconds
                        setTimeout(() => setCacheMessage(null), 3000);
                      } catch (error) {
                        setCacheMessage(
                          error instanceof Error
                            ? error.message
                            : "Erreur lors du vidage du cache."
                        );
                      } finally {
                        setClearingCache(false);
                      }
                    }}
                    title="Vider le cache (schéma, requêtes, prompts, connexion ChromaDB) - Le vector store est conservé"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      width="16"
                      height="16"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className="h-4 w-4 mr-2"
                    >
                      <path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 12" />
                      <path d="M3 3v9h9" />
                    </svg>
                    {clearingCache ? "Vidage..." : "Vider cache"}
                  </Button>
                  {schemaError && (
                    <span className="text-sm text-destructive">{schemaError}</span>
                  )}
                  {purgeMessage && (
                    <span className="text-sm text-muted-foreground">{purgeMessage}</span>
                  )}
                  {reindexMessage && (
                    <span className="text-sm text-muted-foreground">{reindexMessage}</span>
                  )}
                  {cacheMessage && (
                    <span className="text-sm text-muted-foreground">{cacheMessage}</span>
                  )}
                </div>

                <div className="mt-6 flex gap-4">
                  <div className="space-y-3 flex-shrink-0" style={{ width: "260px" }}>
                    <p className="text-sm text-muted-foreground">
                      {entitiesLabel} disponibles
                    </p>
                    {schema.length === 0 && !schemaLoading && (
                      <p className="text-sm text-muted-foreground">
                        Aucune table disponible.
                      </p>
                    )}
                    <div className="space-y-2">
                      {schema.map((table) => {
                        const isExpanded = expandedTables.has(table.name);
                        return (
                          <div
                            key={table.name}
                            className={`w-full rounded-lg border transition ${
                              selectedTable === table.name
                                ? "border-primary bg-primary/10"
                                : "border-border hover:bg-muted/40"
                            }`}
                          >
                            <div className="flex items-center justify-between px-3 py-2">
                              <button
                                type="button"
                                onClick={() => {
                                  setSelectedTable(table.name);
                                  setPreviewCurrentPage(0);
                                }}
                                className="flex-1 text-left text-sm font-medium text-foreground"
                              >
                                {table.name}
                              </button>
                              <button
                                type="button"
                                onClick={() => {
                                  setExpandedTables((prev) => {
                                    const next = new Set(prev);
                                    if (next.has(table.name)) {
                                      next.delete(table.name);
                                    } else {
                                      next.add(table.name);
                                    }
                                    return next;
                                  });
                                }}
                                className="ml-2 flex-shrink-0 text-muted-foreground hover:text-foreground transition-colors"
                                aria-label={isExpanded ? "Réduire" : "Développer"}
                              >
                                <svg
                                  className={`h-4 w-4 transition-transform ${
                                    isExpanded ? "rotate-180" : ""
                                  }`}
                                  fill="none"
                                  stroke="currentColor"
                                  viewBox="0 0 24 24"
                                >
                                  <path
                                    strokeLinecap="round"
                                    strokeLinejoin="round"
                                    strokeWidth={2}
                                    d="M19 9l-7 7-7-7"
                                  />
                                </svg>
                              </button>
                            </div>
                            {isExpanded && (
                              <div className="px-3 pb-2 pt-1 border-t border-border/50">
                                <div className="text-xs text-muted-foreground space-y-1">
                                  {table.columns.map((col) => (
                                    <div key={col.name} className="truncate flex justify-between gap-2">
                                      <span>{col.name}</span>
                                      <span className="text-muted-foreground/60 font-mono text-[10px]">
                                        {col.type}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div className="space-y-3 flex-shrink-0 relative" ref={resizeWidthRef} style={{ width: `${previewContainerWidth}px`, height: `${previewContainerHeight}px` }}>
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <p className="text-sm text-muted-foreground">
                          Aperçu ({previewTotalCount > 0
                            ? `${previewCurrentPage * previewPageSize + 1}-${Math.min(
                                (previewCurrentPage + 1) * previewPageSize,
                                previewTotalCount
                              )} sur ${previewTotalCount}`
                            : "Aucune donnée"})
                        </p>
                        {previewTotalCount > previewPageSize && (
                          <div className="flex items-center gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={!previewHasPrevious || previewLoading}
                              onClick={() => setPreviewCurrentPage((prev) => Math.max(0, prev - 1))}
                            >
                              Précédent
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={!previewHasNext || previewLoading}
                              onClick={() => setPreviewCurrentPage((prev) => prev + 1)}
                            >
                              Suivant
                            </Button>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-muted-foreground">
                          Lignes par page:
                        </label>
                        <select
                          className="rounded-md border border-border bg-background px-2 py-1 text-xs"
                          value={previewPageSize}
                          onChange={(e) => {
                            setPreviewPageSize(Number(e.target.value));
                            setPreviewCurrentPage(0);
                          }}
                        >
                          <option value={25}>25</option>
                          <option value={50}>50</option>
                          <option value={100}>100</option>
                          <option value={200}>200</option>
                        </select>
                      </div>
                    </div>
                    {previewError && (
                      <p className="text-sm text-destructive">{previewError}</p>
                    )}
                    {previewLoading && (
                      <p className="text-sm text-muted-foreground">
                        Chargement des données...
                      </p>
                    )}
                    {!previewLoading && previewRows.length === 0 && (
                      <p className="text-sm text-muted-foreground">
                        Aucune donnée à afficher.
                      </p>
                    )}
                    {previewRows.length > 0 && (
                      <div className="relative rounded-xl border border-border overflow-hidden" style={{ height: `${previewContainerHeight - 120}px` }}>
                        {/* Scrollbar horizontale en haut */}
                        <div
                          ref={horizontalScrollbarRef}
                          className="absolute top-0 left-0 right-0 h-4 bg-muted/50 rounded-t-xl custom-horizontal-scrollbar z-20"
                          onMouseDown={(e) => {
                            const container = scrollContainerRef.current;
                            const scrollbar = horizontalScrollbarRef.current;
                            if (!container || !scrollbar) return;

                            const rect = scrollbar.getBoundingClientRect();
                            const clickX = e.clientX - rect.left;
                            const scrollbarWidth = rect.width;
                            const scrollRatio = clickX / scrollbarWidth;
                            const maxScroll = container.scrollWidth - container.clientWidth;
                            container.scrollLeft = scrollRatio * maxScroll;

                            const handleMouseMove = (moveEvent: MouseEvent) => {
                              const moveX = moveEvent.clientX - rect.left;
                              const newScrollRatio = Math.max(0, Math.min(1, moveX / scrollbarWidth));
                              container.scrollLeft = newScrollRatio * maxScroll;
                            };

                            const handleMouseUp = () => {
                              document.removeEventListener("mousemove", handleMouseMove);
                              document.removeEventListener("mouseup", handleMouseUp);
                            };

                            document.addEventListener("mousemove", handleMouseMove);
                            document.addEventListener("mouseup", handleMouseUp);
                          }}
                        >
                          <div className="custom-scrollbar-thumb-horizontal" />
                        </div>

                        {/* Scrollbar verticale à gauche */}
                        <div
                          ref={verticalScrollbarRef}
                          className="custom-vertical-scrollbar z-20 bg-muted/50 rounded-l-xl"
                          style={{ 
                            display: "block"
                          }}
                          onMouseDown={(e) => {
                            const container = scrollContainerRef.current;
                            const scrollbar = verticalScrollbarRef.current;
                            if (!container || !scrollbar) return;

                            const rect = scrollbar.getBoundingClientRect();
                            const clickY = e.clientY - rect.top;
                            const scrollbarHeight = rect.height;
                            const scrollRatio = clickY / scrollbarHeight;
                            const maxScroll = container.scrollHeight - container.clientHeight;
                            container.scrollTop = scrollRatio * maxScroll;

                            const handleMouseMove = (moveEvent: MouseEvent) => {
                              const moveY = moveEvent.clientY - rect.top;
                              const newScrollRatio = Math.max(0, Math.min(1, moveY / scrollbarHeight));
                              container.scrollTop = newScrollRatio * maxScroll;
                            };

                            const handleMouseUp = () => {
                              document.removeEventListener("mousemove", handleMouseMove);
                              document.removeEventListener("mouseup", handleMouseUp);
                            };

                            document.addEventListener("mousemove", handleMouseMove);
                            document.addEventListener("mouseup", handleMouseUp);
                          }}
                        >
                          <div className="custom-scrollbar-thumb-vertical" style={{ top: "0%", height: "100%" }} />
                        </div>

                        {/* Conteneur scrollable */}
                        <div
                          ref={scrollContainerRef}
                          className="overflow-auto custom-scrollbar-invisible"
                          style={{
                            position: "absolute",
                            top: "16px", /* Après la scrollbar horizontale */
                            left: "16px", /* Après la scrollbar verticale */
                            right: "0",
                            bottom: "0",
                            paddingLeft: "4px",
                            paddingTop: "4px",
                            paddingBottom: "4px",
                            paddingRight: "4px",
                            boxSizing: "border-box",
                          }}
                        >
                          <table className="min-w-full text-sm">
                            <thead className="bg-muted/60 text-left text-xs uppercase text-muted-foreground sticky top-0 z-10">
                              <tr>
                                {previewColumns.map((column) => (
                                  <th key={column} className="px-3 py-2 whitespace-nowrap">
                                    {column}
                                  </th>
                                ))}
                              </tr>
                            </thead>
                            <tbody>
                              {previewRows.map((row, index) => (
                                <tr
                                  key={`${index}-${selectedTable ?? "table"}`}
                                  className="border-t border-border"
                                >
                                  {previewColumns.map((column) => (
                                    <td key={column} className="px-3 py-2 whitespace-nowrap">
                                      {row[column] !== undefined && row[column] !== null
                                        ? String(row[column])
                                        : ""}
                                    </td>
                                  ))}
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                    {/* Handle de redimensionnement vertical en bas */}
                    <div
                      ref={resizeHeightRef}
                      className="absolute bottom-0 left-0 right-0 h-2 cursor-row-resize group flex items-center justify-center z-30"
                      onMouseDown={(e) => {
                        e.preventDefault();
                        setIsResizingHeight(true);
                      }}
                    >
                      <div className="absolute inset-x-0 h-1 bg-border group-hover:bg-primary/50 transition-colors" />
                      <div className="absolute inset-x-0 flex items-center justify-center">
                        <div className="h-0.5 w-8 bg-muted-foreground/30 group-hover:bg-primary/70 transition-colors" />
                      </div>
                    </div>
                  </div>
                  
                  {/* Handle de redimensionnement horizontal à droite */}
                  <div
                    className="relative flex items-center justify-center w-2 cursor-col-resize group flex-shrink-0 z-30"
                    onMouseDown={(e) => {
                      e.preventDefault();
                      setIsResizingWidth(true);
                    }}
                  >
                    <div className="absolute inset-y-0 w-1 bg-border group-hover:bg-primary/50 transition-colors" />
                    <div className="absolute inset-y-0 flex items-center">
                      <div className="w-0.5 h-8 bg-muted-foreground/30 group-hover:bg-primary/70 transition-colors" />
                    </div>
                  </div>
                </div>
                <div className="mt-6 space-y-3">
                  <p className="text-sm text-muted-foreground">
                    Importer des fichiers CSV, XLSX ou Parquet.
                  </p>
                  {(ingestCurrentStep || ingestEvents.length > 0) && (
                    <div className="rounded-lg border border-border bg-muted/40 p-3 text-sm text-muted-foreground">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-xs uppercase tracking-wide text-muted-foreground">
                          Ingestion {ingestProgress < 100 ? "en cours" : "terminée"}
                        </p>
                        {ingestEvents.length > 3 && (
                          <Button
                            variant="ghost"
                            className="h-6 px-2 text-xs"
                            onClick={() => setShowIngestHistory((prev) => !prev)}
                          >
                            {showIngestHistory ? "Replier" : `Voir tout (${ingestEvents.length})`}
                          </Button>
                        )}
                      </div>
                      <div className="mt-3">
                        <div className="h-2 w-full rounded-full bg-muted">
                          <div
                            className="h-2 rounded-full bg-primary transition-all duration-300"
                            style={{ width: `${ingestProgress}%` }}
                          />
                        </div>
                        <div className="mt-2 flex items-center gap-2 text-sm text-foreground">
                          {ingestProgress < 100 && (
                            <span className="animate-spin h-3 w-3 border-2 border-primary border-t-transparent rounded-full" />
                          )}
                          {ingestCurrentStep ?? "En attente"}
                        </div>
                      </div>
                      <ul className="mt-3 max-h-48 space-y-0.5 overflow-y-auto font-mono text-[11px] text-muted-foreground">
                        {(showIngestHistory ? ingestEvents : ingestEvents.slice(-5)).map((event, index) => (
                          <li key={`${event}-${index}`} className="leading-relaxed">
                            {event}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                  <input
                    type="file"
                    multiple
                    accept=".csv,.xlsx,.parquet"
                    className="text-sm text-muted-foreground"
                    onChange={(event) => {
                      const files = event.target.files
                        ? Array.from(event.target.files)
                        : [];
                      setSelectedFiles(files);
                      setUploadMessage(
                        files.length
                          ? `Fichiers sélectionnés: ${files.length}`
                          : null
                      );
                    }}
                  />
                  <div className="flex items-center gap-3">
                    <Button
                      disabled={selectedFiles.length === 0 || uploading}
                      onClick={async () => {
                        // Check if any Excel files are selected
                        const hasExcelFiles = selectedFiles.some(f => 
                          f.name.endsWith('.xlsx') || f.name.endsWith('.xls')
                        );
                        
                        // If Excel files, show sheet preview dialog
                        if (hasExcelFiles) {
                          setShowExcelPreview(true);
                          return;
                        }
                        
                        // Otherwise, proceed with normal upload
                        try {
                          setUploadMessage("Upload en cours...");
                          setIngestEvents([]);
                          setIngestCurrentStep(null);
                          setIngestProgress(0);
                          setUploading(true);
                          // Forcer le backend en mode sélectionné (SQL → DuckDB, NoSQL → collections)
                          await apiSetDatabaseMode(databaseMode);
                          const result = await uploadFiles(selectedFiles, true);
                          if (result.job_id && result.status === "processing") {
                            setUploadMessage("Ingestion en cours...");
                            startIngestStream(result.job_id);
                          } else {
                            setUploadMessage(
                              `Upload OK: ${result.files_received} fichiers, ${result.tables_created} tables.`
                            );
                            setSchema([]);
                            setSelectedTable(null);
                            setSchemaFetched(false);
                            setLastIngestion(new Date().toLocaleString("fr-FR"));
                            if (activeTab === "data") {
                              await refreshContext();
                            }
                          }
                        } catch (error) {
                          setUploadMessage(
                            error instanceof Error
                              ? error.message
                              : "Erreur lors de l'upload."
                          );
                        } finally {
                          setUploading(false);
                        }
                      }}
                    >
                      {uploading ? "Upload..." : "Lancer l'upload"}
                    </Button>
                    {uploadMessage && (
                      <span className="text-sm text-muted-foreground">
                        {uploadMessage}
                      </span>
                    )}
                  </div>
                  
                  {/* Excel Sheet Preview Dialog */}
                  <ExcelSheetPreview
                    files={selectedFiles}
                    isOpen={showExcelPreview}
                    onClose={() => setShowExcelPreview(false)}
                    onSuccess={async (message, jobId, status) => {
                      if (jobId && status === "processing") {
                        setUploadMessage("Ingestion en cours...");
                        setIngestEvents([]);
                        setIngestCurrentStep(null);
                        setIngestProgress(0);
                        startIngestStream(jobId);
                      } else {
                        setUploadMessage(message);
                        setSchema([]);
                        setSelectedTable(null);
                        setSchemaFetched(false);
                        setLastIngestion(new Date().toLocaleString("fr-FR"));
                        if (activeTab === "data") {
                          await refreshContext();
                        }
                      }
                    }}
                    onError={(error) => {
                      setUploadMessage(error);
                    }}
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="modeling">
            <Card>
              <CardHeader>
                <CardTitle>Modélisation</CardTitle>
                <CardDescription>
                  Diagramme ER interactif avec React Flow.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <p className="text-sm text-muted-foreground">
                        Déclarer une relation
                      </p>
                      <div className="space-y-2">
                        <select
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                          value={relationForm.from_table}
                          onChange={(event) => {
                            const value = event.target.value;
                            const columns =
                              schema.find((item) => item.name === value)?.columns ??
                              [];
                            setRelationForm((prev) => ({
                              ...prev,
                              from_table: value,
                              from_column: columns[0]?.name ?? "",
                            }));
                          }}
                        >
                          <option value="">{entityLabel} source</option>
                          {schema.map((item) => (
                            <option key={item.name} value={item.name}>
                              {item.name}
                            </option>
                          ))}
                        </select>
                        <select
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                          value={relationForm.from_column}
                          onChange={(event) =>
                            setRelationForm((prev) => ({
                              ...prev,
                              from_column: event.target.value,
                            }))
                          }
                        >
                          <option value="">Colonne source</option>
                          {schema
                            .find((item) => item.name === relationForm.from_table)
                            ?.columns.map((col) => (
                              <option key={col.name} value={col.name}>
                                {col.name} ({col.type})
                              </option>
                            ))}
                        </select>
                        <select
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                          value={relationForm.to_table}
                          onChange={(event) => {
                            const value = event.target.value;
                            const columns =
                              schema.find((item) => item.name === value)?.columns ??
                              [];
                            setRelationForm((prev) => ({
                              ...prev,
                              to_table: value,
                              to_column: columns[0]?.name ?? "",
                            }));
                          }}
                        >
                          <option value="">{entityLabel} cible</option>
                          {schema.map((item) => (
                            <option key={item.name} value={item.name}>
                              {item.name}
                            </option>
                          ))}
                        </select>
                        <select
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                          value={relationForm.to_column}
                          onChange={(event) =>
                            setRelationForm((prev) => ({
                              ...prev,
                              to_column: event.target.value,
                            }))
                          }
                        >
                          <option value="">Colonne cible</option>
                          {schema
                            .find((item) => item.name === relationForm.to_table)
                            ?.columns.map((col) => (
                              <option key={col.name} value={col.name}>
                                {col.name} ({col.type})
                              </option>
                            ))}
                        </select>
                        <Button
                          onClick={async () => {
                            try {
                              setRelationMessage(null);
                              const updated = await createRelation(relationForm);
                              setRelations(updated);
                              setRelationMessage("Relation enregistrée.");
                            } catch (error) {
                              setRelationMessage(
                                error instanceof Error
                                  ? error.message
                                  : "Erreur lors de la sauvegarde."
                              );
                            }
                          }}
                          disabled={
                            !relationForm.from_table ||
                            !relationForm.from_column ||
                            !relationForm.to_table ||
                            !relationForm.to_column
                          }
                        >
                          Ajouter la relation
                        </Button>
                        {relationMessage && (
                          <p className="text-sm text-muted-foreground">
                            {relationMessage}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    <p className="text-sm text-muted-foreground">
                      Diagramme ER
                    </p>
                    {schema.length === 0 ? (
                      <div className="flex h-[600px] items-center justify-center rounded-lg border border-border bg-muted/20">
                        <p className="text-sm text-muted-foreground">
                          Aucune table disponible. Importez des données pour voir le diagramme.
                        </p>
                      </div>
                    ) : (
                      <ERDiagram tables={schema} relations={relations} />
                    )}
                  </div>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="vectorstore">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle>Vector Store</CardTitle>
                    <CardDescription>
                      Explorez et testez le contenu de ChromaDB.
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    {vsPurgeMessage && (
                      <span className="text-sm text-muted-foreground">{vsPurgeMessage}</span>
                    )}
                    <Button
                      variant="destructive"
                      size="sm"
                      disabled={vsPurging}
                      onClick={async () => {
                        if (!window.confirm("Supprimer toutes les collections et vider le cache vectoriel ?")) return;
                        try {
                          setVsPurging(true);
                          setVsPurgeMessage("Purge en cours...");
                          const result = await purgeVectorStore();
                          setVsPurgeMessage(
                            `${result.collections_deleted.length} collection(s) supprimée(s)`
                          );
                          setVsCollections([]);
                          setVsSelectedCollection(null);
                          setVsDocuments([]);
                          setVsDocsTotal(0);
                          setVsQueryResults([]);
                          setVsHealth(null);
                          setIndexCount(0);
                          setTimeout(() => setVsPurgeMessage(null), 4000);
                        } catch (error) {
                          setVsPurgeMessage(
                            error instanceof Error ? error.message : "Erreur lors de la purge."
                          );
                        } finally {
                          setVsPurging(false);
                        }
                      }}
                    >
                      <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="mr-1.5">
                        <path d="M3 6h18"/><path d="M19 6v14c0 1-1 2-2 2H7c-1 0-2-1-2-2V6"/><path d="M8 6V4c0-1 1-2 2-2h4c1 0 2 1 2 2v2"/>
                      </svg>
                      {vsPurging ? "Purge..." : "Purger le vector store"}
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {/* Navigation des vues */}
                <div className="flex gap-2 mb-6">
                  <Button
                    variant={vsActiveView === "content" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setVsActiveView("content")}
                  >
                    Contenu
                  </Button>
                  <Button
                    variant={vsActiveView === "debug" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setVsActiveView("debug")}
                  >
                    Simulation & Debug
                  </Button>
                  <Button
                    variant={vsActiveView === "health" ? "default" : "outline"}
                    size="sm"
                    onClick={() => setVsActiveView("health")}
                  >
                    Santé
                  </Button>
                </div>

                {/* Vue Contenu */}
                {vsActiveView === "content" && (
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-center gap-4">
                      <div className="flex items-center gap-2">
                        <label className="text-sm text-muted-foreground">Collection :</label>
                        <select
                          className="rounded-md border border-border bg-background px-3 py-1.5 text-sm"
                          value={vsSelectedCollection ?? ""}
                          onChange={(e) => setVsSelectedCollection(e.target.value || null)}
                        >
                          <option value="">Sélectionner...</option>
                          {vsCollections.map((col) => (
                            <option key={col.name} value={col.name}>
                              {col.name} ({col.count} docs)
                            </option>
                          ))}
                        </select>
                      </div>
                      <div className="flex items-center gap-2">
                        <select
                          className="rounded-md border border-border bg-background px-2 py-1.5 text-sm"
                          value={vsDocsLimit}
                          onChange={(e) => setVsDocsLimit(Number(e.target.value))}
                        >
                          <option value={10}>10</option>
                          <option value={20}>20</option>
                          <option value={50}>50</option>
                        </select>
                        <span className="text-sm text-muted-foreground">par page</span>
                      </div>
                    </div>

                    {vsDocsLoading ? (
                      <p className="text-sm text-muted-foreground">Chargement...</p>
                    ) : vsDocuments.length === 0 ? (
                      <p className="text-sm text-muted-foreground">Aucun document dans cette collection.</p>
                    ) : (
                      <>
                        <div className="overflow-auto rounded-lg border border-border">
                          <table className="w-full text-xs">
                            <thead className="bg-muted/60">
                              <tr>
                                <th className="px-3 py-2 text-left font-medium text-muted-foreground w-[200px]">ID</th>
                                <th className="px-3 py-2 text-left font-medium text-muted-foreground">Document</th>
                                <th className="px-3 py-2 text-left font-medium text-muted-foreground w-[300px]">Metadata</th>
                              </tr>
                            </thead>
                            <tbody>
                              {vsDocuments.map((doc) => (
                                <tr key={doc.id} className="border-t border-border/50 hover:bg-muted/30">
                                  <td className="px-3 py-2 text-foreground font-mono text-[10px] break-all">{doc.id}</td>
                                  <td className="px-3 py-2 text-foreground max-w-[500px]">
                                    <div className="line-clamp-3">{doc.content}</div>
                                  </td>
                                  <td className="px-3 py-2 text-muted-foreground font-mono text-[10px]">
                                    <pre className="whitespace-pre-wrap break-all">{JSON.stringify(doc.metadata, null, 1)}</pre>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>

                        {/* Pagination */}
                        <div className="flex items-center justify-between">
                          <p className="text-sm text-muted-foreground">
                            {vsDocsOffset + 1}-{Math.min(vsDocsOffset + vsDocsLimit, vsDocsTotal)} sur {vsDocsTotal}
                          </p>
                          <div className="flex gap-2">
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={!vsDocsHasPrevious}
                              onClick={() => vsSelectedCollection && loadVsDocuments(vsSelectedCollection, Math.max(0, vsDocsOffset - vsDocsLimit))}
                            >
                              Précédent
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              disabled={!vsDocsHasNext}
                              onClick={() => vsSelectedCollection && loadVsDocuments(vsSelectedCollection, vsDocsOffset + vsDocsLimit)}
                            >
                              Suivant
                            </Button>
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}

                {/* Vue Simulation & Debug */}
                {vsActiveView === "debug" && (
                  <div className="space-y-4">
                    <div className="flex flex-wrap items-end gap-4">
                      <div className="flex-1 min-w-[300px]">
                        <label className="text-sm text-muted-foreground block mb-1.5">Question de test</label>
                        <input
                          type="text"
                          className="w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                          placeholder="Ex: Combien de clients ont commandé en 2023 ?"
                          value={vsQuery}
                          onChange={(e) => setVsQuery(e.target.value)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") {
                              void handleVsQuery();
                            }
                          }}
                        />
                      </div>
                      <div>
                        <label className="text-sm text-muted-foreground block mb-1.5">Collection</label>
                        <select
                          className="rounded-md border border-border bg-background px-3 py-2 text-sm"
                          value={vsSelectedCollection ?? ""}
                          onChange={(e) => setVsSelectedCollection(e.target.value || null)}
                        >
                          <option value="">Sélectionner...</option>
                          {vsCollections.map((col) => (
                            <option key={col.name} value={col.name}>
                              {col.name}
                            </option>
                          ))}
                        </select>
                      </div>
                      <Button
                        onClick={() => void handleVsQuery()}
                        disabled={!vsQuery.trim() || !vsSelectedCollection || vsQueryLoading}
                      >
                        {vsQueryLoading ? "Recherche..." : "Rechercher"}
                      </Button>
                    </div>

                    {vsQueryResults.length > 0 && (
                      <div className="space-y-3">
                        <p className="text-sm font-medium text-foreground">
                          {vsQueryResults.length} résultat(s) trouvé(s)
                        </p>
                        <div className="space-y-3">
                          {vsQueryResults.map((result, idx) => (
                            <div
                              key={result.id}
                              className={`rounded-lg border p-4 ${
                                result.distance !== null && result.distance !== undefined && result.distance < 0.5
                                  ? "border-green-500/50 bg-green-500/5"
                                  : result.distance !== null && result.distance !== undefined && result.distance < 1.0
                                  ? "border-yellow-500/50 bg-yellow-500/5"
                                  : "border-red-500/50 bg-red-500/5"
                              }`}
                            >
                              <div className="flex items-start justify-between gap-4 mb-2">
                                <span className="text-xs font-medium text-muted-foreground">#{idx + 1}</span>
                                <div className="flex items-center gap-2">
                                  <span className="text-xs text-muted-foreground">Distance :</span>
                                  <span
                                    className={`text-sm font-mono font-bold ${
                                      result.distance !== null && result.distance !== undefined && result.distance < 0.5
                                        ? "text-green-500"
                                        : result.distance !== null && result.distance !== undefined && result.distance < 1.0
                                        ? "text-yellow-500"
                                        : "text-red-500"
                                    }`}
                                  >
                                    {result.distance?.toFixed(4) ?? "N/A"}
                                  </span>
                                  {result.distance !== null && result.distance !== undefined && result.distance < 0.5 && (
                                    <span className="text-xs text-green-500">✓ Pertinent</span>
                                  )}
                                  {result.distance !== null && result.distance !== undefined && result.distance >= 1.0 && (
                                    <span className="text-xs text-red-500">⚠ Risque d'hallucination</span>
                                  )}
                                </div>
                              </div>
                              <p className="text-sm text-foreground mb-2">{result.content}</p>
                              {result.metadata && Object.keys(result.metadata).length > 0 && (
                                <details className="text-xs">
                                  <summary className="text-muted-foreground cursor-pointer hover:text-foreground">
                                    Metadata
                                  </summary>
                                  <pre className="mt-1 p-2 bg-muted/30 rounded text-[10px] overflow-auto">
                                    {JSON.stringify(result.metadata, null, 2)}
                                  </pre>
                                </details>
                              )}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {vsQueryResults.length === 0 && vsQuery && !vsQueryLoading && (
                      <p className="text-sm text-muted-foreground">
                        Aucun résultat. Lancez une recherche pour tester le retrieval.
                      </p>
                    )}

                    <div className="mt-6 p-4 rounded-lg bg-muted/30 border border-border">
                      <h4 className="text-sm font-medium text-foreground mb-2">Guide d'interprétation des distances</h4>
                      <ul className="text-xs text-muted-foreground space-y-1">
                        <li className="flex items-center gap-2">
                          <span className="w-3 h-3 rounded-full bg-green-500" />
                          <span><strong>&lt; 0.5</strong> : Contexte très pertinent, le LLM devrait bien répondre</span>
                        </li>
                        <li className="flex items-center gap-2">
                          <span className="w-3 h-3 rounded-full bg-yellow-500" />
                          <span><strong>0.5 - 1.0</strong> : Contexte moyennement pertinent, résultat incertain</span>
                        </li>
                        <li className="flex items-center gap-2">
                          <span className="w-3 h-3 rounded-full bg-red-500" />
                          <span><strong>&gt; 1.0</strong> : Contexte peu pertinent, risque d'hallucination</span>
                        </li>
                      </ul>
                    </div>
                  </div>
                )}

                {/* Vue Santé */}
                {vsActiveView === "health" && (
                  <div className="space-y-4">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => void loadVsHealth()}
                    >
                      Actualiser
                    </Button>

                    {vsHealth ? (
                      <div className="grid gap-4 md:grid-cols-3">
                        <div className="rounded-lg border border-border p-4">
                          <p className="text-sm text-muted-foreground">Statut</p>
                          <p className={`text-2xl font-bold ${vsHealth.status === "ok" ? "text-green-500" : "text-red-500"}`}>
                            {vsHealth.status === "ok" ? "✓ OK" : "✗ Erreur"}
                          </p>
                          {vsHealth.error && (
                            <p className="text-xs text-red-500 mt-1">{vsHealth.error}</p>
                          )}
                        </div>
                        <div className="rounded-lg border border-border p-4">
                          <p className="text-sm text-muted-foreground">Total Collections</p>
                          <p className="text-2xl font-bold text-foreground">{vsHealth.total_collections}</p>
                        </div>
                        <div className="rounded-lg border border-border p-4">
                          <p className="text-sm text-muted-foreground">Total Vecteurs</p>
                          <p className="text-2xl font-bold text-foreground">{vsHealth.total_vectors}</p>
                        </div>
                      </div>
                    ) : (
                      <p className="text-sm text-muted-foreground">Cliquez sur Actualiser pour charger les statistiques.</p>
                    )}

                    {vsHealth && vsHealth.collections.length > 0 && (
                      <div className="space-y-2">
                        <h4 className="text-sm font-medium text-foreground">Détail par collection</h4>
                        <div className="overflow-auto rounded-lg border border-border">
                          <table className="w-full text-sm">
                            <thead className="bg-muted/60">
                              <tr>
                                <th className="px-4 py-2 text-left font-medium text-muted-foreground">Collection</th>
                                <th className="px-4 py-2 text-right font-medium text-muted-foreground">Nombre de vecteurs</th>
                              </tr>
                            </thead>
                            <tbody>
                              {vsHealth.collections.map((col) => (
                                <tr key={col.name} className="border-t border-border/50">
                                  <td className="px-4 py-2 text-foreground">{col.name}</td>
                                  <td className="px-4 py-2 text-right text-foreground font-mono">{col.count}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="skills">
            <Card>
              <CardHeader>
                <CardTitle>Gestion des Skills</CardTitle>
                <CardDescription>
                  Générez, importez et exportez des connaissances métier injectables dans le contexte de l&apos;agent.
                </CardDescription>
              </CardHeader>
              <CardContent>
                <SkillManager />
              </CardContent>
            </Card>
          </TabsContent>
          </Tabs>
        </div>
      </main>
    </div>
  );
}

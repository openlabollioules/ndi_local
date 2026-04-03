"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  getConfig,
  getAvailableModels,
  setCurrentModel as apiSetCurrentModel,
  getDatabaseMode,
  setDatabaseMode as apiSetDatabaseMode,
  getSchema,
  getIndexStatus,
} from "@/lib/api";

// ── Types ────────────────────────────────────────────────────────────

export interface SchemaTable {
  name: string;
  columns: { name: string; type: string }[];
}

interface AppState {
  // Database mode
  databaseMode: string;
  databaseModeLoading: boolean;
  switchDatabaseMode: (mode: string) => Promise<void>;

  // Schema
  schema: SchemaTable[];
  schemaLoading: boolean;
  schemaError: string | null;
  schemaFetched: boolean;
  refreshSchema: () => Promise<void>;
  indexCount: number;

  // LLM model
  llmModel: string;
  availableModels: string[];
  selectedModel: string;
  setSelectedModel: (m: string) => void;
  modelsLoading: boolean;
  modelChanging: boolean;
  loadModel: () => Promise<void>;

  // Labels (adapt to SQL/NoSQL)
  entityLabel: string;
  entitiesLabel: string;
  fieldLabel: string;
  fieldsLabel: string;
}

const AppContext = createContext<AppState | null>(null);

// ── Provider ─────────────────────────────────────────────────────────

export function AppStateProvider({ children }: { children: ReactNode }) {
  // Database mode
  const [databaseMode, setDatabaseMode] = useState("sql");
  const [databaseModeLoading, setDatabaseModeLoading] = useState(false);

  // Schema
  const [schema, setSchema] = useState<SchemaTable[]>([]);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [schemaFetched, setSchemaFetched] = useState(false);
  const [indexCount, setIndexCount] = useState(0);

  // LLM model
  const [llmModel, setLlmModel] = useState("Chargement...");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState("");
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelChanging, setModelChanging] = useState(false);

  // ── Loaders ──────────────────────────────────────────────────────

  const refreshSchema = useCallback(async () => {
    try {
      setSchemaLoading(true);
      setSchemaError(null);
      const [data, status] = await Promise.all([getSchema(), getIndexStatus()]);
      setSchema(data);
      setIndexCount(status.indexed);
    } catch (error) {
      setSchemaError(error instanceof Error ? error.message : "Erreur schéma");
    } finally {
      setSchemaLoading(false);
      setSchemaFetched(true);
    }
  }, []);

  const switchDatabaseMode = useCallback(async (mode: string) => {
    if (mode === databaseMode) return;
    try {
      setDatabaseModeLoading(true);
      const result = await apiSetDatabaseMode(mode);
      setDatabaseMode(result.current_mode);
      setSchemaFetched(false);
    } catch (error) {
      alert(error instanceof Error ? error.message : "Erreur changement de mode.");
    } finally {
      setDatabaseModeLoading(false);
    }
  }, [databaseMode]);

  const loadModel = useCallback(async () => {
    if (!selectedModel || selectedModel === llmModel) return;
    try {
      setModelChanging(true);
      const result = await apiSetCurrentModel(selectedModel);
      setLlmModel(result.current);
    } catch (error) {
      alert(error instanceof Error ? error.message : "Erreur changement modèle.");
    } finally {
      setModelChanging(false);
    }
  }, [selectedModel, llmModel]);

  // ── Init ─────────────────────────────────────────────────────────

  useEffect(() => {
    const init = async () => {
      try {
        const [config, modeData, modelsData] = await Promise.allSettled([
          getConfig(),
          getDatabaseMode(),
          getAvailableModels(),
        ]);
        if (config.status === "fulfilled") {
          setLlmModel(config.value.llm_model);
          setSelectedModel(config.value.llm_model);
          if (config.value.database_mode) setDatabaseMode(config.value.database_mode);
        }
        if (modeData.status === "fulfilled") {
          setDatabaseMode(modeData.value.current_mode || "sql");
        }
        if (modelsData.status === "fulfilled") {
          setAvailableModels(modelsData.value.models);
          setLlmModel(modelsData.value.current);
          setSelectedModel(modelsData.value.current);
        }
      } catch {
        // silent
      }
    };
    void init();
  }, []);

  // ── Labels ───────────────────────────────────────────────────────

  const entityLabel = databaseMode === "nosql" ? "Collection" : "Table";
  const entitiesLabel = databaseMode === "nosql" ? "Collections" : "Tables";
  const fieldLabel = databaseMode === "nosql" ? "Champ" : "Colonne";
  const fieldsLabel = databaseMode === "nosql" ? "Champs" : "Colonnes";

  // ── Context value ────────────────────────────────────────────────

  const value = useMemo<AppState>(() => ({
    databaseMode, databaseModeLoading, switchDatabaseMode,
    schema, schemaLoading, schemaError, schemaFetched, refreshSchema, indexCount,
    llmModel, availableModels, selectedModel, setSelectedModel, modelsLoading, modelChanging, loadModel,
    entityLabel, entitiesLabel, fieldLabel, fieldsLabel,
  }), [
    databaseMode, databaseModeLoading, switchDatabaseMode,
    schema, schemaLoading, schemaError, schemaFetched, refreshSchema, indexCount,
    llmModel, availableModels, selectedModel, modelsLoading, modelChanging, loadModel,
    entityLabel, entitiesLabel, fieldLabel, fieldsLabel,
  ]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

// ── Hook ──────────────────────────────────────────────────────────────

export function useAppState(): AppState {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useAppState must be used within AppStateProvider");
  return ctx;
}

"use client";

import { useState, useCallback, useEffect } from "react";
import { getConfig, getAvailableModels, setCurrentModel } from "@/lib/api";

export interface ModelState {
  llmModel: string;
  availableModels: string[];
  selectedModel: string;
  modelsLoading: boolean;
  modelChanging: boolean;
  loadConfig: () => Promise<void>;
  loadModels: () => Promise<void>;
  handleLoadModel: () => Promise<void>;
  setSelectedModel: (model: string) => void;
}

export function useModel(): ModelState {
  const [llmModel, setLlmModel] = useState<string>("Chargement...");
  const [availableModels, setAvailableModels] = useState<string[]>([]);
  const [selectedModel, setSelectedModel] = useState<string>("");
  const [modelsLoading, setModelsLoading] = useState(false);
  const [modelChanging, setModelChanging] = useState(false);

  const loadConfig = useCallback(async () => {
    try {
      const config = await getConfig();
      setLlmModel(config.llm_model);
      setSelectedModel(config.llm_model);
    } catch {
      setLlmModel("Non disponible");
    }
  }, []);

  const loadModels = useCallback(async () => {
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
  }, []);

  const handleLoadModel = useCallback(async () => {
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
  }, [selectedModel, llmModel]);

  // Load on mount
  useEffect(() => {
    void loadConfig();
    void loadModels();
  }, [loadConfig, loadModels]);

  return {
    llmModel,
    availableModels,
    selectedModel,
    modelsLoading,
    modelChanging,
    loadConfig,
    loadModels,
    handleLoadModel,
    setSelectedModel,
  };
}

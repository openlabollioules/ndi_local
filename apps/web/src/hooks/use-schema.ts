"use client";

import { useState, useCallback, useEffect } from "react";
import { getSchema, getIndexStatus, reindexSchema } from "@/lib/api";

export interface SchemaState {
  schema: { name: string; columns: { name: string; type: string }[] }[];
  schemaLoading: boolean;
  schemaError: string | null;
  schemaFetched: boolean;
  selectedTable: string | null;
  indexCount: number;
  lastIngestion: string | null;
  reindexing: boolean;
  reindexMessage: string | null;
  loadSchema: () => Promise<void>;
  refreshContext: () => Promise<void>;
  setSelectedTable: (table: string | null) => void;
  handleReindex: () => Promise<void>;
}

export function useSchema(): SchemaState {
  const [schema, setSchema] = useState<{ name: string; columns: { name: string; type: string }[] }[]>([]);
  const [schemaLoading, setSchemaLoading] = useState(false);
  const [schemaError, setSchemaError] = useState<string | null>(null);
  const [schemaFetched, setSchemaFetched] = useState(false);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [indexCount, setIndexCount] = useState(0);
  const [lastIngestion, setLastIngestion] = useState<string | null>(null);
  const [reindexing, setReindexing] = useState(false);
  const [reindexMessage, setReindexMessage] = useState<string | null>(null);

  const loadSchema = useCallback(async () => {
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
  }, [selectedTable]);

  const loadIndexStatus = useCallback(async () => {
    try {
      const status = await getIndexStatus();
      setIndexCount(status.indexed);
    } catch {
      setIndexCount(0);
    }
  }, []);

  const refreshContext = useCallback(async () => {
    await Promise.all([loadSchema(), loadIndexStatus()]);
  }, [loadSchema, loadIndexStatus]);

  const handleReindex = useCallback(async () => {
    try {
      setReindexing(true);
      setReindexMessage("Indexation en cours...");
      await reindexSchema();
      setReindexMessage("Indexation terminée avec succès !");
      await loadIndexStatus();
      setTimeout(() => setReindexMessage(null), 3000);
    } catch (error) {
      setReindexMessage(
        error instanceof Error ? error.message : "Erreur lors de la réindexation."
      );
    } finally {
      setReindexing(false);
    }
  }, [loadIndexStatus]);

  return {
    schema,
    schemaLoading,
    schemaError,
    schemaFetched,
    selectedTable,
    indexCount,
    lastIngestion,
    reindexing,
    reindexMessage,
    loadSchema,
    refreshContext,
    setSelectedTable,
    handleReindex,
  };
}

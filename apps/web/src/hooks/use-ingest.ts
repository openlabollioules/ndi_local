"use client";

import { useState, useCallback, useRef, useEffect } from "react";
import { uploadFiles, getIngestStreamUrl, purgeData } from "@/lib/api";

export interface IngestState {
  selectedFiles: File[];
  uploading: boolean;
  uploadMessage: string | null;
  ingestEvents: string[];
  ingestCurrentStep: string | null;
  ingestProgress: number;
  showIngestHistory: boolean;
  purging: boolean;
  purgeMessage: string | null;
  setSelectedFiles: (files: File[]) => void;
  handleFileSelect: (files: FileList | null) => void;
  handleUpload: () => Promise<void>;
  handlePurge: () => Promise<void>;
  setShowIngestHistory: (show: boolean) => void;
  clearUploadMessage: () => void;
}

export function useIngest(onSuccess?: () => void): IngestState {
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<string | null>(null);
  const [ingestEvents, setIngestEvents] = useState<string[]>([]);
  const [ingestCurrentStep, setIngestCurrentStep] = useState<string | null>(null);
  const [ingestProgress, setIngestProgress] = useState(0);
  const [showIngestHistory, setShowIngestHistory] = useState(false);
  const [purging, setPurging] = useState(false);
  const [purgeMessage, setPurgeMessage] = useState<string | null>(null);
  const ingestStreamRef = useRef<EventSource | null>(null);

  const handleFileSelect = useCallback((files: FileList | null) => {
    if (files) {
      setSelectedFiles(Array.from(files));
      setUploadMessage(null);
    }
  }, []);

  const startIngestStream = useCallback((jobId: string) => {
    if (ingestStreamRef.current) {
      ingestStreamRef.current.close();
    }

    const source = new EventSource(getIngestStreamUrl(jobId));
    ingestStreamRef.current = source;

    source.addEventListener("progress", (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload?.message) {
          setIngestEvents((prev) => [...prev, payload.message]);
          setIngestCurrentStep(payload.message);
        }
        if (payload?.step) {
          const stepMap: Record<string, number> = {
            start: 5,
            read_file: 15,
            normalize_columns: 35,
            normalize_values: 50,
            write_duckdb: 65,
            dictionary: 85,
            vector_index: 95,
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
      source.close();
      ingestStreamRef.current = null;
      setUploadMessage("Ingestion terminée.");
      setIngestCurrentStep("Ingestion terminée.");
      setIngestProgress(100);
      setSelectedFiles([]);
      onSuccess?.();
    });

    source.onerror = () => {
      source.close();
      ingestStreamRef.current = null;
      setUploadMessage("Erreur lors du streaming.");
    };
  }, [onSuccess]);

  const handleUpload = useCallback(async () => {
    if (selectedFiles.length === 0) return;

    setUploading(true);
    setUploadMessage("Upload en cours...");
    setIngestEvents([]);
    setIngestProgress(0);

    try {
      const result = await uploadFiles(selectedFiles, true);
      if (result.job_id) {
        startIngestStream(result.job_id);
        setUploadMessage("Traitement en cours...");
      } else {
        setUploadMessage(result.message || "Upload terminé.");
        setSelectedFiles([]);
        onSuccess?.();
      }
    } catch (error) {
      setUploadMessage(
        error instanceof Error ? error.message : "Erreur lors de l'upload."
      );
    } finally {
      setUploading(false);
    }
  }, [selectedFiles, startIngestStream, onSuccess]);

  const handlePurge = useCallback(async () => {
    if (!typeof window || !window.confirm("Supprimer toutes les données ?")) return;

    setPurging(true);
    try {
      await purgeData();
      setPurgeMessage("Données supprimées avec succès.");
      onSuccess?.();
    } catch (error) {
      setPurgeMessage(
        error instanceof Error ? error.message : "Erreur lors de la suppression."
      );
    } finally {
      setPurging(false);
    }
  }, [onSuccess]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (ingestStreamRef.current) {
        ingestStreamRef.current.close();
      }
    };
  }, []);

  return {
    selectedFiles,
    uploading,
    uploadMessage,
    ingestEvents,
    ingestCurrentStep,
    ingestProgress,
    showIngestHistory,
    purging,
    purgeMessage,
    setSelectedFiles,
    handleFileSelect,
    handleUpload,
    handlePurge,
    setShowIngestHistory,
    clearUploadMessage: () => setUploadMessage(null),
  };
}

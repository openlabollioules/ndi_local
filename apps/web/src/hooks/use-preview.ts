"use client";

import { useState, useCallback, useEffect } from "react";
import { getPreview } from "@/lib/api";

export interface PreviewState {
  previewColumns: string[];
  previewRows: Record<string, unknown>[];
  previewLoading: boolean;
  previewError: string | null;
  previewPageSize: number;
  previewCurrentPage: number;
  previewTotalCount: number;
  previewHasNext: boolean;
  previewHasPrevious: boolean;
  previewContainerWidth: number;
  previewContainerHeight: number;
  isResizingWidth: boolean;
  isResizingHeight: boolean;
  setPreviewPageSize: (size: number) => void;
  setPreviewCurrentPage: (page: number) => void;
  setPreviewContainerWidth: (width: number) => void;
  setPreviewContainerHeight: (height: number) => void;
  setIsResizingWidth: (resizing: boolean) => void;
  setIsResizingHeight: (resizing: boolean) => void;
  loadPreview: (table: string) => Promise<void>;
}

export function usePreview(selectedTable: string | null): PreviewState {
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

  const loadPreview = useCallback(async (table: string) => {
    try {
      setPreviewLoading(true);
      setPreviewError(null);
      const offset = previewCurrentPage * previewPageSize;
      const data = await getPreview(table, previewPageSize, offset);
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
  }, [previewCurrentPage, previewPageSize]);

  // Reset when table changes
  useEffect(() => {
    if (!selectedTable) {
      setPreviewColumns([]);
      setPreviewRows([]);
      setPreviewTotalCount(0);
      setPreviewCurrentPage(0);
    } else {
      void loadPreview(selectedTable);
    }
  }, [selectedTable, previewCurrentPage, previewPageSize, loadPreview]);

  return {
    previewColumns,
    previewRows,
    previewLoading,
    previewError,
    previewPageSize,
    previewCurrentPage,
    previewTotalCount,
    previewHasNext,
    previewHasPrevious,
    previewContainerWidth,
    previewContainerHeight,
    isResizingWidth,
    isResizingHeight,
    setPreviewPageSize,
    setPreviewCurrentPage,
    setPreviewContainerWidth,
    setPreviewContainerHeight,
    setIsResizingWidth,
    setIsResizingHeight,
    loadPreview,
  };
}

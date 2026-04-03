"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { exportToCSV, exportToXLSX, exportToParquet } from "@/lib/export";

interface ExportButtonsProps {
  data: Record<string, unknown>[];
  filename?: string;
}

export function ExportButtons({ data, filename = "export" }: ExportButtonsProps) {
  const [isExporting, setIsExporting] = useState<string | null>(null);

  const handleExport = async (format: "csv" | "xlsx" | "parquet") => {
    if (data.length === 0) return;
    
    setIsExporting(format);
    try {
      switch (format) {
        case "csv":
          await exportToCSV(data, filename);
          break;
        case "xlsx":
          await exportToXLSX(data, filename);
          break;
        case "parquet":
          await exportToParquet(data, filename);
          break;
      }
    } catch (error) {
      console.error("Export error:", error);
    } finally {
      setIsExporting(null);
    }
  };

  if (data.length === 0) return null;

  return (
    <div className="flex items-center gap-1">
      <span className="text-xs text-muted-foreground mr-1">Exporter:</span>
      <Button
        variant="ghost"
        size="sm"
        disabled={isExporting !== null}
        onClick={() => handleExport("csv")}
        className="h-6 text-xs px-2"
      >
        {isExporting === "csv" ? "..." : "CSV"}
      </Button>
      <Button
        variant="ghost"
        size="sm"
        disabled={isExporting !== null}
        onClick={() => handleExport("xlsx")}
        className="h-6 text-xs px-2"
      >
        {isExporting === "xlsx" ? "..." : "Excel"}
      </Button>
      <Button
        variant="ghost"
        size="sm"
        disabled={isExporting !== null}
        onClick={() => handleExport("parquet")}
        className="h-6 text-xs px-2"
      >
        {isExporting === "parquet" ? "..." : "Parquet"}
      </Button>
    </div>
  );
}

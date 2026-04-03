"use client";

import { useState, useMemo, useCallback } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { ChartRenderer, type ChartConfig, type ChartType } from "./chart-renderer";

const CHART_OPTIONS: { value: ChartType; label: string }[] = [
  { value: "bar", label: "Barres" },
  { value: "line", label: "Courbe" },
  { value: "pie", label: "Camembert" },
  { value: "area", label: "Aire" },
  { value: "scatter", label: "Nuage de points" },
  { value: "radar", label: "Radar" },
];

interface ChartConfigDialogProps {
  rows: Record<string, unknown>[];
  initialConfig?: ChartConfig | null;
  onApply: (config: ChartConfig) => void;
}

export function ChartConfigDialog({ rows, initialConfig, onApply }: ChartConfigDialogProps) {
  const [open, setOpen] = useState(false);

  const columns = useMemo(() => {
    if (!rows.length) return [];
    return Object.keys(rows[0]);
  }, [rows]);

  const [chartType, setChartType] = useState<ChartType>(initialConfig?.type ?? "bar");
  const [xKey, setXKey] = useState(initialConfig?.xKey ?? columns[0] ?? "");
  const [yKeys, setYKeys] = useState<string[]>(initialConfig?.yKeys ?? (columns.length > 1 ? [columns[1]] : []));

  const toggleYKey = useCallback(
    (col: string) => {
      setYKeys((prev) =>
        prev.includes(col) ? prev.filter((k) => k !== col) : [...prev, col],
      );
    },
    [],
  );

  const previewConfig = useMemo<ChartConfig | null>(() => {
    if (!xKey || !yKeys.length) return null;
    return { type: chartType, xKey, yKeys };
  }, [chartType, xKey, yKeys]);

  const handleApply = () => {
    if (!previewConfig) return;
    onApply(previewConfig);
    setOpen(false);
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="text-xs gap-1.5">
          <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 3v16a2 2 0 0 0 2 2h16" />
            <path d="M7 16l4-8 4 4 4-12" />
          </svg>
          Visualiser
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>Configurer le graphique</DialogTitle>
        </DialogHeader>

        <div className="grid gap-4 py-2">
          {/* Chart type */}
          <div className="grid gap-1.5">
            <Label htmlFor="chart-type">Type de graphique</Label>
            <select
              id="chart-type"
              value={chartType}
              onChange={(e) => setChartType(e.target.value as ChartType)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {CHART_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* X axis */}
          <div className="grid gap-1.5">
            <Label htmlFor="x-key">
              {chartType === "pie" ? "Libellés (catégories)" : "Axe X"}
            </Label>
            <select
              id="x-key"
              value={xKey}
              onChange={(e) => setXKey(e.target.value)}
              className="flex h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {columns.map((col) => (
                <option key={col} value={col}>{col}</option>
              ))}
            </select>
          </div>

          {/* Y axis (multi-select via checkboxes) */}
          <div className="grid gap-1.5">
            <Label>
              {chartType === "pie" ? "Valeurs" : "Axe(s) Y"}
            </Label>
            <div className="flex flex-wrap gap-2">
              {columns
                .filter((c) => c !== xKey)
                .map((col) => (
                  <label
                    key={col}
                    className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs cursor-pointer transition-colors ${
                      yKeys.includes(col)
                        ? "bg-primary/10 border-primary/30 text-foreground"
                        : "border-input text-muted-foreground hover:bg-muted/40"
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={yKeys.includes(col)}
                      onChange={() => toggleYKey(col)}
                      className="sr-only"
                    />
                    {col}
                  </label>
                ))}
            </div>
          </div>

          {/* Live preview */}
          {previewConfig && rows.length > 0 && (
            <div className="border rounded-lg p-2 bg-muted/20">
              <p className="text-xs text-muted-foreground mb-1">Apercu</p>
              <ChartRenderer data={rows} config={previewConfig} />
            </div>
          )}
        </div>

        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={() => setOpen(false)}>
            Annuler
          </Button>
          <Button size="sm" disabled={!previewConfig} onClick={handleApply}>
            Appliquer
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

"use client";

import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog";
import { Label } from "@/components/ui/label";
import { previewExcelSheets, uploadExcelWithSheetSelection, type ExcelSheetInfo, type ExcelSheetsResponse } from "@/lib/api";

interface ExcelSheetPreviewProps {
  files: File[];
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (message: string, jobId?: string, status?: string) => void;
  onError: (error: string) => void;
}

export function ExcelSheetPreview({ files, isOpen, onClose, onSuccess, onError }: ExcelSheetPreviewProps) {
  const [previews, setPreviews] = useState<ExcelSheetsResponse[]>([]);
  const [selections, setSelections] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [activeFile, setActiveFile] = useState<string | null>(null);

  const excelFiles = files.filter(f => 
    f.name.endsWith('.xlsx') || f.name.endsWith('.xls')
  );

  // Reset state when dialog opens with new files
  useEffect(() => {
    if (isOpen && excelFiles.length > 0) {
      // Reset state
      setPreviews([]);
      setSelections({});
      setActiveFile(null);
      // Load previews
      loadPreviews();
    }
  }, [isOpen, files]);

  const loadPreviews = async () => {
    console.log(`loadPreviews called, excelFiles count: ${excelFiles.length}`);
    if (excelFiles.length === 0) {
      console.log("No excel files to preview");
      return;
    }
    
    setLoading(true);
    try {
      const previewsData: ExcelSheetsResponse[] = [];
      const initialSelections: Record<string, string[]> = {};
      
      for (const file of excelFiles) {
        console.log(`Loading preview for: ${file.name}`);
        const preview = await previewExcelSheets(file);
        console.log(`Preview received for ${file.name}:`, JSON.stringify(preview, null, 2));
        previewsData.push(preview);
        // Select all sheets by default
        initialSelections[preview.filename] = preview.sheets.map(s => s.name);
        console.log(`Selected sheets for ${preview.filename}:`, initialSelections[preview.filename]);
      }
      
      console.log(`Setting previews:`, previewsData.length, "files");
      setPreviews(previewsData);
      setSelections(initialSelections);
      
      // Set active file to first file
      if (previewsData.length > 0) {
        console.log(`Setting active file to:`, previewsData[0].filename);
        setActiveFile(previewsData[0].filename);
      }
    } catch (error) {
      console.error("Error loading previews:", error);
      onError(error instanceof Error ? error.message : "Erreur de prévisualisation");
    } finally {
      setLoading(false);
    }
  };

  const handleToggleSheet = (filename: string, sheetName: string, checked: boolean) => {
    setSelections(prev => {
      const current = prev[filename] || [];
      if (checked) {
        return { ...prev, [filename]: [...current, sheetName] };
      } else {
        return { ...prev, [filename]: current.filter(s => s !== sheetName) };
      }
    });
  };

  const handleUpload = async () => {
    // Validate at least one sheet is selected per file
    const hasSelection = Object.values(selections).some(sheets => sheets.length > 0);
    if (!hasSelection) {
      onError("Veuillez sélectionner au moins un feuillet");
      return;
    }

    setUploading(true);
    try {
      const result = await uploadExcelWithSheetSelection(excelFiles, selections, true);
      onSuccess(result.message, result.job_id, result.status);
      // Reset previews after successful upload
      setPreviews([]);
      setSelections({});
      setActiveFile(null);
      onClose();
    } catch (error) {
      onError(error instanceof Error ? error.message : "Erreur d'upload");
    } finally {
      setUploading(false);
    }
  };

  const getTotalSelectedSheets = () => {
    return Object.values(selections).reduce((sum, sheets) => sum + sheets.length, 0);
  };

  const getTotalSheets = () => {
    return previews.reduce((sum, p) => sum + p.total_sheets, 0);
  };

  // Get currently active preview
  const activePreview = previews.find(p => p.filename === activeFile) || previews[0];

  return (
    <Dialog open={isOpen} onOpenChange={(open) => {
      if (!open) {
        onClose();
      }
    }}>
      <DialogContent className="max-w-4xl max-h-[85vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle>Sélection des feuillets Excel</DialogTitle>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <div className="flex flex-col items-center gap-4">
              <div className="animate-spin h-8 w-8 border-2 border-primary border-t-transparent rounded-full" />
              <p className="text-sm text-muted-foreground">Analyse des fichiers Excel...</p>
            </div>
          </div>
        ) : previews.length === 0 ? (
          <div className="flex items-center justify-center py-12">
            <p className="text-sm text-muted-foreground">Aucun fichier Excel à prévisualiser</p>
          </div>
        ) : (
          <>
            <div className="flex gap-4 flex-1 overflow-hidden min-h-0">
              {/* File tabs - only show if multiple files */}
              {excelFiles.length > 1 && (
                <div className="w-48 border-r pr-4 space-y-1 overflow-y-auto">
                  <p className="text-xs font-medium text-muted-foreground mb-2">Fichiers</p>
                  {previews.map((preview) => (
                    <button
                      key={preview.filename}
                      onClick={() => setActiveFile(preview.filename)}
                      className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                        activeFile === preview.filename
                          ? "bg-primary/10 text-foreground border border-primary/20"
                          : "text-muted-foreground hover:bg-muted border border-transparent"
                      }`}
                    >
                      <div className="truncate">{preview.filename}</div>
                      <div className="text-xs text-muted-foreground">
                        {preview.sheets.length} feuillet(s)
                      </div>
                    </button>
                  ))}
                </div>
              )}

              {/* Sheet list */}
              <div className="flex-1 overflow-y-auto">
                {activePreview ? (
                  <div>
                    {/* Header with file info */}
                    <div className="flex items-center justify-between mb-4">
                      <div>
                        <h3 className="font-medium">{activePreview.filename}</h3>
                        <p className="text-sm text-muted-foreground">
                          {activePreview.sheets?.length || 0} feuillet(s) disponible(s)
                        </p>
                      </div>
                      <div className="flex gap-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSelections(prev => ({
                              ...prev,
                              [activePreview.filename]: activePreview.sheets.map(s => s.name)
                            }));
                          }}
                        >
                          Tout sélectionner
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setSelections(prev => ({
                              ...prev,
                              [activePreview.filename]: []
                            }));
                          }}
                        >
                          Tout désélectionner
                        </Button>
                      </div>
                    </div>

                    {/* Sheets */}
                    {!activePreview.sheets || activePreview.sheets.length === 0 ? (
                      <p className="text-sm text-muted-foreground">Aucun feuillet trouvé dans ce fichier</p>
                    ) : (
                      <div className="space-y-3">
                        {activePreview.sheets.map((sheet) => (
                          <SheetCard
                            key={`${activePreview.filename}-${sheet.name}`}
                            sheet={sheet}
                            checked={(selections[activePreview.filename] || []).includes(sheet.name)}
                            onCheckedChange={(checked) => 
                              handleToggleSheet(activePreview.filename, sheet.name, checked as boolean)
                            }
                          />
                        ))}
                      </div>
                    )}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">Sélectionnez un fichier pour voir ses feuillets</p>
                )}
              </div>
            </div>

            <DialogFooter className="border-t pt-4 mt-4">
              <div className="flex items-center justify-between w-full">
                <p className="text-sm text-muted-foreground">
                  {getTotalSelectedSheets()} feuillet(s) sélectionné(s) sur {getTotalSheets()} au total
                </p>
                <div className="flex gap-2">
                  <Button variant="outline" onClick={onClose} disabled={uploading}>
                    Annuler
                  </Button>
                  <Button 
                    onClick={handleUpload} 
                    disabled={uploading || getTotalSelectedSheets() === 0}
                  >
                    {uploading ? (
                      <span className="flex items-center gap-2">
                        <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                        Upload...
                      </span>
                    ) : (
                      "Ingérer les feuillets sélectionnés"
                    )}
                  </Button>
                </div>
              </div>
            </DialogFooter>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

interface SheetCardProps {
  sheet: ExcelSheetInfo;
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
}

function SheetCard({ sheet, checked, onCheckedChange }: SheetCardProps) {
  const [showPreview, setShowPreview] = useState(false);

  return (
    <Card className={`transition-colors ${checked ? "border-primary" : ""}`}>
      <CardHeader className="py-3">
        <div className="flex items-start gap-3">
          <Checkbox
            id={`sheet-${sheet.name}`}
            checked={checked}
            onCheckedChange={onCheckedChange}
          />
          <div className="flex-1 min-w-0">
            <Label 
              htmlFor={`sheet-${sheet.name}`}
              className="font-medium cursor-pointer flex items-center gap-2"
            >
              {sheet.name}
              {sheet.error && (
                <span className="text-xs text-destructive">(Erreur de lecture)</span>
              )}
            </Label>
            <div className="flex items-center gap-4 mt-1 text-xs text-muted-foreground">
              <span>{sheet.row_count.toLocaleString()} lignes</span>
              <span>{sheet.column_count} colonnes</span>
              {sheet.columns.length > 0 && (
                <button
                  onClick={() => setShowPreview(!showPreview)}
                  className="text-primary hover:underline"
                >
                  {showPreview ? "Masquer" : "Voir"} les colonnes
                </button>
              )}
            </div>
          </div>
        </div>
      </CardHeader>
      
      {showPreview && sheet.columns.length > 0 && (
        <CardContent className="pt-0 pb-3">
          <div className="text-xs space-y-2">
            <p className="font-medium text-muted-foreground">Colonnes:</p>
            <div className="flex flex-wrap gap-1">
              {sheet.columns.map((col) => (
                <span 
                  key={col}
                  className="px-2 py-0.5 bg-muted rounded text-muted-foreground"
                >
                  {col}
                </span>
              ))}
            </div>
            
            {sheet.preview_rows.length > 0 && (
              <>
                <p className="font-medium text-muted-foreground mt-3">Aperçu (3 premieres lignes):</p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b">
                        {sheet.columns.map((col) => (
                          <th key={col} className="text-left py-1 px-2 font-medium">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody>
                      {sheet.preview_rows.map((row, idx) => (
                        <tr key={idx} className="border-b border-muted">
                          {sheet.columns.map((col) => (
                            <td key={col} className="py-1 px-2 truncate max-w-[150px]">
                              {String(row[col] ?? "")}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        </CardContent>
      )}
    </Card>
  );
}

"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";

interface SmartTableProps {
  headers: string[];
  rows: string[][];
}

export function SmartTable({ headers, rows }: SmartTableProps) {
  const [expanded, setExpanded] = useState(false);
  const displayRows = expanded ? rows : rows.slice(0, 10);
  const hasMore = rows.length > 10;

  // Detect numeric columns
  const isNumericColumn = (header: string, values: string[]): boolean => {
    const numericKeywords = ["total", "somme", "moyenne", "nombre", "nb", "heures", "montant", "prix", "min", "max", "valeur", "value"];
    const lower = header.toLowerCase();
    
    if (lower === "rang" || lower === "n°" || lower === "#") return false;
    if (numericKeywords.some(kw => lower.includes(kw))) return true;
    
    // Check if most values look numeric
    const numericValues = values.filter(v => v != null && /^[\d\s,.]+$/.test(String(v).trim()) && /\d/.test(String(v)));
    return numericValues.length > values.length / 2;
  };

  const numericColumns = headers.map((h, i) => 
    isNumericColumn(h, rows.map(r => r[i]))
  );

  return (
    <div className="rounded-lg border border-border overflow-hidden my-3 bg-background">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-muted/80">
            <tr>
              {headers.map((header, i) => (
                <th
                  key={i}
                  className={`px-4 py-2.5 text-xs font-semibold text-muted-foreground uppercase tracking-wider border-b ${
                    numericColumns[i] ? "text-right" : "text-left"
                  }`}
                >
                  {header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {displayRows.map((row, rowIdx) => (
              <tr key={rowIdx} className="hover:bg-muted/30 transition-colors">
                {row.map((cell, cellIdx) => {
                  const isRank = headers[cellIdx]?.toLowerCase() === "rang" || 
                                  headers[cellIdx]?.toLowerCase() === "n°";
                  return (
                    <td
                      key={cellIdx}
                      className={`px-4 py-2 border-b ${
                        isRank 
                          ? "text-center font-medium text-muted-foreground w-12"
                          : numericColumns[cellIdx]
                            ? "text-right font-mono tabular-nums"
                            : "text-left"
                      }`}
                    >
                      {cell}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {hasMore && (
        <div className="p-2 border-t bg-muted/30 flex justify-center">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setExpanded(!expanded)}
            className="text-xs"
          >
            {expanded ? "Voir moins" : `Voir les ${rows.length - 10} lignes supplémentaires`}
          </Button>
        </div>
      )}
    </div>
  );
}

// Parse markdown table to extract headers and rows
export function parseMarkdownTable(content: string): SmartTableProps | null {
  const lines = content.split('\n');
  
  // Find table lines
  const tableLines: string[] = [];
  let inTable = false;
  
  for (const line of lines) {
    if (line.trim().startsWith('|')) {
      tableLines.push(line);
      inTable = true;
    } else if (inTable && !line.trim().startsWith('|')) {
      break;
    }
  }
  
  if (tableLines.length < 2) return null;
  
  // Parse header (first line)
  const headerLine = tableLines[0];
  const headers = headerLine
    .split('|')
    .map(h => h.trim())
    .filter(h => h.length > 0);
  
  // Skip separator line (second line with ---)
  const dataLines = tableLines.slice(2);
  
  // Parse rows
  const rows = dataLines.map(line =>
    line
      .split('|')
      .map(c => c.trim())
      .filter((_, i, arr) => i > 0 && i < arr.length) // Remove first and last empty
  );
  
  if (headers.length === 0 || rows.length === 0) return null;
  
  return { headers, rows };
}

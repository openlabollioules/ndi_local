import * as XLSX from "xlsx";

/**
 * Exporte des données en CSV et télécharge le fichier
 */
export function exportToCSV(
  data: Record<string, unknown>[],
  filename = "export"
): void {
  if (data.length === 0) return;

  const headers = Object.keys(data[0]);
  const csvRows: string[] = [];

  // En-têtes
  csvRows.push(headers.join(";"));

  // Données
  for (const row of data) {
    const values = headers.map((header) => {
      const value = row[header];
      if (value === null || value === undefined) return "";
      const stringValue = String(value);
      // Échapper les guillemets et encadrer si nécessaire
      if (stringValue.includes(";") || stringValue.includes('"') || stringValue.includes("\n")) {
        return `"${stringValue.replace(/"/g, '""')}"`;
      }
      return stringValue;
    });
    csvRows.push(values.join(";"));
  }

  const csvContent = csvRows.join("\n");
  const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
  downloadBlob(blob, `${filename}.csv`);
}

/**
 * Exporte des données en XLSX et télécharge le fichier
 */
export function exportToXLSX(
  data: Record<string, unknown>[],
  filename = "export"
): void {
  if (data.length === 0) return;

  const worksheet = XLSX.utils.json_to_sheet(data);
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, worksheet, "Résultats");

  // Ajuster la largeur des colonnes
  const headers = Object.keys(data[0]);
  worksheet["!cols"] = headers.map((header) => ({
    wch: Math.max(
      header.length,
      ...data.map((row) => String(row[header] ?? "").length)
    ) + 2,
  }));

  XLSX.writeFile(workbook, `${filename}.xlsx`);
}

/**
 * Exporte des données en Parquet via l'API backend
 */
export async function exportToParquet(
  data: Record<string, unknown>[],
  filename = "export"
): Promise<void> {
  if (data.length === 0) return;

  try {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    // Add API key if available
    const apiKey = typeof window !== "undefined" ? localStorage.getItem("ndi_api_key") : null;
    if (apiKey) headers["X-API-Key"] = apiKey;

    const response = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api"}/export/parquet`,
      {
        method: "POST",
        headers,
        body: JSON.stringify({ data, filename }),
      }
    );

    if (!response.ok) {
      throw new Error("Erreur lors de l'export Parquet");
    }

    const blob = await response.blob();
    downloadBlob(blob, `${filename}.parquet`);
  } catch (error) {
    console.error("Erreur export Parquet:", error);
    throw error;
  }
}

/**
 * Télécharge un Blob comme fichier
 */
function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

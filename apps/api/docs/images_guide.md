# Guide Complet : Analyse et Ingestion d'Images

Ce guide couvre les 3 cas d'usage principaux pour travailler avec des images.

---

## 🎯 Les 3 Cas d'Usage

| # | Cas | Endpoint | Résultat |
|---|-----|----------|----------|
| 1 | **Analyser une photo** | `POST /images/analyze` | Description textuelle |
| 2 | **OCR / Extraction de texte** | `POST /images/analyze` (ocr) | Texte brut |
| 3 | **Extraire un tableau** | `POST /images/ingest` | Données ingérées en base |

---

## 1️⃣ Analyser une Photo (Description Générale)

### Cas d'usage
- Décrire le contenu d'une image
- Identifier des objets, scènes, personnes
- Analyser des graphiques/charts

### Commande
```bash
curl -X POST "http://localhost:8000/api/images/analyze" \
  -H "X-API-Key: your-api-key" \
  -F "file=@photo_navire.jpg" \
  -F "analysis_type=general"
```

### Réponse
```json
{
  "description": "Une photographie montrant un navire militaire de type frégate...",
  "confidence": 0.87,
  "objects_detected": ["navire", "mer", "ciel", "antennes"],
  "analysis_type": "general"
}
```

### Exemple Frontend (React)
```typescript
async function analyzePhoto(file: File) {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('analysis_type', 'general');

  const response = await fetch('/api/images/analyze', {
    method: 'POST',
    headers: { 'X-API-Key': API_KEY },
    body: formData,
  });

  return await response.json();
}
```

---

## 2️⃣ OCR - Extraction de Texte

### Cas d'usage
- Extraire du texte de documents scannés
- Numériser des rapports papier
- Récupérer du texte de captures d'écran

### Commande
```bash
curl -X POST "http://localhost:8000/api/images/analyze" \
  -H "X-API-Key: your-api-key" \
  -F "file=@document_scan.jpg" \
  -F "analysis_type=ocr"
```

### Réponse
```json
{
  "description": "RAPPORT MENSUEL - Février 2026\n\nTotal des ventes: 150 000€\nNombre de clients: 45\n...",
  "confidence": 0.92,
  "objects_detected": [],
  "analysis_type": "ocr"
}
```

### Prompt personnalisé
```bash
curl -X POST "http://localhost:8000/api/images/analyze" \
  -H "X-API-Key: your-api-key" \
  -F "file=@document.jpg" \
  -F "prompt=Extrais uniquement les dates et les montants en euros"
```

---

## 3️⃣ Extraire et Ingérer un Tableau de Données ⭐

### Cas d'usage
- Screenshot d'un Excel/Spreadsheet
- Photo d'un tableau papier
- Capture d'écran d'un dashboard
- Document scanné avec données tabulaires

### Commande (tout-en-un)
```bash
curl -X POST "http://localhost:8000/api/images/ingest" \
  -H "X-API-Key: your-api-key" \
  -F "file=@tableau_excel.jpg" \
  -F "table_name=ventes_q1"
```

### Réponse
```json
{
  "success": true,
  "table_name": "ventes_q1",
  "rows_ingested": 24,
  "columns": ["Produit", "Quantité", "Prix", "Total"],
  "analysis_preview": "| Produit | Quantité | Prix | Total |\n|---------|----------|------|-------|...",
  "message": "Successfully extracted and ingested 24 rows into 'ventes_q1'"
}
```

### Ce qui se passe automatiquement :
1. 🖼️ L'image est analysée pour extraire le tableau
2. 📝 Le markdown est converti en CSV
3. 📊 Les données sont ingérées dans DuckDB (ou JSON en mode NoSQL)
4. 🔍 L'indexation est lancée en arrière-plan

### Exemple avec curl et suivi

```bash
# 1. Ingestion
 curl -X POST "http://localhost:8000/api/images/ingest" \
   -H "X-API-Key: your-api-key" \
   -F "file=@screenshot_dashboard.png"

# 2. Vérifier les données ingérées
curl "http://localhost:8000/api/data/preview?table=screenshot_dashboard"

# 3. Interroger en NL
 curl -X POST "http://localhost:8000/api/conversation/query" \
   -H "Content-Type: application/json" \
   -d '{
     "question": "Quel est le total des ventes ?",
     "conversation_id": "test"
   }'
```

---

## 📊 Types d'Analysis Disponibles

| Type | Usage | Retour |
|------|-------|--------|
| `general` | Description générale | Texte libre |
| `ocr` | Extraction de texte | Texte brut |
| `objects` | Détection d'objets | Liste structurée |
| `chart` | Analyse de graphiques | Description + tendances |
| `data_table` | Extraction de tableau | Tableau markdown |

---

## 🔧 Prérequis

### 1. Installer un modèle vision
```bash
# Option 1: LLaVA (équilibre qualité/vitesse)
ollama pull llava

# Option 2: Moondream (léger, rapide)
ollama pull moondream

# Option 3: Qwen2.5-VL (très performant)
ollama pull qwen2.5-vl
```

### 2. Configurer l'API
```bash
# Dans apps/api/.env
NDI_VISION_MODEL=llava
```

### 3. Redémarrer l'API
```bash
# Ctrl+C puis
uv run uvicorn ndi_api.main:app --reload
```

---

## 💡 Conseils pour de Meilleurs Résultats

### Pour l'OCR
- 📷 Utilisez une bonne résolution (minimum 300 DPI pour les scans)
- 💡 Assurez un bon contraste (fond blanc, texte noir)
- 📐 Évitez les distorsions de perspective

### Pour l'extraction de tableaux
- 📏 L'image doit montrer le tableau ENTIER (pas coupé)
- 🔲 Les bordures des cellules doivent être visibles
- 📊 Évitez les couleurs de fond trop foncées

### Exemple d'image optimale
```
┌─────────┬──────────┬────────┐
│  Produit│ Quantité │  Prix  │  ← En-têtes clairs
├─────────┼──────────┼────────┤
│   A     │    10    │  50€   │  ← Lignes bien alignées
│   B     │    20    │  30€   │
└─────────┴──────────┴────────┘
```

---

## 🐛 Dépannage

### "Current model may not support vision"
```bash
# Solution: Installer un modèle vision
ollama pull llava
```

### "Could not extract valid table data"
- L'image ne contient pas de tableau clair
- Essayez avec `analysis_type=ocr` d'abord
- Vérifiez la qualité de l'image

### "Unable to open database file" (ChromaDB)
```bash
# Purger et redémarrer
curl -X POST "http://localhost:8000/api/ingest/purge"
# Redémarrer l'API
```

---

## 📱 Exemple Complet : Application React

```typescript
function ImageAnalyzer() {
  const [result, setResult] = useState(null);
  const [mode, setMode] = useState<'analyze' | 'ingest'>('analyze');

  async function handleFile(file: File) {
    const formData = new FormData();
    formData.append('file', file);

    const endpoint = mode === 'ingest' 
      ? '/api/images/ingest' 
      : '/api/images/analyze';
    
    if (mode === 'analyze') {
      formData.append('analysis_type', 'general');
    }

    const response = await fetch(endpoint, {
      method: 'POST',
      headers: { 'X-API-Key': API_KEY },
      body: formData,
    });

    const data = await response.json();
    setResult(data);
  }

  return (
    <div>
      <select value={mode} onChange={e => setMode(e.target.value)}>
        <option value="analyze">Juste analyser</option>
        <option value="ingest">Extraire & Ingérer tableau</option>
      </select>
      
      <input 
        type="file" 
        accept="image/*"
        onChange={e => e.target.files?.[0] && handleFile(e.target.files[0])}
      />
      
      {result && <pre>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
}
```

---

## 🔗 Résumé des Endpoints

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/images/analyze` | Analyser une image |
| POST | `/images/ingest` | Extraire tableau et ingérer |
| GET | `/images/supported-formats` | Formats supportés |

---

Besoin d'aide sur un cas spécifique ? Consultez les logs :
```bash
tail -f apps/api/logs/ndi_api.log
```
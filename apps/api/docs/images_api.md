# API d'Analyse d'Images

Cette API permet d'analyser des images en utilisant des modèles de vision (VLM) via Ollama.

## Configuration

### Prérequis

1. **Installer un modèle vision dans Ollama** :
   ```bash
   ollama pull llava           # ou bakllava, moondream, qwen2.5-vl
   ```

2. **Configurer le modèle vision** dans `.env` :
   ```bash
   NDI_VISION_MODEL=llava
   ```

   Si non configuré, l'API utilisera le modèle LLM par défaut.

## Endpoints

### 1. Analyser une Image

```bash
POST /api/images/analyze
```

**Paramètres** :
- `file` (required) : Fichier image (JPG, PNG, GIF, WebP, BMP)
- `prompt` (optional) : Prompt personnalisé pour l'analyse
- `analysis_type` (optional) : Type d'analyse
  - `general` : Description générale (défaut)
  - `ocr` : Extraction de texte
  - `objects` : Détection d'objets
  - `chart` : Analyse de graphiques
  - `data_table` : Extraction de tableaux de données

**Exemple** :
```bash
curl -X POST "http://localhost:8000/api/images/analyze" \
  -H "X-API-Key: your-api-key" \
  -F "file=@/path/to/image.jpg" \
  -F "analysis_type=general"
```

**Réponse** :
```json
{
  "description": "Une image montrant un navire militaire gris sur l'océan...",
  "confidence": 0.85,
  "objects_detected": ["navire", "océan", "ciel"],
  "analysis_type": "general"
}
```

### 2. Formats Supportés

```bash
GET /api/images/supported-formats
```

**Exemple** :
```bash
curl "http://localhost:8000/api/images/supported-formats"
```

**Réponse** :
```json
{
  "formats": [".bmp", ".png", ".jpeg", ".jpg", ".gif", ".webp"],
  "max_size_mb": 10.0,
  "max_dimension": 2048
}
```

## Limites

- **Taille maximale** : 10 Mo
- **Dimensions maximales** : 2048x2048 pixels
- **Formats supportés** : JPG, JPEG, PNG, GIF, WebP, BMP

## Modèles Recommandés

| Modèle | Description | Taille |
|--------|-------------|--------|
| `llava` | Bon équilibre qualité/vitesse | ~4GB |
| `bakllava` | Version optimisée de LLaVA | ~4GB |
| `moondream` | Léger et rapide | ~1.6GB |
| `qwen2.5-vl` | Très performant | ~8GB |
| `gemma3` | Google's vision model | ~4GB |

## Exemples d'Utilisation

### OCR (Reconnaissance de Texte)

```bash
curl -X POST "http://localhost:8000/api/images/analyze" \
  -H "X-API-Key: your-api-key" \
  -F "file=@document.jpg" \
  -F "analysis_type=ocr"
```

### Analyse de Graphique

```bash
curl -X POST "http://localhost:8000/api/images/analyze" \
  -H "X-API-Key: your-api-key" \
  -F "file=@chart.png" \
  -F "analysis_type=chart"
```

### Extraction de Tableau

```bash
curl -X POST "http://localhost:8000/api/images/analyze" \
  -H "X-API-Key: your-api-key" \
  -F "file=@table.jpg" \
  -F "analysis_type=data_table"
```

## Intégration avec le Frontend

Exemple de code React/TypeScript :

```typescript
async function analyzeImage(file: File, analysisType: string = 'general') {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('analysis_type', analysisType);

  const response = await fetch('/api/images/analyze', {
    method: 'POST',
    headers: {
      'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || '',
    },
    body: formData,
  });

  if (!response.ok) {
    throw new Error('Analysis failed');
  }

  return await response.json();
}
```

## Dépannage

### Erreur "Current model may not support vision"

Cette erreur apparaît si le modèle configuré n'est pas un modèle vision. Solution :

```bash
# Installer un modèle vision
ollama pull llava

# Mettre à jour le .env
NDI_VISION_MODEL=llava
```

### Erreur "Image too large"

L'image dépasse la limite de 10 Mo. Redimensionnez ou compressez l'image.

### Erreur "Unsupported format"

Convertissez l'image en JPG, PNG, GIF, WebP ou BMP.

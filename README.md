#Data Intelligence (NDI)

Application NL-to-Query permettant d'interroger des données locales en langage naturel (français). Supporte les modes **SQL** (DuckDB) et **NoSQL** (Documents JSON).


## 🚀 Fonctionnalités

- **Import de données** : Upload de fichiers CSV, XLSX, Parquet (lecture par chunks pour gros CSV)
- **Normalisation automatique** : Noms de colonnes (snake_case, whitelist de préfixes), déduplication des colonnes, conversion numérique et **détection de dates** (ISO, FR, US, DE)
- **Génération de dictionnaire de données** : Descriptions LLM par colonne (modèle dédié optionnel)
- **Vectorisation sémantique** : Indexation ChromaDB pour le RAG, avec reranking (lightweight ou Ollama)
- **Modélisation** : Diagramme ER interactif avec définition de relations PK/FK (mode SQL uniquement)
- **Chat NL-to-Query** : Interrogation en français avec génération SQL ou NoSQL (LangGraph), annulation de requête côté interface
- **Historique des conversations** : Fil de discussion conservé par conversation, restauré au changement d’onglet
- **Visualisation** : Graphiques (barres, lignes, camembert, aires, nuages de points, radar) suggérés automatiquement ou configurés manuellement (Recharts)
- **Agrégations avancées** (mode NoSQL) : Pipeline MongoDB-style avec `$project`, `$group`, `$dateToTime`, `$year`, `$month`, `$avg`, `$sum`, etc.
- **Skills métier** : Génération de skills structurés depuis un contexte brut ; **raffinement assisté** via questions ciblées du LLM puis régénération enrichie
- **Export** : CSV, XLSX, Parquet
- **Monitoring** : Logs structurés (query, audit, reasoning), métriques de performance par étape et endpoint `/api/health/performance`

## 🏗️ Architecture

```
NDI_V2/
├── apps/
│   ├── api/          # Backend FastAPI + LangGraph
│   │   └── logs/     # query.log, audit.log, reasoning.log, ingestion.log, indexing.log
│   └── web/          # Frontend Next.js + Tailwind
└── packages/         # Assets partagés
```

## 🛠️ Stack technique

### Backend
- Python 3.12 + uv
- FastAPI
- LangChain / LangGraph (pipeline NL-to-Query compilé une fois au démarrage)
- **DuckDB** (stockage SQL local) OU **JSON Documents** (stockage NoSQL)
- ChromaDB (vector store)
- Ollama (LLM + embeddings en local)

### Frontend
- Next.js 14+ (App Router)
- Tailwind CSS
- Shadcn/UI
- React Flow (diagramme ER)
- Recharts (visualisations)

## 📦 Installation

### Prérequis
- Python 3.12+
- Node.js 18+
- [Ollama](https://ollama.ai/) avec au moins un modèle LLM et un modèle d'embedding (ex. `bge-m3`)

### Backend

```bash
cd apps/api
uv sync
cp .env.example .env   # Puis éditer les variables
uv run uvicorn src.ndi_api.main:app --reload
```

### Frontend

```bash
cd apps/web
npm install
npm run dev
```

## ⚙️ Configuration

Fichier `.env` dans `apps/api/` (préfixe `NDI_`) :

| Variable | Description | Exemple |
|----------|-------------|---------|
| `NDI_DATABASE_MODE` | Mode base de données (`sql` ou `nosql`) | `sql` |
| `NDI_OLLAMA_BASE_URL` | URL Ollama | `http://localhost:11434` |
| `NDI_LLM_MODEL` | Modèle pour les requêtes NL-to-Query | `qwen3:8b` |
| `NDI_INDEXING_LLM_MODEL` | Modèle pour l'indexation / dictionnaire (optionnel) | `mistral-small3.2:latest` |
| `NDI_EMBEDDING_MODEL` | Modèle d'embedding | `bge-m3` |
| `NDI_DATA_DIR` | Répertoire des données | `data` |
| `NDI_CHROMA_DIR` | Répertoire ChromaDB | `data/chroma` |
| `NDI_CHROMA_COLLECTION` | Collection vectorielle | `schema_index` |
| `NDI_RETRIEVAL_K` | Nombre de documents récupérés avant rerank | `20` |
| `NDI_RERANKER_TYPE` | Type de reranker : `lightweight`, `ollama`, `none` | `lightweight` |
| `NDI_RERANKER_FINAL_K` | Nombre de documents après rerank (si utilisé) | `8` |

Exemple minimal :

```env
NDI_DATABASE_MODE=sql
NDI_OLLAMA_BASE_URL=http://localhost:11434
NDI_LLM_MODEL=qwen3:8b
NDI_EMBEDDING_MODEL=bge-m3
NDI_DATA_DIR=./data
NDI_CHROMA_DIR=./data/chroma
NDI_CHROMA_COLLECTION=ndi_schema
```

## 🎯 Utilisation

1. **Importer des données** : Onglet « Données » → Upload de fichiers (CSV, XLSX, Parquet).
2. **Indexer le schéma** (optionnel) : Lance l'indexation vectorielle et la génération des descriptions de colonnes.
3. **Définir les relations** (mode SQL) : Onglet « Modélisation » → Ajouter PK/FK.
4. **Interroger** : Onglet « Chat » → Poser des questions en français ; le bouton stop permet d'annuler une requête en cours. Les résultats peuvent être visualisés en graphiques (suggestion auto ou configuration manuelle).
5. **Skills métier** (optionnel) : Paramètres → Générer un skill depuis votre contexte, ou le raffiner via des questions ciblées pour l'enrichir.

### Mode de base de données

| Mode | Description | Stockage | Relations |
|------|-------------|----------|-----------|
| `sql` | Données relationnelles avec JOINs | DuckDB (`.duckdb`) | ✅ Tables liées par PK/FK |
| `nosql` | Données documentaires hiérarchiques | JSON (fichiers `.json`) | ❌ Données imbriquées dans les documents |

Changement de mode temporaire :
```bash
curl -X POST http://localhost:8000/api/health/database/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "nosql"}'
```

### Agrégations NoSQL (MongoDB-style)

Le mode NoSQL supporte les pipelines d'agrégation avec opérateurs MongoDB :

```json
{
  "collection": "commandes",
  "aggregate": [
    {
      "$project": {
        "date_commande": { "$dateToTime": "$CDE_DATE" },
        "ecart_jours": {
          "$divide": [
            { "$subtract": ["$date_livraison", "$date_commande"] },
            86400000
          ]
        }
      }
    },
    {
      "$group": {
        "_id": { "$year": "$date_commande" },
        "avg_ecart": { "$avg": "$ecart_jours" },
        "total": { "$sum": 1 }
      }
    }
  ]
}
```

**Opérateurs supportés :**
- `$dateToTime` : Conversion date → timestamp (ms)
- `$year`, `$month`, `$dayOfMonth` : Extraction de parties de date
- `$subtract`, `$divide`, `$multiply`, `$add` : Opérations arithmétiques
- `$avg`, `$sum`, `$min`, `$max`, `$count` : Agrégations
- `$project`, `$group`, `$sort`, `$limit` : Étapes de pipeline

**Formats de date auto-détectés :** ISO (`2023-12-31`), FR (`31/12/2023`), US (`12/31/2023`), DE (`31.12.2023`)

### Skills métier

Les skills encapsulent des règles, du vocabulaire et des exemples métier pour guider le LLM lors des requêtes. Workflow :

1. **Générer** : Saisir un contexte métier brut → le LLM produit un skill structuré (Markdown).
2. **Raffiner** : Cliquer sur « Raffiner » → le LLM pose 3 questions ciblées sur ce qui manque.
3. **Répondre** : Renseigner les champs puis « Régénérer le skill » → le skill est enrichi et réinjecté.

Endpoints API : `POST /api/skills/generate`, `POST /api/skills/refine`, `POST /api/skills/regenerate`, `POST /api/skills/inject`, `GET /api/skills/active`, `DELETE /api/skills/active`.

## 📊 Santé et performances

- **GET /api/health** : état de l'API.
- **GET /api/health/config** : configuration exposée (modèles, reranker, database_mode, etc.).
- **GET /api/health/performance** : statistiques agrégées par étape du pipeline (count, avg, min, max, p95).
- **GET /api/health/database/mode** : mode de base de données courant et plugins disponibles.

Les logs détaillés sont dans `apps/api/logs/` (query, audit, reasoning, ingestion, indexing).

**ChromaDB « no such table: tenants »** : après une mise à jour de ChromaDB, un ancien répertoire de données peut être incompatible. Supprimez le dossier configuré dans `NDI_CHROMA_DIR` (ex. `data/chroma`) puis relancez l’indexation du schéma depuis l’interface.

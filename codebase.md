# NDI (Natural Data Intelligence) - Base de Connaissance

## Vue d'ensemble

NDI est une application **NL-to-Query** permettant d'interroger des données locales en langage naturel (français). Elle supporte deux modes :
- **SQL** : Base relationnelle DuckDB avec JOINs
- **NoSQL** : Base documentaire JSON (style MongoDB) sans JOINs

## Architecture

```
NDI/
├── apps/
│   ├── api/          # Backend FastAPI + LangGraph
│   │   ├── agents/   # Mémoire et skills des agents
│   │   ├── docs/     # Documentation technique
│   │   ├── scripts/  # Scripts utilitaires
│   │   ├── src/ndi_api/
│   │   │   ├── api/        # Routes et router
│   │   │   ├── plugins/    # Plugins SQL/NoSQL
│   │   │   ├── schemas/    # Schémas Pydantic
│   │   │   ├── services/   # Services métier
│   │   │   ├── main.py     # Point d'entrée FastAPI
│   │   │   └── settings.py # Configuration
│   │   └── tests/    # Tests unitaires
│   └── web/          # Frontend Next.js + Tailwind
│       ├── src/
│       │   ├── app/        # Pages Next.js
│       │   ├── components/ # Composants React
│       │   ├── hooks/      # Hooks personnalisés
│       │   └── lib/        # Utilitaires
│       └── public/   # Assets statiques
└── codebase.md       # Ce fichier
```

## Backend (apps/api)

### Stack Technique
- **Python 3.12** avec `uv` pour la gestion des dépendances
- **FastAPI** - Framework web async
- **LangChain / LangGraph** - Pipeline NL-to-Query
- **DuckDB** - Base SQL locale
- **ChromaDB** - Vector store pour le RAG
- **Ollama** - LLM et embeddings en local
- **chardet** - Détection d'encodage des fichiers

### Configuration (.env)

Variables principales (préfixe `NDI_`) :

| Variable | Description | Défaut |
|----------|-------------|--------|
| `NDI_DATABASE_MODE` | Mode base: `sql` ou `nosql` | `sql` |
| `NDI_OLLAMA_BASE_URL` | URL Ollama | requis |
| `NDI_LLM_MODEL` | Modèle LLM principal | requis |
| `NDI_INDEXING_LLM_MODEL` | Modèle pour l'indexation (optionnel) | - |
| `NDI_EMBEDDING_MODEL` | Modèle d'embedding | requis |
| `NDI_DATA_DIR` | Répertoire des données | `data` |
| `NDI_CHROMA_DIR` | Répertoire ChromaDB | `data/chroma` |
| `NDI_RETRIEVAL_K` | Documents récupérés avant rerank | `20` |
| `NDI_RERANKER_TYPE` | Type de reranker: `lightweight`, `ollama`, `none` | `lightweight` |
| `NDI_RERANKER_FINAL_K` | Documents après rerank | `8` |
| `NDI_API_KEY` | Clé API pour l'authentification | - |
| `NDI_AUTH_ENABLED` | Activer l'authentification | `true` |

### Structure du Backend

#### 1. Plugins (`src/ndi_api/plugins/`)

Système de plugins pour supporter SQL et NoSQL :

**`base.py`** - Interface abstraite `DataPlugin` :
- `initialize()`, `close()`, `purge()`
- `ingest_dataframe()`, `read_file()`
- `list_tables()`, `get_schema()`, `get_table_schema()`
- `execute_query()`, `preview_table()`
- `get_query_context()`, `validate_query()`, `get_system_prompt()`
- `supports_relations()`, `get_relations()`, `save_relation()`

**`sql_plugin.py`** - Plugin DuckDB :
- Stockage dans fichier `.duckdb`
- Support des relations PK/FK
- Normalisation des noms de colonnes (snake_case)
- Détection automatique des dates

**`nosql_plugin.py`** - Plugin JSON :
- Stockage en documents JSON
- Pas de relations (données imbriquées)
- Requêtes style MongoDB

**`manager.py`** - PluginManager (singleton) :
- Gestion du cycle de vie des plugins
- Basculement dynamique SQL ↔ NoSQL
- `get_plugin_manager()`, `get_plugin()`

#### 2. Services (`src/ndi_api/services/`)

**`nl_sql.py`** - Pipeline LangGraph NL-to-Query :
- Graph d'états : `route` → `schema_context` → `sql_generate` → `sql_execute` → `sql_correct` → `response`
- Validation SQL en lecture seule uniquement
- Cache des résultats
- Monitoring des performances par étape

**`agent_prompts.py`** - Gestion des prompts agents :
- Chargement de `AGENTS.md` (mémoire globale)
- Chargement des skills (`SKILL.md`) selon le mode
- Injection des skills de session
- Cache LRU des prompts

**`indexing.py`** - Indexation vectorielle :
- Génération des descriptions de colonnes (batch LLM)
- Indexation dans ChromaDB
- Support stats de colonnes (optionnel)

**`vector_store.py`** - Gestion ChromaDB :
- `upsert_documents()`, `query_documents()`
- Gestion des collections

**`reranker.py`** - Re-ranking des résultats :
- Reranker léger (cross-encoder)
- Reranker Ollama (optionnel)

**`image_agent.py`** - Agent d'analyse d'images :
- Détection d'intent : `describe`, `ocr`, `extract_table`, `ingest_table`, `chart`
- Extraction de tableaux depuis les images
- Ingestion sécurisée (avec validation)
- Utilise le skill `image-ingest`

**`image_analysis.py`** - Service d'analyse d'images :
- OCR, description, extraction de tableaux
- Intégration avec le VLM Ollama

**`ingestion.py`** - Ingestion de fichiers :
- Support CSV (tous encodages via `chardet`), XLSX, Parquet
- Lecture par chunks pour les gros fichiers
- Normalisation automatique
- Prévisualisation et sélection des feuillets Excel
- Détection automatique des encodages (UTF-8, ISO-8859-1, Windows-1252, etc.)

**`conversation_memory.py`** - Gestion des conversations :
- Stockage des conversations actives
- Fil de discussion par conversation

**`session_skills.py`** - Skills éphémères :
- Injection temporaire de skills métier
- Génération et raffinement via LLM

**`monitoring.py`** - Monitoring et logs :
- Logs structurés (query, audit, reasoning, ingestion, indexing)
- Métriques de performance
- Endpoint `/api/health/performance`

**`llm.py`** - Gestion des LLMs :
- Connexion à Ollama
- Modèle principal et modèle d'indexation

**`cache.py`** - Cache applicatif :
- Cache des requêtes NL-SQL
- Cache du hash du schéma

**`rate_limiter.py`** - Rate limiting :
- Protection des endpoints
- Configuration via `slowapi`

#### 3. Routes API (`src/ndi_api/api/routes/`)

| Route | Description |
|-------|-------------|
| `health.py` | Santé, config, performance, mode DB, cache |
| `ingest.py` | Upload et ingestion de fichiers |
| `ingest.py` | `POST /excel/sheets` - Prévisualisation des feuillets Excel |
| `ingest.py` | `POST /excel/upload` - Upload Excel avec sélection de feuillets |
| `index.py` | Indexation du schéma (vector store) |
| `query.py` | Requêtes NL-to-Query |
| `schema.py` | Informations sur le schéma |
| `relations.py` | Gestion des relations PK/FK (SQL) |
| `data.py` | Preview des données |
| `export.py` | Export CSV/XLSX/Parquet |
| `vectorstore.py` | Gestion du vector store |
| `conversation.py` | Gestion des conversations |
| `skills.py` | Gestion des skills métier |
| `images.py` | Analyse d'images |
| `eval.py` | Évaluation des requêtes |

#### 4. Schémas (`src/ndi_api/schemas/`)

- `ingest.py` - Schémas d'ingestion (IngestSummary, PurgeResponse, ExcelSheetInfo, ExcelSheetsResponse, SheetSelection, ExcelIngestRequest)
- `query.py` - Schémas de requête
- `schema.py` - Schémas de schéma
- `relations.py` - Schémas de relations
- `data.py` - Schémas de données
- `status.py` - Schémas de statut

### Agents et Skills (`agents/`)

#### AGENTS.md - Mémoire globale

Définit la personnalité et les règles de base :
- Rôle : Assistant NDI spécialisé NL-to-Query
- Langue : Français (sauf termes techniques)
- Ton : Professionnel, précis, accessible
- Sécurité : Requêtes en lecture seule uniquement
- Conventions : Respect strict des noms de colonnes du schéma

#### Skills (`agents/skills/`)

**`sql-query/SKILL.md`** - Génération SQL :
- Règles strictes pour DuckDB
- Fonctions utiles (dates, texte, agrégation)
- Exemples de requêtes
- Interdiction : pas de JOIN sans relation déclarée

**`nosql-query/SKILL.md`** - Génération NoSQL :
- Syntaxe JSON compacte (une seule ligne)
- Opérateurs : `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$exists`, `$regex`, `$ilike`
- Agrégations : `$sum`, `$avg`, `$count`, `$min`, `$max`
- Pipeline `$group` avec syntaxe `{"by": ..., "agg": {...}}`
- Opérateurs de date : `$year`, `$month`, `$day`, `$quarter`, `$week`
- Règle ultra-critique : `},"aggregate"` (jamais `}},"aggregate`)

**`image-ingest/SKILL.md`** - Ingestion d'images :
- Validation des données extraites
- Conventions de nommage (préfixe `img_`)
- Limites de sécurité (10k lignes, 100 colonnes)

**`open-analysis/SKILL.md`** - Analyse ouverte :
- Analyse exploratoire des données
- Suggestions de visualisations

**`chart-gen/SKILL.md`** - Génération de graphiques :
- Configuration Recharts
- Types de graphiques supportés

### Pipeline NL-to-Query (LangGraph)

```
┌─────────┐    ┌────────────────┐    ┌───────────────┐    ┌─────────────┐
│  START  │───→│     route      │───→│schema_context │───→│sql_generate │
└─────────┘    └────────────────┘    └───────────────┘    └──────┬──────┘
                                                                  │
    ┌─────────────────────────────────────────────────────────────┘
    ↓
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌────────┐
│ sql_execute │───→│{error?}     │───→│ sql_correct │───→│response│
└─────────────┘    └──────┬──────┘    └─────────────┘    └───┬────┘
                          │{ok}                               │
                          └───────────────────────────────────→└──────┐
                                                                      ↓
                                                                ┌─────────┐
                                                                │   END   │
                                                                └─────────┘
```

**Étapes détaillées :**

1. **`_route`** - Détermine le type de requête
2. **`_schema_context`** - Récupère le contexte schéma :
   - Vector search (ChromaDB) avec reranking
   - Filtrage selon le mode (SQL/NoSQL)
   - Extraction des relations (SQL uniquement)
   - Scoring des tables par pertinence
3. **`_sql_generate`** - Génère la requête avec LLM
4. **`_sql_execute`** - Exécute la requête :
   - Validation de sécurité (lecture seule)
   - Exécution via le plugin
5. **`_sql_correct`** - Corrige en cas d'erreur (max 2 tentatives)
6. **`_response`** - Formate la réponse :
   - Résultats scalaires (count/sum/avg) → formatage direct
   - Autres résultats → tableaux Markdown

**Sécurité SQL :**
- Mots-clés autorisés : SELECT, FROM, WHERE, JOIN, GROUP BY, etc.
- Mots-clés interdits : DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, TRUNCATE
- La requête doit commencer par SELECT ou WITH

## Frontend (apps/web)

### Stack Technique
- **Next.js 15+** (App Router)
- **React 19**
- **TypeScript**
- **Tailwind CSS**
- **Shadcn/UI** - Composants UI
- **React Flow** - Diagramme ER
- **Recharts** - Visualisations
- **Lucide React** - Icônes

### Structure

#### Pages (`src/app/`)
- `page.tsx` - Page principale (rend MainShell)
- `layout.tsx` - Layout racine avec providers

#### Composants (`src/components/`)

**`shell/main-shell.tsx`** - Interface principale :
- Sidebar avec sélecteur de mode (SQL/NoSQL)
- Sélecteur de modèle Ollama
- Historique des conversations
- Gestion des onglets (Chat, Données, Modélisation, Vector Store, Skills)

**`chat/chat-interface.tsx`** - Interface de chat :
- Zone de saisie des questions
- Affichage des réponses
- Visualisations des résultats
- Bouton d'annulation des requêtes

**`chat/chart-renderer.tsx`** - Rendu des graphiques :
- Support : barres, lignes, camembert, aires, nuages de points, radar
- Configuration manuelle ou suggestion automatique

**`chat/smart-table.tsx`** - Tableau de résultats :
- Pagination
- Tri
- Redimensionnement

**`chat/markdown-renderer.tsx`** - Rendu Markdown :
- Support GFM (GitHub Flavored Markdown)
- Tableaux, code, listes

**`er-diagram.tsx`** - Diagramme ER :
- Visualisation des tables et relations
- React Flow pour l'interactivité

**`skill-manager.tsx`** - Gestion des skills :
- Génération de skills depuis contexte
- Raffinement assisté (questions/réponses)
- Injection de skills

**`excel-sheet-preview.tsx`** - Prévisualisation des feuillets Excel :
- Liste des feuillets avec nombre de lignes/colonnes
- Aperçu des colonnes et données (3 premières lignes)
- Sélection/désélection individuelle ou par lot
- Upload des feuillets sélectionnés uniquement

#### Hooks (`src/hooks/`)

- `use-chat.ts` - Gestion du chat
- `use-conversation.ts` - Gestion des conversations
- `use-ingest.ts` - Gestion de l'ingestion
- `use-model.ts` - Gestion des modèles Ollama
- `use-preview.ts` - Preview des données
- `use-schema.ts` - Gestion du schéma

#### Librairies (`src/lib/`)

- `api.ts` - Client API (fetch wrappers)
- `export.ts` - Export CSV/XLSX/Parquet
- `utils.ts` - Utilitaires (cn, formatters)

### Interface Utilisateur

#### Onglets

1. **Chat** - Interface de conversation NL-to-Query
   - Historique des messages
   - Visualisations des résultats
   - Export des résultats

2. **Données** - Gestion des données
   - Upload de fichiers (CSV, XLSX, Parquet)
   - **Sélection des feuillets Excel** - Prévisualisation et sélection avant ingestion
   - Preview des tables/collections
   - Purge des données
   - Réindexation
   - Vider le cache (schéma/requêtes/prompts uniquement)

3. **Modélisation** (SQL uniquement) - Relations entre tables
   - Diagramme ER interactif
   - Définition des PK/FK
   - Visualisation des relations

4. **Vector Store** - Gestion ChromaDB
   - Collections disponibles
   - Documents indexés
   - Recherche sémantique
   - Health check

5. **Skills** - Gestion des skills métier
   - Génération depuis contexte
   - Raffinement assisté
   - Skills actifs

#### Sidebar

- Logo NDI
- Indicateur de mode (Local)
- Sélecteur de mode Database (SQL/NoSQL)
- Indicateur du mode actif
- Sélecteur de modèle Ollama
- Bouton "Charger le modèle"
- Indicateur du modèle actif
- Historique des conversations
- Bouton "Nouvelle conversation"

## Flux de Données

### Ingestion

**Fichiers CSV/Parquet :**
```
Fichier (CSV/Parquet)
    ↓
[POST /api/ingest/upload]
    ↓
Ingestion Service
    ↓
├─→ Détection d'encodage (chardet) pour CSV
├─→ Lecture par chunks (gros fichiers)
├─→ Normalisation des colonnes (snake_case)
├─→ Détection des dates
├─→ Dédoublonnage
└─→ Stockage (DuckDB ou JSON)
    ↓
Réponse SSE (progression en temps réel)
```

**Fichiers Excel (.xlsx/.xls) :**
```
Fichier Excel
    ↓
[POST /api/ingest/excel/sheets]
    ↓
Prévisualisation des feuillets
    ↓
Sélection des feuillets à ingérer
    ↓
[POST /api/ingest/excel/upload]
    ↓
Ingestion des feuillets sélectionnés
    ↓
Tables créées : {fichier}_{feuillet}
```

### Requête NL-to-Query

```
Question (français)
    ↓
[POST /api/query]
    ↓
NL-SQL Pipeline (LangGraph)
    ↓
├─→ Vector Search (ChromaDB) → Reranking
├─→ Génération SQL/JSON avec LLM
├─→ Validation sécurité
├─→ Exécution via Plugin
└─→ Formatage réponse
    ↓
Réponse (Markdown + données)
```

### Indexation

```
Schéma existant
    ↓
[POST /api/index]
    ↓
Indexing Service
    ↓
├─→ Génération descriptions colonnes (LLM batch)
├─→ Création documents (tables + colonnes)
└─→ Upsert dans ChromaDB
    ↓
Confirmation
```

## Points Clés d'Architecture

### Dual Mode (SQL / NoSQL)

Le système supporte deux modes de stockage interchangeables :

| Aspect | SQL (DuckDB) | NoSQL (JSON) |
|--------|--------------|--------------|
| Stockage | Fichier `.duckdb` | Fichiers `.json` |
| Relations | ✅ PK/FK avec JOINs | ❌ Données imbriquées |
| Requêtes | SQL standard | JSON style MongoDB |
| Agrégations | SQL GROUP BY | Pipeline `$group` |
| Recherche texte | `ILIKE` | `$ilike` |

Basculement dynamique via `POST /api/health/database/mode`

### Sécurité

1. **Requêtes en lecture seule uniquement**
   - Liste blanche de mots-clés SQL
   - Validation avec `sqlparse`
   - Pas de `INSERT`, `UPDATE`, `DELETE`, `DROP`

2. **Authentification API Key**
   - Header `X-API-Key` ou `Authorization: Bearer`
   - Désactivable via `NDI_AUTH_ENABLED=false`

3. **Rate Limiting**
   - Protection contre les abus
   - Configurable via `slowapi`

4. **Ingestion sécurisée depuis images**
   - Validation des données extraites
   - Limites de taille (10k lignes, 100 colonnes)
   - Pas d'écrasement de tables existantes

### Performance

1. **Cache multi-niveaux**
   - Cache des requêtes NL-SQL (avec invalidation au changement de schéma)
   - Cache du hash du schéma
   - Cache des prompts agents (LRU)
   - **Note** : Le bouton "Vider le cache" vide uniquement les caches applicatifs (schéma, requêtes, prompts) mais conserve le vector store. Pour purger ChromaDB, utilisez "Purger Vector Store".

2. **Reranking**
   - Récupération de K documents (20 par défaut)
   - Reranking pour sélectionner les K finals (8 par défaut)

3. **Optimisations LLM**
   - Traitement par batch pour les descriptions de colonnes
   - Formatage direct des résultats scalaires (pas d'appel LLM)
   - Truncation des résultats pour le contexte LLM

4. **Ingestion par chunks**
   - Lecture progressive des gros fichiers CSV
   - Progression en temps réel (SSE)

### Monitoring

Logs structurés dans `apps/api/logs/` :
- `query.log` - Requêtes utilisateur
- `audit.log` - Événements de sécurité
- `reasoning.log` - Prompts et raisonnements LLM
- `ingestion.log` - Ingestion de données
- `indexing.log` - Indexation vectorielle

Endpoint `/api/health/performance` :
- Statistiques agrégées par étape
- Count, avg, min, max, p95

## Développement

### Lancer le Backend

```bash
cd apps/api
uv sync
cp .env.example .env  # Éditer les variables
uv run uvicorn src.ndi_api.main:app --reload
```

### Lancer le Frontend

```bash
cd apps/web
npm install
npm run dev
```

### Tests

```bash
cd apps/api
uv run pytest tests/
```

### Structure des Fichiers Importants

```
api/src/ndi_api/
├── main.py                 # FastAPI app
├── settings.py             # Configuration Pydantic
├── api/
│   ├── router.py           # Routeur principal
│   └── routes/             # Routes API
├── plugins/
│   ├── base.py             # Interface DataPlugin
│   ├── sql_plugin.py       # Plugin DuckDB
│   ├── nosql_plugin.py     # Plugin JSON
│   └── manager.py          # Gestionnaire de plugins
├── services/
│   ├── nl_sql.py           # Pipeline LangGraph
│   ├── agent_prompts.py    # Gestion des prompts
│   ├── indexing.py         # Indexation ChromaDB
│   ├── image_agent.py      # Agent d'images
│   └── ...
└── schemas/                # Schémas Pydantic

web/src/
├── app/
│   ├── layout.tsx
│   └── page.tsx
├── components/
│   ├── shell/main-shell.tsx
│   ├── chat/
│   │   ├── chat-interface.tsx
│   │   ├── chart-renderer.tsx
│   │   └── smart-table.tsx
│   ├── excel-sheet-preview.tsx  # Prévisualisation Excel
│   └── er-diagram.tsx
├── hooks/
└── lib/
    └── api.ts
```

## Conventions de Code

### Backend (Python)

- Typage strict avec `typing`
- Docstrings Google style
- `__future__` annotations pour compatibilité
- Dataclasses pour les structures de données
- Logging structuré

### Frontend (TypeScript)

- Types stricts
- Hooks personnalisés pour la logique métier
- Composants fonctionnels avec hooks
- Tailwind pour le styling
- Shadcn/UI comme base de composants

## Dépannage

### Problèmes d'encodage CSV

L'application détecte automatiquement l'encodage des fichiers CSV via `chardet`. Si un fichier pose problème :
- L'encodage est détecté automatiquement (UTF-8, ISO-8859-1, Windows-1252, etc.)
- Fallback sur `latin-1` si la détection échoue

### ChromaDB "no such table: tenants"

Solution : Supprimer le dossier `NDI_CHROMA_DIR` (ex: `data/chroma`) et relancer l'indexation.

### Changement de mode SQL/NoSQL

```bash
curl -X POST http://localhost:8000/api/health/database/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "nosql"}'
```

### Invalider le cache (sans supprimer le vector store)

```bash
curl -X POST http://localhost:8000/api/health/cache/invalidate
```

**Note** : Cette commande vide les caches applicatifs (schéma, requêtes, prompts, connexion ChromaDB) mais conserve les données indexées dans le vector store.

## Résumé des fonctionnalités récentes

### Cache vs Purge

| Action | Effet sur les caches | Effet sur Vector Store |
|--------|---------------------|------------------------|
| **Vider le cache** | ✅ Vide schéma, requêtes, prompts, connexion ChromaDB | ✅ **Conservé** |
| **Purger les données** | ✅ Vide tout | ❌ Supprime tout (DuckDB + ChromaDB) |
| **Purger Vector Store** | - | ❌ Supprime uniquement ChromaDB |

### Ingestion de fichiers

| Format | Encodage | Feuillets/Sélection |
|--------|----------|---------------------|
| **CSV** | Auto-détection (chardet) + fallback latin-1 | N/A |
| **Excel (.xlsx/.xls)** | Natif | ✅ Sélection interactive des feuillets |
| **Parquet** | Natif | N/A |

### API Endpoints Excel

| Endpoint | Description |
|----------|-------------|
| `POST /api/ingest/excel/sheets` | Prévisualise tous les feuillets d'un fichier Excel |
| `POST /api/ingest/excel/upload` | Upload avec sélection spécifique de feuillets |

Les feuillets sélectionnés sont ingérés comme tables séparées nommées `{fichier}_{feuillet}`.

## Ressources

- [DuckDB Documentation](https://duckdb.org/docs/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [ChromaDB Documentation](https://docs.trychroma.com/)
- [Ollama Documentation](https://ollama.ai/)
- [Next.js Documentation](https://nextjs.org/docs)
- [Shadcn/UI Documentation](https://ui.shadcn.com/)

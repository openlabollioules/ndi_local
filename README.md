# Naval Data Intelligence (NDI)

Application d'interrogation de donnees en langage naturel (francais). Convertit des questions en requetes **SQL** (DuckDB) ou **NoSQL** (JSON/MongoDB-style) via un pipeline LLM (LangGraph).

Mode recommande : **web + api + qdrant dans Docker**, avec **Ollama lance sur le Mac hote**.

## Demarrage en 2 minutes

```bash
# 1. Lancer Ollama sur le Mac
ollama serve
ollama pull qwen3.6:35b
ollama pull bge-m3:latest

# 2. Configurer l'app
cd apps/api
cp .env.example .env

# 3. Lancer la stack
cd ../..
docker compose up -d --build
```

Acces :

- Frontend : `http://localhost:3001`
- API : `http://localhost:8001/api`
- Docs API : `http://localhost:8001/docs`
- Qdrant : `http://localhost:6333/dashboard`

---

## Table des matieres

1. [Prerequis](#prerequis)
2. [Architecture](#architecture)
3. [Installation rapide](#installation-rapide)
4. [Configuration](#configuration)
5. [Modes de lancement](#modes-de-lancement)
6. [Ports et acces](#ports-et-acces)
7. [Utilisation](#utilisation)
8. [Fonctionnalites](#fonctionnalites)
9. [API Endpoints](#api-endpoints)
10. [Skills](#skills)
11. [Modes SQL / NoSQL](#modes-sql--nosql)
12. [Logs et monitoring](#logs-et-monitoring)
13. [Troubleshooting](#troubleshooting)

---

## Prerequis

| Outil | Version | Usage |
|-------|---------|-------|
| **Docker** ou **Podman** | recent | Stack conteneurisee (web, api, qdrant) |
| **Ollama** | latest | LLM local sur Mac pour generation et embeddings |

---

## Architecture

```
naval_data_intelligence/
├── docker-compose.yml              # Stack conteneurisee (web + api + qdrant)
├── apps/
│   ├── api/                        # Backend Python (FastAPI)
│   │   ├── pyproject.toml          # Dependances Python
│   │   ├── .env                    # Variables d'environnement
│   │   ├── .env.example            # Template de configuration
│   │   ├── agents/
│   │   │   ├── AGENTS.md           # Persona et regles globales de l'agent
│   │   │   └── skills/             # Definitions des skills (SKILL.md)
│   │   │       ├── sql-query/
│   │   │       ├── nosql-query/
│   │   │       ├── chart-gen/
│   │   │       ├── compare/
│   │   │       ├── data-quality/
│   │   │       ├── data-conformity/
│   │   │       ├── image-ingest/
│   │   │       ├── kpi-dashboard/
│   │   │       ├── maintenance-navale/
│   │   │       ├── open-analysis/
│   │   │       ├── query-explain/
│   │   │       └── summarize/
│   │   ├── data/                   # Donnees locales (cree au runtime)
│   │   │   ├── ndi.duckdb          # Base SQL (DuckDB)
│   │   │   ├── collections/        # Documents JSON (mode NoSQL)
│   │   │   └── qdrant/             # Stockage Qdrant (bind mount Docker)
│   │   ├── logs/                   # Logs structures
│   │   ├── src/ndi_api/
│   │   │   ├── main.py             # Point d'entree FastAPI
│   │   │   ├── settings.py         # Configuration (lecture du .env)
│   │   │   ├── constants.py        # Constantes (mots-cles SQL interdits, etc.)
│   │   │   ├── api/
│   │   │   │   ├── router.py       # Routeur principal
│   │   │   │   ├── dependencies.py # Injection de dependances (plugin, auth)
│   │   │   │   └── routes/         # Modules de routes (voir section API)
│   │   │   ├── plugins/            # Abstraction base de donnees
│   │   │   │   ├── base.py         # Interface DataPlugin
│   │   │   │   ├── sql_plugin.py   # Implementation DuckDB
│   │   │   │   ├── nosql_plugin.py # Implementation JSON/MongoDB-style
│   │   │   │   └── manager.py      # PluginManager (singleton)
│   │   │   ├── services/           # Logique metier
│   │   │   │   ├── nl_sql.py       # Pipeline LangGraph NL-to-SQL
│   │   │   │   ├── llm.py          # Client LLM (OpenAI-compatible)
│   │   │   │   ├── vector_store.py # Integration Qdrant
│   │   │   │   ├── ingestion.py    # Upload et parsing de fichiers
│   │   │   │   ├── indexing.py     # Indexation schema + embeddings
│   │   │   │   ├── open_analysis.py # Analyse ouverte
│   │   │   │   ├── agent_prompts.py # Chargement AGENTS.md + SKILL.md
│   │   │   │   ├── reranker.py     # Reranking des documents retrieves
│   │   │   │   ├── image_agent.py  # Agent vision (analyse d'images)
│   │   │   │   ├── conformity.py   # Audit de conformite
│   │   │   │   ├── cache.py        # Cache requetes/schema
│   │   │   │   ├── auth.py         # Authentification API key
│   │   │   │   ├── rate_limiter.py # Rate limiting (SlowAPI)
│   │   │   │   └── monitoring.py   # Metriques de performance
│   │   │   └── skills/             # Implementations Python des skills
│   │   │       ├── base.py         # Classe abstraite SkillBase
│   │   │       ├── router.py       # Routage intent -> skill
│   │   │       └── registry.py     # Auto-decouverte des skills
│   └── web/                        # Frontend React/Next.js
│       ├── package.json
│       ├── src/
│       │   ├── app/                # Pages Next.js (App Router)
│       │   ├── components/
│       │   │   ├── shell/          # Layout principal
│       │   │   ├── chat/           # Interface de chat
│       │   │   ├── chart/          # Graphiques (Recharts)
│       │   │   ├── tabs/           # Onglets
│       │   │   └── ui/             # Composants Shadcn/UI
│       │   ├── hooks/              # Hooks React
│       │   ├── lib/                # Utilitaires (api.ts, etc.)
│       │   └── contexts/           # Contexte React global
│       └── tailwind.config.ts
└── README.md
```

### Stack technique

| Composant | Technologies |
|-----------|-------------|
| **Backend** | Python 3.12, FastAPI, Uvicorn, LangChain, LangGraph, DuckDB, Qdrant, Pandas, Polars |
| **Frontend** | Next.js 15, React 19, TypeScript, TailwindCSS, Shadcn/UI, Recharts, React Flow |
| **Vector DB** | Qdrant (Docker/Podman) |
| **LLM** | Tout serveur OpenAI-compatible (vLLM, Ollama, LiteLLM, etc.) |

---

## Installation rapide

### 1. Cloner le projet

```bash
git clone <url-du-repo>
cd naval_data_intelligence
```

### 2. Preparer Ollama sur le Mac hote

```bash
ollama serve
ollama pull qwen3:14b
ollama pull nomic-embed-text
ollama pull llava
```

### 3. Configurer l'application

```bash
cd apps/api
cp .env.example .env
# Editer .env pour votre instance Ollama locale si besoin
```

### 4. Lancer toute la stack conteneurisee

```bash
cd ../..
docker compose up -d --build
```

Le `docker-compose.yml` lance :
- `web` sur `http://localhost:3001`
- `api` sur `http://localhost:8001`
- `qdrant` sur `http://localhost:6333`

Sur macOS, l'API conteneurisee contacte Ollama via `http://host.docker.internal:11434`.

> Ports actuels du projet : `3001` pour le frontend et `8001` pour l'API. Cela evite les conflits avec d'autres services locaux deja presents sur `3000` et `8000`.

> **Environnement securise (pas d'acces registre)** : si l'image Qdrant est deja presente localement, le `docker-compose.yml` utilise `pull_policy: never` pour eviter tout pull distant.

---

## Modes de lancement

### Mode unique recommande : stack Docker standalone

Le projet est maintenant pense pour un usage standalone local :

- `web`, `api` et `qdrant` tournent en conteneurs
- `ollama` tourne sur l'hote macOS
- l'API conteneurisee joint Ollama via `host.docker.internal`

Commandes :

```bash
docker compose up -d --build
docker compose down
```

---

## Ports et acces

### Ports actuels du projet

| Service | Port hote | URL |
|---------|-----------|-----|
| **Frontend NDI** | `3001` | http://localhost:3001 |
| **API NDI** | `8001` | http://localhost:8001/api |
| **Docs API** | `8001` | http://localhost:8001/docs |
| **Qdrant** | `6333` | http://localhost:6333/dashboard |
| **Qdrant gRPC** | `6334` | `localhost:6334` |

### Pourquoi `3001` et `8001`

Le projet est actuellement configure ainsi pour eviter des conflits locaux frequents :

- `3000` est souvent utilise par d'autres interfaces web locales
- `8000` est souvent utilise par d'autres APIs ou services Python

Si vous n'avez aucun conflit, vous pouvez remettre `3000` et `8000` dans `docker-compose.yml`.

### Conflits frequents

Exemples observes sur cette machine :

- `open-webui` sur `3000`
- `duckdb-uploader` sur `8000`

Pour diagnostiquer un conflit :

```bash
docker ps
lsof -nP -iTCP:3000 -sTCP:LISTEN
lsof -nP -iTCP:8000 -sTCP:LISTEN
```

---

## Configuration

Toutes les variables sont dans `apps/api/.env` avec le prefixe `NDI_`.

### Variables obligatoires

| Variable | Description | Exemple |
|----------|-------------|---------|
| `NDI_LLM_BASE_URL` | URL Ollama locale ou URL OpenAI-compatible | `http://localhost:11434` |
| `NDI_LLM_MODEL` | Modele LLM pour la generation de requetes | `qwen3:14b` |
| `NDI_EMBEDDING_MODEL` | Modele d'embeddings | `nomic-embed-text` |

### Variables optionnelles

| Variable | Default | Description |
|----------|---------|-------------|
| **Serveur** | | |
| `NDI_API_PREFIX` | `/api` | Prefixe des routes API |
| `NDI_ENVIRONMENT` | `local` | Environnement (`local`, `production`) |
| `NDI_ALLOWED_ORIGINS` | `["http://localhost:3001","http://127.0.0.1:3001"]` | Origines CORS autorisees (JSON array) |
| **Base de donnees** | | |
| `NDI_DATABASE_MODE` | `sql` | Mode : `sql` (DuckDB) ou `nosql` (JSON) |
| `NDI_DATA_DIR` | `data` | Repertoire de stockage local |
| `NDI_DUCKDB_FILENAME` | `ndi.duckdb` | Nom du fichier DuckDB |
| **Qdrant** | | |
| `NDI_QDRANT_URL` | `http://localhost:6333` | URL du serveur Qdrant |
| `NDI_QDRANT_API_KEY` | *(vide)* | Cle API Qdrant (si auth activee) |
| `NDI_QDRANT_COLLECTION` | `schema_index` | Nom de la collection vectorielle |
| **LLM** | | |
| `NDI_LLM_API_KEY` | `ollama` | Cle API du serveur LLM |
| `NDI_VISION_MODEL` | *(vide)* | Modele vision pour analyse d'images |
| `NDI_INDEXING_LLM_MODEL` | *(vide)* | Modele dedie a l'indexation (descriptions de colonnes) |
| `NDI_LLM_CONTEXT_LENGTH` | `65536` | Taille de la fenetre de contexte (tokens) |
| **Embeddings** | | |
| `NDI_EMBEDDING_BASE_URL` | *(= LLM_BASE_URL)* | URL du serveur d'embeddings (si different du LLM) |
| `NDI_EMBEDDING_API_KEY` | *(= LLM_API_KEY)* | Cle API embeddings |
| `NDI_RETRIEVAL_TOP_K` | `6` | Nombre de documents retenus apres reranking |
| **Reranker** | | |
| `NDI_USE_RERANKER` | `true` | Activer le reranking des resultats vectoriels |
| `NDI_RERANKER_TYPE` | `lightweight` | Type : `lightweight` ou `none` |
| `NDI_RETRIEVAL_K` | `10` | Documents recuperes avant reranking |
| **Authentification** | | |
| `NDI_AUTH_ENABLED` | `true` | Activer l'authentification par API key |
| `NDI_API_KEY` | *(vide)* | Cle API pour acceder aux endpoints |
| **Cache** | | |
| `NDI_CACHE_TTL_QUERY` | `3600` | TTL cache requetes (secondes) |
| `NDI_CACHE_TTL_SCHEMA` | `300` | TTL cache schema |
| **Prompts** | | |
| `NDI_AGENTS_BASE_DIR` | `agents` | Chemin vers le dossier agents/ |

### Exemple minimal (.env)

```env
# LLM local via Ollama
NDI_LLM_BASE_URL=http://localhost:11434
NDI_LLM_API_KEY=ollama
NDI_LLM_MODEL=qwen3:14b

# Embeddings via Ollama
NDI_EMBEDDING_BASE_URL=http://localhost:11434
NDI_EMBEDDING_API_KEY=ollama
NDI_EMBEDDING_MODEL=nomic-embed-text

# Qdrant local
NDI_QDRANT_URL=http://localhost:6333

# App locale
NDI_AUTH_ENABLED=false
NDI_DATA_DIR=data
NDI_DATABASE_MODE=sql
```

### Demarrage Ollama sur Mac

```bash
ollama serve
ollama pull qwen3:14b
ollama pull nomic-embed-text
ollama pull llava
```

---

## Notes de connectivite

- Le frontend conteneurise appelle l'API via `http://localhost:8001/api` car c'est l'URL vue par le navigateur.
- Le backend conteneurise appelle Qdrant via `http://qdrant:6333`.
- Le backend conteneurise appelle Ollama sur le Mac via `http://host.docker.internal:11434`.

---

## Utilisation

### Workflow standard

1. **Importer des donnees** : Onglet "Donnees" > Upload de fichiers (CSV, XLSX, Parquet). Les colonnes sont automatiquement normalisees (snake_case, detection de types, conversion de dates).

2. **Indexer le schema** : Onglet "Donnees" > "Indexer". Genere des descriptions de colonnes via le LLM et stocke les embeddings dans Qdrant pour la recherche semantique (RAG).

3. **Definir les relations** (mode SQL) : Onglet "Modelisation" > Ajouter des relations PK/FK entre tables. Le diagramme ER se met a jour en temps reel.

4. **Interroger** : Onglet "Chat" > Poser une question en francais. Le pipeline LangGraph genere la requete, l'execute et formate la reponse. Les graphiques sont suggeres automatiquement.

5. **Exporter** : Les resultats peuvent etre exportes en CSV, XLSX ou Parquet.

### Pipeline de requete (NL-to-SQL)

```
Question utilisateur
    |
    v
[QuestionRouter] -- classifie : nl_to_query / open_analysis / follow_up / quality / ...
    |
    v
[SkillRouter] -- selectionne le(s) skill(s) : sql-query, data-quality, chart-gen, ...
    |
    v
[RAG] -- recherche semantique dans Qdrant (schema indexe) + reranking
    |
    v
[LLM] -- genere la requete SQL/NoSQL avec le contexte schema
    |
    v
[Validation] -- verifie la syntaxe, mots-cles interdits, read-only
    |
    v
[Execution] -- DuckDB (SQL) ou moteur JSON (NoSQL)
    |
    v
[Reponse] -- formatage LLM (tableau markdown, phrase, graphique)
```

---

## Fonctionnalites

- **Chat NL-to-Query** : Interrogation en francais, generation SQL (DuckDB) ou NoSQL (MongoDB-style), correction automatique en cas d'erreur
- **Conversations multi-tour** : Historique conserve, questions de suivi, contexte des resultats precedents
- **Import de donnees** : CSV, XLSX (multi-feuilles), Parquet. Normalisation automatique des colonnes, detection de dates (ISO/FR/US/DE), deduplication
- **Indexation semantique** : Descriptions de colonnes generees par LLM, embeddings stockes dans Qdrant, reranking
- **Analyse d'images** : Upload d'images, OCR, extraction de tableaux, ingestion de donnees depuis des images (modele vision)
- **Visualisation** : Suggestion automatique de graphiques (barres, lignes, camembert, aires, radar, scatter) via Recharts
- **Modelisation** : Diagramme ER interactif, definition de relations PK/FK (mode SQL)
- **Skills metier** : Generation, raffinement assiste, injection dans la conversation
- **Audit qualite** : Analyse de completude, doublons, outliers, score global /10
- **Conformite** : Verification de regles metier, export des corrections
- **Export** : CSV, XLSX, Parquet
- **Monitoring** : Logs structures, metriques de performance par etape du pipeline

---

## API Endpoints

### Sante et administration

| Methode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/health/health` | Etat de l'API (liveness, sans auth) |
| GET | `/api/health/config` | Configuration courante |
| GET | `/api/health/models` | Modeles LLM disponibles |
| POST | `/api/health/model` | Changer le modele LLM (temporaire) |
| POST | `/api/health/model/reset` | Revenir au modele par defaut |
| GET | `/api/health/performance` | Statistiques de performance (count, avg, p95) |
| GET | `/api/health/cache/stats` | Statistiques du cache |
| POST | `/api/health/cache/invalidate` | Vider les caches |
| GET | `/api/health/database/mode` | Mode base de donnees courant |
| POST | `/api/health/database/mode` | Changer le mode (sql/nosql) |

### Ingestion de donnees

| Methode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/ingest/upload` | Upload de fichiers (CSV, XLSX, Parquet) |
| POST | `/api/ingest/purge` | Supprimer toutes les donnees |
| POST | `/api/ingest/excel/sheets` | Lister les feuilles d'un fichier Excel |
| POST | `/api/ingest/excel/upload` | Uploader des feuilles specifiques |

### Indexation et vector store

| Methode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/index/reindex` | Reindexer le schema (embeddings + descriptions) |
| GET | `/api/index/status` | Statut de l'indexation |
| GET | `/api/index/reindex/stream` | Reindexation en streaming (SSE) |

### Schema et relations

| Methode | Endpoint | Description |
|---------|----------|-------------|
| GET | `/api/schema` | Schema de la base (tables + colonnes + types) |
| GET | `/api/relations` | Relations PK/FK declarees |
| POST | `/api/relations` | Creer/modifier une relation |
| GET | `/api/data/preview` | Apercu des donnees d'une table |

### Requetes

| Methode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/query` | Requete NL-to-SQL directe (sync) |
| POST | `/api/conversation/query` | Requete conversationnelle avec memoire |
| POST | `/api/conversation/query/stream` | Requete en streaming (SSE) |
| GET | `/api/conversation/{id}/history` | Historique d'une conversation |
| DELETE | `/api/conversation/{id}` | Supprimer une conversation |
| GET | `/api/conversation/list` | Lister les conversations |

### Images

| Methode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/conversation/image-chat` | Chat avec image (analyse, OCR, extraction) |
| POST | `/api/images/analyze` | Analyser une image |
| POST | `/api/images/ingest` | Extraire et ingerer des donnees depuis une image |

### Skills

| Methode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/skills/generate` | Generer un skill depuis un contexte brut |
| POST | `/api/skills/refine` | Raffiner un skill (questions ciblees) |
| POST | `/api/skills/regenerate` | Regenerer apres raffinement |
| POST | `/api/skills/inject` | Activer un skill dans la conversation |
| GET | `/api/skills/active` | Skill actif pour la conversation |
| DELETE | `/api/skills/active` | Desactiver le skill |

### Export

| Methode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/export/csv` | Exporter en CSV |
| POST | `/api/export/xlsx` | Exporter en Excel |
| POST | `/api/export/parquet` | Exporter en Parquet |

### Conformite

| Methode | Endpoint | Description |
|---------|----------|-------------|
| POST | `/api/conformity/audit` | Audit de conformite des donnees |
| POST | `/api/conformity/export-corrected` | Exporter les donnees corrigees |

---

## Skills

NDI utilise un systeme de skills pour specialiser le comportement du LLM selon le type de question.

### Skills integres

| Skill | Declenchement | Description |
|-------|---------------|-------------|
| `sql-query` | Mode SQL (defaut) | Generation de requetes DuckDB |
| `nosql-query` | Mode NoSQL | Generation de requetes MongoDB-style |
| `data-quality` | "qualite", "audit", "doublon", "outlier" | Audit de qualite (completude, doublons, outliers) |
| `data-conformity` | "conformite", "valider", "corriger" | Verification de regles metier |
| `chart-gen` | "graphique", "diagramme", "chart" | Suggestion de visualisation |
| `compare` | "compare", "versus", "evolution" | Comparaison de jeux de donnees |
| `kpi-dashboard` | "kpi", "indicateur", "dashboard" | Tableau de bord d'indicateurs |
| `open-analysis` | "analyse", "pattern", "correlation" | Analyse exploratoire libre |
| `query-explain` | "explique", "comment ca marche" | Explication de requetes |
| `summarize` | "resume", "synthese" | Synthese de resultats |
| `image-ingest` | Upload d'image | Extraction de donnees depuis images |
| `maintenance-navale` | Contexte naval | Skill specifique au domaine naval |

### Structure d'un skill

Chaque skill est compose de :
- **`agents/skills/<nom>/SKILL.md`** : Definition en Markdown (regles, exemples, declencheurs)
- **`src/ndi_api/skills/<nom>/skill.py`** : Implementation Python (outils, schemas)

### Creer un skill personnalise

1. Via l'interface : Parametres > Generer un skill > Saisir le contexte metier > Raffiner > Injecter
2. Via l'API : `POST /api/skills/generate` puis `POST /api/skills/inject`

---

## Modes SQL / NoSQL

| | Mode SQL | Mode NoSQL |
|---|----------|------------|
| **Stockage** | DuckDB (`data/ndi.duckdb`) | Fichiers JSON (`data/collections/`) |
| **Requetes** | SQL standard (SELECT, JOIN, GROUP BY) | Pipeline MongoDB-style (filter, aggregate) |
| **Relations** | PK/FK, JOINs entre tables | Donnees imbriquees, pas de JOINs |
| **Changement** | `NDI_DATABASE_MODE=sql` dans `.env` | `NDI_DATABASE_MODE=nosql` dans `.env` |

Changement temporaire via API :

```bash
curl -X POST http://localhost:8001/api/health/database/mode \
  -H "Content-Type: application/json" \
  -d '{"mode": "nosql"}'
```

### Operateurs NoSQL supportes

- **Pipeline** : `$project`, `$group`, `$sort`, `$limit`, `$match`
- **Aggregation** : `$sum`, `$avg`, `$min`, `$max`, `$count`
- **Date** : `$dateToTime`, `$year`, `$month`, `$dayOfMonth`
- **Arithmetique** : `$add`, `$subtract`, `$multiply`, `$divide`
- **Formats de date detectes** : ISO (`2023-12-31`), FR (`31/12/2023`), US (`12/31/2023`), DE (`31.12.2023`)

---

## Logs et monitoring

### Fichiers de logs

Les logs sont dans `apps/api/logs/` :

| Fichier | Contenu |
|---------|---------|
| `query.log` | Requetes NL-to-SQL (question, SQL genere, resultats, temps) |
| `audit.log` | Requetes HTTP (methode, path, status, duree) |
| `reasoning.log` | Etapes de raisonnement LangGraph (prompts, reponses LLM) |
| `ingestion.log` | Upload et parsing de fichiers |
| `indexing.log` | Indexation schema et generation d'embeddings |

### Metriques de performance

```bash
curl http://localhost:8001/api/health/performance
```

Retourne les statistiques par etape du pipeline : `retrieval_ms`, `reranking_ms`, `sql_generate_ms`, `sql_execute_ms`, `sql_correct_ms`, `response_ms` (count, avg, min, max, p95).

---

## Troubleshooting

### Qdrant ne demarre pas

```bash
# Verifier que l'image est presente localement
docker images | grep qdrant

# Si pull_policy: never et pas d'image -> charger l'image manuellement
docker load -i qdrant-image.tar

# Supprimer un ancien conteneur qui bloque
docker rm -f ndi-qdrant
docker compose up -d
```

### Le LLM genere des erreurs SQL

Les erreurs les plus frequentes sont corrigees automatiquement (2 tentatives max) :
- **GROUP BY manquant** : le systeme detecte et demande au LLM de corriger
- **Alias avec espaces** (`as null values`) : corrige automatiquement en `as null_values`
- **Mots reserves SQL** (`at`, `order`, `type`) : le LLM est instruit d'utiliser des guillemets doubles

Si le probleme persiste, verifier les regles dans `apps/api/agents/skills/sql-query/SKILL.md`.

### Le frontend ne se connecte pas au backend

Verifier que l'URL du backend est autorisee dans `NDI_ALLOWED_ORIGINS` :

```env
NDI_ALLOWED_ORIGINS=["http://localhost:3001","http://127.0.0.1:3001"]
```

### Cache obsolete apres modification des donnees

```bash
curl -X POST http://localhost:8001/api/health/cache/invalidate
```

### Reindexer le schema apres un nouvel import

Via l'interface (onglet Donnees > Indexer) ou via l'API :

```bash
curl -X POST http://localhost:8001/api/index/reindex
```

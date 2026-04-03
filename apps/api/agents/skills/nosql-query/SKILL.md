---
name: nosql-query
description: Génère des requêtes JSON compactes (style MongoDB) pour la base documentaire. Utilisé lorsque le mode base est NoSQL.
version: 1.1.0
tags: [nosql, json, mongodb, query-generation]
---

# Skill: NoSQL Query Generation

## Règles STRICTES

1. Les données sont stockées comme des documents JSON (style MongoDB).
2. Chaque 'table' est en fait une collection de documents.
3. Les documents peuvent avoir des champs imbriqués (ex: `client.adresse.ville`).
4. PAS de JOINs - les données liées sont imbriquées dans les documents.
5. Retourne UNIQUEMENT un objet JSON de requête, **sur une seule ligne**, sans espaces superflus, sans markdown, sans backticks.

## ⚠️ RÈGLE ULTRA-CRITIQUE : UN SEUL objet JSON

Ta réponse est toujours **UN SEUL objet JSON** avec `collection`, `filter`, `aggregate`, etc. comme clés sœurs.

**✅ CORRECT** — une seule paire d'accolades extérieures, clés séparées par des virgules :
```
{"collection":"nom","filter":{"champ":{"$ilike":"%val%"}},"aggregate":{"$sum":"montant"}}
```

**❌ INTERDIT** — fermer puis rouvrir un objet (double `}{`) :
```
{"collection":"nom","filter":{"champ":{"$ilike":"%val%"}}},{"aggregate":{"$sum":"montant"}}
```

**Règle mnémonique :** `},"aggregate"` (virgule) — jamais `}},{"aggregate"` (double accolade).

## Format de réponse

Retourne UNIQUEMENT le JSON compacté sur une ligne, rien d'autre :
```
{"collection":"nom","filter":{"champ":"valeur"},"limit":10}
```

**PAS** de formatage multi-lignes. **PAS** d'explications avant/après.

## Structure de la requête JSON

Champs possibles (tous optionnels sauf `collection`):

- `"collection": "nom"` — **OBLIGATOIRE**
- `"filter": {...}` — opérateurs: `$eq`, `$ne`, `$gt`, `$gte`, `$lt`, `$lte`, `$in`, `$exists`, `$regex`, `$ilike`
- `"aggregate": {...}` ou `[...]` — agrégation (count, sum, avg, pipeline)
- `"sort": {"champ": 1}` — tri: `1`=ascendant, `-1`=descendant
- `"project": ["champ1", "champ2"]` — champs à retourner
- `"distinct": "champ"` — valeurs distinctes
- `"limit": N` — nombre maximum de documents

## Recherche textuelle ($ilike)

Pour TOUTE recherche textuelle (sauf ID technique exact), utilise `$ilike` avec `%` :

**❌ INTERDIT :** `{"motif": {"$eq": "main d'oeuvre"}}` — trop strict, rate les variations de casse
**✅ OBLIGATOIRE :** `{"motif": {"$ilike": "%main d'oeuvre%"}}` — insensible à la casse

Exemples :
```json
{"collection":"ventes","filter":{"motif":{"$ilike":"%main d'oeuvre%"}},"aggregate":{"$sum":"montant"}}
{"collection":"clients","filter":{"nom":{"$ilike":"%dupont%"}},"limit":20}
```

## Dates

Formats détectés automatiquement: ISO (`2023-12-31`), FR (`31/12/2023`), US (`12/31/2023`)

```json
{"collection":"commandes","filter":{"date":{"$gte":"2023-01-01","$lte":"2023-12-31"}}}
```

## Agrégations simples

```json
{"collection":"ventes","aggregate":{"$count":true}}
{"collection":"ventes","aggregate":{"$sum":"montant"}}
{"collection":"ventes","aggregate":{"$avg":"montant"}}
{"collection":"ventes","aggregate":{"$min":"prix"}}
{"collection":"ventes","aggregate":{"$max":"prix"}}
```

## Groupement

### Syntaxe OBLIGATOIRE

Utilise TOUJOURS `{"by": ..., "agg": {...}}` :

```json
{"collection":"nom","aggregate":{"$group":{"by":"champ_groupement","agg":{"$sum":"champ_valeur"}}}}
```

- `by` : champ de groupement (string, opérateur de date, ou `null` pour agrégation globale)
- `agg` : opération (`$sum`, `$avg`, `$count`, `$min`, `$max`)
- Le nom de la colonne résultat est **automatiquement généré** (ex: `sum_montant`, `avg_prix`)
- **INTERDIT** de nommer le résultat (pas de `"total_heures": {"$sum": ...}`)

### Agrégation globale (sans groupement)

Utilise `"by": null` :

```json
{"collection":"commandes","aggregate":{"$group":{"by":null,"agg":{"$sum":"montant"}}}}
```

### ❌ SYNTAXE INTERDITE

```
{"$group": {"_id": "$OT", "total_heures": {"$sum": "$champ"}}}
{"$group": {"by": "OT", "total": {"$sum": "champ"}}}
```

Le moteur NDI ne supporte pas les champs nommés personnalisés dans `$group`.

### Top N après groupement

```json
{"collection":"ventes","aggregate":{"$group":{"by":"client","agg":{"$sum":"montant"}}},"sort":{"sum_montant":-1},"limit":1}
```

Le nom dans `sort` correspond au nom **auto-généré** : `$sum` → `sum_champ`, `$avg` → `avg_champ`, `$count` → `count`.

### Opérateurs de date dans `by`

Pour grouper par année, mois, jour, etc. :

```json
{"collection":"commandes","aggregate":{"$group":{"by":{"$year":"$date_commande"},"agg":{"$count":true}}}}
{"collection":"ventes","aggregate":{"$group":{"by":{"$month":"$date_vente"},"agg":{"$sum":"montant"}}}}
{"collection":"events","aggregate":{"$group":{"by":{"$quarter":"$date"},"agg":{"$count":true}}}}
```

Opérateurs disponibles : `$year`, `$month`, `$day`, `$quarter`, `$week`

Multi-clés : `{"$group":{"by":[{"$year":"$date"},"statut"],"agg":{"$count":true}}}`

## Pipeline d'agrégation multi-étapes

Utilise une **liste** `[stage1, stage2, ...]` pour calculs complexes.

**Écart moyen entre deux dates (global) :**
```json
{"collection":"commandes","aggregate":[{"$project":{"ecart_jours":{"$divide":[{"$subtract":[{"$dateToTime":"$date_livraison"},{"$dateToTime":"$date_commande"}]},86400000]}}},{"$group":{"by":null,"agg":{"$avg":"ecart_jours"}}}]}
```

**Écart moyen par année :**
```json
{"collection":"commandes","aggregate":[{"$project":{"d1":{"$dateToTime":"$date1"},"d2":{"$dateToTime":"$date2"},"ecart_jours":{"$divide":[{"$subtract":["$d2","$d1"]},86400000]}}},{"$group":{"by":{"$year":"$date1"},"agg":{"$avg":"ecart_jours"}}}]}
```

**Opérateurs dans $project :** `$dateToTime` (date→ms), `$subtract [a,b]`, `$divide [a,b]`, `$add [a,b]`, `$multiply [a,b]`

Constante : `86400000` = millisecondes par jour

## Exemples complets

**Nombre de commandes en 2023 :**
```
{"collection":"commandes","filter":{"date":{"$gte":"2023-01-01","$lte":"2023-12-31"}},"aggregate":{"$count":true}}
```

**Nombre de commandes par année :**
```
{"collection":"commandes","aggregate":{"$group":{"by":{"$year":"$date"},"agg":{"$count":true}}}}
```

**CA par mois en 2024 :**
```
{"collection":"ventes","filter":{"date":{"$gte":"2024-01-01","$lte":"2024-12-31"}},"aggregate":{"$group":{"by":{"$month":"$date"},"agg":{"$sum":"montant"}}}}
```

**Montant total par client :**
```
{"collection":"ventes","aggregate":{"$group":{"by":"client","agg":{"$sum":"montant"}}}}
```

**Top 5 produits les plus chers :**
```
{"collection":"produits","sort":{"prix":-1},"limit":5}
```

**Clients de Paris avec âge > 30 :**
```
{"collection":"clients","filter":{"ville":"Paris","age":{"$gt":30}}}
```

**CA moyen par mois :**
```
{"collection":"ventes","aggregate":{"$group":{"by":{"$month":"$date"},"agg":{"$avg":"montant"}}}}
```

**Catégories distinctes :**
```
{"collection":"produits","distinct":"categorie"}
```

**OT avec le plus d'heures d'aléas (top 1) :**
```
{"collection":"d2m_tln_extract_ale_as_seuls_2025","aggregate":{"$group":{"by":"OT","agg":{"$sum":"Nombre d'heures Aléas"}}},"sort":{"sum_Nombre d'heures Aléas":-1},"limit":1}
```

**Recherche textuelle + agrégation :**
```
{"collection":"d2m_tln_extract_ale_as_seuls_2025","filter":{"MOTIF":{"$ilike":"%main d'oeuvre%"}},"aggregate":{"$group":{"by":null,"agg":{"$sum":"Nombre d'heures Aléas"}}}}
```

## ❌ Ce que tu ne dois PAS faire

- **NE PAS** écrire `}},{"aggregate` — c'est TOUJOURS `},"aggregate`
- **NE PAS** utiliser `$eq` pour des recherches textuelles — utilise `$ilike`
- **NE PAS** nommer les champs résultat dans `$group` (pas de `"total_heures": ...`)
- **NE PAS** utiliser la syntaxe MongoDB standard `_id` dans `$group` (utilise `by`)
- **NE PAS** retourner tous les documents quand une agrégation répond à la question
- **NE PAS** utiliser de syntaxe SQL (SELECT, FROM, WHERE) — c'est du JSON

## Règle d'or

Quand la question demande un **NOMBRE**, un **TOTAL**, une **MOYENNE**, un **MINIMUM** ou un **MAXIMUM**, tu DOIS utiliser `"aggregate"`. Ne retourne JAMAIS tous les documents bruts quand une agrégation répond à la question.

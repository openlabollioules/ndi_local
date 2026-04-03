---
name: sql-query
description: Génère des requêtes SQL DuckDB à partir de questions en français. Utilisé lorsque le mode base est SQL.
version: 1.1.0
tags: [sql, duckdb, query-generation]
---

# Skill: SQL Query Generation

## Règles STRICTES

1. Utilise UNIQUEMENT les noms de colonnes listés dans le schéma fourni — respecte la casse exacte.
2. Chaque colonne est au format 'nom (type)' — utilise EXACTEMENT le nom indiqué.
3. N'effectue des JOINs QUE si une relation est déclarée dans le schéma (relations PK/FK).
4. Retourne UNIQUEMENT la requête SQL brute, sans explication, sans markdown, sans backticks.
5. Ne PAS ajouter de `LIMIT` sauf si l'utilisateur demande explicitement un nombre restreint de résultats (ex: "top 10", "les 5 premiers").

## Format de réponse

Retourne UNIQUEMENT la requête SQL, rien d'autre. Pas de `Q:`, pas de `SQL:`, pas de préfixe.

Exemple — si la question est "liste des commandes de 2025", tu réponds :
```
SELECT * FROM commandes WHERE YEAR(date_commande) = 2025```

## Fonctions DuckDB utiles

### Dates
- `YEAR(col)`, `MONTH(col)`, `DAY(col)`
- `EXTRACT(YEAR FROM col)`, `EXTRACT(MONTH FROM col)`
- `CURRENT_DATE`, `CURRENT_TIMESTAMP`

### Texte
- `LOWER(col)`, `UPPER(col)`
- `CONTAINS(col, 'x')` — vrai si col contient 'x'
- `col ILIKE '%x%'` — recherche insensible à la casse (PRIVILÉGIER pour les recherches textuelles)

### Agrégation
- `COUNT(*)`, `SUM(col)`, `AVG(col)`, `MIN(col)`, `MAX(col)`
- `COUNT(DISTINCT col)` — nombre de valeurs uniques

### Fenêtrage
- `ROW_NUMBER() OVER (PARTITION BY col ORDER BY col2)`
- `RANK() OVER (ORDER BY col DESC)`

### Conditions
- `CASE WHEN condition THEN valeur ELSE autre END`
- `COALESCE(col, valeur_defaut)` — première valeur non NULL
- `NULLIF(col, '')` — retourne NULL si col est vide

## ❌ Ce que tu ne dois PAS faire

- **NE PAS** inventer de colonnes absentes du schéma
- **NE PAS** faire de JOINs sans relation déclarée — retourne les données d'une seule table
- **NE PAS** ajouter de `LIMIT` sauf demande explicite de l'utilisateur
- **NE PAS** ajouter de backticks markdown (```) autour de la requête
- **NE PAS** inclure d'explication — uniquement la requête SQL brute
- **NE PAS** utiliser `$eq`, `$group`, ou tout opérateur JSON/MongoDB — c'est du SQL

## Exemples

**Filtre simple :**
SELECT * FROM commandes WHERE YEAR(date_commande) = 2025
**Agrégation par groupe :**
SELECT ville, COUNT(*) as nb_clients FROM clients GROUP BY ville ORDER BY nb_clients DESC

**Agrégation temporelle :**
SELECT MONTH(date_vente) as mois, SUM(montant) as total FROM ventes WHERE YEAR(date_vente) = 2024 GROUP BY mois ORDER BY mois

**JOIN avec relation déclarée (seulement si PK/FK existe dans le schéma) :**
SELECT c.nom, COUNT(o.id) as nb_commandes FROM clients c JOIN commandes o ON c.id = o.client_id GROUP BY c.nom ORDER BY nb_commandes DESC LIMIT 10

**CASE WHEN (catégorisation) :**
SELECT nom, montant, CASE WHEN montant > 1000 THEN 'élevé' WHEN montant > 100 THEN 'moyen' ELSE 'faible' END as categorie FROM ventes
**Sous-requête (top N par groupe) :**
SELECT * FROM (SELECT *, ROW_NUMBER() OVER (PARTITION BY categorie ORDER BY montant DESC) as rn FROM produits) sub WHERE rn <= 3

**Recherche textuelle insensible à la casse :**
SELECT * FROM employes WHERE nom ILIKE '%dupont%'
**HAVING (filtre post-agrégation) :**
SELECT categorie, COUNT(*) as nb FROM produits GROUP BY categorie HAVING COUNT(*) > 5 ORDER BY nb DESC

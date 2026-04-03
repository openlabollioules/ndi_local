---
name: query-explain
description: Explique en français ce que fait une requête SQL/NoSQL générée, pour les utilisateurs non-techniques.
version: 1.0.0
tags: [explain, pedagogy, sql, nosql]
---

# Skill: Explication de Requête

## Quand utiliser cette skill

Ce skill est un **post-processeur** qui se déclenche quand :
- L'utilisateur demande une **explication** de la requête
- Les mots "explique", "comment ça marche", "c'est quoi cette requête" apparaissent
- Après une génération de requête, pour enrichir la réponse

## Format de réponse

```
EXPLICATION :
Cette requête [action en français simple] sur la table [nom].

ÉTAPES :
1. [étape 1 en langage naturel]
2. [étape 2 en langage naturel]

COLONNES UTILISÉES :
- `[colonne]` : [rôle dans la requête — filtre, regroupement, calcul, tri]

RÉSULTAT ATTENDU :
[description du format de sortie en 1 phrase]
```

## Règles

1. **Langage simple** — pas de jargon SQL sauf les noms de colonnes
2. **Traduire les opérations** : GROUP BY → "regroupe par", WHERE → "filtre sur", JOIN → "croise avec"
3. **Mentionner les filtres** appliqués (dates, valeurs, conditions)
4. **Court et concis** — max 10 lignes
5. **Adapter au mode** : SQL → termes SQL simplifiés, NoSQL → termes JSON

## Exemples

**Requête :** `SELECT motif, SUM(nombre_d_heures_al_as) FROM table GROUP BY motif ORDER BY SUM(...) DESC`

**Explication :**
> Cette requête calcule le total d'heures d'aléas par motif, trié du plus grand au plus petit. Elle regroupe toutes les lignes par motif et additionne les heures pour chacun.

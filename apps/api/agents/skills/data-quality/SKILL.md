---
name: data-quality
description: Audit de qualité des données — détection de valeurs manquantes, doublons, outliers, incohérences de types.
version: 1.0.0
tags: [quality, audit, completeness, duplicates, outliers]
---

# Skill: Audit Qualité des Données

## Quand utiliser cette skill

Utilise cette skill quand la question porte sur :
- La **qualité** ou **propreté** des données
- Les **valeurs manquantes** (nulls, vides)
- Les **doublons**
- Les **outliers** ou valeurs aberrantes
- La **complétude** d'une table/collection
- La **cohérence des types** (texte dans une colonne numérique, etc.)

## Format de réponse

Retourne un rapport structuré :

```
RAPPORT QUALITÉ : [nom de la table]

COMPLÉTUDE :
- [colonne] : X% rempli (Y valeurs manquantes sur Z)
- ...

DOUBLONS :
- X lignes potentiellement dupliquées (basé sur [colonnes clés])
- Exemples : [exemples concrets]

OUTLIERS :
- [colonne numérique] : Y valeurs hors de [Q1-1.5*IQR, Q3+1.5*IQR]
- Exemples : [valeurs aberrantes]

TYPES :
- [colonne] : type attendu [type], mais contient [anomalies]

SCORE GLOBAL : X/10
- [résumé en 1-2 phrases]

RECOMMANDATIONS :
1. [action corrective 1]
2. [action corrective 2]
```

## Règles

1. **Toujours donner des chiffres** — pourcentages, comptes, exemples concrets
2. **Score sur 10** — 10 = données parfaites, 0 = inutilisables
3. **Prioriser** les problèmes par impact (colonnes clés d'abord)
4. **Proposer des actions** concrètes et réalistes
5. **Ne pas inventer** de problèmes — base-toi sur l'échantillon fourni

## Ce que tu ne dois PAS faire

- Ne dis pas "les données semblent correctes" sans vérifier
- Ne retourne pas une simple requête SQL — fais l'analyse
- N'ignore pas les colonnes avec des noms inhabituels

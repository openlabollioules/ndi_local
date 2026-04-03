---
name: data-conformity
description: Audit de conformité des données par rapport à des règles métier. Détecte les non-conformités, propose des corrections, et peut générer un fichier corrigé.
version: 1.0.0
tags: [conformity, rules, validation, correction, audit, compliance]
---

# Skill: Audit de Conformité aux Règles Métier

## Quand utiliser cette skill

Utilise cette skill quand la question porte sur :
- La **conformité** des données par rapport à des règles
- La **validation** de valeurs attendues dans une colonne
- La **vérification** de cohérence entre colonnes selon des règles métier
- La **correction** de données non conformes
- L'application de **règles de gestion** sur un jeu de données

## Types de règles supportées

### 1. Valeurs autorisées (enum)
> "La colonne Motif ne doit contenir que : Main d'Oeuvre, Matériel, Management, Milieu, Méthode"

### 2. Format attendu
> "La colonne Référence doit être au format XX-YYYY-ZZZ (2 lettres, 4 chiffres, 3 chiffres)"

### 3. Cohérence inter-colonnes
> "Si Motif = Main d'Oeuvre, alors Commentaires doit mentionner un nom d'opérateur ou une compétence"

### 4. Plages de valeurs
> "Le nombre d'heures d'aléas ne peut pas dépasser 24 par jour"

### 5. Complétude conditionnelle
> "Si État = Actif, alors les colonnes Responsable et Date de mise en service doivent être remplies"

### 6. Unicité
> "La colonne Référence FA doit être unique (pas de doublons)"

## Stratégie d'analyse

1. **Pré-filtrage Python** : pour les règles simples (enum, nulls, format, plages),
   le backend vérifie directement sans appeler le LLM → rapide et exhaustif.
2. **Analyse LLM par batch** : pour les règles sémantiques (cohérence entre colonnes,
   pertinence d'un commentaire), les lignes suspectes sont envoyées au LLM par lots.
3. **Agrégation** : les résultats sont consolidés en un rapport unique.

## Format de réponse

```
AUDIT DE CONFORMITÉ : [table/collection]
Règles appliquées : [N] | Lignes analysées : [N]

RÉSUMÉ :
- [X] non-conformités détectées sur [Y] lignes ([Z%])
- Score de conformité global : [score]%

DÉTAILS PAR RÈGLE :

Règle 1 : [description]
- Statut : ❌ [N] violations / ✅ Conforme
- Exemples de violations :
  - Ligne [N] : colonne `[col]` = "[valeur]" → attendu : [valeur attendue]
  - Ligne [N] : colonne `[col]` = "[valeur]" → attendu : [valeur attendue]
- Correction suggérée : [description]

Règle 2 : [description]
- Statut : ✅ Conforme (0 violation)

CORRECTIONS PROPOSÉES :
| Ligne | Colonne       | Valeur actuelle     | Correction suggérée   | Raison           |
|-------|---------------|---------------------|-----------------------|------------------|
| 42    | `motif`       | "MO"                | "Main d'Oeuvre"       | Abréviation      |
| 156   | `commentaires`| ""                  | "[À compléter]"       | Champ obligatoire|

FICHIER CORRIGÉ :
Un fichier corrigé est disponible au téléchargement avec [N] corrections appliquées.
```

## Règles de fonctionnement

1. **Toujours montrer des exemples concrets** de violations (ligne, colonne, valeur)
2. **Proposer des corrections réalistes** — basées sur le contexte et les valeurs existantes
3. **Distinguer** les corrections automatiques (certaines) des suggestions (incertaines)
4. **Quantifier** : nombre de violations, pourcentage de conformité
5. **Prioriser** les violations par sévérité (bloquant > warning > info)
6. Si les règles ne sont pas explicites, **les déduire** du schéma et des données

## Ce que tu ne dois PAS faire

- Ne dis pas "je ne peux pas vérifier" — tu as l'échantillon de données
- Ne propose pas de corrections qui changeraient la sémantique des données
- Ne corrige pas silencieusement — toujours expliquer pourquoi
- Ne fais pas de corrections sur des colonnes d'identifiant (clés primaires)

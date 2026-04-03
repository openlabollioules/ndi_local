---
name: maintenance-navale
description: Contexte métier Naval Group — suivi des aléas et arrêts sur les Ordres de Travail (OT) en chantier naval. Mappings colonnes, vocabulaire métier, règles de requêtage.
version: 1.1.0
tags: [maintenance, naval, aléas, OT, arrêts, chantier, D2M, TLN]
---

# Skill: Maintenance Navale — Suivi des Aléas

## Contexte métier

Ce skill couvre le suivi des **aléas** et **arrêts** (AL/AS) sur les chantiers navals.
Chaque ligne de données représente une imputation d'heures d'aléas sur un **Ordre de Travail (OT)**.
Les données proviennent d'extractions D2M (outil de gestion industrielle) du site de Toulon (TLN).

## Vocabulaire clé

- **OT** : Ordre de Travail — unité de suivi de production, identifié par un numéro (ex: 2950379)
- **AT** : Affaire Technique — regroupement de plusieurs OT pour un même chantier ou programme
- **Aléa (AL)** : Événement imprévu qui génère des heures supplémentaires non planifiées
- **Arrêt (AS)** : Interruption de production sur un OT (panne, attente, etc.)
- **AL/AS** : Aléas et Arrêts — le terme regroupe les deux catégories
- **Motif** : Catégorie de l'aléa selon la classification 5M :
  - **Main d'Oeuvre (MO)** : problème lié au personnel (absence, compétence, effectif)
  - **Matériel** : problème lié à l'outillage ou aux équipements
  - **Management** : problème d'organisation, de planification ou de coordination
  - **Milieu** : problème lié à l'environnement de travail (accès, espace, conditions)
  - **Méthode** : problème lié aux procédures, gammes ou instructions de travail
- **D2M** : Système d'information de gestion industrielle Naval Group
- **TLN** : Site de Toulon
- **Nombre d'heures AL/AS** : Volume d'heures imputées au titre de l'aléa ou de l'arrêt
- **Date d'imputation** : Date à laquelle les heures ont été déclarées dans le système
- **Libellé OT** : Description textuelle de l'Ordre de Travail (nature des travaux)
- **Commentaires AL/AS** : Texte libre décrivant la cause de l'aléa, rempli par l'opérateur

## Mappings colonnes

Correspondance entre les termes métier et les colonnes réelles du schéma :

| Terme métier | Colonne | Type | Description |
|---|---|---|---|
| Motif | `motif` | VARCHAR | Catégorie 5M de l'aléa (MO, Matériel, Management, Milieu, Méthode) |
| Commentaires | `commentaires_al_as` | VARCHAR | Description libre de la cause de l'aléa |
| Affaire Technique | `at` | VARCHAR | Code AT du chantier |
| Ordre de Travail | `ot` | BIGINT | Numéro d'OT (identifiant numérique) |
| Libellé OT | `libell_ot` | VARCHAR | Description de l'OT |
| Date d'imputation | `date_imputation` | TIMESTAMP | Date de déclaration des heures |
| Heures d'aléas | `nombre_d_heures_al_as` | DOUBLE | Volume d'heures imputées |

## Règles spécifiques

1. Les **motifs** sont classés selon les **5M** : Main d'Oeuvre, Matériel, Management, Milieu, Méthode
2. Un même OT peut avoir **plusieurs aléas** sur des dates différentes — pour le total d'un OT, il faut **sommer** les heures
3. La colonne `nombre_d_heures_al_as` peut contenir des **valeurs décimales** (ex: 7.5 heures)
4. La colonne `commentaires_al_as` est un **texte libre** souvent incomplet — utiliser `$ilike` pour les recherches
5. Un OT est identifié par son **numéro** (`ot`) mais peut aussi être recherché par son **libellé** (`libell_ot`)
6. Les analyses temporelles se font sur `date_imputation` — utiliser `YEAR()`, `MONTH()`, `WEEK()` pour les regroupements
7. Quand l'utilisateur dit "aléas", il parle de la table `d2m_tln_extract_ale_as_seuls_2025`

## Exemples

**Q:** Quel est le motif générant le plus d'heures d'aléas ?
**SQL:** SELECT motif, SUM(nombre_d_heures_al_as) AS total_heures FROM d2m_tln_extract_ale_as_seuls_2025 GROUP BY motif ORDER BY total_heures DESC

**Q:** Combien d'heures d'aléas par OT ?
**SQL:** SELECT ot, libell_ot, SUM(nombre_d_heures_al_as) AS total_heures FROM d2m_tln_extract_ale_as_seuls_2025 GROUP BY ot, libell_ot ORDER BY total_heures DESC

**Q:** Évolution mensuelle des aléas en 2025
**SQL:** SELECT MONTH(date_imputation) AS mois, SUM(nombre_d_heures_al_as) AS total_heures, COUNT(*) AS nb_aleas FROM d2m_tln_extract_ale_as_seuls_2025 WHERE YEAR(date_imputation) = 2025 GROUP BY mois ORDER BY mois

**Q:** Quels sont les aléas liés à la main d'oeuvre ?
**SQL:** SELECT ot, libell_ot, commentaires_al_as, nombre_d_heures_al_as, date_imputation FROM d2m_tln_extract_ale_as_seuls_2025 WHERE motif ILIKE '%main d''oeuvre%' ORDER BY nombre_d_heures_al_as DESC

**Q:** Top 5 des OT avec le plus d'aléas
**SQL:** SELECT ot, libell_ot, COUNT(*) AS nb_aleas, SUM(nombre_d_heures_al_as) AS total_heures FROM d2m_tln_extract_ale_as_seuls_2025 GROUP BY ot, libell_ot ORDER BY total_heures DESC LIMIT 5

**Q:** Répartition des motifs pour l'OT 2950379
**SQL:** SELECT motif, SUM(nombre_d_heures_al_as) AS total_heures, COUNT(*) AS nb FROM d2m_tln_extract_ale_as_seuls_2025 WHERE ot = 2950379 GROUP BY motif ORDER BY total_heures DESC

## Contraintes

- Les noms de colonnes sont en **snake_case** — ne jamais utiliser de majuscules ou d'espaces
- La table s'appelle `d2m_tln_extract_ale_as_seuls_2025` — ne pas inventer d'autres noms
- Les commentaires peuvent contenir des **apostrophes** (ex: "main d'oeuvre") — les échapper avec `''` en SQL
- Les valeurs de `motif` peuvent varier en casse — utiliser `ILIKE` pour les recherches textuelles

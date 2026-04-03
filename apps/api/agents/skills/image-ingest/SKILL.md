---
name: image-ingest
description: Règles d'ingestion sécurisée de données extraites d'images ou de textes transformés en tableaux.
version: 1.0.0
tags: [ingestion, image, table-extraction, sécurité, write]
---

# Skill: Ingestion Sécurisée (Image / Texte → Base)

## Contexte

Ce skill gouverne l'écriture de données dans la base **uniquement** lorsqu'elles
proviennent d'une extraction d'image (tableau, OCR structuré) ou d'une
transformation de texte en tableau. Toute autre écriture est interdite.

## Périmètre autorisé

L'ingestion est permise **seulement** si :

1. Les données proviennent d'un **traitement d'image** (extraction de tableau,
   OCR) ou d'une **transformation explicite** de texte brut en tableau.
2. L'utilisateur a **explicitement demandé** la sauvegarde (mots-clés :
   « ingère », « sauvegarde », « importe dans la base », « stocke »).
3. Le DataFrame résultant contient au moins **1 ligne** et au moins **2 colonnes**.

## Règles de sécurité

### Isolation des données existantes

- **NE JAMAIS écraser** une table/collection existante (`CREATE OR REPLACE` interdit).
- Si le nom de table cible existe déjà, **ajouter un suffixe horodaté** :
  `{nom}_img_{YYYYMMDD_HHmmss}`.
- Conserver l'intégrité des données déjà présentes : aucune suppression, aucun UPDATE.

### Validation pré-ingestion

1. **Taille** : rejeter si > 10 000 lignes (seuil de sécurité pour données image).
2. **Colonnes** : rejeter si > 100 colonnes ou si aucun en-tête valide.
3. **Noms de colonnes** : normaliser (snake_case, sans caractères spéciaux).
4. **Types** : détecter et convertir les types numériques et dates automatiquement.

### Nommage

- Préfixe obligatoire : `img_` pour les tables issues d'images.
- Caractères autorisés : `[a-z0-9_]` uniquement.
- Longueur max : 63 caractères.

### Traçabilité

- Logger : nom de table, nombre de lignes/colonnes, source (image/texte), timestamp.
- Stocker les métadonnées dans la réponse (table_name, rows_ingested, columns).

## Ce qui est INTERDIT

- Écrire des données issues de requêtes NL-to-Query (mode lecture seule).
- Modifier ou supprimer des tables existantes.
- Ingérer sans demande explicite de l'utilisateur.
- Contourner les validations (taille, colonnes, nommage).

## Exemples de flux

**Image → Extraction → Ingestion :**
1. Utilisateur uploade une image de tableau.
2. Le VLM extrait les données en markdown.
3. L'agent parse le markdown en DataFrame.
4. L'utilisateur dit « Ingère ce tableau ».
5. Validation (taille, colonnes, nom unique) → ingestion sécurisée.

**Refus attendu :**
- « Supprime la table X » → Refusé (hors périmètre).
- « Modifie la colonne Y » → Refusé (lecture seule sauf ingestion image).
- Extraction sans demande d'ingestion → Aperçu seulement, pas d'écriture.

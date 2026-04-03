---
name: chart-gen
description: Règles de suggestion de visualisation graphique pour les résultats de requêtes
version: 1.0.0
---

# Skill — Suggestion de graphiques

Tu es capable de recommander un type de visualisation graphique adapté aux résultats retournés.

## Quand suggérer un graphique

- Résultats avec au moins 2 lignes ET au moins 1 colonne numérique
- La question porte sur une comparaison, une répartition, une tendance ou une distribution

## Types de graphiques disponibles

| Type      | Quand l'utiliser                                                  |
|-----------|-------------------------------------------------------------------|
| `bar`     | Comparaison entre catégories (ex: ventes par région)              |
| `line`    | Tendance temporelle (ex: évolution mensuelle)                     |
| `pie`     | Répartition / proportions avec <= 8 catégories                    |
| `area`    | Série chronologique avec notion de cumul ou volume                |
| `scatter` | Corrélation entre 2 variables numériques                          |
| `radar`   | Profil multi-critères (>= 3 axes numériques par catégorie)        |

## Règles

1. Ne recommande JAMAIS un graphique si les données sont purement textuelles
2. Pour un pie chart, limite à 8 catégories maximum (agrège le reste en "Autres")
3. Privilégie `bar` en cas de doute entre `bar` et `pie`
4. Utilise `line` uniquement si l'axe X est temporel ou ordonné
5. Si la question contient "évolution", "tendance", "trend" → préfère `line` ou `area`
6. Si la question contient "répartition", "proportion", "part" → préfère `pie`

## Format de réponse

Quand un graphique est pertinent, mentionne-le dans ta réponse textuelle :

> Les données se prêtent bien à une visualisation en **diagramme en barres**.

Le système génère automatiquement la configuration du graphique côté serveur.
Ne produis PAS de JSON de configuration — le moteur heuristique s'en charge.

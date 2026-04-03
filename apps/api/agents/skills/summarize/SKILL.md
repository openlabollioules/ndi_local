---
name: summarize
description: Résume un jeu de résultats volumineux en points clés — top/bottom, totaux, moyennes, distribution.
version: 1.0.0
tags: [summarize, synthesis, digest, overview]
---

# Skill: Résumé de Résultats

## Quand utiliser cette skill

Ce skill est un **post-processeur** qui se déclenche quand :
- Les résultats contiennent plus de 20 lignes
- L'utilisateur demande un "résumé", "synthèse", "en bref", "l'essentiel"
- La question implique un aperçu global plutôt qu'un détail

## Format de réponse

```
RÉSUMÉ : [titre contextuel]

CHIFFRES CLÉS :
- Total : [valeur]
- Moyenne : [valeur]
- Médiane : [valeur] (si pertinent)

TOP 3 :
1. [élément] — [valeur] ([X% du total])
2. [élément] — [valeur] ([X% du total])
3. [élément] — [valeur] ([X% du total])

BOTTOM 3 :
1. [élément] — [valeur]
2. [élément] — [valeur]
3. [élément] — [valeur]

DISTRIBUTION :
- [catégorie A] : X% des résultats
- [catégorie B] : Y% des résultats
- Autres : Z%

EN BREF :
[conclusion en 1-2 phrases max]
```

## Règles

1. **Max 15 lignes** — c'est un résumé, pas une analyse complète
2. **Chiffres arrondis** — pas de décimales inutiles (75% pas 74.83%)
3. **Top/Bottom** — toujours inclure au moins top 3 si les données le permettent
4. **Pourcentages** — donner la part du total pour contextualiser
5. Si moins de 5 lignes, ne pas résumer — retourner les données directement

## Ce que tu ne dois PAS faire

- Ne répète pas les 50 lignes de résultats en tableau
- Ne fais pas d'analyse approfondie (c'est le rôle d'open-analysis)
- Ne dis pas "je vais résumer" — résume directement

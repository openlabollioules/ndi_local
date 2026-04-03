---
name: compare
description: Compare deux périodes, deux groupes, ou deux métriques. Calcule les écarts, tendances, variations.
version: 1.0.0
tags: [compare, evolution, trend, difference, variation]
---

# Skill: Comparaison de Données

## Quand utiliser cette skill

Utilise cette skill quand la question contient :
- "compare", "vs", "versus", "par rapport à"
- "différence entre", "écart entre"
- "évolution", "tendance", "progression", "régression"
- "avant/après", "mois dernier vs ce mois"
- "augmentation", "diminution", "variation"

## Stratégie d'analyse

### Comparaison temporelle (deux périodes)
1. Identifier les deux périodes (mois, trimestres, années)
2. Calculer les métriques sur chaque période
3. Calculer l'écart absolu et le pourcentage de variation
4. Identifier les éléments qui ont le plus varié

### Comparaison de groupes (deux catégories)
1. Identifier les deux groupes (ex: motif A vs motif B)
2. Calculer les métriques pour chaque groupe
3. Comparer en absolu et en pourcentage

## Format de réponse

```
COMPARAISON : [Sujet A] vs [Sujet B]

RÉSUMÉ :
[conclusion principale en 1-2 phrases avec le chiffre clé]

DÉTAILS :
| Métrique       | [Sujet A] | [Sujet B] | Écart    | Variation |
|----------------|-----------|-----------|----------|-----------|
| [métrique 1]   | [val]     | [val]     | [+/-val] | [+/-X%]   |
| [métrique 2]   | [val]     | [val]     | [+/-val] | [+/-X%]   |

TENDANCES :
- [observation 1 avec chiffre]
- [observation 2 avec chiffre]

POINTS D'ATTENTION :
- [élément notable ou alerte]
```

## Règles

1. **Toujours chiffrer** les écarts en absolu ET en pourcentage
2. **Identifier le sens** : hausse ↑, baisse ↓, stable →
3. **Contextualiser** : un +5% est-il significatif dans ce contexte ?
4. **Ordonner** par impact décroissant
5. Si la comparaison est impossible (données insuffisantes), le dire clairement

## Ce que tu ne dois PAS faire

- Ne compare pas des éléments incomparables (ex: heures vs euros)
- Ne dis pas "similaire" sans donner l'écart exact
- Ne conclus pas sur un échantillon trop petit sans le mentionner

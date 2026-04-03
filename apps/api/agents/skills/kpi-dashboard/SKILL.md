---
name: kpi-dashboard
description: Génère un tableau de bord KPI — métriques clés, répartitions, top N, pour une vue rapide des données.
version: 1.0.0
tags: [kpi, dashboard, indicators, metrics, overview]
---

# Skill: Tableau de Bord KPI

## Quand utiliser cette skill

Utilise cette skill quand la question porte sur :
- "KPI", "indicateurs", "métriques clés"
- "tableau de bord", "dashboard", "vue d'ensemble"
- "état des lieux", "bilan", "point sur"
- "chiffres clés", "statistiques générales"

## Stratégie

1. **Identifier la table cible** à partir de la question ou prendre la table principale
2. **Calculer les métriques de base** :
   - Nombre total de lignes
   - Pour chaque colonne numérique : total, moyenne, min, max
   - Pour chaque colonne catégorielle : nombre de valeurs distinctes, top 3 valeurs
3. **Détecter les colonnes de date** et calculer la plage temporelle
4. **Présenter** de manière structurée et visuelle

## Format de réponse

```
TABLEAU DE BORD : [Table/Collection]
Période : [date min] → [date max] (si applicable)

VOLUMÉTRIE :
- [N] enregistrements au total
- [N] colonnes

MÉTRIQUES NUMÉRIQUES :
| Indicateur          | Total      | Moyenne  | Min    | Max     |
|---------------------|------------|----------|--------|---------|
| [colonne num 1]     | [val]      | [val]    | [val]  | [val]   |
| [colonne num 2]     | [val]      | [val]    | [val]  | [val]   |

RÉPARTITIONS :
- [colonne cat 1] : [val A] (X%), [val B] (Y%), [val C] (Z%), autres (W%)
- [colonne cat 2] : [val A] (X%), [val B] (Y%), ...

TOP 5 [métrique principale] :
1. [élément] — [valeur]
2. [élément] — [valeur]
3. [élément] — [valeur]
4. [élément] — [valeur]
5. [élément] — [valeur]

ALERTES :
- [observation notable : pic, anomalie, donnée manquante]
```

## Règles

1. **Adapter les métriques** à la sémantique des colonnes (heures → total d'heures, montant → CA total)
2. **Limiter les répartitions** à 5 catégories max (regrouper le reste en "Autres")
3. **Formater les nombres** : espaces comme séparateurs de milliers, virgule pour les décimales
4. **Arrondir** intelligemment (pas 3.14159 → 3,14 suffit)
5. Si une colonne semble être un identifiant (valeurs uniques), ne pas la compter comme catégorielle

## Ce que tu ne dois PAS faire

- Ne retourne pas toutes les lignes en brut
- Ne calcule pas de KPI sur des colonnes texte libres (commentaires, etc.)
- Ne fais pas de prédictions — reste sur les faits observés

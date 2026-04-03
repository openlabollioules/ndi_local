---
name: open-analysis
description: Analyser, interpréter et commenter les données au-delà des requêtes simples. Utilisé pour les questions ouvertes, évaluations, cohérences, patterns.
version: 1.0.0
tags: [analysis, interpretation, coherence, patterns, insights]
---

# Skill: Open Data Analysis

## Quand utiliser cette skill

Utilise cette skill quand la question demande :
- Une **évaluation** ou **analyse** de qualité des données
- Une **comparaison** entre colonnes (cohérence, similarité)
- La détection de **patterns** ou **tendances**
- Une **interprétation** des résultats
- Une **opinion** sur les données

## Types d'analyses

### 1. Cohérence entre colonnes

Quand on demande d'évaluer la cohérence entre deux champs (ex: Motif vs Commentaire) :

```json
{"collection":"ma_table","limit":100}
```

**Ne génère pas de requête complexe.** L'analyse de cohérence se fait sur un échantillon extrait par le système.

### 2. Patterns et tendances

Quand on demande des patterns, tendances, évolutions :

Pour une analyse temporelle :
```json
{"collection":"ma_table","aggregate":{"$group":{"by":{"$month":"$date_colonne"},"agg":{"$count":true}}}}
```

### 3. Distribution et répartition

Pour analyser la répartition des valeurs :
```json
{"collection":"ma_table","aggregate":{"$group":{"by":"categorie","agg":{"$count":true}}}}
```

## Format de réponse

Pour les analyses ouvertes, tu dois fournir une réponse structurée :

```
ANALYSE: [type d'analyse effectuée]

SYNTHÈSE: [conclusion principale en 1-2 phrases]

DÉTAILS:
- [point clé 1 avec chiffre]
- [point clé 2 avec chiffre]
- [point clé 3 avec chiffre]

EXEMPLES:
1. [exemple concret 1]
2. [exemple concret 2]

HYPOTHÈSES: [si pertinent, explications possibles]

LIMITES: [taille de l'échantillon, biais éventuels]
```

## Exemples de questions et réponses

**Q:** "Évalue la cohérence entre Motif et Commentaires"

**Réponse type:**
```
ANALYSE: Cohérence textuelle entre deux colonnes

SYNTHÈSE: 78% de cohérence globale. Les motifs correspondent bien aux commentaires dans la majorité des cas.

DÉTAILS:
- 78% des paires motif/commentaire sont cohérentes (similarité > 70%)
- 15% présentent une faible similarité (possible incohérence)
- 7% ont un motif ou commentaire manquant

EXEMPLES:
1. ✅ Cohérent: Motif="Panne matérielle" / Commentaire="Machine HS, besoin de remplacement"
2. ⚠️  Incohérent: Motif="Formation" / Commentaire="Problème de logiciel récurrent"

HYPOTHÈSES:
- Les incohérences pourraient être dues à des erreurs de saisie
- Certaines entrées peuvent avoir été modifiées après coup

LIMITES:
- Analyse basée sur un échantillon de 100 lignes
- Similarité textuelle simple (ne capture pas les synonymes)
```

**Q:** "Quelles tendances observes-tu sur les 3 derniers mois ?"

**Réponse type:**
```
ANALYSE: Tendance temporelle sur 3 mois

SYNTHÈSE: Augmentation progressive de 23% des aléas, avec un pic en janvier.

DÉTAILS:
- Novembre: 145 aléas
- Décembre: 168 aléas (+16%)
- Janvier: 178 aléas (+23% vs nov)

PATTERNS:
- Hausse constante mois après mois
- Les lundi et vendredi sont les jours les plus concernés
- Pic observé la dernière semaine de janvier

HYPOTHÈSES:
- Augmentation liée à la reprise d'activité post-congés
- Possible sous-estimation en novembre (période de congés)

LIMITES:
- Données disponibles uniquement jusqu'au 15 février
- Pas de comparaison avec l'année précédente
```

## Règles importantes

1. **Toujours donner des chiffres** - Pas d'affirmations sans données
2. **Citer des exemples concrets** - Rend l'analyse crédible
3. **Mentionner les limites** - Taille d'échantillon, biais potentiels
4. **Proposer des hypothèses** - Mais distinguer clairement fait/interprétation
5. **Être honnête sur les incertitudes** - "Les données suggèrent..." plutôt que "C'est prouvé que..."

## Ce que tu ne dois PAS faire

❌ Ne dis jamais "Je n'ai pas accès aux données" - on te fournit un échantillon
❌ Ne réponds pas par une simple requête SQL - fais l'analyse
❌ N'invente pas de données - base-toi sur l'échantillon fourni
❌ Ne dis pas "En tant qu'IA..." - réponds directement

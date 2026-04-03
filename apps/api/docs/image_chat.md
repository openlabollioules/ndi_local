# Image Chat - Guide Utilisateur

L'Image Chat permet d'uploader des images dans la conversation et d'interagir avec elles en langage naturel.

## 🎯 Fonctionnalités

- 📷 **Upload d'images** directement dans le chat
- 💬 **Commandes en langage naturel** ("Extraire le tableau", "Décris cette image")
- 📊 **Extraction automatique** de tableaux de données
- 💾 **Ingestion directe** dans la base de données
- 📝 **OCR** pour extraire du texte

## 🚀 Comment utiliser

### 1. Upload une image

Cliquez sur le bouton 📷 à côté de la zone de texte et sélectionnez une image.

### 2. Décrivez ce que vous voulez faire (optionnel)

Tapez une instruction ou laissez vide pour une analyse par défaut :

| Ce que vous voulez | Message à taper |
|-------------------|-----------------|
| Description générale | *(rien)* ou "Décris cette image" |
| Extraire le texte | "Extraire le texte" ou "OCR" |
| Extraire un tableau (preview) | "Extraire le tableau" |
| Extraire ET sauvegarder | "Ingère ces données" ou "Sauvegarde dans la base" |
| Analyser un graphique | "Analyse ce graphique" |

### 3. Envoyez

Cliquez sur le bouton d'envoi ou appuyez sur Entrée.

## 💡 Exemples de conversations

### Exemple 1 : Extraction de tableau

```
[Utilisateur upload screenshot_excel.png]
Message: "Extraire le tableau"

[Assistant]
📊 Tableau extrait (24 lignes, 4 colonnes)

Colonnes: Produit, Quantité, Prix, Total

Aperçu:
| Produit | Quantité | Prix | Total |
|---------|----------|------|-------|
| A       | 10       | 50€  | 500€  |
...

💡 Pour ingérer ces données, demandez: 'Ingère ce tableau'
```

### Exemple 2 : Ingestion directe

```
[Utilisateur upload tableau_ventes.jpg]
Message: "Ingère ces données dans la table ventes_q1"

[Assistant]
📊 Tableau extrait (156 lignes, 5 colonnes)
...

✅ Données ingérées dans la table `ventes_q1`

Vous pouvez maintenant interroger ces données en langage naturel !
```

### Exemple 3 : OCR sur document

```
[Utilisateur upload document_scan.jpg]
Message: "Extraire le texte"

[Assistant]
📝 Texte extrait

```
RAPPORT MENSUEL - Février 2026
Total des ventes: 150 000€
...
```

_Confiance: 92%_
```

### Exemple 4 : Analyse de graphique

```
[Utilisateur upload chart.png]
Message: "Analyse ce graphique"

[Assistant]
📈 Analyse du graphique

Ce graphique montre l'évolution des ventes sur l'année 2025...
```

## 🔧 Mots-clés reconnus

### Pour l'OCR
- "texte", "extraire le texte", "transcrire", "lis ce document"
- "qu'est-ce qui est écrit", "contenu du document"

### Pour les tableaux
- "tableau", "données", "extraire les données", "csv"
- "extraire le tableau", "récupérer le tableau"

### Pour l'ingestion
- "ingérer", "importer", "mettre dans la base"
- "sauvegarder", "stocker", "sauvegarde"

### Pour les graphiques
- "graphique", "chart", "courbe", "histogramme"
- "analyser ce graphique", "interprète"

### Pour la description
- "décris", "description", "que vois-tu"
- "qu'est-ce que c'est", "montre"

## ⚙️ Configuration requise

### 1. Modèle Vision
```bash
ollama pull llava  # ou moondream, qwen2.5-vl, bakllava
```

### 2. Configuration
```bash
# .env
NDI_VISION_MODEL=llava
```

### 3. Redémarrage
```bash
# Redémarrer l'API
```

## 📋 Limites

- **Formats**: JPG, PNG, GIF, WebP, BMP
- **Taille max**: 10 Mo
- **Dimensions max**: 2048x2048 pixels
- **Résolution recommandée**: 300+ DPI pour l'OCR

## 🐛 Dépannage

### "Current model may not support vision"
```bash
ollama pull llava
```

### "Could not extract valid table data"
- Vérifiez que le tableau est bien visible et complet
- Assurez-vous que les bordures sont claires
- Essayez avec une meilleure résolution

### L'image ne s'upload pas
- Vérifiez la taille (< 10 Mo)
- Vérifiez le format (JPG, PNG, etc.)
- Vérifiez la connexion réseau

## 🔗 API Endpoints

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/conversation/image-chat` | POST | Upload + analyse par langage naturel |
| `/images/analyze` | POST | Analyse simple |
| `/images/ingest` | POST | Extraction + ingestion |

### Exemple curl

```bash
curl -X POST "http://localhost:8000/api/conversation/image-chat" \
  -H "X-API-Key: your-key" \
  -F "file=@tableau.jpg" \
  -F "message=Extraire le tableau" \
  -F "table_name=mes_donnees"
```

## 🎨 Interface

L'interface montre :
- ✅ Prévisualisation de l'image sélectionnée
- ✅ Bouton pour supprimer l'image avant envoi
- ✅ Indication de la taille du fichier
- ✅ Message de statut "Image prête à l'envoi"
- ✅ Placeholder contextuel pour guider l'utilisateur

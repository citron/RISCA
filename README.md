# RISCA - PACS Nuclear Medicine Retriever

Récupération et filtrage d'images DICOM de médecine nucléaire depuis un serveur PACS.

## Installation

```bash
# Installer les dépendances
pip install -r pyproject.toml
# ou avec uv
uv sync
```

## Configuration

1. Copier le fichier de configuration exemple :
```bash
cp .env.example .env
```

2. Éditer `.env` avec vos identifiants PACS :
```
PACS_HOST=votre_serveur_pacs
PACS_PORT=11112
PACS_AET=VOTRE_AET
LOCAL_AET=VOTRE_LOCAL_AET
LOCAL_PORT=11112
```

## Utilisation

### 1. Récupérer des images DICOM depuis le PACS

```bash
# Test en mode dry-run (recommandé)
./pacs_nm_retriever.py --dry-run

# Récupérer 5 études maximum
./pacs_nm_retriever.py --max-studies 5

# Récupérer pour une période donnée
./pacs_nm_retriever.py --from-date 20210901 --to-date 20210930 --max-studies 10

# Récupérer tout (attention!)
./pacs_nm_retriever.py
```

### 2. Identifier les scintigraphies du torse

Une fois les images récupérées, utilisez `find_chest_scans.py` pour identifier les scintigraphies du torse :

```bash
# Générer un rapport CSV
./find_chest_scans.py -i ./nm_images -o chest_scans_report.csv

# Copier les scans du torse dans un dossier séparé
./find_chest_scans.py -i ./nm_images -o chest_scans_report.csv --copy-to ./chest_scans

# Ajouter des mots-clés personnalisés
./find_chest_scans.py -i ./nm_images -o report.csv --keywords "poumon,thorax,cardiaque"
```

Le script recherche les mots-clés suivants dans les tags DICOM :
- **Anglais** : chest, thorax, lung, pulmonary, ventilation, perfusion, v/q, heart, myocardial, cardiac
- **Français** : poumon, thoracique, cardiaque

**Tags DICOM analysés :**
- `BodyPartExamined` (0018,0015)
- `SeriesDescription` (0008,103E)
- `StudyDescription` (0008,1030)

## Structure des fichiers

Les images DICOM sont organisées selon :
```
nm_images/
├── PatientID/
│   ├── StudyInstanceUID/
│   │   ├── SeriesInstanceUID/
│   │   │   ├── SOPInstanceUID.dcm
│   │   │   └── ...
```

## Sécurité

⚠️ **IMPORTANT** : Ne jamais commiter le fichier `.env` contenant vos identifiants PACS !

Le fichier `.gitignore` est configuré pour exclure :
- `.env` (identifiants)
- `nm_images/` (images DICOM)
- `data/` (données sensibles)
- `test_dcmtk/` (tests)
- `old/` (anciens fichiers)
- `__pycache__/` (cache Python)

## Fichiers

- `pacs_nm_retriever.py` - Récupération d'images depuis le PACS
- `find_chest_scans.py` - Identification des scintigraphies du torse
- `list_dicom_info.py` - Liste les informations de tous les fichiers DICOM
- `.env.example` - Template de configuration
- `PACS_SAFETY_CHECKLIST.md` - Checklist de sécurité
- `QUICKSTART.md` - Guide de démarrage rapide

## Lister les informations des fichiers DICOM

Pour obtenir un aperçu de tous les fichiers DICOM (nom patient, date, zone explorée) :

```bash
# Générer un rapport complet
./list_dicom_info.py -i ./nm_images -o dicom_list.csv

# Générer un rapport minimal (seulement nom, date, zone, fichier)
./list_dicom_info.py -i ./nm_images -o dicom_list.csv --minimal

# Anonymiser les noms des patients
./list_dicom_info.py -i ./nm_images -o dicom_list.csv --anonymize

# Combiner anonymisation et rapport minimal
./list_dicom_info.py -i ./nm_images -o dicom_list.csv --anonymize --minimal
```

**Informations extraites :**
- Nom du patient (PatientName)
- Date d'observation (StudyDate, SeriesDate, ou AcquisitionDate)
- Zone explorée (BodyPartExamined + descriptions)
- Modalité, institution, UIDs, etc.


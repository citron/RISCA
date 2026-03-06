# DICOM to FHIR Converter

Convertisseur de fichiers DICOM vers ressources HL7 FHIR.

## Description

Ce script utilise `dcmdump` (DCMTK) pour extraire les métadonnées DICOM de fichiers et les convertit en ressources FHIR standardisées (Bundle contenant Patient et ImagingStudy).

## Prérequis

- Python 3.7+
- DCMTK (pour dcmdump)

## Installation

```bash
# Installer DCMTK
sudo apt-get install dcmtk  # Debian/Ubuntu
# ou
brew install dcmtk  # macOS
```

## Utilisation

```bash
# Conversion basique (exclut PixelData par défaut)
./dicom2fhir.py /chemin/vers/dicom

# Spécifier un répertoire de sortie
./dicom2fhir.py /chemin/vers/dicom -o /chemin/sortie

# Inclure les données de pixels (non recommandé pour FHIR)
./dicom2fhir.py /chemin/vers/dicom --include-pixel-data
```

## Options

- `input_dir` : Répertoire contenant les fichiers DICOM (requis)
- `-o, --output-dir` : Répertoire de sortie (défaut: `input_dir/fhir_output`)
- `--include-pixel-data` : Inclure le champ PixelData (par défaut: exclu)

## Fonctionnalités

- ✅ Parcours récursif des répertoires
- ✅ Extraction complète des métadonnées DICOM via dcmdump
- ✅ Exclusion automatique du champ PixelData (7FE0,0010)
- ✅ Conversion en ressources FHIR ImagingStudy et Patient
- ✅ Format de sortie: Bundle FHIR JSON
- ✅ Préservation de toutes les métadonnées DICOM en extension
- ✅ Gestion des dates/heures DICOM → ISO 8601
- ✅ Mapping des modalités et genres DICOM vers FHIR

## Structure de sortie

Chaque fichier DICOM génère un Bundle FHIR contenant:

1. **Patient** : Informations démographiques
   - PatientID, PatientName, PatientBirthDate, PatientSex
   
2. **ImagingStudy** : Étude d'imagerie
   - StudyInstanceUID, AccessionNumber, StudyDate/Time
   - Series (SeriesInstanceUID, Modality, SeriesDescription)
   - Instances (SOPInstanceUID, SOPClassUID, InstanceNumber)
   - Extension avec métadonnées DICOM complètes

## Exemple de sortie

```json
{
  "resourceType": "Bundle",
  "type": "collection",
  "entry": [
    {
      "resource": {
        "resourceType": "Patient",
        "id": "12345",
        "name": [{"text": "DOE JOHN"}],
        "gender": "male"
      }
    },
    {
      "resource": {
        "resourceType": "ImagingStudy",
        "identifier": [...],
        "series": [...]
      }
    }
  ]
}
```

## Notes

- Le champ PixelData est exclu par défaut car il contient les données d'image binaires, non pertinentes pour les métadonnées FHIR
- Les métadonnées DICOM complètes sont préservées dans l'extension `dicom-tags`
- Les fichiers non-DICOM sont automatiquement ignorés

## Licence

Voir LICENSE du projet parent.

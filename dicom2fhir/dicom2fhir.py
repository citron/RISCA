#!/usr/bin/env python3
"""
Script de conversion DICOM vers HL7 FHIR.
Lance dcmdump sur tous les fichiers DICOM d'un répertoire et convertit
chaque sortie en ressources FHIR, en excluant le champ PixelData.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime


class DicomToFhirConverter:
    """Convertisseur DICOM vers FHIR."""
    
    def __init__(self, exclude_pixel_data: bool = True):
        self.exclude_pixel_data = exclude_pixel_data
        
    def run_dcmdump(self, dicom_file: Path) -> Optional[str]:
        """
        Exécute dcmdump sur un fichier DICOM.
        
        Args:
            dicom_file: Chemin vers le fichier DICOM
            
        Returns:
            Sortie de dcmdump ou None en cas d'erreur
        """
        try:
            cmd = ['dcmdump', str(dicom_file)]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True
            )
            return result.stdout
        except subprocess.CalledProcessError as e:
            print(f"Erreur dcmdump pour {dicom_file}: {e}", file=sys.stderr)
            return None
        except FileNotFoundError:
            print("Erreur: dcmdump n'est pas installé ou introuvable", file=sys.stderr)
            sys.exit(1)
            
    def parse_dcmdump_output(self, dcmdump_output: str) -> Dict[str, Any]:
        """
        Parse la sortie de dcmdump pour extraire les tags DICOM.
        
        Args:
            dcmdump_output: Sortie brute de dcmdump
            
        Returns:
            Dictionnaire des tags DICOM extraits
        """
        dicom_data = {}
        
        # Pattern pour parser les lignes dcmdump
        # Format: (GGGG,EEEE) VR (Description) [Value]
        pattern = r'\(([0-9A-Fa-f]{4}),([0-9A-Fa-f]{4})\)\s+(\w{2})\s+(?:\[([^\]]*)\]|\(no value available\)|\([^)]+\))\s*(?:#.*)?(?:\s+(.+))?'
        
        for line in dcmdump_output.split('\n'):
            match = re.search(pattern, line)
            if match:
                group = match.group(1)
                element = match.group(2)
                vr = match.group(3)
                value = match.group(4) if match.group(4) is not None else ""
                description = match.group(5) if match.group(5) else ""
                
                tag = f"({group},{element})"
                
                # Exclure PixelData si demandé
                if self.exclude_pixel_data and tag == "(7FE0,0010)":
                    continue
                    
                dicom_data[tag] = {
                    'vr': vr,
                    'value': value.strip(),
                    'description': description.strip() if description else ""
                }
                
        return dicom_data
    
    def convert_to_fhir(self, dicom_data: Dict[str, Any], source_file: Path) -> Dict[str, Any]:
        """
        Convertit les données DICOM en ressource FHIR ImagingStudy.
        
        Args:
            dicom_data: Données DICOM parsées
            source_file: Fichier source DICOM
            
        Returns:
            Ressource FHIR au format JSON
        """
        # Helper pour récupérer une valeur DICOM
        def get_value(tag: str) -> str:
            return dicom_data.get(tag, {}).get('value', '')
        
        # Extraction des données DICOM courantes
        patient_id = get_value('(0010,0020)')  # PatientID
        patient_name = get_value('(0010,0010)')  # PatientName
        patient_birth_date = get_value('(0010,0030)')  # PatientBirthDate
        patient_sex = get_value('(0010,0040)')  # PatientSex
        
        study_instance_uid = get_value('(0020,000D)')  # StudyInstanceUID
        study_date = get_value('(0008,0020)')  # StudyDate
        study_time = get_value('(0008,0030)')  # StudyTime
        study_description = get_value('(0008,1030)')  # StudyDescription
        accession_number = get_value('(0008,0050)')  # AccessionNumber
        
        series_instance_uid = get_value('(0020,000E)')  # SeriesInstanceUID
        series_number = get_value('(0020,0011)')  # SeriesNumber
        series_description = get_value('(0008,103E)')  # SeriesDescription
        modality = get_value('(0008,0060)')  # Modality
        
        sop_instance_uid = get_value('(0008,0018)')  # SOPInstanceUID
        sop_class_uid = get_value('(0008,0016)')  # SOPClassUID
        instance_number = get_value('(0020,0013)')  # InstanceNumber
        
        # Construction de la ressource FHIR ImagingStudy
        fhir_resource = {
            'resourceType': 'ImagingStudy',
            'id': study_instance_uid or 'unknown',
            'identifier': [],
            'status': 'available',
            'subject': {
                'reference': f'Patient/{patient_id}' if patient_id else 'Patient/unknown'
            },
            'started': self._format_dicom_datetime(study_date, study_time),
            'numberOfSeries': 1,
            'numberOfInstances': 1,
            'series': []
        }
        
        # Ajout des identifiants
        if study_instance_uid:
            fhir_resource['identifier'].append({
                'system': 'urn:dicom:uid',
                'value': f'urn:oid:{study_instance_uid}'
            })
        
        if accession_number:
            fhir_resource['identifier'].append({
                'type': {
                    'coding': [{
                        'system': 'http://terminology.hl7.org/CodeSystem/v2-0203',
                        'code': 'ACSN'
                    }]
                },
                'value': accession_number
            })
        
        # Description de l'étude
        if study_description:
            fhir_resource['description'] = study_description
        
        # Série
        series_data = {
            'uid': series_instance_uid or 'unknown',
            'number': int(series_number) if series_number.isdigit() else 0,
            'modality': {
                'system': 'http://dicom.nema.org/resources/ontology/DCM',
                'code': modality or 'OT'
            },
            'description': series_description,
            'numberOfInstances': 1,
            'instance': []
        }
        
        # Instance
        instance_data = {
            'uid': sop_instance_uid or 'unknown',
            'sopClass': {
                'system': 'urn:ietf:rfc:3986',
                'code': f'urn:oid:{sop_class_uid}' if sop_class_uid else 'urn:oid:unknown'
            },
            'number': int(instance_number) if instance_number and instance_number.isdigit() else 0
        }
        
        series_data['instance'].append(instance_data)
        fhir_resource['series'].append(series_data)
        
        # Ajout de l'extension pour les métadonnées DICOM complètes
        fhir_resource['extension'] = [{
            'url': 'http://hl7.org/fhir/StructureDefinition/dicom-tags',
            'valueAttachment': {
                'contentType': 'application/dicom+json',
                'data': self._encode_dicom_metadata(dicom_data)
            }
        }]
        
        # Ressource Patient associée
        patient_resource = {
            'resourceType': 'Patient',
            'id': patient_id or 'unknown',
            'identifier': [{
                'value': patient_id or 'unknown'
            }],
            'name': [{
                'text': patient_name.replace('^', ' ') if patient_name else 'Unknown'
            }],
            'gender': self._map_dicom_gender(patient_sex),
            'birthDate': self._format_dicom_date(patient_birth_date)
        }
        
        # Bundle FHIR contenant les deux ressources
        fhir_bundle = {
            'resourceType': 'Bundle',
            'type': 'collection',
            'timestamp': datetime.utcnow().isoformat() + 'Z',
            'entry': [
                {
                    'fullUrl': f'Patient/{patient_id or "unknown"}',
                    'resource': patient_resource
                },
                {
                    'fullUrl': f'ImagingStudy/{study_instance_uid or "unknown"}',
                    'resource': fhir_resource
                }
            ],
            'meta': {
                'source': str(source_file),
                'profile': ['http://hl7.org/fhir/StructureDefinition/Bundle']
            }
        }
        
        return fhir_bundle
    
    def _format_dicom_date(self, dicom_date: str) -> Optional[str]:
        """
        Convertit une date DICOM (YYYYMMDD) en format FHIR (YYYY-MM-DD).
        
        Args:
            dicom_date: Date au format DICOM
            
        Returns:
            Date au format FHIR ou None
        """
        if not dicom_date or len(dicom_date) != 8:
            return None
        
        try:
            return f"{dicom_date[0:4]}-{dicom_date[4:6]}-{dicom_date[6:8]}"
        except (ValueError, IndexError):
            return None
    
    def _format_dicom_datetime(self, dicom_date: str, dicom_time: str) -> Optional[str]:
        """
        Combine date et heure DICOM en format FHIR (ISO 8601).
        
        Args:
            dicom_date: Date DICOM (YYYYMMDD)
            dicom_time: Heure DICOM (HHMMSS.FFFFFF)
            
        Returns:
            DateTime au format FHIR ou None
        """
        formatted_date = self._format_dicom_date(dicom_date)
        if not formatted_date:
            return None
        
        if dicom_time:
            # Extraire HH:MM:SS
            time_parts = dicom_time.split('.')
            base_time = time_parts[0]
            
            if len(base_time) >= 6:
                formatted_time = f"{base_time[0:2]}:{base_time[2:4]}:{base_time[4:6]}"
                return f"{formatted_date}T{formatted_time}Z"
        
        return formatted_date
    
    def _map_dicom_gender(self, dicom_sex: str) -> str:
        """
        Convertit le sexe DICOM en genre FHIR.
        
        Args:
            dicom_sex: Sexe DICOM (M, F, O)
            
        Returns:
            Genre FHIR
        """
        mapping = {
            'M': 'male',
            'F': 'female',
            'O': 'other',
            '': 'unknown'
        }
        return mapping.get(dicom_sex.upper(), 'unknown')
    
    def _encode_dicom_metadata(self, dicom_data: Dict[str, Any]) -> str:
        """
        Encode les métadonnées DICOM complètes en JSON.
        
        Args:
            dicom_data: Métadonnées DICOM
            
        Returns:
            JSON encodé des métadonnées
        """
        # Créer un dictionnaire structuré des métadonnées DICOM
        metadata = {}
        for tag, data in dicom_data.items():
            metadata[tag] = {
                'vr': data.get('vr', ''),
                'value': data.get('value', ''),
                'description': data.get('description', '')
            }
        
        return json.dumps(metadata, indent=2)
    
    def process_directory(self, input_dir: Path, output_dir: Path) -> int:
        """
        Traite tous les fichiers DICOM d'un répertoire.
        
        Args:
            input_dir: Répertoire contenant les fichiers DICOM
            output_dir: Répertoire de sortie pour les fichiers FHIR
            
        Returns:
            Nombre de fichiers traités
        """
        if not input_dir.exists():
            print(f"Erreur: Le répertoire {input_dir} n'existe pas", file=sys.stderr)
            sys.exit(1)
        
        # Créer le répertoire de sortie
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Trouver tous les fichiers potentiellement DICOM
        dicom_files = []
        for root, dirs, files in os.walk(input_dir):
            for file in files:
                file_path = Path(root) / file
                # Exclure les fichiers cachés et non-DICOM évidents
                if not file.startswith('.') and file.lower() not in ['readme.txt', 'dicomdir']:
                    dicom_files.append(file_path)
        
        if not dicom_files:
            print(f"Aucun fichier trouvé dans {input_dir}", file=sys.stderr)
            return 0
        
        processed = 0
        for dicom_file in dicom_files:
            print(f"Traitement de {dicom_file}...")
            
            # Exécuter dcmdump
            dcmdump_output = self.run_dcmdump(dicom_file)
            if not dcmdump_output:
                print(f"  ⚠ Ignoré (pas un fichier DICOM valide)")
                continue
            
            # Parser la sortie
            dicom_data = self.parse_dcmdump_output(dcmdump_output)
            if not dicom_data:
                print(f"  ⚠ Aucune donnée DICOM extraite")
                continue
            
            # Convertir en FHIR
            fhir_bundle = self.convert_to_fhir(dicom_data, dicom_file)
            
            # Générer le nom du fichier de sortie
            output_file = output_dir / f"{dicom_file.stem}.fhir.json"
            
            # Écrire le fichier FHIR
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(fhir_bundle, f, indent=2, ensure_ascii=False)
            
            print(f"  ✓ Converti vers {output_file}")
            processed += 1
        
        return processed


def main():
    """Point d'entrée principal du script."""
    parser = argparse.ArgumentParser(
        description='Convertit des fichiers DICOM en ressources HL7 FHIR',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples:
  %(prog)s /chemin/vers/dicom
  %(prog)s /chemin/vers/dicom -o /chemin/sortie
  %(prog)s /chemin/vers/dicom --include-pixel-data
        """
    )
    
    parser.add_argument(
        'input_dir',
        type=Path,
        help='Répertoire contenant les fichiers DICOM'
    )
    
    parser.add_argument(
        '-o', '--output-dir',
        type=Path,
        default=None,
        help='Répertoire de sortie pour les fichiers FHIR (défaut: input_dir/fhir_output)'
    )
    
    parser.add_argument(
        '--include-pixel-data',
        action='store_true',
        help='Inclure le champ PixelData dans la conversion (par défaut: exclu)'
    )
    
    args = parser.parse_args()
    
    # Déterminer le répertoire de sortie
    output_dir = args.output_dir or (args.input_dir / 'fhir_output')
    
    # Créer le convertisseur
    converter = DicomToFhirConverter(exclude_pixel_data=not args.include_pixel_data)
    
    # Traiter les fichiers
    print(f"Conversion DICOM → FHIR")
    print(f"Répertoire d'entrée: {args.input_dir}")
    print(f"Répertoire de sortie: {output_dir}")
    print(f"Exclusion PixelData: {not args.include_pixel_data}")
    print("-" * 80)
    
    processed = converter.process_directory(args.input_dir, output_dir)
    
    print("-" * 80)
    print(f"✓ {processed} fichier(s) converti(s) avec succès")
    
    return 0 if processed > 0 else 1


if __name__ == '__main__':
    sys.exit(main())

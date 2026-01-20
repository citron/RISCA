#!/usr/bin/env python3
"""
List DICOM File Information

Scans DICOM files and extracts patient name, observation date, and examined body part.
Generates a CSV report with all information.
"""

import argparse
import logging
from pathlib import Path
from typing import List, Dict
from datetime import datetime

try:
    import pydicom
    import pandas as pd
except ImportError:
    print("Error: Required packages not installed. Install with:")
    print("  pip install pydicom pandas")
    import sys
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DicomInfoLister:
    """Extract patient, date, and body part information from DICOM files"""
    
    def __init__(self, input_dir: str, anonymize: bool = False):
        self.input_dir = Path(input_dir)
        if not self.input_dir.exists():
            raise ValueError(f"Directory does not exist: {input_dir}")
        
        self.anonymize = anonymize
        self.results = []
    
    def format_date(self, date_str: str) -> str:
        """Format DICOM date (YYYYMMDD) to readable format"""
        if not date_str or date_str == '':
            return ''
        try:
            # DICOM date format is YYYYMMDD
            if len(date_str) >= 8:
                year = date_str[0:4]
                month = date_str[4:6]
                day = date_str[6:8]
                return f"{day}/{month}/{year}"
            return date_str
        except:
            return date_str
    
    def format_time(self, time_str: str) -> str:
        """Format DICOM time (HHMMSS) to readable format"""
        if not time_str or time_str == '':
            return ''
        try:
            # DICOM time format is HHMMSS.FFFFFF
            if len(time_str) >= 6:
                hour = time_str[0:2]
                minute = time_str[2:4]
                second = time_str[4:6]
                return f"{hour}:{minute}:{second}"
            return time_str
        except:
            return time_str
    
    def anonymize_name(self, name: str, patient_id: str) -> str:
        """Anonymize patient name using patient ID"""
        if not name or name == '':
            return f"Patient_{patient_id}" if patient_id else "UNKNOWN"
        return f"Patient_{patient_id}"
    
    def extract_info(self, dcm_file: Path) -> Dict:
        """
        Extract patient, date, and body part information from DICOM file
        
        Returns:
            Dict with extracted information
        """
        try:
            ds = pydicom.dcmread(dcm_file, stop_before_pixels=True)
            
            # Extract patient information
            patient_name = str(getattr(ds, 'PatientName', '')).strip()
            patient_id = str(getattr(ds, 'PatientID', 'UNKNOWN')).strip()
            patient_birth_date = str(getattr(ds, 'PatientBirthDate', '')).strip()
            patient_sex = str(getattr(ds, 'PatientSex', '')).strip()
            
            # Anonymize if requested
            if self.anonymize and patient_name:
                display_name = self.anonymize_name(patient_name, patient_id)
            else:
                display_name = patient_name if patient_name else patient_id
            
            # Extract dates (try multiple date fields)
            study_date = str(getattr(ds, 'StudyDate', '')).strip()
            series_date = str(getattr(ds, 'SeriesDate', '')).strip()
            acquisition_date = str(getattr(ds, 'AcquisitionDate', '')).strip()
            content_date = str(getattr(ds, 'ContentDate', '')).strip()
            
            # Use the first available date
            observation_date = study_date or series_date or acquisition_date or content_date
            
            # Extract times
            study_time = str(getattr(ds, 'StudyTime', '')).strip()
            series_time = str(getattr(ds, 'SeriesTime', '')).strip()
            acquisition_time = str(getattr(ds, 'AcquisitionTime', '')).strip()
            
            observation_time = study_time or series_time or acquisition_time
            
            # Extract body part and descriptions
            body_part = str(getattr(ds, 'BodyPartExamined', '')).strip()
            study_desc = str(getattr(ds, 'StudyDescription', '')).strip()
            series_desc = str(getattr(ds, 'SeriesDescription', '')).strip()
            
            # Combine descriptions for examined area
            examined_area = body_part
            if study_desc and study_desc not in examined_area:
                examined_area = f"{body_part} - {study_desc}" if body_part else study_desc
            if series_desc and series_desc not in examined_area:
                examined_area = f"{examined_area} - {series_desc}" if examined_area else series_desc
            
            # Extract additional metadata
            modality = str(getattr(ds, 'Modality', '')).strip()
            institution = str(getattr(ds, 'InstitutionName', '')).strip()
            study_uid = str(getattr(ds, 'StudyInstanceUID', '')).strip()
            series_uid = str(getattr(ds, 'SeriesInstanceUID', '')).strip()
            series_number = str(getattr(ds, 'SeriesNumber', '')).strip()
            instance_number = str(getattr(ds, 'InstanceNumber', '')).strip()
            
            return {
                'file_path': str(dcm_file),
                'patient_name': display_name,
                'patient_id': patient_id,
                'patient_sex': patient_sex,
                'patient_birth_date': self.format_date(patient_birth_date),
                'observation_date': self.format_date(observation_date),
                'observation_time': self.format_time(observation_time),
                'observation_date_raw': observation_date,
                'examined_area': examined_area,
                'body_part': body_part,
                'study_description': study_desc,
                'series_description': series_desc,
                'modality': modality,
                'institution': institution,
                'study_uid': study_uid,
                'series_uid': series_uid,
                'series_number': series_number,
                'instance_number': instance_number,
            }
            
        except Exception as e:
            logger.warning(f"Error reading {dcm_file}: {e}")
            return {
                'file_path': str(dcm_file),
                'patient_name': 'ERROR',
                'patient_id': 'ERROR',
                'patient_sex': '',
                'patient_birth_date': '',
                'observation_date': '',
                'observation_time': '',
                'observation_date_raw': '',
                'examined_area': f'ERROR: {str(e)}',
                'body_part': '',
                'study_description': '',
                'series_description': '',
                'modality': '',
                'institution': '',
                'study_uid': '',
                'series_uid': '',
                'series_number': '',
                'instance_number': '',
            }
    
    def scan_directory(self) -> List[Dict]:
        """Scan directory and extract information from all DICOM files"""
        logger.info(f"Scanning directory: {self.input_dir}")
        
        # Find all DICOM files
        dcm_files = list(self.input_dir.rglob('*.dcm'))
        logger.info(f"Found {len(dcm_files)} DICOM files")
        
        if not dcm_files:
            logger.warning("No DICOM files found!")
            return []
        
        # Process each file
        results = []
        for idx, dcm_file in enumerate(dcm_files, 1):
            if idx % 100 == 0:
                logger.info(f"Processed {idx}/{len(dcm_files)} files...")
            
            info = self.extract_info(dcm_file)
            results.append(info)
        
        logger.info(f"Extracted information from {len(results)} files")
        self.results = results
        return results
    
    def save_report(self, output_file: str, minimal: bool = False):
        """Save results to CSV file"""
        if not self.results:
            logger.warning("No results to save")
            return
        
        df = pd.DataFrame(self.results)
        
        # Select columns based on mode
        if minimal:
            columns = ['patient_name', 'observation_date', 'examined_area', 'file_path']
            df_output = df[columns]
        else:
            df_output = df
        
        df_output.to_csv(output_file, index=False)
        logger.info(f"Report saved to: {output_file}")
        
        # Print summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Total DICOM files: {len(self.results)}")
        print(f"Unique patients: {df['patient_id'].nunique()}")
        print(f"Unique studies: {df['study_uid'].nunique()}")
        print(f"Unique series: {df['series_uid'].nunique()}")
        print(f"Modalities: {', '.join(df['modality'].unique())}")
        
        # Date range
        valid_dates = df[df['observation_date_raw'] != '']['observation_date_raw']
        if len(valid_dates) > 0:
            min_date = valid_dates.min()
            max_date = valid_dates.max()
            print(f"\nDate range: {self.format_date(min_date)} to {self.format_date(max_date)}")
        
        # Body parts summary
        print(f"\nBody parts examined:")
        body_parts = df[df['body_part'] != '']['body_part'].value_counts()
        for part, count in body_parts.head(10).items():
            print(f"  - {part}: {count} files")
        
        print(f"\nSample records:")
        print("-" * 80)
        for _, row in df.head(5).iterrows():
            print(f"Patient: {row['patient_name']}")
            print(f"  Date: {row['observation_date']} {row['observation_time']}")
            print(f"  Area: {row['examined_area']}")
            print(f"  File: {Path(row['file_path']).name}")
            print()


def main():
    parser = argparse.ArgumentParser(
        description='List patient, date, and body part information from DICOM files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Generate full report
  %(prog)s -i ./nm_images -o dicom_list.csv
  
  # Generate minimal report (only name, date, area, file)
  %(prog)s -i ./nm_images -o dicom_list.csv --minimal
  
  # Anonymize patient names
  %(prog)s -i ./nm_images -o dicom_list.csv --anonymize
  
  # Combine anonymization and minimal output
  %(prog)s -i ./nm_images -o dicom_list.csv --anonymize --minimal
        '''
    )
    
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Input directory containing DICOM files'
    )
    parser.add_argument(
        '-o', '--output',
        default='dicom_list.csv',
        help='Output CSV file (default: dicom_list.csv)'
    )
    parser.add_argument(
        '--minimal',
        action='store_true',
        help='Output only essential columns (patient_name, observation_date, examined_area, file_path)'
    )
    parser.add_argument(
        '--anonymize',
        action='store_true',
        help='Anonymize patient names (replace with Patient_ID)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create lister
    lister = DicomInfoLister(args.input, anonymize=args.anonymize)
    
    # Scan directory
    lister.scan_directory()
    
    # Save report
    if lister.results:
        lister.save_report(args.output, minimal=args.minimal)
    else:
        logger.error("No DICOM files processed!")


if __name__ == '__main__':
    main()

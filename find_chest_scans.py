#!/usr/bin/env python3
"""
Find Chest Scans in DICOM Files

Scans DICOM files and identifies chest/thorax scintigraphy images based on
DICOM tags like BodyPartExamined, SeriesDescription, and StudyDescription.
"""

import argparse
import logging
from pathlib import Path
from typing import List, Dict
import shutil

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


class ChestScanFinder:
    """Find chest/thorax scintigraphy scans in DICOM files"""
    
    # Keywords to identify chest scans (case-insensitive)
    CHEST_KEYWORDS = [
        'chest', 'thorax', 'lung', 'pulmonary', 
        'ventilation', 'perfusion', 'v/q', 'vq',
        'heart', 'myocardial', 'cardiac', 'coronary',
        'poumon', 'thoracique', 'cardiaque'  # French keywords
    ]
    
    def __init__(self, input_dir: str):
        self.input_dir = Path(input_dir)
        if not self.input_dir.exists():
            raise ValueError(f"Directory does not exist: {input_dir}")
        
        self.results = []
    
    def is_chest_scan(self, dcm_file: Path) -> Dict:
        """
        Check if DICOM file is a chest scan
        
        Returns:
            Dict with file info and matching criteria, or None if not a chest scan
        """
        try:
            ds = pydicom.dcmread(dcm_file, stop_before_pixels=True)
            
            # Extract relevant tags
            body_part = str(getattr(ds, 'BodyPartExamined', '')).lower()
            series_desc = str(getattr(ds, 'SeriesDescription', '')).lower()
            study_desc = str(getattr(ds, 'StudyDescription', '')).lower()
            modality = str(getattr(ds, 'Modality', '')).upper()
            patient_id = str(getattr(ds, 'PatientID', 'UNKNOWN'))
            study_uid = str(getattr(ds, 'StudyInstanceUID', 'UNKNOWN'))
            series_uid = str(getattr(ds, 'SeriesInstanceUID', 'UNKNOWN'))
            series_number = str(getattr(ds, 'SeriesNumber', ''))
            
            # Check for chest keywords
            matches = []
            matched_text = []
            
            for keyword in self.CHEST_KEYWORDS:
                if keyword in body_part:
                    matches.append('BodyPartExamined')
                    matched_text.append(f"BodyPart: {body_part}")
                    break
            
            for keyword in self.CHEST_KEYWORDS:
                if keyword in series_desc:
                    matches.append('SeriesDescription')
                    matched_text.append(f"Series: {series_desc}")
                    break
            
            for keyword in self.CHEST_KEYWORDS:
                if keyword in study_desc:
                    matches.append('StudyDescription')
                    matched_text.append(f"Study: {study_desc}")
                    break
            
            # If any match found, return info
            if matches:
                return {
                    'file': str(dcm_file),
                    'patient_id': patient_id,
                    'study_uid': study_uid,
                    'series_uid': series_uid,
                    'series_number': series_number,
                    'modality': modality,
                    'body_part': body_part,
                    'series_desc': series_desc,
                    'study_desc': study_desc,
                    'matched_on': ', '.join(matches),
                    'matched_text': ' | '.join(matched_text)
                }
            
            return None
            
        except Exception as e:
            logger.warning(f"Error reading {dcm_file}: {e}")
            return None
    
    def scan_directory(self) -> List[Dict]:
        """Scan directory for chest scans"""
        logger.info(f"Scanning directory: {self.input_dir}")
        
        # Find all DICOM files
        dcm_files = list(self.input_dir.rglob('*.dcm'))
        logger.info(f"Found {len(dcm_files)} DICOM files")
        
        if not dcm_files:
            logger.warning("No DICOM files found!")
            return []
        
        # Check each file
        chest_scans = []
        for idx, dcm_file in enumerate(dcm_files, 1):
            if idx % 100 == 0:
                logger.info(f"Processed {idx}/{len(dcm_files)} files...")
            
            result = self.is_chest_scan(dcm_file)
            if result:
                chest_scans.append(result)
                logger.info(f"✓ Found chest scan: {result['matched_text']}")
        
        logger.info(f"Found {len(chest_scans)} chest scans out of {len(dcm_files)} files")
        self.results = chest_scans
        return chest_scans
    
    def save_report(self, output_file: str):
        """Save results to CSV file"""
        if not self.results:
            logger.warning("No results to save")
            return
        
        df = pd.DataFrame(self.results)
        df.to_csv(output_file, index=False)
        logger.info(f"Report saved to: {output_file}")
        
        # Print summary
        print("\n" + "="*80)
        print("SUMMARY")
        print("="*80)
        print(f"Total DICOM files scanned: {len(list(self.input_dir.rglob('*.dcm')))}")
        print(f"Chest scans found: {len(self.results)}")
        print(f"\nUnique patients: {df['patient_id'].nunique()}")
        print(f"Unique studies: {df['study_uid'].nunique()}")
        print(f"Unique series: {df['series_uid'].nunique()}")
        
        if len(self.results) > 0:
            print(f"\nSample descriptions:")
            for _, row in df.head(5).iterrows():
                print(f"  - {row['series_desc']}")
    
    def copy_chest_scans(self, output_dir: str):
        """Copy chest scan files to separate directory"""
        if not self.results:
            logger.warning("No chest scans to copy")
            return
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Copying {len(self.results)} chest scans to {output_dir}")
        
        for result in self.results:
            src = Path(result['file'])
            # Preserve directory structure: PatientID/StudyUID/SeriesUID/
            rel_path = src.relative_to(self.input_dir)
            dst = output_path / rel_path
            
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        
        logger.info(f"Copied {len(self.results)} files to {output_dir}")


def main():
    parser = argparse.ArgumentParser(
        description='Find chest/thorax scintigraphy scans in DICOM files',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Scan and generate report
  %(prog)s -i ./nm_images -o chest_scans_report.csv
  
  # Scan and copy chest scans to separate directory
  %(prog)s -i ./nm_images -o chest_scans_report.csv --copy-to ./chest_scans
  
  # Scan with custom keywords
  %(prog)s -i ./nm_images -o report.csv --keywords "poumon,thorax,cardiaque"
        '''
    )
    
    parser.add_argument(
        '-i', '--input',
        required=True,
        help='Input directory containing DICOM files'
    )
    parser.add_argument(
        '-o', '--output',
        default='chest_scans_report.csv',
        help='Output CSV report file (default: chest_scans_report.csv)'
    )
    parser.add_argument(
        '--copy-to',
        help='Copy chest scan files to this directory'
    )
    parser.add_argument(
        '--keywords',
        help='Additional keywords to search for (comma-separated)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create finder
    finder = ChestScanFinder(args.input)
    
    # Add custom keywords if provided
    if args.keywords:
        custom_keywords = [kw.strip().lower() for kw in args.keywords.split(',')]
        finder.CHEST_KEYWORDS.extend(custom_keywords)
        logger.info(f"Added custom keywords: {custom_keywords}")
    
    # Scan directory
    finder.scan_directory()
    
    # Save report
    if finder.results:
        finder.save_report(args.output)
        
        # Copy files if requested
        if args.copy_to:
            finder.copy_chest_scans(args.copy_to)
    else:
        logger.warning("No chest scans found!")


if __name__ == '__main__':
    main()

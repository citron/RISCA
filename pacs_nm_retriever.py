#!/usr/bin/env python3
"""
PACS NM (Nuclear Medicine) Image Retriever

This script retrieves DICOM Nuclear Medicine images from a PACS server using DICOM C-FIND and C-MOVE operations.
Supports limiting the number of images retrieved or downloading everything.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

try:
    from pynetdicom import AE, evt, debug_logger
    from pynetdicom.sop_class import (
        PatientRootQueryRetrieveInformationModelFind,
        PatientRootQueryRetrieveInformationModelMove,
        StudyRootQueryRetrieveInformationModelFind,
        StudyRootQueryRetrieveInformationModelMove,
    )
    from pydicom.dataset import Dataset
except ImportError:
    print("Error: pynetdicom and pydicom are required. Install with:")
    print("  pip install pynetdicom pydicom")
    sys.exit(1)


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PACSNMRetriever:
    """Retrieve Nuclear Medicine DICOM images from PACS"""
    
    def __init__(
        self,
        pacs_host: str,
        pacs_port: int,
        pacs_aet: str,
        local_aet: str = "MY_LOCAL_AET",
        local_port: int = 11112,
        output_dir: str = "./nm_images",
        use_study_root: bool = True,
        dry_run: bool = False,
        use_c_get: bool = True  # Default to C-GET (simpler)
    ):
        self.pacs_host = pacs_host
        self.pacs_port = pacs_port
        self.pacs_aet = pacs_aet
        self.local_aet = local_aet
        self.local_port = local_port
        self.output_dir = Path(output_dir).resolve()
        
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Output directory: {self.output_dir}")
        except PermissionError as e:
            logger.error(f"Permission denied creating directory {self.output_dir}: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to create output directory {self.output_dir}: {e}")
            raise
        
        self.use_study_root = use_study_root
        self.dry_run = dry_run
        self.use_c_get = use_c_get
        
        # Initialize Application Entity
        self.ae = AE(ae_title=local_aet)
        
        # Set network timeout (30 seconds)
        self.ae.network_timeout = 30
        self.ae.acse_timeout = 30
        self.ae.dimse_timeout = 30
        
        # Add presentation contexts for query/retrieve
        if use_study_root:
            self.ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)
            if use_c_get:
                from pynetdicom.sop_class import StudyRootQueryRetrieveInformationModelGet
                self.ae.add_requested_context(StudyRootQueryRetrieveInformationModelGet)
            else:
                self.ae.add_requested_context(StudyRootQueryRetrieveInformationModelMove)
        else:
            self.ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
            if use_c_get:
                from pynetdicom.sop_class import PatientRootQueryRetrieveInformationModelGet
                self.ae.add_requested_context(PatientRootQueryRetrieveInformationModelGet)
            else:
                self.ae.add_requested_context(PatientRootQueryRetrieveInformationModelMove)
        
        # Add storage contexts for NM and ALL common DICOM SOP classes
        # This PACS might have NM data in different SOP classes
        from pynetdicom.sop_class import (
            NuclearMedicineImageStorage,
            CTImageStorage,
            MRImageStorage,
            UltrasoundImageStorage,
            SecondaryCaptureImageStorage,
            ComputedRadiographyImageStorage,
            DigitalXRayImageStorageForPresentation,
            DigitalXRayImageStorageForProcessing,
        )
        from pydicom.uid import (
            ImplicitVRLittleEndian,
            ExplicitVRLittleEndian,
            ExplicitVRBigEndian,
            JPEGBaseline8Bit,
            JPEG2000Lossless,
        )
        
        transfer_syntaxes = [
            ImplicitVRLittleEndian,
            ExplicitVRLittleEndian,
            ExplicitVRBigEndian,
            JPEGBaseline8Bit,
            JPEG2000Lossless,
        ]
        
        # Add all common storage SOP classes
        storage_classes = [
            NuclearMedicineImageStorage,
            CTImageStorage,
            MRImageStorage,
            UltrasoundImageStorage,
            SecondaryCaptureImageStorage,
            ComputedRadiographyImageStorage,
            DigitalXRayImageStorageForPresentation,
            DigitalXRayImageStorageForProcessing,
        ]
        
        # Add as both requested (for SCU) and supported (for SCP)
        for sop_class in storage_classes:
            for ts in transfer_syntaxes:
                self.ae.add_requested_context(sop_class, ts)
                self.ae.add_supported_context(sop_class, ts)
        
        self.image_count = 0
        
    def handle_store(self, event):
        """Handle C-STORE requests (incoming DICOM files)"""
        ds = event.dataset
        ds.file_meta = event.file_meta
        
        # Create directory structure: PatientID/StudyInstanceUID/SeriesInstanceUID/
        patient_id = getattr(ds, 'PatientID', 'UNKNOWN')
        study_uid = getattr(ds, 'StudyInstanceUID', 'UNKNOWN')
        series_uid = getattr(ds, 'SeriesInstanceUID', 'UNKNOWN')
        sop_uid = getattr(ds, 'SOPInstanceUID', 'UNKNOWN')
        
        # Sanitize directory names
        patient_id = "".join(c for c in patient_id if c.isalnum() or c in ('-', '_'))
        
        self.image_count += 1
        
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would store image {self.image_count}: {patient_id}/{study_uid}/{series_uid}/{sop_uid}.dcm")
            return 0x0000
        
        save_dir = self.output_dir / patient_id / study_uid / series_uid
        save_dir.mkdir(parents=True, exist_ok=True)
        
        # Save file
        filename = f"{sop_uid}.dcm"
        filepath = save_dir / filename
        
        try:
            ds.save_as(filepath, write_like_original=False)
            logger.info(f"Stored image {self.image_count}: {filepath}")
        except Exception as e:
            logger.error(f"Failed to save image {self.image_count}: {e}")
            return 0xC000  # Failure
        
        return 0x0000  # Success
    
    def find_nm_studies(self, limit: Optional[int] = None, study_date: str = '') -> list[Dataset]:
        """Find NM studies on PACS
        
        Args:
            limit: Maximum number of studies to return
            study_date: Study date filter (YYYYMMDD, YYYYMMDD-, -YYYYMMDD, or YYYYMMDD-YYYYMMDD)
        """
        logger.info(f"Searching for studies on {self.pacs_host}:{self.pacs_port}")
        
        if not study_date:
            # Default to last 30 days
            from datetime import datetime, timedelta
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)
            study_date = f"{start_date.strftime('%Y%m%d')}-{end_date.strftime('%Y%m%d')}"
            logger.info(f"No date specified, using last 30 days: {study_date}")
        
        # This PACS requires StudyDate filter
        ds = Dataset()
        ds.QueryRetrieveLevel = 'STUDY'
        ds.StudyDate = study_date
        ds.StudyInstanceUID = ''
        ds.PatientID = ''
        ds.ModalitiesInStudy = ''  # Request this field to filter by NM
        
        all_studies = []
        
        # Associate with PACS
        query_model = (StudyRootQueryRetrieveInformationModelFind if self.use_study_root
                      else PatientRootQueryRetrieveInformationModelFind)
        
        try:
            assoc = self.ae.associate(self.pacs_host, self.pacs_port, ae_title=self.pacs_aet)
            
            if assoc.is_established:
                logger.info(f"Sending C-FIND request for studies (date: {study_date})...")
                responses = assoc.send_c_find(ds, query_model)
                
                for status, identifier in responses:
                    if status and status.Status in (0xFF00, 0xFF01):  # Pending
                        if identifier:
                            all_studies.append(identifier)
                            if len(all_studies) % 100 == 0:
                                logger.info(f"Retrieved {len(all_studies)} studies so far...")
                
                assoc.release()
                logger.info(f"Retrieved {len(all_studies)} studies for date range {study_date}")
            else:
                logger.error("Failed to associate with PACS")
                return []
        except Exception as e:
            logger.error(f"Error during C-FIND: {e}")
            return []
        
        if not all_studies:
            logger.warning("No studies found for specified date range")
            return []
        
        # Filter for studies containing NM modality
        nm_studies = []
        for study in all_studies:
            modalities = getattr(study, 'ModalitiesInStudy', None)
            if modalities:
                # Convert to string for easier parsing
                modalities_str = str(modalities)
                logger.debug(f"Study modalities: {modalities_str} (type: {type(modalities).__name__})")
                
                # Check if NM is in the modalities
                if 'NM' in modalities_str:
                    nm_studies.append(study)
                    logger.info(f"Found NM study: {study.StudyInstanceUID} - Modalities: {modalities_str}")
                    
                    if limit and len(nm_studies) >= limit:
                        logger.info(f"Reached study limit of {limit}")
                        break
        
        # Return studies up to limit
        result_studies = nm_studies[:limit] if limit else nm_studies
        logger.info(f"Returning {len(result_studies)} NM studies (out of {len(all_studies)} total)")
        
        if len(nm_studies) == 0:
            logger.warning(f"No NM studies found in date range {study_date}")
            logger.warning(f"Total studies in range: {len(all_studies)}")
        
        return result_studies
    
    def _study_has_nm_series(self, study_uid: str) -> bool:
        """Check if a study has any NM series"""
        return True
    
    def find_nm_series(self, study_uid: str, limit: Optional[int] = None) -> list[Dataset]:
        """Find all NM series in a study"""
        ds = Dataset()
        ds.QueryRetrieveLevel = 'SERIES'
        ds.StudyInstanceUID = study_uid
        ds.Modality = 'NM'
        ds.SeriesInstanceUID = ''
        ds.SeriesDescription = ''
        ds.SeriesNumber = ''
        ds.NumberOfSeriesRelatedInstances = ''
        
        series = []
        
        query_model = (StudyRootQueryRetrieveInformationModelFind if self.use_study_root
                      else PatientRootQueryRetrieveInformationModelFind)
        
        try:
            assoc = self.ae.associate(self.pacs_host, self.pacs_port, ae_title=self.pacs_aet)
            
            if assoc.is_established:
                responses = assoc.send_c_find(ds, query_model)
                
                for status, identifier in responses:
                    if status and status.Status in (0xFF00, 0xFF01):
                        if identifier:
                            series.append(identifier)
                            
                            if limit and len(series) >= limit:
                                break
                
                assoc.release()
        except Exception as e:
            logger.error(f"Error finding series: {e}")
            
        return series
    
    def retrieve_study(self, study_uid: str) -> bool:
        """Retrieve only NM series from study using C-GET or C-MOVE"""
        logger.info(f"{'[DRY-RUN] ' if self.dry_run else ''}Retrieving NM series from study: {study_uid}")
        
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would retrieve NM series from study {study_uid}")
            return True
        
        # First, find NM series in this study
        nm_series = self.find_nm_series(study_uid)
        
        if not nm_series:
            logger.warning(f"No NM series found in study {study_uid}")
            return False
        
        logger.info(f"Found {len(nm_series)} NM series in study")
        
        # Retrieve each NM series
        success = True
        for series in nm_series:
            series_uid = series.SeriesInstanceUID
            
            # Create retrieve dataset for SERIES level
            ds = Dataset()
            ds.QueryRetrieveLevel = 'SERIES'
            ds.StudyInstanceUID = study_uid
            ds.SeriesInstanceUID = series_uid
            
            if self.use_c_get:
                if not self._retrieve_with_get(ds):
                    success = False
            else:
                if not self._retrieve_with_move(ds):
                    success = False
        
        return success
    
    def _retrieve_with_get(self, ds: Dataset) -> bool:
        """Retrieve using C-GET via DCMTK getscu (more reliable)"""
        import subprocess
        import shutil
        
        # Check if getscu is available
        if not shutil.which('getscu'):
            logger.error("getscu (DCMTK) not found in PATH")
            logger.error("Install with: apt-get install dcmtk")
            return False
        
        query_level = ds.QueryRetrieveLevel
        study_uid = ds.StudyInstanceUID
        
        # Build getscu command
        # Note: getscu doesn't support --filename-extension, files saved as-is from PACS
        cmd = [
            'getscu',
            '-v',  # Verbose
            '-S',  # Study Root
            '-aet', self.local_aet,
            '-aec', self.pacs_aet,
            self.pacs_host,
            str(self.pacs_port),
            '-k', f'QueryRetrieveLevel={query_level}',
            '-k', f'StudyInstanceUID={study_uid}',
        ]
        
        # Add SeriesInstanceUID if querying at SERIES level
        if query_level == 'SERIES' and hasattr(ds, 'SeriesInstanceUID'):
            series_uid = ds.SeriesInstanceUID
            cmd.extend(['-k', f'SeriesInstanceUID={series_uid}'])
            logger.info(f"Retrieving NM series {series_uid}...")
        else:
            logger.info(f"Retrieving study {study_uid}...")
        
        cmd.extend(['-od', str(self.output_dir)])
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5 minute timeout
            )
            
            if result.returncode == 0:
                # Parse output to count retrieved images
                completed = 0
                for line in result.stdout.split('\n'):
                    if 'Completed Suboperations' in line:
                        try:
                            completed = int(line.split(':')[1].strip())
                        except:
                            pass
                
                # Rename files without .dcm extension
                renamed_count = 0
                for root, dirs, files in os.walk(self.output_dir):
                    for filename in files:
                        if not filename.endswith('.dcm'):
                            old_path = Path(root) / filename
                            new_path = Path(root) / f"{filename}.dcm"
                            try:
                                old_path.rename(new_path)
                                renamed_count += 1
                            except Exception as e:
                                logger.warning(f"Failed to rename {old_path}: {e}")
                
                if renamed_count > 0:
                    logger.info(f"Renamed {renamed_count} files to add .dcm extension")
                
                if completed > 0:
                    self.image_count += completed
                    logger.info(f"Retrieved {completed} images")
                else:
                    logger.info(f"getscu completed (check {self.output_dir} for files)")
                    
                return True
            else:
                logger.error(f"getscu failed with return code {result.returncode}")
                if result.stderr:
                    logger.error(f"stderr: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"getscu timed out after 5 minutes")
            return False
        except Exception as e:
            logger.error(f"Error running getscu: {e}")
            return False
    
    def _retrieve_with_move(self, ds: Dataset) -> bool:
        """Retrieve using C-MOVE (requires storage SCP)"""
    def _retrieve_with_move(self, ds: Dataset) -> bool:
        """Retrieve using C-MOVE (requires storage SCP)"""
        # Setup storage SCP handlers
        handlers = [(evt.EVT_C_STORE, self.handle_store)]
        
        # Start storage SCP in background
        try:
            logger.info(f"Starting storage SCP on port {self.local_port}...")
            scp = self.ae.start_server(
                ('0.0.0.0', self.local_port),  # Listen on all interfaces
                block=False,
                evt_handlers=handlers
            )
            
            if scp:
                logger.info(f"Storage SCP started successfully on port {self.local_port}")
            else:
                logger.error("start_server returned None")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start storage SCP on port {self.local_port}: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False
        
        try:
            # Associate and send C-MOVE
            from pynetdicom.sop_class import (
                StudyRootQueryRetrieveInformationModelMove,
                PatientRootQueryRetrieveInformationModelMove
            )
            
            move_model = (StudyRootQueryRetrieveInformationModelMove if self.use_study_root
                         else PatientRootQueryRetrieveInformationModelMove)
            
            assoc = self.ae.associate(
                self.pacs_host,
                self.pacs_port,
                ae_title=self.pacs_aet
            )
            
            if assoc.is_established:
                responses = assoc.send_c_move(
                    ds,
                    self.local_aet,  # Destination AET (ourselves)
                    move_model
                )
                
                for status, identifier in responses:
                    if status:
                        logger.debug(f"C-MOVE status: 0x{status.Status:04x}")
                        if status.Status in (0xA701, 0xA702, 0xA900, 0xC000):
                            logger.warning(f"C-MOVE warning/error status: 0x{status.Status:04x}")
                
                assoc.release()
                return True
            else:
                logger.error("Failed to associate for C-MOVE")
                return False
        except Exception as e:
            logger.error(f"Error during C-MOVE: {e}")
            return False
        finally:
            scp.shutdown()
    
    def retrieve_images(
        self,
        max_studies: Optional[int] = None,
        max_images: Optional[int] = None
    ):
        """
        Retrieve NM images from PACS
        
        Args:
            max_studies: Maximum number of studies to retrieve (None = all)
            max_images: Maximum number of images to retrieve (None = all)
        """
        # Find studies
        studies = self.find_nm_studies(limit=max_studies, study_date=getattr(self, 'study_date', ''))
        
        if not studies:
            logger.warning("No NM studies found")
            return
        
        logger.info(f"Found {len(studies)} studies to retrieve")
        
        # Estimate total images
        total_images = sum(int(getattr(s, 'NumberOfStudyRelatedInstances', 0) or 0) for s in studies)
        if total_images > 0:
            logger.info(f"Estimated total images: {total_images}")
        
        if not self.dry_run:
            logger.warning("=" * 60)
            logger.warning("PRODUCTION MODE: Images will be downloaded!")
            logger.warning(f"Target: {self.pacs_host}:{self.pacs_port} ({self.pacs_aet})")
            logger.warning(f"Studies to retrieve: {len(studies)}")
            logger.warning(f"Output directory: {self.output_dir}")
            logger.warning("=" * 60)
        
        logger.info(f"Starting retrieval of {len(studies)} studies")
        
        for idx, study in enumerate(studies, 1):
            study_uid = study.StudyInstanceUID
            logger.info(f"Processing study {idx}/{len(studies)}: {study_uid}")
            
            self.retrieve_study(study_uid)
            
            if max_images and self.image_count >= max_images:
                logger.info(f"Reached image limit of {max_images}")
                break
        
        if self.dry_run:
            logger.info(f"[DRY-RUN] Would have retrieved approximately {self.image_count} images to {self.output_dir}")
        else:
            logger.info(f"Retrieval complete. Retrieved {self.image_count} images to {self.output_dir}")
        
        # Count actual files
        import os
        if os.path.exists(self.output_dir):
            total_files = len([f for f in os.listdir(self.output_dir) if os.path.isfile(os.path.join(self.output_dir, f))])
            logger.info(f"Total files in output directory: {total_files}")


def main():
    parser = argparse.ArgumentParser(
        description='Retrieve Nuclear Medicine DICOM images from PACS',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # DRY-RUN FIRST (RECOMMENDED): Test connection without downloading
  %(prog)s --dry-run
  
  # Retrieve maximum 5 studies (safer for initial test)
  %(prog)s --max-studies 5
  
  # Date range examples
  %(prog)s --from-date 20210901 --to-date 20210930 --max-studies 10
  %(prog)s --from-date 20210101 --to-date 20211231 --max-studies 50
  
  # Specific single date
  %(prog)s --study-date 20210901 --max-studies 5
  
  # Retrieve all NM images (use with caution!)
  %(prog)s
  
  # Use custom output directory
  %(prog)s --from-date 20210901 --to-date 20210930 -o /data/nm_images --max-studies 10
  
  # Override connection parameters if needed
  %(prog)s --host OTHER_HOST --aet OTHER_AET --local-aet OTHER_LOCAL
        '''
    )
    
    parser.add_argument(
        '--host',
        default=os.getenv('PACS_HOST'),
        help='PACS server hostname or IP address (required if not set in .env)'
    )
    parser.add_argument(
        '--port',
        type=int,
        default=int(os.getenv('PACS_PORT', '11112')),
        help='PACS server port (default: from .env or 11112)'
    )
    parser.add_argument(
        '--aet',
        default=os.getenv('PACS_AET'),
        help='PACS Application Entity Title (required if not set in .env)'
    )
    parser.add_argument(
        '--local-aet',
        default=os.getenv('LOCAL_AET', 'MY_LOCAL_AET'),
        help='Local Application Entity Title (default: from .env or MY_LOCAL_AET)'
    )
    parser.add_argument(
        '--local-port',
        type=int,
        default=int(os.getenv('LOCAL_PORT', '11112')),
        help='Local port for receiving images (default: from .env or 11112)'
    )
    parser.add_argument(
        '-o', '--output',
        default='./nm_images',
        help='Output directory for DICOM files (default: ./nm_images)'
    )
    parser.add_argument(
        '--max-studies',
        type=int,
        help='Maximum number of studies to retrieve (default: all)'
    )
    parser.add_argument(
        '--max-images',
        type=int,
        help='Maximum number of images to retrieve (default: all)'
    )
    parser.add_argument(
        '--study-date',
        help='Study date: YYYYMMDD, YYYYMMDD-, -YYYYMMDD, or YYYYMMDD-YYYYMMDD (deprecated, use --from-date/--to-date)'
    )
    parser.add_argument(
        '--from-date',
        help='Start date (YYYYMMDD) - retrieves studies from this date onwards'
    )
    parser.add_argument(
        '--to-date',
        help='End date (YYYYMMDD) - retrieves studies up to this date'
    )
    parser.add_argument(
        '--use-c-move',
        action='store_true',
        help='Use C-MOVE instead of C-GET (requires network routing and storage SCP)'
    )
    parser.add_argument(
        '--patient-root',
        action='store_true',
        help='Use Patient Root model instead of Study Root (Study Root is default for this PACS)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Perform queries but do not download images (test mode)'
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help='Enable debug logging'
    )
    
    args = parser.parse_args()
    
    # Validate required arguments
    if not args.host:
        parser.error("--host is required (set in .env or provide as argument)")
    if not args.aet:
        parser.error("--aet is required (set in .env or provide as argument)")
    
    if args.debug:
        debug_logger()
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create retriever
    retriever = PACSNMRetriever(
        pacs_host=args.host,
        pacs_port=args.port,
        pacs_aet=args.aet,
        local_aet=args.local_aet,
        local_port=args.local_port,
        output_dir=args.output,
        use_study_root=not args.patient_root,  # Study Root is default
        dry_run=args.dry_run,
        use_c_get=not args.use_c_move  # C-GET is default
    )
    
    # Set study date if provided
    if args.from_date or args.to_date:
        # Build date range from --from-date and --to-date
        from_date = args.from_date or '19700101'  # Default to beginning of time
        to_date = args.to_date or '29991231'  # Default to far future
        retriever.study_date = f"{from_date}-{to_date}"
        logger.info(f"Date range: {from_date} to {to_date}")
    elif args.study_date:
        retriever.study_date = args.study_date
        logger.info(f"Using study date filter: {args.study_date}")
    else:
        # Default to None - will use last 30 days in find_nm_studies
        retriever.study_date = None
    
    # Retrieve images
    try:
        retriever.retrieve_images(
            max_studies=args.max_studies,
            max_images=args.max_images
        )
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error during retrieval: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

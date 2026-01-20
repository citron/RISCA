# PACS NM Retriever - Production Safety Checklist

## ✅ CRITICAL FIXES APPLIED

### 1. **Port Configuration** ✓
- **Issue**: Hard-coded port 11112 could conflict
- **Fix**: Added `--local-port` parameter (default: 11112)
- **Action**: Use different port if 11112 is occupied

### 2. **Transfer Syntax Support** ✓
- **Issue**: Only one transfer syntax supported
- **Fix**: Added support for:
  - ImplicitVRLittleEndian
  - ExplicitVRLittleEndian
  - ExplicitVRBigEndian
  - JPEGBaseline8Bit
  - JPEG2000Lossless

### 3. **Timeout Protection** ✓
- **Issue**: No timeouts could cause hanging
- **Fix**: Set 30-second timeouts for:
  - Network operations
  - ACSE (Association Control Service Element)
  - DIMSE (DICOM Message Service Element)

### 4. **Error Handling** ✓
- **Issue**: Incomplete error handling
- **Fix**: Added try-catch blocks for all PACS operations
- **Result**: Graceful failure with proper cleanup

### 5. **Dry-Run Mode** ✓
- **Issue**: No way to test without downloading
- **Fix**: Added `--dry-run` flag
- **Result**: Test queries without actual data transfer

### 6. **Better Logging** ✓
- **Issue**: Insufficient error details
- **Fix**: Added detailed status logging and warnings

## 📋 PRE-FLIGHT CHECKLIST

### Before First Run:

1. **Install Dependencies**
   ```bash
   pip install pynetdicom pydicom
   ```

2. **Verify PACS Configuration**
   - [ ] PACS hostname/IP correct
   - [ ] PACS port correct (typically 11112 or 104)
   - [ ] PACS AET (Application Entity Title) correct
   - [ ] Your local AET is registered/allowed on PACS

3. **Network Requirements**
   - [ ] Firewall allows outbound to PACS port
   - [ ] Firewall allows inbound to local port (for C-STORE)
   - [ ] No port conflicts on local port

4. **Test Connection First**
   ```bash
   # Parameters are pre-configured - just run:
   python pacs_nm_retriever.py --dry-run
   ```

5. **Small Test Retrieval**
   ```bash
   # Retrieve only 1 study first
   python pacs_nm_retriever.py --max-studies 1 -o ./test_output
   ```

6. **Check Disk Space**
   - [ ] Sufficient disk space for DICOM images
   - [ ] NM studies can be 100MB - 1GB+ each

## 🔧 RECOMMENDED USAGE PATTERN

**NOTE: Parameters are pre-configured for your PACS:**
- Host: `172.19.32.28`
- Port: `11112`
- PACS AET: `EE2006194AMIP`
- Local AET: `ALBIZIA_WG`

### Step 1: Dry-Run (ALWAYS DO THIS FIRST)
```bash
python pacs_nm_retriever.py --dry-run --debug
```
**Expected**: Lists found NM studies without downloading

### Step 2: Small Limited Test
```bash
python pacs_nm_retriever.py --max-studies 1 -o ./test_nm
```
**Expected**: Downloads 1 study successfully

### Step 3: Production Run (if Step 1 & 2 OK)
```bash
python pacs_nm_retriever.py --max-studies 100 -o /path/to/output
```

## ⚠️ IMPORTANT WARNINGS

### 1. Network Load
- Retrieving many studies creates significant network traffic
- Consider running during off-peak hours
- Use `--max-studies` to limit scope

### 2. PACS Impact
- C-FIND and C-MOVE are standard operations
- Script is read-only (no data modification)
- Still, monitor PACS load during first runs

### 3. Disk Space
- Monitor disk usage during retrieval
- NM images are often large (multi-frame)
- Script creates directory structure: PatientID/StudyUID/SeriesUID/

### 4. PHI/Privacy
- DICOM files contain Protected Health Information
- Ensure output directory has proper permissions
- Follow your institution's data handling policies

### 5. Association Limits
- Some PACS limit concurrent associations
- Script uses one association at a time
- If retrieval fails, check PACS association logs

## 🐛 TROUBLESHOOTING

### "Failed to associate with PACS"
- Check PACS hostname/IP and port
- Verify PACS AET is correct
- Confirm your local AET is allowed on PACS
- Check firewall rules

### "Failed to start storage SCP"
- Port conflict on local port
- Try different port: `--local-port 11113`
- Check if another process is using the port

### "No NM studies found"
- PACS may not have NM modality data
- Try `--debug` to see query details
- Verify modality filter is correct

### Timeout errors
- Network latency too high
- PACS under heavy load
- Try during off-peak hours

### "C-MOVE warning/error status"
- Check PACS logs for specific errors
- Verify destination AET matches local AET
- Ensure storage SCP is reachable from PACS

## 📊 MONITORING DURING RUN

Watch for:
- Studies found count (should match expectation)
- Images received count (incremental progress)
- Error messages (red flags)
- Disk space consumption
- Network bandwidth usage

## 🛑 EMERGENCY STOP

Press `Ctrl+C` to interrupt gracefully:
- Current association will be released
- Storage SCP will shut down
- Partial downloads are kept

## ✅ VALIDATION AFTER RUN

1. Check image count matches expectation
2. Verify DICOM files are valid:
   ```bash
   # Use pydicom to validate
   python -c "import pydicom; pydicom.dcmread('path/to/file.dcm')"
   ```
3. Check directory structure is correct
4. Verify no errors in logs

## 📝 COMMAND REFERENCE

**Pre-configured defaults:**
- PACS: 172.19.32.28:11112 (EE2006194AMIP)
- Local AET: ALBIZIA_WG

```bash
# Simplest commands (using defaults)
python pacs_nm_retriever.py --dry-run           # Test only
python pacs_nm_retriever.py --max-studies 5     # Get 5 studies

# Full command with all options (override defaults if needed)
python pacs_nm_retriever.py \
  --host 172.19.32.28 \        # Optional: already default
  --port 11112 \               # Optional: already default
  --aet EE2006194AMIP \        # Optional: already default
  --local-aet ALBIZIA_WG \     # Optional: already default
  --local-port 11112 \         # Optional: default 11112
  -o OUTPUT_DIR \              # Optional: default ./nm_images
  --max-studies N \            # Optional: limit studies
  --max-images N \             # Optional: limit images
  --study-root \               # Optional: use Study Root model
  --dry-run \                  # Optional: test without download
  --debug                      # Optional: verbose logging
```

## 🔒 SECURITY NOTES

- Script is READ-ONLY (only queries and retrieves)
- No data is sent TO the PACS (only FROM)
- No modification of PACS data
- Uses standard DICOM protocols (C-FIND, C-MOVE, C-STORE)
- Secure communication depends on network setup (consider VPN/private network)

---

**Last Updated**: 2026-01-19
**Script Version**: pacs_nm_retriever.py (Production-Ready)

# PACS NM Retriever - Quick Start Guide

## Pre-configured for your PACS

```
PACS Server:  172.19.32.28:11112
PACS AET:     EE2006194AMIP
Local AET:    ALBIZIA_WG
```

## Installation

```bash
pip install pynetdicom pydicom
```

## Usage (3 Simple Steps)

### Step 1: Test Connection (Dry-Run)
```bash
python pacs_nm_retriever.py --dry-run
```
**This will:**
- Connect to PACS
- Query for NM studies
- List what would be downloaded
- **NOT download anything**

### Step 2: Download 1 Study (Test)
```bash
python pacs_nm_retriever.py --max-studies 1
```
**This will:**
- Download 1 NM study
- Save to `./nm_images/`
- Verify everything works

### Step 3: Production Download
```bash
# Download specific number of studies
python pacs_nm_retriever.py --max-studies 10

# Download from date range
python pacs_nm_retriever.py --from-date 20210901 --to-date 20210930 --max-studies 50

# Download all NM studies (careful!)
python pacs_nm_retriever.py

# Custom output directory
python pacs_nm_retriever.py --from-date 20210901 --to-date 20210930 -o /data/nm_images
```

## Common Options

| Option | Description | Example |
|--------|-------------|---------|
| `--dry-run` | Test without downloading | `--dry-run` |
| `--max-studies N` | Limit to N studies | `--max-studies 10` |
| `--max-images N` | Limit to N images | `--max-images 100` |
| `--from-date YYYYMMDD` | Start date | `--from-date 20210901` |
| `--to-date YYYYMMDD` | End date | `--to-date 20210930` |
| `--study-date YYYYMMDD` | Specific date or range | `--study-date 20210901` |
| `-o DIR` | Output directory | `-o /data/nm` |
| `--debug` | Verbose logging | `--debug` |
| `--local-port N` | Local port for receiving | `--local-port 11113` |

## Date Range Examples

```bash
# Download NM studies for September 2021
python pacs_nm_retriever.py --from-date 20210901 --to-date 20210930 --max-studies 20

# Download NM studies for entire year 2021
python pacs_nm_retriever.py --from-date 20210101 --to-date 20211231 --max-studies 100

# Download from specific date to now
python pacs_nm_retriever.py --from-date 20210901 --max-studies 30

# Download up to specific date
python pacs_nm_retriever.py --to-date 20211231 --max-studies 25
```

## Output Structure

```
nm_images/
├── PatientID1/
│   └── StudyInstanceUID1/
│       └── SeriesInstanceUID1/
│           ├── SOPInstanceUID1.dcm
│           ├── SOPInstanceUID2.dcm
│           └── ...
└── PatientID2/
    └── ...
```

## Troubleshooting

### Connection Failed
```bash
# Test with debug
python pacs_nm_retriever.py --dry-run --debug

# Check if port is free
netstat -an | grep 11112
```

### Port Already in Use
```bash
# Use different local port
python pacs_nm_retriever.py --local-port 11113
```

### No Studies Found
- PACS might not have NM (Nuclear Medicine) studies
- Check with `--debug` flag for details

## Safety Features

- ✅ Read-only (won't modify PACS)
- ✅ 30-second timeouts (won't hang)
- ✅ Graceful interrupt (Ctrl+C anytime)
- ✅ Error recovery
- ✅ Production warnings

## Need Help?

See detailed documentation:
- `PACS_SAFETY_CHECKLIST.md` - Complete safety guide
- `python pacs_nm_retriever.py --help` - All options

## Emergency Stop

Press `Ctrl+C` to stop at any time. The script will:
- Release PACS connection
- Shutdown storage server
- Keep already downloaded files

---

**Ready to start? Run:** `python pacs_nm_retriever.py --dry-run`

# DocForge

**Offline Document Intelligence for PDF Collections**

DocForge automatically processes, classifies, renames, and organizes PDF document collections using local Vision-Language Models — completely offline, no cloud APIs, no data leaves your machine.

Drop a folder of messy PDFs, get clean descriptive filenames and organized folder structures.

---

## Before & After

```
BEFORE:                                          AFTER:
IMG_20231105_scan.pdf                       →    quarterly_financial_report_q3_2023.pdf
Document (3).pdf                            →    deep_learning_specialization_certificate_2020.pdf
scan_0042.pdf                               →    independent_contractor_agreement_nda_2025.pdf
IMG_3847.pdf                                →    pan_card_identity_document_2023.pdf
Copy of Final_v2_FINAL.pdf                  →    btech_degree_certificate_university_2022.pdf
```

---

## Features

- **VLM-Powered Naming** — Uses local Vision-Language Models (via [Ollama](https://ollama.ai)) to read each page and generate descriptive filenames
- **Heuristic Fallback** — Fast regex + metadata extraction when VLM is unavailable or for quick processing
- **OCR Support** — Tesseract integration for scanned/image-only PDFs
- **Smart Organisation** — Automatically sorts files into folders by type, year, or domain
- **Dry-Run Preview** — See all proposed changes before anything is modified
- **Full Rollback** — Undo any rename/move operation by job ID
- **Multi-Format Export** — Export processing results to Excel, JSON, CSV, or Markdown
- **100% Offline** — Everything runs locally. Your documents never leave your machine
- **Cross-Platform** — Works on Windows, macOS, and Linux

---

## Quick Start

### 1. Install

```bash
# Clone the repository
git clone https://github.com/your-username/DocForge.git
cd DocForge

# Create virtual environment
python -m venv venv
source venv/bin/activate        # Linux/macOS
# venv\Scripts\activate         # Windows

# Install in development mode
pip install -e .
```

### 2. Setup

```bash
docforge setup
```

This interactive wizard will:
- Check Python version and dependencies
- Detect your hardware (CPU, RAM, GPU)
- Install and configure Ollama + VLM model
- Detect Tesseract OCR (optional)
- Generate optimized configuration

### 3. Process Your PDFs

```bash
# Process a folder of PDFs (dry-run by default)
docforge process /path/to/your/pdfs

# Preview the proposed renames
docforge rename

# Apply renames when satisfied
docforge rename --execute

# Export results to Excel
docforge export -f excel
```

---

## How It Works

DocForge runs a 5-stage pipeline on each PDF:

```
PDF File
  │
  ├─ Stage 1: Metadata Extraction    (PDF info dict, page count, file hash)
  ├─ Stage 2: Text Probe             (embedded text extraction + quality scoring)
  ├─ Stage 3: Content Extraction      (VLM vision pass OR heuristic regex)
  ├─ Stage 4: Field Merging           (combine sources, resolve conflicts)
  └─ Stage 5: Filename Generation     (VLM-suggested name or template-based)
```

### VLM Naming (Default)

When Ollama is available, DocForge renders each PDF page as an image and sends it to a local Vision-Language Model with the prompt: *"Look at this document and generate a descriptive filename."*

The VLM sees the page exactly as a human would — reading titles, logos, names, dates, stamps, and layout — and produces a clean, descriptive filename.

### Heuristic Fallback

When VLM is unavailable (no GPU, no Ollama), DocForge falls back to fast heuristic extraction:
- Largest-font text detection for titles
- Regex patterns for dates, authors, organizations, report IDs
- Document type classification via keyword scoring
- Template-based filename assembly

---

## CLI Commands

| Command | Description |
|---------|-------------|
| `docforge setup` | First-run wizard: check dependencies, configure, download models |
| `docforge process <path>` | Process PDFs: extract metadata, classify, generate names |
| `docforge scan <path>` | Scan a directory and register PDFs in the database |
| `docforge rename` | Preview proposed file renames (dry-run) |
| `docforge rename --execute` | Apply file renames |
| `docforge organize` | Organize files into folder structure |
| `docforge export -f <format>` | Export results (excel, json, csv, markdown) |
| `docforge status` | Show processing progress and statistics |
| `docforge rollback` | Undo rename/move operations |
| `docforge model list` | List available and installed VLM models |
| `docforge model pull` | Download a VLM model via Ollama |

### Common Options

```bash
docforge process /path/to/pdfs --vlm          # Enable VLM (default)
docforge process /path/to/pdfs --no-vlm       # Heuristic only (fast, no GPU needed)
docforge process /path/to/pdfs -m llava       # Use a specific model
docforge process /path/to/pdfs --execute      # Process + rename in one step
docforge process /path/to/pdfs -v             # Verbose logging
```

---

## Supported VLM Models

DocForge uses [Ollama](https://ollama.ai) to run Vision-Language Models locally:

| Model | Size | RAM Required | Quality |
|-------|------|-------------|---------|
| `minicpm-v` | 5.4 GB | 8+ GB | Best |
| `llava` | 4.7 GB | 6+ GB | Good |
| `moondream` | 1.7 GB | 4+ GB | Lightweight |

```bash
# Install Ollama (https://ollama.ai)
# Pull a model
ollama pull minicpm-v
```

---

## Folder Organisation Strategies

```bash
docforge organize -s type          # By document type (default)
docforge organize -s year          # By year
docforge organize -s year_type     # Year → Type
docforge organize -s domain_type   # Domain → Type (academic, employment, financial...)
docforge organize -s domain_year   # Domain → Type → Year
```

**Example output with `domain_type`:**

```
organized/
├── academic/
│   ├── certificate/
│   └── project_report/
├── employment/
│   ├── offer_letter/
│   └── contract/
├── financial/
│   └── invoice/
├── identity/
│   ├── id_card/
│   └── license/
└── general/
    └── other/
```

---

## Configuration

DocForge stores configuration at `~/.docforge/config.toml`. Generated automatically by `docforge setup`, or create manually:

```toml
[general]
db_path = "~/.docforge/state.db"
log_level = "INFO"

[vlm]
enabled = true
model = "minicpm-v"
runtime = "ollama"

[naming]
max_length = 80
default_template = "{type}_{org}_{title_short}_{year}"

[organizer]
enabled = true
strategy = "type"
base_dir = "./organized"

[safety]
dry_run = true    # Preview by default, --execute to apply
```

---

## Project Structure

```
DocForge/
├── src/docforge/
│   ├── cli/              # Click CLI commands (scan, process, rename, export...)
│   ├── extractors/       # Metadata, text, heuristic, and VLM extractors
│   ├── infra/            # Configuration, hardware profiling, logging
│   ├── models/           # Data models, enums, field definitions
│   ├── naming/           # Filename generation, templates, sanitization
│   ├── ocr/              # Tesseract OCR integration
│   ├── organizer/        # Folder organisation strategies
│   ├── pipeline/         # Orchestrator, router, scheduler, workers
│   ├── renamer/          # File rename execution with rollback
│   ├── reporting/        # Export (Excel, JSON, CSV, Markdown) + formatters
│   ├── scanner.py        # Directory scanning and PDF discovery
│   ├── storage/          # SQLite state database
│   └── vlm/              # Ollama runtime, prompt engineering, response parsing
├── tests/                # 110 pytest tests
├── scripts/              # Benchmark and test PDF generation utilities
└── pyproject.toml
```

---

## Requirements

- **Python** 3.10+
- **Ollama** (optional, for VLM-powered naming) — [ollama.ai](https://ollama.ai)
- **Tesseract** (optional, for OCR) — [tesseract-ocr](https://github.com/UB-Mannheim/tesseract/wiki)

### Hardware Recommendations

| Setup | RAM | GPU | Processing Speed |
|-------|-----|-----|-----------------|
| Heuristic only | 4 GB | None | ~50ms per PDF |
| VLM (minicpm-v) | 8+ GB | Any (4GB+ VRAM) | ~40s per PDF |
| VLM (moondream) | 4+ GB | Optional | ~20s per PDF |

---

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run tests with coverage
pytest --cov=docforge

# Lint
ruff check src/

# Type check
mypy src/docforge/
```

---

## License

MIT License. See [LICENSE](LICENSE) for details.

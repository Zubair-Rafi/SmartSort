# SmartSort — Intelligent Download Organizer

A lightweight, cross-platform desktop utility that automatically monitors, analyzes, and organizes files downloaded by users.

> **Operating Systems Course Project — Semester 5**

---

## Features (Milestone 1)

- **Extension-based classification** — 100+ file extensions mapped to a hierarchical category tree
- **Safe file moves** — atomic rename on same filesystem; copy-verify-delete across filesystems
- **Conflict resolution** — automatic `file (1).pdf` renaming, never silent overwrites
- **Activity history** — every operation recorded in SQLite with undo support
- **Watched directory management** — add/remove directories from the Settings panel
- **Cross-platform** — Windows, Linux, macOS via a single codebase

## Quick Start

```bash
# 1. Create a virtual environment
python -m venv .venv

# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the application
python -m app.main

# 4. Run tests
pip install -r requirements-dev.txt
pytest tests/ -v
```

## Project Structure

```
smart-sort/
├── app/
│   ├── main.py                    # Entry point
│   ├── core/
│   │   ├── classification/        # 5-stage classification pipeline
│   │   ├── file_ops/              # safe_move, conflict resolution
│   │   ├── history/               # Operation recording + undo
│   │   └── sync/                  # Per-path locks (PathLockManager)
│   ├── platform/                  # OS adapters (Windows/Linux/macOS)
│   ├── database/                  # SQLite layer (WAL mode)
│   ├── services/                  # OrganizerService coordinator
│   └── ui/                        # PySide6 panels
├── resources/
│   └── categories_default.json   # Default category hierarchy
├── tests/
│   └── unit/                     # pytest unit tests
├── requirements.txt
└── requirements-dev.txt
```

## OS Concepts Demonstrated

| Concept | Where |
|---|---|
| **Filesystem monitoring** | `watchdog` (Milestone 2) |
| **Directory traversal** | `OrganizerService.organize_existing_files()` using `os.scandir()` |
| **File metadata access** | `FileTypeClassifier` — extension lookup without opening files |
| **Safe file I/O** | `safe_move()` — atomic rename vs. copy-verify-delete |
| **Multithreading** | `ThreadPoolExecutor`, `QThread` workers |
| **Synchronization** | `PathLockManager` (per-path mutex), `threading.RLock` on config |
| **Memory management** | Bounded text extraction (Milestone 3) |
| **OS abstraction** | `PlatformAdapter` hides Win/Linux/macOS differences |
| **IPC via signals** | Qt signals carry results across thread boundaries |

## Classification Pipeline

```
File detected
     ↓
Stage 1: Extension → category (zero I/O)
     ↓ (if confidence < auto_confirm_threshold)
Stage 2: Filename keyword analysis           [Milestone 2]
     ↓
Stage 3: Document metadata extraction        [Milestone 3]
     ↓
Stage 4: TF-IDF semantic classification      [Milestone 3]
     ↓
Stage 5: Confidence threshold decision       [running]
     ↓
Auto-move or Review Queue
```

## Milestone Status

- [x] **M1** Foundation — extension classification, safe moves, UI shell, SQLite history
- [ ] **M2** Filesystem monitoring — Watchdog, download-completion detection
- [ ] **M3** Intelligent classification — metadata, text extraction, TF-IDF
- [ ] **M4** Custom rules and category management
- [ ] **M5** Full UI polish and notifications
- [ ] **M6** Undo, conflict handling, error recovery
- [ ] **M7** Cross-platform validation and packaging

## Platform Notes

- **Windows**: Fully tested. Mandatory file locking used for download-detection.
- **Linux**: Fully tested. `/proc/<pid>/fd` scanning for open-file detection.
- **macOS**: Implemented but not yet tested on real hardware. Advisory locking only.

## Technology Stack

| Component | Library |
|---|---|
| GUI | PySide6 |
| FS monitoring | watchdog |
| PDF extraction | pypdf |
| DOCX extraction | python-docx |
| EPUB extraction | ebooklib |
| Text analysis | scikit-learn |
| Database | SQLite (stdlib) |
| Paths | platformdirs + pathlib |
| Testing | pytest |

## License

University course project — not for redistribution.

# SmartSort — Architecture, Strategy & Implementation Roadmap

---

## 1. Project Understanding

SmartSort is a **background-first, event-driven** desktop utility whose primary value proposition is *intelligent automatic organization* — not just sorting files into extension-based buckets, but classifying them by what they actually *are*.

The three core design tensions that must be managed throughout the project:

| Tension | Left pole | Right pole |
|---|---|---|
| Intelligence vs. Privacy | Rich semantic understanding | Fully offline, local processing |
| Automation vs. Safety | Zero user friction | Never silently destroy data |
| Lightweight vs. Capable | Minimal resource use | Multi-stage content analysis |

Every architectural decision should be evaluated against these three trade-offs.

**What makes this an OS project, not just a Python script:** The interesting OS work is in the monitoring loop (filesystem events, inotify/ReadDirectoryChangesW/FSEvents), the background thread pool, synchronization primitives preventing race conditions on simultaneous downloads, safe cross-filesystem file moves, and platform-abstracted path/permission handling.

---

## 2. Architecture Proposal

### 2.1 Component Map

```
┌─────────────────────────────────────────────────────────────────┐
│                         UI Layer (PySide6)                       │
│  Dashboard │ History │ Categories │ Rules │ Review Queue │ Settings │
└──────────────────────────┬──────────────────────────────────────┘
                           │ Qt Signals / slots (thread-safe)
┌──────────────────────────▼──────────────────────────────────────┐
│                      Service Layer                               │
│  OrganizerService  │  RuleEngine  │  HistoryService             │
│  (coordinates all pipeline stages)                              │
└───┬──────────┬──────────┬────────────────────────────────────────┘
    │          │          │
    ▼          ▼          ▼
┌───────┐ ┌───────┐ ┌───────────────────────────────────────────┐
│Monitor│ │ Rule  │ │           Classification Pipeline          │
│Worker │ │Engine │ │  Stage1    Stage2    Stage3    Stage4      │
│       │ │       │ │ FileType→Filename→ Metadata→ TF-IDF       │
│Watch- │ │Rules  │ │ +Magic   Patterns  Extraction Classifier   │
│dog    │ │JSON   │ │                                            │
└───┬───┘ └───────┘ └────────────────────────────────────────────┘
    │
    ▼ filesystem events (thread-safe queue)
┌──────────────────────────────────────┐
│          Event Processor             │
│  Dedup cache │ Stability checker     │
│  (is download complete?)             │
└──────────────────┬───────────────────┘
                   │
                   ▼
         ┌─────────────────┐
         │  File Ops Layer  │
         │  safe_move()    │
         │  conflict_resolve│
         │  undo stack     │
         └────────┬────────┘
                  │
         ┌────────▼────────┐
         │  Database Layer  │
         │  SQLite          │
         │  history + cfg   │
         └─────────────────┘
```

### 2.2 Proposed Directory Structure

```
smart-sort/
├── app/
│   ├── main.py                    # Entry point, QApplication bootstrap
│   ├── core/
│   │   ├── monitoring/
│   │   │   ├── watcher.py         # Watchdog event handler
│   │   │   ├── event_queue.py     # Thread-safe bounded queue
│   │   │   ├── stability.py       # Download-complete detection
│   │   │   └── dedup.py           # Event deduplication cache
│   │   ├── classification/
│   │   │   ├── pipeline.py        # Orchestrates stages 1-5
│   │   │   ├── file_type.py       # Stage 1: extension + magic bytes
│   │   │   ├── filename_analysis.py # Stage 2: pattern matching
│   │   │   ├── metadata.py        # Stage 2b: PDF/DOCX/EXIF metadata
│   │   │   ├── tfidf_classifier.py # Stage 4: scikit-learn classifier
│   │   │   ├── confidence.py      # Stage 5: threshold decisions
│   │   │   └── base.py            # Abstract classifier interface
│   │   ├── extraction/
│   │   │   ├── extractor.py       # Factory / dispatcher
│   │   │   ├── pdf_extractor.py   # pypdf
│   │   │   ├── docx_extractor.py  # python-docx
│   │   │   ├── epub_extractor.py  # ebooklib
│   │   │   └── txt_extractor.py   # plain text
│   │   ├── rules/
│   │   │   ├── rule_engine.py     # Priority-ordered evaluation
│   │   │   ├── rule_model.py      # Rule dataclass / serialization
│   │   │   └── built_in_rules.py  # Defaults (editable)
│   │   ├── file_ops/
│   │   │   ├── mover.py           # safe_move, cross-fs detection
│   │   │   ├── conflict.py        # Rename strategy
│   │   │   └── undo.py            # Undo stack operations
│   │   ├── history/
│   │   │   └── history_service.py # CRUD on SQLite history table
│   │   └── sync/
│   │       └── locks.py           # Named file locks, path-level mutex
│   ├── platform/
│   │   ├── base.py                # Abstract PlatformAdapter
│   │   ├── windows.py             # Win32 paths, APPDATA, locking
│   │   ├── linux.py               # XDG dirs, inotify notes
│   │   └── macos.py               # ~/Library paths, FSEvents notes
│   ├── database/
│   │   ├── db.py                  # SQLite connection pool (thread-safe)
│   │   ├── migrations.py          # Schema versioning
│   │   └── models.py              # dataclasses for DB rows
│   ├── ui/
│   │   ├── main_window.py
│   │   ├── dashboard.py
│   │   ├── history_view.py
│   │   ├── categories_view.py
│   │   ├── rules_view.py
│   │   ├── review_queue.py
│   │   ├── settings_view.py
│   │   └── widgets/               # Reusable custom widgets
│   ├── services/
│   │   └── organizer_service.py   # Top-level coordinator
│   └── utils/
│       ├── config.py              # JSON/SQLite config manager
│       ├── logging_setup.py
│       └── path_utils.py          # Safe path manipulation
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/                  # Sample files for testing
├── resources/
│   ├── categories_default.json    # Default category tree
│   └── icons/
├── docs/
├── requirements.txt
└── README.md
```

### 2.3 Key Design Decisions

**Event flow is unidirectional and queue-based.** Watchdog puts raw events onto a `queue.Queue`. The Event Processor consumes from this queue in a worker thread, checks dedup + stability, and only then submits a classification task to a `ThreadPoolExecutor`. Results flow back to the UI via Qt signals — never by accessing UI widgets from background threads.

**Classification pipeline is a chain of stages with early exits.** Each stage produces a `ClassificationResult` (category, confidence, explanation). If a stage produces a result above the `auto_confirm` threshold, later stages are skipped. This keeps most common files (e.g., `.mp4` video) very cheap to classify.

**The rule engine has highest priority.** User-defined rules are checked before the ML pipeline. This is safer: users see predictable behavior, not opaque classifier decisions.

---

## 3. Technology Evaluation

### 3.1 Confirmed Stack

| Component | Library | Assessment |
|---|---|---|
| GUI | PySide6 | ✅ Best choice. LGPL, native look-and-feel, Qt signals solve cross-thread UI safely. |
| FS monitoring | watchdog | ✅ Abstracts inotify / ReadDirectoryChangesW / kqueue. Widely used. |
| Path operations | pathlib | ✅ Mandatory for cross-platform correctness. |
| PDF extraction | pypdf | ✅ Pure Python, lightweight, good for text + metadata. No binary dependency. |
| DOCX extraction | python-docx | ✅ Standard, well-maintained. |
| EPUB extraction | ebooklib | ⚠️ Less maintained but acceptable. Consider `zipfile` fallback (EPUB is a ZIP). |
| Text analysis | scikit-learn | ✅ TF-IDF + cosine similarity is the right lightweight choice. |
| Database | SQLite (stdlib) | ✅ Zero additional dependency, single file, good for embedded use. |
| Testing | pytest | ✅ Standard. |
| Packaging | PyInstaller | ✅ Works on all three platforms. |
| Concurrency | threading + concurrent.futures | ✅ Sufficient. asyncio is unnecessary here (no network I/O). |

### 3.2 Suggested Adjustments

**Add `python-magic` (optional, with fallback):**  
Extensions can be spoofed. Reading the first few magic bytes lets us correctly identify a file whose extension was changed. On Windows, `python-magic` requires a DLL (`libmagic`). A simpler fallback: maintain a small internal table of magic byte signatures for the most common types. Make `python-magic` an optional enhancement.

**Do not add `Pillow` unless needed:**  
Image EXIF metadata could be extracted for photos. However, images rarely need intelligent categorization — extension is sufficient. Only add `Pillow` if EXIF-based organization (by date, camera, GPS) is in scope.

**`ebooklib` warning:** It depends on `lxml` which has binary wheels. Confirm this installs cleanly on all three platforms before committing to it.

**Reject `watchfiles` (Rust-based alternative):** Watchdog is more established and pure Python. No reason to change.

**Avoid `appdirs`/`platformdirs` if building a custom platform adapter anyway** — but actually, `platformdirs` is a very lightweight, zero-dependency library that returns the correct config/data paths per OS. Consider including it so the platform adapter doesn't re-implement this logic.

### 3.3 Full Requirements File Estimate

```
PySide6>=6.7
watchdog>=4.0
pypdf>=4.0
python-docx>=1.1
ebooklib>=0.18
scikit-learn>=1.4
platformdirs>=4.0
pytest>=8.0
pytest-qt>=4.0
```

Total install size: approximately 120–180 MB (dominated by PySide6 + scikit-learn's numpy/scipy). Acceptable for a desktop application.

---

## 4. Classification Strategy

### 4.1 Pipeline Overview

```
New file detected
      │
      ▼
[Stage 1: File Type]  ─── extension + magic bytes lookup
      │
      ├─ Non-document (video, audio, image, archive, installer)?
      │    └─ Direct rule → done (cheap, no text analysis)
      │
      ▼
[Stage 2: Filename + Metadata]  ─── keyword patterns, document title/author
      │
      ├─ High-confidence match from filename alone?
      │    └─ Apply category → done
      │
      ▼
[Stage 3: Text Extraction]  ─── bounded extraction (first N chars)
      │
      ├─ Extraction failed / encrypted / scanned?
      │    └─ Return low-confidence result → Review Queue
      │
      ▼
[Stage 4: TF-IDF Classification]
      │
      ├─ Confidence ≥ auto_confirm_threshold?
      │    └─ Move automatically
      │
      ├─ Confidence ≥ suggest_threshold?
      │    └─ Show in Review Queue with suggestion
      │
      └─ Below suggest_threshold?
           └─ Place in Uncategorized / Others
```

### 4.2 Hierarchical Category Representation

Categories are stored as a tree of nodes. Each node has:

```python
@dataclass
class Category:
    id: str                # UUID
    name: str
    parent_id: str | None  # None = root
    destination: Path      # Resolved output directory
    description: str       # Used as TF-IDF "document" for comparison
    keywords: list[str]    # Weighted boost terms
    enabled: bool
```

The tree is persisted in SQLite. The TF-IDF corpus is built from all leaf-node descriptions at startup and rebuilt when categories change.

### 4.3 TF-IDF Classifier Design

**Corpus construction:** Each leaf category's `description + keywords` becomes one "document" in the training corpus. The `TfidfVectorizer` is fitted on this corpus. This happens at startup and is cached.

**Query time:** The extracted text from a new file becomes the query. Its TF-IDF vector is computed and cosine similarity against all category vectors is calculated. The top match, its score, and alternatives are returned as `ClassificationResult`.

**Honest limitations to document:**
- TF-IDF cannot understand synonyms, context, or domain-specific jargon that doesn't appear in category descriptions.
- A document about "neural networks" will score well for Computer Science only if "neural" or "network" appears in that category's description.
- Classification quality depends heavily on how well category descriptions are written. Make them editable.

**Threshold calibration:** Do not use a fixed 0.5 cutoff. Instead, expose configurable thresholds:
- `auto_confirm_threshold` (default: 0.72) — move without asking
- `suggest_threshold` (default: 0.45) — show suggestion to user
- Below `suggest_threshold` — place in Review Queue with no suggestion

These defaults should be documented as empirically tuned starting points that users should adjust based on their experience.

### 4.4 Why This Is Better Than Extension-Only

| File | Extension-only | SmartSort Stage |
|---|---|---|
| `Atomic_Habits.pdf` | Documents/ | Stage 2: "habits" keyword → Self-Help |
| `invoice_october.pdf` | Documents/ | Stage 2: "invoice" keyword → Invoices |
| `lec03_scheduling.pdf` | Documents/ | Stage 2: "lec" pattern → Lecture Notes |
| `paper_2024.pdf` | Documents/ | Stage 3+4: extract text → Research Papers |
| `corrupted.pdf` | Documents/ | Stage 3 fails gracefully → Review Queue |

---

## 5. Cross-Platform Strategy

### 5.1 What Differs Between Platforms

| Concern | Windows | Linux | macOS |
|---|---|---|---|
| Default Downloads path | `%USERPROFILE%\Downloads` | `$HOME/Downloads` | `$HOME/Downloads` |
| Config directory | `%APPDATA%\SmartSort` | `$XDG_CONFIG_HOME/smartsort` | `~/Library/Application Support/SmartSort` |
| FS event backend | ReadDirectoryChangesW | inotify | FSEvents (kqueue) |
| File locking | Mandatory (OS-enforced) | Advisory only | Advisory only |
| Path case sensitivity | Case-insensitive | Case-sensitive | Case-insensitive (by default) |
| Executable permissions | Not applicable | `chmod` bits | `chmod` bits |

### 5.2 Platform Abstraction

A `PlatformAdapter` base class exposes:

```python
class PlatformAdapter:
    def get_downloads_dir(self) -> Path: ...
    def get_config_dir(self) -> Path: ...
    def get_data_dir(self) -> Path: ...
    def is_file_locked(self, path: Path) -> bool: ...
    def get_platform_name(self) -> str: ...
```

`platformdirs` handles the path methods automatically. The `is_file_locked()` implementation differs: on Windows, attempt to open the file exclusively; on Linux/macOS, use `fcntl.flock()`.

### 5.3 Watchdog Backends

Watchdog selects the appropriate backend automatically:
- Windows: `WindowsApiObserver` (ReadDirectoryChangesW)
- Linux: `InotifyObserver`
- macOS: `FSEventsObserver`

No code changes needed — this is Watchdog's core purpose. However, be aware that inotify has a default limit on the number of watched directories. Document how to raise this limit (`fs.inotify.max_user_watches`).

### 5.4 Safe Path Handling

- Always use `pathlib.Path` — never string concatenation for paths.
- Validate that resolved destination paths are within the configured base directory (prevent directory traversal from category names like `../../sensitive`).
- Normalize paths before comparison to handle symlinks and case differences.

---

## 6. Technical Challenges

### 6.1 Detecting Download Completion

This is the **hardest problem in the monitoring subsystem.**

**The challenge:** Files appear in the Downloads folder while they are still being written. Moving an incomplete file corrupts it.

**Signals that a download is in progress:**
- The file has a temporary extension (`.part`, `.crdownload`, `.download`, `.tmp`, `.opdownload`)
- The file size is still growing
- The file is locked (Windows) or has an open file descriptor (Linux: `/proc/*/fd`)
- The file was just created and has not been stable for N seconds

**Proposed stability check algorithm:**
1. When a `FileCreatedEvent` arrives, add it to a "pending" dictionary with its current size and timestamp.
2. A stability checker thread wakes every `stability_poll_interval` seconds (default: 2s).
3. For each pending file: check current size. If size equals the previous size and the file is not locked and at least `min_stable_duration` seconds (default: 5s) has passed → promote to the classification queue.
4. If the temporary-extension pattern matches, do not classify until a rename event removes the temp extension.

**Watch for rename events:** Browsers typically write `file.part` then rename to `file.pdf`. The rename event must trigger re-evaluation, not a fresh "new file" event.

### 6.2 Race Conditions and Deduplication

Watchdog can emit multiple events for one logical operation (created, modified, modified, modified). A naive handler would classify the same file multiple times.

**Deduplication strategy:**
- Maintain a set of "in-flight" paths (paths currently in the stability queue or classification pipeline).
- Before enqueuing a file, check if it's already in-flight. If so, update its stability timestamp and skip.
- Use a `threading.Lock` on the in-flight set.
- After classification completes, remove from in-flight regardless of outcome.

### 6.3 Simultaneous Downloads

If five files are downloaded simultaneously, all five enter the pipeline at once. An unbounded thread pool would spike CPU and RAM.

**Solution:** Use `concurrent.futures.ThreadPoolExecutor(max_workers=N)` where `N` is configurable (default: 2). Excess tasks queue automatically. This also prevents overwhelming the TF-IDF classifier.

### 6.4 Cross-Filesystem Moves

`shutil.move()` handles this transparently, but it's worth knowing: if source and destination are on different filesystems, the move becomes a copy + delete. This is slower and means the copy can fail partway through.

**Safe implementation:**
1. Copy to a temporary file in the destination directory first.
2. Verify the copy (size check).
3. Delete the original only after verification.
4. Handle permission errors gracefully at each step.

### 6.5 Filename Conflicts

If `report.pdf` already exists at the destination:
- `report (1).pdf` → `report (2).pdf` → etc.
- Never silently overwrite.
- Never silently skip without informing the user.
- Log the conflict and resolution in history.

### 6.6 Classification Accuracy

TF-IDF is a reasonable starting point but will make mistakes, especially for:
- Documents whose title or text content doesn't match any category description
- Files with misleading filenames
- Short documents without enough text
- Non-English documents (TF-IDF works best in the language the category descriptions are written in)

These are honest limitations. Document them. The Review Queue exists precisely for ambiguous cases.

### 6.7 File Permissions

SmartSort must not require admin privileges. It should:
- Detect when it lacks write permissions to the destination directory.
- Detect when the source file is read-only or owned by another user.
- Surface permission errors clearly in the UI rather than crashing.

### 6.8 GUI Thread Safety

PySide6 enforces that UI elements may only be modified from the main thread. Background workers must communicate results via Qt Signals (which are automatically marshalled to the main thread when using `Qt.QueuedConnection`). Never pass widget references to worker threads.

---

## 7. Implementation Roadmap

### Milestone 1: Foundation (Week 1–2)
**Goal:** Runnable skeleton with basic extension-based sorting and a working UI shell.

- [ ] Repository setup, virtual environment, `requirements.txt`
- [ ] Project directory structure
- [ ] `platformdirs`-based config + data directories
- [ ] SQLite schema (history table, config table, categories table, rules table)
- [ ] `CategoryTree` loaded from `categories_default.json`
- [ ] Stage 1: Extension → category mapping
- [ ] `safe_move()` with conflict resolution
- [ ] PySide6 main window shell (tabs, no logic)
- [ ] pytest setup + first unit tests for extension mapping

**Exit criterion:** Given a folder of mixed-extension files, the app can move them to correct top-level categories via a "Organize Now" button.

---

### Milestone 2: Filesystem Monitoring (Week 3–4)
**Goal:** Automatic background monitoring with correct download-completion detection.

- [ ] Watchdog integration + platform-appropriate observer selection
- [ ] Download stability checker (size polling + lock detection)
- [ ] Temporary extension detection (`.part`, `.crdownload`, etc.)
- [ ] Rename event handling (temp → final filename)
- [ ] Thread-safe event queue
- [ ] In-flight deduplication cache
- [ ] `ThreadPoolExecutor` worker pool
- [ ] Dashboard: live monitoring status + event log
- [ ] Integration tests using `tmp_path` + synthetic file writes

**Exit criterion:** Drop a file into the watched Downloads folder; the app correctly detects when it is stable, classifies by extension, and moves it — even if the file was written slowly.

---

### Milestone 3: Intelligent Classification (Week 5–6)
**Goal:** Multi-stage classification pipeline with TF-IDF and confidence thresholds.

- [ ] Stage 2: Filename keyword patterns
- [ ] Stage 2b: PDF metadata extraction (pypdf), DOCX properties
- [ ] Stage 3: Bounded text extraction (PDF, DOCX, EPUB, TXT) with size/page/char limits
- [ ] Stage 4: TF-IDF vectorizer fitted on category descriptions
- [ ] `ClassificationResult` dataclass (category, confidence, alternatives, explanation)
- [ ] Stage 5: Confidence thresholds → auto-move vs. review queue
- [ ] Review Queue UI panel
- [ ] Unit tests for each extractor with sample documents

**Exit criterion:** Given a set of PDFs with different subjects, the classifier correctly routes most to appropriate subcategories; ambiguous files appear in the Review Queue.

---

### Milestone 4: Custom Rules (Week 7–8)
**Goal:** User-defined rules override or supplement automatic classification.

- [ ] `Rule` dataclass (conditions: extension, filename pattern, size, keyword, classifier result)
- [ ] `RuleEngine` with priority ordering
- [ ] Built-in default rules (editable)
- [ ] Rules CRUD UI panel
- [ ] Enable/disable individual rules
- [ ] Learning prompt: "Create a rule for similar files?" after user correction
- [ ] Rule conflict logging

**Exit criterion:** User creates a rule "filename contains 'invoice' → Documents/Invoices"; all matching files route correctly regardless of classifier output.

---

### Milestone 5: Full UI Polish (Week 9–10)
**Goal:** All UI panels functional and usable.

- [ ] Dashboard: stats, recent activity, category distribution chart
- [ ] Activity History: filterable list, original/destination paths
- [ ] Categories: editable tree with CRUD
- [ ] Rules: full rule management UI
- [ ] Settings: all configurable parameters
- [ ] Error/warning notifications
- [ ] Non-blocking UI during classification (progress indicators)

**Exit criterion:** A user unfamiliar with the project can navigate all panels and understand what the application is doing.

---

### Milestone 6: Reliability (Week 11–12)
**Goal:** Undo, conflict handling, error recovery, and persistent history.

- [ ] Undo: restore file to original path, handle conflicts
- [ ] Persistent history with SQLite
- [ ] Error recovery: partial moves, permission failures, missing directories
- [ ] Performance profiling and optimization (classification caching)
- [ ] Logging to rotating file

**Exit criterion:** Every file operation is recorded and reversible. Errors surface in the UI with enough detail to diagnose without crashing the application.

---

### Milestone 7: Cross-Platform Validation & Packaging (Week 13–14)
**Goal:** Confirmed working on Windows and Linux; packaged for distribution.

- [ ] Windows testing: path handling, file locking, temp extensions
- [ ] Linux testing: inotify limits, XDG paths, permissions
- [ ] macOS notes (if hardware available)
- [ ] PyInstaller spec files per platform
- [ ] README installation instructions

**Exit criterion:** Application runs from a PyInstaller-produced executable on Windows and Linux.

---

## 8. MVP Definition

### Essential (Must Have for a Passing Submission)

- [ ] Automatic Downloads folder monitoring (Watchdog)
- [ ] Download-completion detection (stability checker)
- [ ] Extension-based classification (Stage 1)
- [ ] Filename keyword classification (Stage 2)
- [ ] At least one document text extractor (PDF via pypdf)
- [ ] TF-IDF classification (Stage 4)
- [ ] Confidence-based routing (auto-move vs. Review Queue)
- [ ] Safe file move with conflict resolution
- [ ] Activity history (SQLite)
- [ ] Basic undo (single level)
- [ ] PySide6 UI with Dashboard, History, and Settings
- [ ] Review Queue panel
- [ ] Configurable thresholds
- [ ] Cross-platform path handling
- [ ] Unit tests for classification pipeline

### Important (Should Have for a Strong Submission)

- [ ] Custom rules with priority ordering
- [ ] DOCX and EPUB extraction
- [ ] Hierarchical category tree UI (CRUD)
- [ ] Full Rules management UI
- [ ] Learning prompt after user correction
- [ ] Multi-level undo
- [ ] Category distribution chart on Dashboard

### Optional (Nice to Have, Do Not Implement Unless Core Is Complete)

- [ ] EXIF-based image organization by date
- [ ] macOS FSEvents testing and packaging
- [ ] Advanced similarity (word embeddings — out of scope per spec)
- [ ] System tray icon
- [ ] Browser extension integration
- [ ] Network share monitoring

---

## 9. Testing Strategy

### 9.1 Principle: Never Touch Real User Files During Tests

All tests use `pytest`'s `tmp_path` fixture, which provides a temporary directory automatically cleaned up after each test session.

```python
def test_safe_move_conflict(tmp_path):
    src = tmp_path / "downloads" / "report.pdf"
    dst_dir = tmp_path / "Documents"
    # create files, run mover, assert outcome
```

### 9.2 Test Categories

**Unit tests** (`tests/unit/`):
- Extension → category mapping table
- Filename keyword rules
- TF-IDF classifier: known documents → known categories
- Conflict resolver: expected renamed filenames
- Dedup cache: same path not enqueued twice
- Stability checker: file marked stable only after correct conditions

**Integration tests** (`tests/integration/`):
- Write a file slowly into a temp "Downloads" folder; verify app waits for stability before classifying
- Drop 5 files simultaneously; verify all are processed without race conditions
- Move file across two `tmp_path` subdirectories simulating different filesystems
- Write a PDF with known content; verify TF-IDF routes to correct category

**UI tests** (`tests/ui/` with `pytest-qt`):
- Dashboard updates when a file is classified
- Review Queue shows correct files
- Undo button restores file to original location

### 9.3 Sample Test Fixtures

Provide a `tests/fixtures/` directory with:
- A short PDF known to be about Computer Science (for classifier regression testing)
- A short PDF known to be about self-help
- A simulated invoice PDF
- Various extension files (empty, but correctly named)
- A corrupted PDF (for error handling tests)

### 9.4 Regression Testing for Classification

Maintain a small labeled test set:

```python
CLASSIFICATION_FIXTURES = [
    ("atomic_habits_excerpt.pdf", "Books/Non-Fiction/Self-Help"),
    ("lec03_scheduling.pdf", "Academic/Lecture Notes"),
    ("invoice_sample.pdf", "Documents/Invoices"),
]
```

Run these in CI to catch classifier regressions when category descriptions are changed.

---

## 10. Open Questions

The following must be resolved before implementation begins:

### Q1: Monitoring Scope
> Should SmartSort only monitor the single default Downloads directory, or support multiple configurable watch paths (e.g., Desktop, a custom folder)?

**Recommendation:** Support a configurable list of watched directories with the Downloads folder as the default. Multiple paths are a small implementation cost and significantly increase usefulness.

---

### Q2: Category Destination Strategy
> Should the organized destination be *inside* the Downloads folder (e.g., `Downloads/Books/Fiction/`) or in a completely separate root directory (e.g., `~/Organized/`)?

**Recommendation:** Make this a per-category setting, with the default being a sibling directory to Downloads or a user-chosen root. Organizing inside Downloads is simpler but may conflict with browsers that re-scan Downloads.

---

### Q3: First-Run Behavior
> When SmartSort is launched for the first time, should it offer to organize *existing* files in Downloads, or only organize newly downloaded files going forward?

**Recommendation:** Default to forward-only monitoring with an explicit "Organize Existing Files" button in Settings. Organizing existing files without user understanding can be alarming.

---

### Q4: Temporary Extension List
> The application needs a list of known temporary download extensions (`.crdownload`, `.part`, `.download`, `.tmp`, `.opdownload`, `.aria2`). Should this list be hardcoded, user-editable, or both?

**Recommendation:** Hardcode a sensible default list in configuration but expose it as a user-editable setting in the advanced Settings panel.

---

### Q5: Category Description Language
> TF-IDF is language-sensitive. Should the category descriptions (and therefore the classifier) target English only, or support multiple languages?

**Recommendation:** English-only for the initial version. Document this limitation clearly. Supporting multiple languages would require either multiple category description sets or a multilingual embedding model (out of scope).

---

### Q6: Notification Behavior
> Should SmartSort show a desktop notification for every file organized, or only when user attention is required (ambiguous classification, error)?

**Recommendation:** Notify only for Review Queue additions and errors. Silent operation for successful auto-moves, with a Dashboard counter for confirmation. Over-notification leads to users ignoring or disabling the application.

---

### Q7: Database Location
> Where should the SQLite database be stored? Options: alongside the application, in the OS config directory, or in the user's home directory?

**Recommendation:** Use `platformdirs.user_data_dir("SmartSort")` — the OS-standard application data location. This separates user data from the application installation and survives application updates.

---

> [!IMPORTANT]
> The questions in Section 10 should be answered before Milestone 1 begins. The most consequential are Q1 (watch scope), Q2 (destination strategy), and Q3 (first-run behavior) — these affect the database schema and core architecture.

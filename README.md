# Product Intelligence Radar

An automated system for collecting and analyzing information about PostgreSQL, MySQL, and database services on hyperscalers (AWS, Azure, etc).

## Objectives

**Product Intelligence Radar** is designed to:

- 🎯 **Monitor information sources** on product evolution and related technologies
- 📊 **Collect articles, release notes and updates** from multiple RSS feeds and web pages
- 🤖 **Automatically classify** collected content using AI (Dify workflow)
- 📈 **Generate reports** with insights on trends and relevant updates
- 🔄 **Perform intelligent deduplication** by URL and content hash

## How It Works

The project has two main stages:

### Stage 1: Data Collection (`Extractor.py` / `Extractor.ipynb`)

```
┌─────────────────────┐
│ sources_config.json │  ← Define sources (RSS feeds, blogs, etc)
└──────────┬──────────┘
           │
           ▼
┌──────────────────────┐
│  collect_source_items│  ← Collect items from sources
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────┐
│  firecrawl_scrape        │  ← Extract content as Markdown
│  (Firecrawl API)         │
└──────────┬───────────────┘
           │
           ▼
┌──────────────────────────┐
│  Deduplication           │  ← By URL and content hash
│  (seen_urls, seen_hashes)│
└──────────┬───────────────┘
           │
           ▼
    ┌──────────────┐
    │items_raw.json│  ← Raw file saved in runs/{date}/raw/
    └──────────────┘
```

**Features:**

- **Supports 4 ingestion methods:**
  - `rss`: RSS feed parsing
  - `html_index`: Link extraction from index pages
  - `release_index`: Release notes monitoring
  - `docs_root`: Documentation page collection

- **Smart collection:**
  - Extracts main content only (no menus/sidebars)
  - Normalizes text (removes timestamps, extra spaces)
  - Validates minimum content size (400 characters default)
  - Deduplication by URL and SHA256 hash

- **State persistence:**
  - Tracks already seen URLs
  - Detects content updates
  - Maintains version history

### Stage 2: AI Processing (`Extractor.py`)

```
┌──────────────────┐
│ items_raw.json   │
└────────┬─────────┘
         │
         ▼
    ┌─────────────┐
    │  Adapt and  │  ← Content clamping (6000 chars max)
    │  Batching   │  ← Groups items in batches for Dify
    └────┬────────┘
         │
         ▼
    ┌──────────────────────┐
    │ Dify Workflow Mode   │
    │ "classify"           │  ← Classify relevance
    └────┬─────────────────┘
         │
         ▼
    ┌────────────────────────┐
    │ classified.json        │  ← Only relevant items
    └────┬───────────────────┘
         │
         ▼
    ┌──────────────────────┐
    │ Dify Workflow Mode   │
    │ "report"             │  ← Generate markdown report
    └────┬─────────────────┘
         │
         ▼
    ┌────────────────────┐
    │ report.md          │  ← Final report
    └────────────────────┘
```

**Steps:**

1. **Classification:** Dify workflow classifies each item as relevant or not
2. **Filtering:** Keep only items marked as relevant
3. **Batching:** Group items in batches to optimize requests
4. **Report Generation:** Dify generates markdown with summary and insights

## Architecture

```
dbaas_Intelligence_Radar/
├── Extractor.py              # Main script (sync/sequential)
├── Extractor.ipynb           # Jupyter Notebook (development/debug)
├── sources_config.json       # Sources and policies configuration
├── sources_config.json       # Persistent state
├── state/
│   └── seen.json            # Seen URLs and content hashes
└── runs/
    └── {date}/
        ├── raw/
        │   └── items_raw.json
        ├── batches/
        ├── responses/
        └── final/
            ├── classified.json
            ├── classified.jsonl
            └── report.md
├── Poduct Intelligent Radar.yml  # Dify workflow configuration
└── README.md, CONTRIBUTING.md     # Project documentation
```

## Dify Workflow

**File:** `Poduct Intelligent Radar.yml`

This is a Dify workflow definition file that powers the AI-driven classification and report generation. The workflow is called by `Extractor.py` via the Dify API and supports two operational modes:

### Workflow Modes

The workflow accepts a `mode` parameter to determine its operation:

#### 1. **Classification Mode** (`mode: "classify"`)

Classifies individual items for relevance:

```json
{
  "inputs": {
    "mode": "classify",
    "items": {
      "items": [
        {
          "url": "https://...",
          "title": "PostgreSQL 16 ...",
          "content_md": "## PostgreSQL 16\n..."
        }
      ]
    }
  }
}
```

**Process:**
- Iterates over each item in the provided list
- Uses an LLM (Ollama/local model: `gemma3:27b`) to analyze relevance
- Extracts structured classification including:
  - `is_relevant`: Boolean indicating if the item is relevant
  - `relevance_score`: Numerical score (0-1)
  - `topics`: Extracted topics and keywords
  - `summary`: Brief description

**Output:**
```json
{
  "classified_items": {
    "items": [
      {
        "url": "...",
        "title": "...",
        "classification": {
          "is_relevant": true,
          "relevance_score": 0.95,
          "topics": ["PostgreSQL", "Performance"],
          "summary": "..."
        }
      }
    ]
  }
}
```

#### 2. **Report Mode** (`mode: "report"`)

Generates a markdown report from classified items:

```json
{
  "inputs": {
    "mode": "report",
    "classified_items": {
      "items": [/* classified items from mode=classify */]
    }
  }
}
```

**Process:**
- Receives previously classified items
- Aggregates relevant items across categories
- Uses LLM to generate a comprehensive weekly/temporal report
- Formats output as markdown with sections by category

**Output:**
```
report_md: "# Weekly Product Radar Report\n\n## PostgreSQL\n..."
```

### Workflow Architecture

```
Start (mode input: classify|report)
  │
  ├─► IF mode = "classify"
  │   └─► Iteration Loop
  │       └─► LLM Classification
  │           └─► Organize Classification
  │               └─► Output (classified.items)
  │
  └─► ELSE IF mode = "report"
      └─► LLM Report Generation
          └─► Output 2 (report_md)
```

### Setup in Dify

1. **Import the workflow:**
   - Open Dify UI
   - Create → Import from File
   - Upload `Poduct Intelligent Radar.yml`

2. **Configure the LLM:**
   - Ensure Ollama plugin is installed (langgenius/ollama)
   - Configure connection to local or remote Ollama instance
   - Model: `gemma3:27b` (or adjust per your setup)

3. **Enable API Access:**
   - Generate API credentials in Dify
   - Update `Extractor.py` with:
     ```python
     DIFY_BASE_URL = "http://your-dify-instance"
     DIFY_API_KEY = "your_api_key_here"
     ```

4. **Test the workflow:**
   - Try Classification mode first with sample items
   - Verify output structure matches `extract_relevant_list()` parser
   - Then test Report mode with classified items

### Workflow Variables

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `mode` | string | Yes | Either `"classify"` or `"report"` |
| `items` | object | For classify | Items to classify: `{items: [...]}`  |
| `classified_items` | object | For report | Already-classified items: `{items: [...]}` |

| Output | Mode | Type | Description |
|--------|------|------|-------------|
| `classified_items` | classify | list | Items with classification results |
| `report_md` | report | string | Markdown report content |

## Configuration

### `sources_config.json`

```json
{
  "run_policy": {
    "max_items_per_source_per_run": 20
  },
  "extract_policy": {
    "content_min_chars": 400
  },
  "tags": {
    "postgresql": ["postgres", "engine"],
    "mysql": ["mysql", "engine"],
    "hyperscalers": ["dbaas", "vendor"]
  },
  "sources": [
    {
      "id": "pg_planet_rss",
      "category": "postgresql",
      "tier": "analysis",
      "name": "Planet PostgreSQL (RSS)",
      "url": "https://planet.postgresql.org/rss20.xml",
      "ingest": { "method": "rss" }
    },
    // ... more sources
  ]
}
```

**Source fields:**
- `id`: Unique identifier
- `name`: Human-readable name
- `url`: Source URL
- `category`: Category (postgresql, mysql, hyperscalers)
- `tier`: Level (official, vendor, analysis)
- `ingest.method`: rss, html_index, release_index, docs_root
- `ingest.discovery.allow_url_prefixes`: (optional, for html_index)

## Dependencies

```
requests              # HTTP requests
feedparser           # RSS feed parsing
python-dateutil      # Date manipulation
```

### Required Environment Variables

```bash
FIRECRAWL_API_KEY=<your_api_key>
FIRECRAWL_BASE_URL=http://firecrawl  # or your URL
```

**Dify (hardcoded - adjust as needed):**
```python
DIFY_BASE_URL = "http://DIFY"
DIFY_API_KEY = "apikey"
DIFY_USER = "product-radar"
```

## How to Use

### 1. Installation

```bash
git clone https://github.com/your-username/dbaas-intelligence-radar.git
cd dbaas-intelligence-radar

pip install -r requirements.txt
```

### 2. Configuration

**Environment variables:**
```bash
export FIRECRAWL_API_KEY="your_token_here"
export FIRECRAWL_BASE_URL="http://your_firecrawl"
```

**Edit `sources_config.json`:**
- Adjust source URLs
- Modify `max_items_per_source_per_run` as needed
- Add/remove sources

**Configure Dify:**
- Update `DIFY_BASE_URL`, `DIFY_API_KEY`, `DIFY_USER` in `Extractor.py`

### 3. Run

**Script mode:**
```bash
python Extractor.py
```

**Jupyter mode:**
```bash
jupyter notebook Extractor.ipynb
# Run cells sequentially
```

### 4. Outputs

Results in `runs/{date}/final/`:
- `classified.json` - List of items classified as relevant
- `classified.jsonl` - One line per item (jsonl format)
- `report.md` - Markdown report generated by Dify

## Main Features

### Smart Deduplication

```python
already_seen(url, content_hash, state)
```

- **URL never seen:** Item is new
- **URL seen + same hash:** Already processed
- **URL seen + different hash:** Content was updated (new item)

### Content Normalization

```python
normalize_text(text)
```

Reduces false positives:
- Removes extra line breaks
- Removes timestamps and "updated on" tags
- Collapses spaces
- Normalizes ISO dates

### Automatic Batching

```python
make_batches(items, max_items_per_batch=10, max_chars_per_batch=180_000)
```

Groups items to:
- Respect request limits
- Optimize AI calls
- Reduce timeout

### Content Clamping

```python
clamp_head_tail(text, max_chars=6000)
```

Reduces content size while keeping:
- 65% from beginning (title, introduction)
- 35% from end (conclusion, important lines)
- Marks middle with `[...]`

## Collected Item Structure

```json
{
  "id": "sha256:...",
  "source_id": "pg_planet_rss",
  "source_name": "Planet PostgreSQL (RSS)",
  "category": "postgresql",
  "tier": "analysis",
  "url": "https://...",
  "title": "PostgreSQL 16: New Feature",
  "published_at": "2026-03-19T10:30:00Z",
  "collected_at": "2026-03-19T15:45:32Z",
  "content_markdown": "## PostgreSQL 16\n\nNew features...",
  "content_hash": "abc123def456...",
  "tags": ["postgres", "engine"]
}
```

## Classified Item Structure

```json
{
  "run_id": "2026-03-19",
  "provider": "Planet PostgreSQL (RSS)",
  "engine": "postgresql",
  "source_type": "postgresql",
  "url": "https://...",
  "title": "PostgreSQL 16: New Feature",
  "fetched_at": "2026-03-19T15:45:32Z",
  "content_hash": "abc123def456",
  "content_md": "## PostgreSQL 16\n...",
  "content_len": 5000,
  "classification": {
    "is_relevant": true,
    "relevance_score": 0.95,
    "topics": ["PostgreSQL", "Performance", "Replication"]
  },
  "metadata": {
    "source_id": "pg_planet_rss",
    "tier": "analysis",
    "tags": ["postgres", "engine"],
    "published_at": "2026-03-19T10:30:00Z"
  }
}
```

## Error Handling

- **Firecrawl timeout:** Automatic retry with exponential backoff
- **Dify failure:** 3 attempts with increasing sleep (1s, 2s, 4s)
- **Unavailable source:** Error log, continues with next sources
- **Content too small:** Ignored (< 400 chars)

## Logging

No log file is configured by default. To add:

```python
import logging
logging.basicConfig(
    filename=f"runs/{RUN_DATE}/extractor.log",
    level=logging.INFO
)
```

## Contributing

1. Fork the project
2. Create a branch for your feature (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## Future Improvements

- [ ] Webhook support for real-time triggers
- [ ] Web dashboard to view classified items
- [ ] REST API to query items
- [ ] Slack/Discord integration for notifications
- [ ] Support for multiple Dify workspaces
- [ ] Distributed cache for deduplication
- [ ] Metrics and monitoring (Prometheus)

## License

This project is licensed under the MIT License.

## Contact

**Team:** Product Radar Team  
**Email:** product-radar@example.com

---

**Last updated:** March 19, 2026

import os
import re
import json
import time
import hashlib
import requests
import feedparser
import math
import datetime as dt
import datetime as dt
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# =========================
# Caminhos do run atual
# =========================

PROJECT_ROOT = Path(".").resolve()
RUN_DATE = dt.date.today().isoformat()
RUN_DIR = PROJECT_ROOT / "runs" / RUN_DATE

RAW_DIR = RUN_DIR / "raw"
BATCH_DIR = RUN_DIR / "batches"
RESP_DIR = RUN_DIR / "responses"
FINAL_DIR = RUN_DIR / "final"

CONFIG_PATH = PROJECT_ROOT / "sources_config.json"  # JSON guia
STATE_DIR = PROJECT_ROOT / "state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

STATE_PATH = STATE_DIR / "seen.json"


RUN_DIR = PROJECT_ROOT / "runs" / RUN_DATE
RAW_DIR = RUN_DIR / "raw"
BATCH_DIR = RUN_DIR / "batches"
RESP_DIR = RUN_DIR / "responses"
FINAL_DIR = RUN_DIR / "final"

def today_str_local() -> str:
    return dt.date.today().isoformat()

RUN_DATE = today_str_local()

FIRECRAWL_API_KEY = os.getenv("FIRECRAWL_API_KEY", "")
FIRECRAWL_BASE_URL = os.getenv("FIRECRAWL_BASE_URL", "http://firecrawl")

DIFY_BASE_URL = "http://DIFY"
DIFY_API_KEY = "apikey"
DIFY_USER = "product-radar"

def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat() + "Z"

for d in [RAW_DIR, BATCH_DIR, RESP_DIR, FINAL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

def load_config() -> Dict[str, Any]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return {"seen_urls": {}, "seen_hashes": {}}
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_state(state: Dict[str, Any]) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)

config = load_config()
state = load_state()

print("RUN_DIR:", RUN_DIR)
print("Loaded sources:", len(config.get("sources", [])))

def sha256_text(text: str) -> str:
    h = hashlib.sha256()
    h.update(text.encode("utf-8", errors="ignore"))
    return h.hexdigest()

def normalize_text(text: str) -> str:
    """
    Normalização mais estável para delta por conteúdo.
    Remove ruídos típicos de páginas web e reduz falsos positivos.
    """
    if not text:
        return ""

    t = text

    # normaliza quebras de linha
    t = t.replace("\r\n", "\n").replace("\r", "\n")

    # remove linhas típicas de "updated" e timestamps
    t = re.sub(r"(?im)^\s*(last\s+updated|updated\s+on|updated|last\s+modified)\s*:?.*$", "", t)

    # remove datas ISO soltas 
    t = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", t)

    # colapsa espaços
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)

    return t.strip()

def seen_url(url: str, state: Dict[str, Any]) -> bool:
    """
    True se a URL já foi vista antes.
    """
    return bool(url and url in state.get("seen_urls", {}))

def already_seen(url: str, content_hash: Optional[str], state: Dict[str, Any]) -> bool:
    """
    Delta por conteúdo:
    - sem URL e com hash: usa seen_hashes
    - com URL e hash:
        - URL nunca vista -> novo
        - URL vista + mesmo hash -> já visto
        - URL vista + hash diferente -> update
    - com URL e sem hash:
        - não decide por conteúdo
        - para gate estrito por URL, use seen_url(url, state)
    """
    if not url:
        return bool(content_hash and content_hash in state.get("seen_hashes", {}))

    url_entry = state.get("seen_urls", {}).get(url)

    if not url_entry:
        return False

    if not content_hash:
        return False

    prev_hash = None
    if isinstance(url_entry, dict):
        prev_hash = url_entry.get("last_hash")
    elif isinstance(url_entry, str):
        prev_hash = None

    if prev_hash and prev_hash == content_hash:
        return True

    return False

def mark_seen(url: str, content_hash: str, state: Dict[str, Any]) -> None:
    """
    Novo state:
    - seen_urls[url] vira um dict com last_hash + timestamps
    - seen_hashes continua existindo só para dedup cross-source (opcional)
    """
    ts = utc_now_iso()

    if url:
        existing = state.get("seen_urls", {}).get(url)

        if isinstance(existing, str) or existing is None:
            state["seen_urls"][url] = {
                "first_seen_at": existing or ts,
                "last_seen_at": ts,
                "last_hash": content_hash,
                "update_count": 0,
            }
        else:
            # já é dict
            existing["last_seen_at"] = ts
            prev_hash = existing.get("last_hash")
            if prev_hash and prev_hash != content_hash:
                existing["update_count"] = int(existing.get("update_count", 0)) + 1
            existing["last_hash"] = content_hash

    # mantém dedup global por hash
    if content_hash:
        state.setdefault("seen_hashes", {})
        if content_hash not in state["seen_hashes"]:
            state["seen_hashes"][content_hash] = ts

def parse_rss(url: str, max_items: int = 50) -> List[Dict[str, Any]]:
    feed = feedparser.parse(url)
    items = []
    for entry in (feed.entries or [])[:max_items]:
        link = getattr(entry, "link", None) or ""
        title = getattr(entry, "title", None) or ""
        published = ""
        if getattr(entry, "published_parsed", None):
            published = dt.datetime(*entry.published_parsed[:6]).replace(microsecond=0).isoformat() + "Z"
        elif getattr(entry, "updated_parsed", None):
            published = dt.datetime(*entry.updated_parsed[:6]).replace(microsecond=0).isoformat() + "Z"

        items.append({
            "url": link,
            "title": title,
            "published_at": published
        })
    return items
    
def firecrawl_scrape(url: str) -> Dict[str, Any]:
    """
    Esperado retornar markdown limpo e metadados.
    Ajuste o endpoint e formato conforme seu Firecrawl.
    """
    endpoint = f"{FIRECRAWL_BASE_URL}/v1/scrape"
    headers = {
        "Authorization": f"Bearer {FIRECRAWL_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "url": url,
        "formats": ["markdown"],
        "onlyMainContent": True
    }
    r = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    r.raise_for_status()
    return r.json()

def firecrawl_extract_links(index_url: str, allow_prefixes: Optional[List[str]] = None, limit: int = 30) -> List[str]:
    """
    Extrai links da página índice usando Firecrawl scrape em markdown e regex simples.
    Isso é suficiente para blog index em muitos casos.
    """
    data = firecrawl_scrape(index_url)
    md = ""
    if isinstance(data, dict):
        md = (
            data.get("data", {}).get("markdown")
            or data.get("markdown")
            or ""
        )
    md = md or ""
    candidates = re.findall(r"\((https?://[^)]+)\)", md)
    urls = []
    for u in candidates:
        u = u.strip()
        if allow_prefixes and not any(u.startswith(p) for p in allow_prefixes):
            continue
        if u not in urls:
            urls.append(u)
        if len(urls) >= limit:
            break
    return urls

def build_item(
    source: Dict[str, Any],
    url: str,
    title: str,
    published_at: str,
    content_markdown: str
) -> Dict[str, Any]:
    content_markdown = normalize_text(content_markdown)

    # mudou aqui: se não tem conteúdo, não inventa hash por URL
    content_hash = sha256_text(content_markdown) if content_markdown else None

    # mudou aqui: item_id continua estável, mas agora não depende do hash falso
    basis = url + "|" + (content_hash or "no-content")
    item_id = f"sha256:{sha256_text(basis)}"

    return {
        "id": item_id,
        "source_id": source["id"],
        "source_name": source["name"],
        "category": source["category"],
        "tier": source["tier"],
        "url": url,
        "title": title,
        "published_at": published_at,
        "collected_at": utc_now_iso(),
        "content_markdown": content_markdown,
        "content_hash": content_hash,
        "tags": config.get("tags", {}).get(source["category"], []),
    }

def collect_source_items(source: Dict[str, Any], state: Dict[str, Any]) -> List[Dict[str, Any]]:
    method = source.get("ingest", {}).get("method")
    max_items = config.get("run_policy", {}).get("max_items_per_source_per_run", 20)

    collected: List[Dict[str, Any]] = []

    if method == "rss":
        feed_items = parse_rss(source["url"], max_items=max_items)
        for fi in feed_items:
            url = fi["url"]
            if not url:
                continue

            # Para RSS, delta por URL
            if seen_url(url, state):
                continue

            scraped = firecrawl_scrape(url)
            md = (
                scraped.get("data", {}).get("markdown")
                or scraped.get("markdown")
                or ""
            )
            md = md or ""
            if len(md) < config.get("extract_policy", {}).get("content_min_chars", 400):
                continue

            item = build_item(
                source=source,
                url=url,
                title=fi.get("title", "") or "",
                published_at=fi.get("published_at", "") or "",
                content_markdown=md
            )

            if already_seen(item["url"], item["content_hash"], state):
                continue

            collected.append(item)
            mark_seen(item["url"], item["content_hash"], state)

        return collected

    if method == "html_index":
        allow_prefixes = source.get("ingest", {}).get("discovery", {}).get("allow_url_prefixes")
        urls = firecrawl_extract_links(source["url"], allow_prefixes=allow_prefixes, limit=max_items)
        for url in urls:
            scraped = firecrawl_scrape(url)
            md = (
                scraped.get("data", {}).get("markdown")
                or scraped.get("markdown")
                or ""
            )
            title = (
                scraped.get("data", {}).get("metadata", {}).get("title")
                or scraped.get("metadata", {}).get("title")
                or ""
            )
            published = (
                scraped.get("data", {}).get("metadata", {}).get("publishedTime")
                or scraped.get("metadata", {}).get("publishedTime")
                or ""
            )

            md = md or ""
            if len(md) < config.get("extract_policy", {}).get("content_min_chars", 400):
                continue

            item = build_item(
                source=source,
                url=url,
                title=title,
                published_at=published,
                content_markdown=md
            )

            if already_seen(item["url"], item["content_hash"], state):
                continue

            collected.append(item)
            mark_seen(item["url"], item["content_hash"], state)

        return collected

    if method == "release_index":
        # Mantém como página atual, mas sem bloquear por URL antes do scrape.
        url = source["url"]

        scraped = firecrawl_scrape(url)
        md = (
            scraped.get("data", {}).get("markdown")
            or scraped.get("markdown")
            or ""
        )
        title = source["name"]
        published = ""

        md = md or ""
        if len(md) < config.get("extract_policy", {}).get("content_min_chars", 400):
            return []

        item = build_item(
            source=source,
            url=url,
            title=title,
            published_at=published,
            content_markdown=md
        )

        if already_seen(item["url"], item["content_hash"], state):
            return []

        mark_seen(item["url"], item["content_hash"], state)
        return [item]

    if method == "docs_root":
        # Mantém como página raiz, mas sem bloquear por URL antes do scrape.
        url = source["url"]

        scraped = firecrawl_scrape(url)
        md = (
            scraped.get("data", {}).get("markdown")
            or scraped.get("markdown")
            or ""
        )

        md = md or ""
        if len(md) < config.get("extract_policy", {}).get("content_min_chars", 400):
            return []

        item = build_item(
            source=source,
            url=url,
            title=source["name"],
            published_at="",
            content_markdown=md
        )

        if already_seen(item["url"], item["content_hash"], state):
            return []

        mark_seen(item["url"], item["content_hash"], state)
        return [item]

    return []

all_items: List[Dict[str, Any]] = []

sources = config.get("sources", [])
for s in sources:
    try:
        items = collect_source_items(s, state)
        print(f"{s['id']}: collected {len(items)}")
        all_items.extend(items)
        time.sleep(0.2)
    except Exception as e:
        print(f"Erro em {s['id']}: {e}")

raw_path = RAW_DIR / "items_raw.json"
with open(raw_path, "w", encoding="utf-8") as f:
    json.dump(all_items, f, ensure_ascii=False, indent=2)

save_state(state)

print("Total items:", len(all_items))
print("Saved:", raw_path)

# =========================
# Setup dirs
# =========================

for d in [RAW_DIR, BATCH_DIR, RESP_DIR, FINAL_DIR]:
    d.mkdir(parents=True, exist_ok=True)

RAW_PATH = RAW_DIR / "items_raw.json"

# =========================
# IO helpers
# =========================

def load_json(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))

def save_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

def append_jsonl(path: Path, items: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")

def save_markdown(path: str, content: str):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)

# =========================
# Dify call + retry
# =========================

def dify_run_workflow(
    inputs: Dict[str, Any],
    response_mode: str = "blocking",
    timeout_seconds: int = 240
) -> Dict[str, Any]:

    url = f"{DIFY_BASE_URL}/v1/workflows/run"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {DIFY_API_KEY}",
    }

    payload = {
        "inputs": inputs,
        "response_mode": response_mode,
        "user": DIFY_USER
    }

    r = requests.post(url, headers=headers, json=payload, timeout=timeout_seconds)

    if r.status_code >= 400:
        print("Dify status:", r.status_code)
        try:
            print("Dify error json:", json.dumps(r.json(), ensure_ascii=False, indent=2)[:4000])
        except Exception:
            print("Dify error text:", (r.text or "")[:4000])

    r.raise_for_status()
    return r.json()

def dify_run_with_retry(
    inputs: Dict[str, Any],
    response_mode: str = "blocking",
    timeout_seconds: int = 240,
    max_retries: int = 3,
    backoff_base_seconds: float = 1.0
) -> Dict[str, Any]:

    last_err: Optional[Exception] = None

    for attempt in range(1, max_retries + 1):
        try:
            return dify_run_workflow(
                inputs=inputs,
                response_mode=response_mode,
                timeout_seconds=timeout_seconds
            )
        except Exception as e:
            last_err = e
            sleep_s = backoff_base_seconds * (2 ** (attempt - 1))
            print(f"Dify attempt {attempt}/{max_retries} falhou: {e}. Retentando em {sleep_s:.1f}s")
            time.sleep(sleep_s)

    raise last_err

# =========================
# Content clamp for Dify
# =========================

def clamp_head_tail(text: Any, max_chars: int = 6000, head_ratio: float = 0.65) -> str:
    if not isinstance(text, str):
        return ""
    text = text.strip()
    if len(text) <= max_chars:
        return text
    head = int(max_chars * head_ratio)
    tail = max_chars - head
    return text[:head] + "\n\n[...]\n\n" + text[-tail:]

# =========================
# Batching
# =========================

def estimate_item_size(it: Dict[str, Any]) -> int:
    # mede o tamanho do payload que vai pro Dify (content_md já clampado)
    md = it.get("content_md", "") or it.get("content_markdown", "") or ""
    return len(md) + 800

def make_batches(
    items: List[Dict[str, Any]],
    max_items_per_batch: int = 10,
    max_chars_per_batch: int = 180_000
) -> List[List[Dict[str, Any]]]:
    batches: List[List[Dict[str, Any]]] = []
    cur: List[Dict[str, Any]] = []
    cur_chars = 0

    for it in items:
        size = estimate_item_size(it)
        if cur and (len(cur) >= max_items_per_batch or (cur_chars + size) > max_chars_per_batch):
            batches.append(cur)
            cur = []
            cur_chars = 0
        cur.append(it)
        cur_chars += size

    if cur:
        batches.append(cur)

    return batches

# =========================
# Adaptador de item para o Dify
# =========================

def adapt_item_for_dify(it: Dict[str, Any], max_content_chars: int = 6000) -> Dict[str, Any]:
    raw_md = it.get("content_markdown") or it.get("content_md") or ""
    md_clamped = clamp_head_tail(raw_md, max_chars=max_content_chars)

    return {
        "run_id": it.get("collected_at") or it.get("run_id") or RUN_DATE,
        "provider": it.get("source_name") or it.get("provider") or it.get("source_id") or "",
        "engine": it.get("category") or it.get("engine") or "",
        "source_type": it.get("category") or it.get("source_type") or "",
        "url": it.get("url") or "",
        "title": it.get("title") or "",
        "fetched_at": it.get("collected_at") or it.get("fetched_at") or "",
        "content_hash": it.get("content_hash") or "",
        # envia conteúdo clampado para reduzir tempo de LLM e payload
        "content_md": md_clamped,
        "content_len": len(raw_md),
        "metadata": {
            "source_id": it.get("source_id"),
            "tier": it.get("tier"),
            "tags": it.get("tags") or [],
            "published_at": it.get("published_at") or ""
        }
    }

# =========================
# Helpers para extrair outputs do Dify
# =========================

def truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ["true", "1", "yes", "y", "sim"]
    return False

def extract_outputs(resp: Dict[str, Any]) -> Dict[str, Any]:
    data = resp.get("data", {})
    if isinstance(data, dict):
        outputs = data.get("outputs", {})
        if isinstance(outputs, dict):
            return outputs
    return {}

def extract_classified_list(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    outputs = extract_outputs(resp)
    classified_obj = (
        outputs.get("classified_items")
        or outputs.get("classified")
        or outputs.get("items")
        or {}
    )

    if isinstance(classified_obj, dict):
        items = classified_obj.get("items", [])
        return items if isinstance(items, list) else []
    if isinstance(classified_obj, list):
        return classified_obj
    return []

def extract_relevant_list(resp: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = extract_classified_list(resp)
    return [
        r
        for r in rows
        if isinstance(r, dict)
        and isinstance(r.get("classification"), dict)
        and truthy(r["classification"].get("is_relevant"))
    ]

def extract_report_md(resp: Dict[str, Any]) -> str:
    outputs = extract_outputs(resp)
    report_md = outputs.get("report_md") or outputs.get("report_markdown") or outputs.get("report") or ""
    return report_md if isinstance(report_md, str) else ""

def merge_part_jsonl_files(run_dir: Path, pattern: str, out_path: Path) -> None:
    part_files = sorted(run_dir.glob(pattern))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as out:
        for pf in part_files:
            with open(pf, "r", encoding="utf-8") as inp:
                for line in inp:
                    out.write(line)

def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    items: List[Dict[str, Any]] = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                if isinstance(obj, dict):
                    items.append(obj)
            except Exception:
                continue
    return items

# =========================
# Rodar Dify a partir do raw
# =========================

def run_dify_from_raw(
    max_items_per_batch: int = 1,
    max_chars_per_batch: int = 6_000,
    max_content_chars: int = 6_000,
    sleep_seconds: float = 0.2,
    max_retries: int = 3
) -> None:
    raw_items = load_json(RAW_PATH, default=[])
    if not isinstance(raw_items, list):
        raw_items = []

    print("RAW_PATH:", RAW_PATH)
    print("Raw items:", len(raw_items))

    if len(raw_items) == 0:
        print("Nada no raw para processar.")
        return

    dify_items = [adapt_item_for_dify(it, max_content_chars=max_content_chars) for it in raw_items]
    batches = make_batches(dify_items, max_items_per_batch=max_items_per_batch, max_chars_per_batch=max_chars_per_batch)
    print("Batches:", len(batches))

    print("Chamando Dify mode=classify...")
    for idx, batch in enumerate(batches, start=1):
        batch_file = BATCH_DIR / f"batch_{idx:03d}.json"
        #save_json(batch_file, batch)

        # debug útil para confirmar clamp
        try:
            it0 = batch[0]
            md0 = it0.get("content_md", "") or ""
            print(f"Batch {idx:03d}: items={len(batch)} len_enviado={len(md0)} len_original={it0.get('content_len', 0)}")
        except Exception:
            pass

        inputs = {
            "mode": "classify",
            "items": {"items": batch}
        }

        try:
            resp = dify_run_with_retry(
                inputs=inputs,
                response_mode="blocking",
                timeout_seconds=300,
                max_retries=max_retries,
                backoff_base_seconds=1.0
            )
        except Exception as e:
            print(f"Falha definitiva no batch {idx:03d}: {e}")
            continue

        resp_file = RESP_DIR / f"classify_resp_{idx:03d}.json"
        classified_list = extract_relevant_list(resp)
        #if classified_list:
        #    save_json(resp_file, classified_list)

        part_path = FINAL_DIR / f"classified.part_{idx:03d}.jsonl"
        if part_path.exists():
            part_path.unlink()
        append_jsonl(part_path, classified_list)

        print(f"Batch {idx:03d}: classificados {len(classified_list)}")
        time.sleep(sleep_seconds)

    merged_rel_jsonl = FINAL_DIR / "classified.jsonl"
    merge_part_jsonl_files(FINAL_DIR, "classified.part_*.jsonl", merged_rel_jsonl)

    merged_rel_list = load_jsonl(merged_rel_jsonl)
    classified_path = FINAL_DIR / "classified.json"
    save_json(classified_path, merged_rel_list)

    print("Total classificados (relevantes):", len(merged_rel_list))
    print("Classificados REL JSONL:", merged_rel_jsonl)
    print("Classificados REL JSON:", classified_path)

    if len(merged_rel_list) == 0:
        print("Nada relevante classificado, não gera report.")
        return

    print("Chamando Dify mode=report...")
    report_inputs = {
        "mode": "report",
        "classified_items": {"items": merged_rel_list}
    }

    report_resp = dify_run_with_retry(
        inputs=report_inputs,
        response_mode="blocking",
        timeout_seconds=420,
        max_retries=max_retries,
        backoff_base_seconds=1.0
    )
    save_json(FINAL_DIR / "report_response.json", report_resp)
    report_md = extract_report_md(report_resp)
    save_markdown(FINAL_DIR / "report.md", report_md)
    

    report_md = extract_report_md(report_resp)
    report_path = FINAL_DIR / "report.md"
    report_path.write_text(report_md, encoding="utf-8")

    print("Report salvo em:", report_path)
    print("Report chars:", len(report_md))

# Execute
run_dify_from_raw()
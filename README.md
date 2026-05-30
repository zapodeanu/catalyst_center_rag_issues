# Catalyst Center GenAI Troubleshooting

Written by Gabi Zapodeanu, Principal TME, updated with Cursor/Codex 5.3.

`Issues Pilot` is a local troubleshooting assistant that:
- collects Catalyst Center issue/device/compliance/command output data into `DATASET/`
- chunks and embeds that data into a Chroma collection
- answers troubleshooting questions from the Chroma context using OpenAI or Anthropic client apps

## Project Structure

- `Data_Collection/network_troubleshooting.py`: pull troubleshooting data for one assurance issue ID
- `Transform_Data/embeddings_to_chroma.py`: ingest `DATASET/` files into Chroma with metadata
- `DB_Server/chroma_db_server.py`: start local Chroma server
- `DB_Server/chroma_create_erase_collection.py`: create/delete target Chroma collection
- `ClientApp/query_issues_pilot_openai.py`: single-turn query client (OpenAI)
- `ClientApp/conversation_issues_pilot_openai.py`: multi-turn conversation client (OpenAI)
- `ClientApp/conversation_issues_pilot_anthropic.py`: multi-turn conversation client (Anthropic)
- `Transform_Data/embeddings_toolkit.py`: embedding model + TLS sanity helper

## Setup

1. Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

3. Configure environment values in `environment.env` (used directly by scripts via `load_dotenv`).

Minimum required values depend on script, but commonly include:
- Chroma: `DB_SERVER`, `DB_PORT`, `DB_COLLECTION`, `DB_PATH`
- Data paths: `APPS_PATH`, `DATASET`
- Embeddings: `MODEL_NAME` or `MODEL_LOCAL_PATH`
- OpenAI clients: `OPENAI_API_KEY`, `OPENAI_MODEL`
- Anthropic client: `CLAUDE_API_KEY`, `CLAUDE_MODEL`
- Data collection: `CC_URL`, `CC_USER`, `CC_PASS`

## Data Collection -> Embedding -> Chroma Flow

Run these in order from repo root:

1) Start Chroma server:

```bash
python DB_Server/chroma_db_server.py
```

2) Create (or reset) collection:

```bash
python DB_Server/chroma_create_erase_collection.py
```

3) Collect troubleshooting data for one assurance issue:

```bash
python Data_Collection/network_troubleshooting.py <assuranceIssueId>
```

4) Embed and load `DATASET/` into Chroma:

```bash
python Transform_Data/embeddings_to_chroma.py
```

## Client Apps and Model Choices

- OpenAI single-turn: `python ClientApp/query_issues_pilot_openai.py`
- OpenAI conversation: `python ClientApp/conversation_issues_pilot_openai.py`
- Anthropic conversation: `python ClientApp/conversation_issues_pilot_anthropic.py`

Model selection is environment-driven:
- embeddings model: `MODEL_LOCAL_PATH` (preferred if set) else `MODEL_NAME`
- OpenAI model: `OPENAI_MODEL`
- Anthropic model: `CLAUDE_MODEL`

Legacy scripts still exist in `Query/` for earlier direct query patterns.

## Retrieval Behavior (Current)

All `ClientApp/*issues_pilot*.py` clients now use this retrieval pipeline:

1. Device-only metadata filter:
   - Detect device from query (exact match first).
   - Apply Chroma filter `{"device name": "<device>"}` when detected.

2. Typo-tolerant hostname normalization:
   - Normalize hostnames (case/`-`/`_` tolerant).
   - Use fuzzy token match (`difflib.get_close_matches`, cutoff `0.74`) for misspelled device names.
   - Rewrite only the typed token in the effective query.

3. Hybrid retrieval:
   - Vector retriever query with `k=20` (plus metadata filter when available).
   - Parallel filter-only fetch via `chroma_db.get(where=metadata_filter, include=["documents", "metadatas"])`.

4. Candidate merge and dedupe:
   - Merge vector and filter candidates.
   - Deduplicate by `(page_content, metadata)` key.

5. Lexical rerank + context cap:
   - Score by lexical overlap between query tokens and:
     - chunk content tokens
     - metadata tokens (`CLI command`, `issue name`, `filename`) with half-weight
   - Keep top 16 chunks as final LLM context.

## Timing Instrumentation

Each query prints a latency line in this format:

```text
IssuesPilot: timing retrieval=<ms>ms filter=<ms>ms rerank=<ms>ms llm=<ms>ms total=<ms>ms
```

How to interpret:
- `retrieval`: vector retrieval time (`as_retriever().invoke`)
- `filter`: metadata-only Chroma fetch (`get(where=...)`)
- `rerank`: merge + dedupe + lexical scoring
- `llm`: answer generation time
- `total`: full end-to-end user-query latency

`llm` may be `0ms` when no matching context is found.

## SSL / Certifi / HF_CA_BUNDLE Troubleshooting

For TLS/proxy certificate issues while loading Hugging Face models:

1. Put your corporate CA bundle in a PEM file.
2. Set `HF_CA_BUNDLE` in `environment.env` to that PEM path.
3. If unset, scripts fall back to:
   - `REQUESTS_CA_BUNDLE` / `SSL_CERT_FILE` (if already set), then
   - `~/hf-ca-bundle.pem` (if present), then
   - `certifi.where()`

Quick check:

```bash
python Transform_Data/embeddings_toolkit.py
```

If model download still fails, use a local embedding path via `MODEL_LOCAL_PATH`.

## Quick Smoke Tests

From repo root, with `.venv` active and `environment.env` configured:

```bash
# 1) Verify embedding model + TLS chain
python Transform_Data/embeddings_toolkit.py

# 2) Start Chroma server (terminal 1)
python DB_Server/chroma_db_server.py

# 3) Ensure collection exists (terminal 2)
python DB_Server/chroma_create_erase_collection.py

# 4) Ingest dataset
python Transform_Data/embeddings_to_chroma.py

# 5) Ask one question
python ClientApp/query_issues_pilot_openai.py
```

Expected signs of success:
- client prints target server/collection/models
- optional device notice/filter message when hostname is detected
- final timing line with retrieval/filter/rerank/llm/total breakdown
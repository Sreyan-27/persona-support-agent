# TechCorp Cloud — Persona-Adaptive Customer Support Agent

An AI customer support agent that detects who it's talking to (a technical
engineer, a frustrated end-user, or a business stakeholder), retrieves
grounded answers from a real knowledge base using RAG, adapts its tone and
depth to the detected persona, and escalates to a human with a structured
handoff summary when it shouldn't handle something alone.

Built for the AdsparkX AI Engineering Internship assignment.

---

## 1. Project Overview

The agent classifies every incoming message into one of three personas
(**Technical Expert**, **Frustrated User**, **Business Executive**),
retrieves the most relevant chunks from a 16-document support knowledge
base (account/security, billing, and API/technical articles for a
fictional SaaS company, "TechCorp Cloud") using a ChromaDB vector store,
and generates a response strictly grounded in that retrieved content. If
retrieval confidence is low, the topic is sensitive (billing, legal,
security), or the user has gone several turns without resolution, the
agent escalates instead of guessing — producing a structured JSON handoff
summary for a human agent.

Two interfaces are provided: a required interactive CLI (`cli.py`) and a
bonus Streamlit chat UI (`app.py`). Both share the exact same orchestration
logic (`src/session.py`), so behavior is identical between them.

## 2. Tech Stack

| Component | Choice | Version |
|---|---|---|
| Language | Python | 3.11+ |
| LLM (classification + generation) | Google Gemini (`gemini-2.5-flash`) | via `google-genai` |
| Embeddings | Gemini `text-embedding-004` | via `google-genai` |
| Vector database | ChromaDB (persistent, local) | `>=0.4.0` |
| Chunking | LangChain `RecursiveCharacterTextSplitter` (with a pure-Python fallback) | `>=0.1.0` |
| PDF parsing | `pypdf` | `>=3.0.0` |
| Web UI | Streamlit | `>=1.30.0` |
| Config | `python-dotenv` | `>=1.0.0` |

## 3. Architecture

```
                         ┌────────────────────┐
   User Query  ───────►  │  Persona Classifier │
                         │  (Gemini structured  │
                         │   JSON; rule-based    │
                         │   fallback if no key) │
                         └──────────┬───────────┘
                                    │ persona: Tech / Frustrated / Exec
                                    ▼
                         ┌────────────────────┐
                         │   RAG Retrieval     │
                         │  embed query ──►     │
                         │  ChromaDB cosine     │
                         │  similarity search   │
                         │  ──► top-k chunks    │
                         └──────────┬───────────┘
                                    │ chunks + scores + source/page
                                    ▼
                         ┌────────────────────┐
                         │  Escalation Check   │──── escalate ───┐
                         │ (confidence, topic,  │                 │
                         │  unresolved turns)   │                 ▼
                         └──────────┬───────────┘      ┌──────────────────┐
                                    │ no escalation     │  Human Handoff    │
                                    ▼                   │  JSON Summary     │
                         ┌────────────────────┐         │ (persona, issue,  │
                         │ Adaptive Generator  │         │  history, sources,│
                         │ persona-specific     │         │  attempted steps, │
                         │ system prompt, only  │         │  recommendation)  │
                         │ grounded in chunks   │         └──────────────────┘
                         └──────────┬───────────┘
                                    ▼
                              Response to User
```

Source-of-truth module map:

```
src/config.py        configuration & escalation thresholds (all tunable via .env)
src/classifier.py     persona detection (LLM + rule-based fallback)
src/rag_pipeline.py   document loading, chunking, embedding, ChromaDB, retrieval
src/generator.py      persona-adaptive prompt construction + grounded generation
src/escalator.py      escalation trigger logic + handoff summary builder
src/session.py        orchestrates one full conversation turn; multi-turn state
src/utils.py          Gemini client + exponential backoff retry wrapper
cli.py                required CLI interface
app.py                bonus Streamlit interface
ingest.py             standalone knowledge-base ingestion script
tests/test_offline.py logic checks that need no API key or network
```

## 4. Persona Detection Strategy

**Primary — LLM classification.** The user's message is sent to Gemini
with a system instruction describing the three personas and a strict JSON
response schema (`persona`, `confidence`, `reasoning`). Temperature is set
to `0.1` for consistency. See `CLASSIFIER_SYSTEM_INSTRUCTION` in
`src/classifier.py`.

**Fallback — rule-based.** If no API key is configured, or the Gemini call
fails/returns malformed JSON after retries, a deterministic keyword-pattern
matcher scores the message against three pattern sets (technical terms like
`api`, `error code`, `webhook`; frustration markers like repeated
exclamation points, "nothing works", "demand"; executive markers like
"business impact", "timeline", "SLA"). The persona with the most pattern
hits wins; ties default to Business Executive, the safest neutral tone.
This fallback keeps the agent fully demoable without a live key and
documents the classification rules transparently rather than leaving them
opaque inside a prompt.

## 5. RAG Pipeline Design

- **Chunking strategy:** `RecursiveCharacterTextSplitter`-equivalent
  algorithm — tries to split on paragraph breaks first, then lines, then
  sentences/words, falling back to raw characters only as a last resort.
  Chunk size: 500 characters, overlap: 50 characters (both configurable via
  `.env`), so a fact near a chunk boundary isn't lost.
- **PDF handling:** parsed page-by-page with `pypdf` so each chunk carries
  an accurate page number, rather than chunking the whole PDF as one blob.
- **Metadata:** every chunk stores `source` (filename) and either `page`
  (for PDFs) or `section` (nearest Markdown heading, for `.md`/`.txt`).
- **Embedding model:** Gemini `text-embedding-004`, used identically for
  both document chunks at ingest time and the live query at retrieval time.
- **Vector database:** ChromaDB in **persistent** mode (`./chroma_db/`),
  configured for cosine similarity. The index is built once and reused
  across runs (`ingest_all()` skips re-embedding unless `--force` is
  passed), so a chat turn never pays the cost of re-indexing.
- **Retrieval:** top-k (default `k=3`) nearest chunks by cosine similarity,
  returned with a `0–1` score (`1 - cosine_distance`) used directly by the
  escalation check.

## 6. Escalation Logic

All thresholds live in `src/config.py` and are overridable via `.env`.

| Trigger | Condition | Default |
|---|---|---|
| No relevant documents | Retrieval returns zero chunks | — |
| Low retrieval confidence | Best chunk score < threshold | `0.45` |
| Sensitive topic | Message contains a billing/legal/security keyword (refund, chargeback, GDPR, dispute, delete my account, etc.) | keyword list in `config.py` |
| Repeated frustration | `unresolved_turns` ≥ threshold for this session | `3` |

When any trigger fires, generation is **skipped entirely** (no LLM call for
the customer-facing answer) and a structured JSON handoff is produced
instead, containing: persona, issue summary, full conversation history,
which documents were consulted, previously attempted steps, the specific
trigger(s), and a trigger-specific recommendation for the human agent.

## 7. Setup Instructions

```bash
# 1. Clone and enter the repo
git clone <your-repo-url>
cd persona-support-agent

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure your API key
cp .env.example .env
# edit .env and paste your real GEMINI_API_KEY

# 5. (Optional) sanity-check your setup with no API calls
python -m tests.test_offline

# 6. Build the vector index
python ingest.py

# 7a. Run the CLI
python cli.py

# 7b. OR run the Streamlit UI
streamlit run app.py
```

## 8. Environment Variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `GEMINI_API_KEY` | **Yes** | — | Your Google Gemini API key |
| `GEMINI_GENERATION_MODEL` | No | `gemini-2.5-flash` | Model for classification + generation |
| `GEMINI_EMBEDDING_MODEL` | No | `text-embedding-004` | Embedding model |
| `CHUNK_SIZE` | No | `500` | Characters per chunk |
| `CHUNK_OVERLAP` | No | `50` | Overlap between chunks |
| `TOP_K` | No | `3` | Chunks retrieved per query |
| `RETRIEVAL_CONFIDENCE_THRESHOLD` | No | `0.45` | Min score to avoid escalation |
| `MAX_UNRESOLVED_TURNS` | No | `3` | Turns before forced escalation |
| `MAX_API_RETRIES` | No | `5` | Backoff retry attempts on API errors |

Never commit your real `.env` — it's already in `.gitignore`.

## 9. Example Queries

1. *"Can you explain the API authentication failure and provide error details?"* → **Technical Expert**, grounded in `api_authentication_guide.md` / `error_code_reference.md`.
2. *"I've tried everything and nothing works! My password reset isn't arriving!"* → **Frustrated User**, empathetic step-by-step from `password_reset_guide.pdf`.
3. *"How does this issue impact operations and when will it be resolved?"* → **Business Executive**, concise answer referencing `uptime_and_sla_policy.md`.
4. *"My billing statement has unexpected duplicate charges. I demand an immediate refund!"* → **Frustrated User** + **escalates** (sensitive billing keyword) with a full handoff JSON.
5. *"What are the retry semantics for failed webhook deliveries?"* → **Technical Expert**, grounded in `webhook_troubleshooting.md`.

## 10. Known Limitations & Future Improvements

- The rule-based persona fallback is a simple keyword matcher; it's a
  safety net for offline/no-key operation, not a replacement for the LLM
  classifier's nuance.
- `unresolved_turns` resets per `SupportSession` instance (in-memory only);
  a production system would persist conversation/session state (e.g.
  Redis or a database) across page reloads and server restarts.
- No automatic re-ingestion on file change — if you edit `/data`, re-run
  `python ingest.py --force`.
- Sensitive-topic detection is keyword-based; a production system might
  combine it with the LLM's own judgment for higher recall on phrasing it
  doesn't anticipate.
- Single-language (English) knowledge base and prompts.
- Not yet implemented (potential bonus additions): sentiment scoring over
  time, a LangGraph-based multi-agent workflow, an analytics dashboard, and
  a human-approval-before-send workflow.

## 11. Submission Checklist

- [x] GitHub repository with source + `/data` knowledge base committed
- [x] `README.md` (this file)
- [x] 16 knowledge base documents (`.md`, `.txt`, and 1 required `.pdf`)
- [ ] Screen recording (3–8 min) — see suggested script below
- [ ] Deployed link (e.g. Streamlit Community Cloud)

### Suggested recording outline
1. Project structure walkthrough (30s)
2. `python ingest.py` — show knowledge base ingestion (30s)
3. 5 example queries above, one per persona + the escalation case (3–4 min)
4. Show retrieved sources + handoff JSON for the escalation case (30s)
5. One technical design decision explained, e.g. *why escalation skips
   generation entirely* or *why PDF chunks are paginated* (1 min)

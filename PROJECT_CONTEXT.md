## FlowMind Project Context

- Last updated: 2026-04-03
- Environment: Windows (`win32 10.0.26200`), FastAPI backend, local OCR + optional Ollama VLM
- Active focus: Image extraction strategy: smart filter by size/aspect ratio (no hard cap), 3 scenario-aware VLM prompts (diagram_only, diagram_with_local_text, diagram_with_context), parallel processing with max_workers=3, image requirements bypass modal verb validation, cross-document linking pass connects image requirements to related text chunks anywhere in document.

## Current Status

- UI and workflow features are largely implemented (client review + manager dashboard flows).
- Extraction pipeline now runs heuristic + pattern + semantic and merges outputs in `rag_agent.py`.
- Retrieval now uses targeted category queries plus an image-summary retrieval pass.
- LLM finalize default is enabled (`FLOWMIND_USE_LLM_FINALIZE=1` default).

## Image/Requirement Extraction Changes

- `rag_agent.py`
  - Removed hard rejection of image-tagged lines in validation.
  - Added preprocessing to strip `[IMAGE*]` / OCR markers into clean prose.
  - Added relaxed validation channel for image-derived content (no strict modal-verb requirement).
  - Removed heuristic early-exit and merged all extraction method outputs.
- `flowmind.py`
  - Image OCR paths now route through advanced OCR helper (`advanced_ocr_extract` via helper).
  - Added dedicated per-image requirement extraction pass.
  - Added `[IMAGE_REQUIREMENTS <image_id>]` markers into merged extraction context.
  - Added structured image-derived requirements with `evidence_image_id` for traceability.
- `services/image_service.py`
  - Added `extract_testable_requirements_from_image(...)` using the dedicated prompt and VLM pass.

## Known Risks / Verification Needed

- VLM requirement extraction quality depends on local model availability and OCR quality.
- Running all extraction methods may increase latency on large documents.
- **Large PDFs / many images:** VLM runs on images that pass a **smart filter** (min size, aspect ratio, OCR length); there is **no** fixed max-image count. Disable the diagram requirement pass with `FLOWMIND_IMAGE_REQ_VLM_PASS=0`. Parallel VLM uses at most `FLOWMIND_VLM_MAX_WORKERS` (default 3). By default semantic extraction still runs on large retrieved text (`FLOWMIND_SKIP_SEMANTIC_LARGE_TEXT=0`); set to `1` to skip semantic when text exceeds the large-text threshold.
- UI verification needed for:
  - Better image-derived requirements
  - No missing text-only requirements
  - Acceptable response time

## Next Step Rule

- One step at a time: implement -> UI verify -> then continue.
- Do not batch further major changes until verification feedback is received.

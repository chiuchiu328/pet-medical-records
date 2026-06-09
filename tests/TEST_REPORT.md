# Test Report

Last updated: 2026-06-09

## Current Status

- Full suite command: `uv run pytest`
- Current result: `21 passed, 1 warning`
- Warning summary: Starlette/FastAPI test client emits a deprecation warning about `httpx`; this does not currently fail the suite, but it is worth tracking during dependency upgrades.

## Test Inventory

### `tests/conftest.py`

- Provides a `TestClient` backed by a temporary SQLite database and temporary `upload_dir`.
- Provides the shared `momo_pet` fixture used by most API tests.

### `tests/helpers.py`

- Provides `delete_with_preview()` and `restore_with_preview()` helpers.
- These helpers enforce the preview-token flow in tests instead of bypassing it.

### `tests/test_rest_api.py`

Focus: happy-path REST workflow coverage.

- End-to-end pet -> medical record -> daily log -> attachment workflow.
- Attachment upload behavior, including:
  - `ocr_status` auto-normalization
  - `storage_path` stored relative to `upload_dir`
  - `local_file_path` resolved to a real absolute path
- Timeline search and category filtering.
- Basic soft-delete behavior for daily logs.

### `tests/test_rest_api_missing_coverage.py`

Focus: broader REST CRUD and search/filter coverage.

- Pet CRUD, keyword search, include-deleted behavior.
- Medical record get/update/delete flows and include-deleted search behavior.
- Daily log get/update flows plus appetite/energy/tag filters.
- Attachment get/update/delete flows, including manual OCR text updates.
- Multi-pet isolation across records, logs, and timeline results.

### `tests/test_soft_delete_visibility.py`

Focus: soft-delete graph behavior and visibility semantics in REST.

- Preview token requirements and error cases.
- Ancestor hiding behavior:
  - deleted pet hides records, logs, and attachments
  - deleted record hides child attachments
- Restore behavior:
  - parent restore re-exposes descendants when descendants are not directly deleted
  - directly deleted children remain deleted after parent restore
- Timeline behavior under ancestor-hidden data.
- `visibility.deleted`, `visibility.hidden_by_ancestor`, and `visibility.hidden_by` semantics.

### `tests/test_mcp_tool_layer.py`

Focus: agent-first MCP behavior and file-path semantics.

- MCP happy path for pet / medical record / daily log / attachment workflows.
- Timeline and summary behavior through the MCP tool layer.
- Attachment path handling:
  - `storage_path` relative to `upload_dir`
  - `local_file_path` absolute and existing
  - resolving local file paths from relative storage keys
- Missing local attachment file failure case.
- Legacy attachment path normalization on MCP initialization.
- Daily log update/get/delete behavior through MCP tools.

### `tests/test_mcp_delete_restore_preview.py`

Focus: delete/restore preview parity in MCP.

- Ensures preview and restore tools exist for pet, medical record, daily log, and attachment resources.
- Validates confirm-token enforcement and invalid-token failures.
- Verifies delete/restore preview impact payloads.
- Verifies ancestor visibility behavior and restore flows through MCP tools.

## Coverage Summary

The current suite gives good coverage for:

- Core CRUD flows for pets, medical records, daily logs, and attachments.
- Search and filtering behavior for common REST queries.
- Soft-delete and restore flows, including preview-token confirmation.
- Ancestor visibility semantics across nested resources.
- MCP parity for the main workflows.
- Attachment storage-path behavior after the recent `upload_dir` / relative-path cleanup.

## Important Behaviors Already Protected

- `storage_path` is modeled as relative to `upload_dir`, not as an absolute path.
- `local_file_path` is derived from runtime `upload_dir`, not from database location.
- Parent deletion hides descendants without necessarily marking them as directly deleted.
- Parent restore does not accidentally undelete directly deleted child rows.
- MCP and REST both use the same storage and visibility semantics.

## Notable Gaps / Potential Next Test Targets

These are the highest-value areas that still look under-tested:

### 1. Validation and bad-request coverage

Potential additions:

- invalid enum values for `media_type`, `category`, `appetite`, `energy`, `ocr_status`
- invalid pagination inputs such as `limit < 1` or `page < 1`
- malformed datetimes and timezone edge cases
- missing required fields on create endpoints

Why it matters:

- The service layer contains explicit invalid-request handling, but only part of that behavior is currently exercised.

### 2. Search, sort, and pagination depth

Potential additions:

- explicit assertions for ascending vs descending sort modes
- pagination across more than one page
- start/end boundary inclusion behavior
- combined filters, for example keyword + tag + category + include_deleted

Why it matters:

- Search endpoints are central to retrieval behavior, and regressions here are easy to introduce silently.

### 3. Attachment edge cases

Potential additions:

- filename sanitization behavior from `app/storage/local.py`
- duplicate uploads to the same owner
- non-image / non-video MIME combinations
- attachment behavior when file metadata is updated without OCR text
- behavior when normalized storage paths are malformed or escape the upload root

Why it matters:

- File handling is one of the riskier parts of the system and has path-safety implications.

### 4. Restore edge cases

Potential additions:

- invalid or expired restore tokens
- restore preview impact when only some descendants are directly deleted
- attachment restore while owner remains hidden by ancestor

Why it matters:

- The preview/restore model is a product-level contract and should stay very predictable.

### 5. Visibility behavior in list endpoints

Potential additions:

- explicit assertions for attachment visibility in list/search results under mixed deleted states
- mixed scenarios where one child is deleted and another is only ancestor-hidden

Why it matters:

- Most visibility rules are covered through get/timeline flows, but list-level combinations are still a likely regression surface.

### 6. Startup normalization behavior in REST app creation

Potential additions:

- a REST-side test proving legacy `uploads/...` rows are normalized during `create_app()`

Why it matters:

- MCP initialization already has direct coverage for legacy normalization, but the FastAPI app startup path should have a matching guardrail.

## Suggested Ongoing Testing Strategy

- Keep `tests/test_rest_api.py` for concise happy-path journeys.
- Keep `tests/test_rest_api_missing_coverage.py` for targeted REST behavior expansions.
- Keep `tests/test_soft_delete_visibility.py` as the source of truth for deletion/restore visibility semantics.
- Keep `tests/test_mcp_tool_layer.py` and `tests/test_mcp_delete_restore_preview.py` focused on MCP parity and agent-facing path behavior.

## Maintenance Rule

When test code changes, update this report in the same commit.

At minimum, update:

- the current test count or suite result if it changed
- any new or renamed test files
- the coverage summary for the affected behaviors
- the gap analysis if a previously missing area is now covered

If a code change alters system behavior but no test section in this report changes, that is a signal to double-check whether the report or the tests are now stale.

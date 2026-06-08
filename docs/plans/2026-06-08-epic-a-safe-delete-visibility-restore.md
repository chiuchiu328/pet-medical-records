# Epic A: Safe Delete, Visibility, and Restore Consistency Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Add safe delete preview/confirm flows, ancestor-aware child visibility, and symmetric restore behavior across REST API and MCP tools.

**Architecture:** Keep the current soft-delete model (`deleted_at`, `delete_reason`) and current polymorphic attachment ownership (`owner_type`, `owner_id`). Do not cascade-write child rows on parent delete. Instead, implement effective visibility in the service layer so resources are hidden when they or any ancestor are deleted. Add preview endpoints/tools with confirm tokens for delete/restore, and restore only the directly targeted resource.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy ORM, Pydantic, SQLite, pytest, MCP stdio tool layer.

---

## Product decisions locked by this plan

1. **Delete safety pattern:** preview + confirm token.
2. **Visibility pattern:** hierarchical effective visibility, not cascade soft delete.
3. **Restore pattern:** restore only the directly targeted resource; child resources become visible again only if they are not directly soft-deleted themselves.
4. **Attachment ownership model:** keep current polymorphic association (`owner_type`, `owner_id`) in Epic A.
5. **`include_deleted=true`:** should expose both directly deleted resources and resources hidden by deleted ancestors.
6. **Response metadata:** when a resource is included despite not being effectively visible by default, expose why (`visibility.deleted`, `visibility.hidden_by_ancestor`, `visibility.hidden_by`).

---

## Current baseline to preserve

- `Pet` -> `MedicalRecord` via `pet_id`
- `Pet` -> `DailyLog` via `pet_id`
- `MedicalRecord` / `DailyLog` -> `MediaAttachment` via polymorphic `owner_type` + `owner_id`
- Existing direct CRUD and search routes/tools must keep working after the change.
- Existing attachment storage behavior must stay unchanged.

---

## Required semantics after implementation

### Effective visibility rules

1. A `Pet` is effectively visible when `pet.deleted_at is None`.
2. A `MedicalRecord` is effectively visible when:
   - `record.deleted_at is None`, and
   - parent `Pet` is effectively visible.
3. A `DailyLog` is effectively visible when:
   - `log.deleted_at is None`, and
   - parent `Pet` is effectively visible.
4. A `MediaAttachment` is effectively visible when:
   - `attachment.deleted_at is None`, and
   - its owner (`MedicalRecord` or `DailyLog`) is effectively visible.

### Restore rules

1. Restoring a `Pet` clears only the pet's own delete markers.
2. Restoring a `MedicalRecord` clears only the record's own delete markers.
3. Restoring a `DailyLog` clears only the log's own delete markers.
4. Restoring a `MediaAttachment` clears only the attachment's own delete markers.
5. No restore operation should directly clear child `deleted_at` values.

### Preview rules

Preview responses must include:
- target resource identity
- delete/restore summary
- effective visibility impact summary
- confirm token
- expiry timestamp

Delete preview should also include impacted descendants that will become hidden by ancestor deletion.
Restore preview should show which descendants will become visible again and which will remain hidden because they are directly deleted.

---

## Files expected to change

**Likely modify:**
- `app/schemas.py`
- `app/services.py`
- `app/api/routes.py`
- `app/mcp/tool_layer.py`
- `README.md`
- `docs/API.md`
- `docs/softwareArchitecture.md`

**Likely add tests:**
- `tests/test_soft_delete_visibility.py`
- `tests/test_mcp_delete_restore_preview.py`

You may instead extend existing test files if that keeps the suite clearer, but coverage must remain explicit and easy to audit.

---

## Task 1: Add schemas for preview / restore / visibility metadata

**Objective:** Introduce request/response schemas needed for preview-confirm delete/restore and explain effective visibility in API responses.

**Files:**
- Modify: `app/schemas.py`
- Test: `tests/test_soft_delete_visibility.py`

**Step 1: Write failing tests**

Add tests that exercise expected response fields from future endpoints/tools:
- preview responses contain `confirm_token` and `expires_at`
- resource read responses contain a `visibility` object
- `visibility.hidden_by_ancestor` is `true` for descendant resources hidden by deleted parents when `include_deleted=true`

**Step 2: Run targeted tests to verify failure**

Run:
```sh
uv run pytest tests/test_soft_delete_visibility.py -q
```
Expected: FAIL because new schemas / routes do not exist yet.

**Step 3: Implement minimal schemas**

Add Pydantic models for:
- `DeleteConfirmRequest`
- `RestoreConfirmRequest`
- `PreviewTokenResponse` (or richer preview schema)
- `VisibilityInfo`

Add `visibility: VisibilityInfo` to:
- `PetRead`
- `MedicalRecordRead`
- `DailyLogRead`
- `MediaAttachmentRead`

Use stable field names like:
- `deleted: bool`
- `hidden_by_ancestor: bool`
- `hidden_by: dict | None`

**Step 4: Re-run tests**

Run:
```sh
uv run pytest tests/test_soft_delete_visibility.py -q
```
Expected: some tests still fail until service and routes are implemented, but schema-level import/validation errors should be resolved.

---

## Task 2: Build effective visibility helpers in the service layer

**Objective:** Centralize ancestor-aware visibility evaluation without cascade-writing descendants.

**Files:**
- Modify: `app/services.py`
- Test: `tests/test_soft_delete_visibility.py`

**Step 1: Write failing tests**

Add tests covering:
- deleted pet hides medical records in direct get/search
- deleted pet hides daily logs in direct get/search
- deleted record hides attachment in direct get
- include_deleted=true returns those resources with `visibility.hidden_by_ancestor == true`

**Step 2: Run targeted tests to verify failure**

Run:
```sh
uv run pytest tests/test_soft_delete_visibility.py -q
```
Expected: FAIL due to old row-local visibility behavior.

**Step 3: Implement visibility helpers**

In `app/services.py`, add helpers such as:
- `build_pet_visibility(...)`
- `build_medical_record_visibility(...)`
- `build_daily_log_visibility(...)`
- `build_attachment_visibility(...)`
- `is_*_effectively_visible(...)`

Key rule:
- effective visibility must consider ancestor delete state.

Then update:
- `get_medical_record`
- `get_daily_log`
- `get_attachment`
- `search_medical_records`
- `search_daily_logs`
- `get_pet_timeline`
- any read-model builder functions

Behavior:
- default read/search hides effectively invisible resources
- `include_deleted=true` includes them and annotates why

**Step 4: Re-run tests**

Run:
```sh
uv run pytest tests/test_soft_delete_visibility.py -q
```
Expected: PASS for visibility rules added so far.

---

## Task 3: Add preview token infrastructure and preview builders

**Objective:** Create preview-confirm flow for delete and restore in the service layer.

**Files:**
- Modify: `app/services.py`
- Modify: `app/schemas.py`
- Test: `tests/test_soft_delete_visibility.py`
- Test: `tests/test_mcp_delete_restore_preview.py`

**Step 1: Write failing tests**

Add tests for:
- delete preview returns token, expiry, summary, and impact counts
- restore preview returns token, expiry, summary, and visibility restoration summary
- using a missing or invalid token for delete/restore fails with 400

**Step 2: Run tests to verify failure**

Run:
```sh
uv run pytest tests/test_soft_delete_visibility.py tests/test_mcp_delete_restore_preview.py -q
```
Expected: FAIL because preview token logic does not exist.

**Step 3: Implement preview token support**

Keep implementation simple and local to process/app for Epic A v1:
- use app-local in-memory preview token store with expiry
- token payload should include:
  - action (`delete` / `restore`)
  - resource type
  - resource id
  - expiry
- tokens should be one-time use

Add preview builder functions for each resource type:
- `build_delete_preview_*`
- `build_restore_preview_*`

Preview impact requirements:
- deleting pet reports counts of medical records, daily logs, and attachments that will become hidden
- deleting record/log reports attachment impact
- restore previews report what may become visible again vs still remain hidden because directly deleted

**Step 4: Re-run tests**

Run:
```sh
uv run pytest tests/test_soft_delete_visibility.py tests/test_mcp_delete_restore_preview.py -q
```
Expected: preview tests now reach route/tool failures instead of service failures.

---

## Task 4: Add delete/restore service operations with confirm token validation

**Objective:** Enforce preview-confirm flow in the service layer for delete and restore.

**Files:**
- Modify: `app/services.py`
- Test: `tests/test_soft_delete_visibility.py`
- Test: `tests/test_mcp_delete_restore_preview.py`

**Step 1: Write failing tests**

Add tests for:
- delete without confirm token fails
- delete with wrong token fails
- delete with correct token succeeds
- restore with correct token succeeds
- restore does not directly undelete already-deleted children

**Step 2: Run tests to verify failure**

Run:
```sh
uv run pytest tests/test_soft_delete_visibility.py tests/test_mcp_delete_restore_preview.py -q
```
Expected: FAIL because delete/restore operations are not yet token-gated.

**Step 3: Implement delete/restore actions**

Replace direct-delete behavior with token-confirmed behavior in service functions.

Suggested service shape:
- `delete_pet(..., reason, confirm_token)`
- `delete_medical_record(..., reason, confirm_token)`
- `delete_daily_log(..., reason, confirm_token)`
- `delete_attachment(..., reason, confirm_token)`
- `restore_pet(..., confirm_token)`
- `restore_medical_record(..., confirm_token)`
- `restore_daily_log(..., confirm_token)`
- `restore_attachment(..., confirm_token)`

Validation requirements:
- token matches action/resource/resource_id
- token not expired
- token consumed after successful use
- meaningful `InvalidRequest` messages on failures

**Step 4: Re-run tests**

Run:
```sh
uv run pytest tests/test_soft_delete_visibility.py tests/test_mcp_delete_restore_preview.py -q
```
Expected: PASS for service-level delete/restore semantics.

---

## Task 5: Expose delete preview and restore flows through REST API

**Objective:** Add explicit preview/restore REST endpoints and update existing delete endpoints to require confirm tokens.

**Files:**
- Modify: `app/api/routes.py`
- Modify: `app/main.py` if error mapping needs extension
- Test: `tests/test_soft_delete_visibility.py`

**Step 1: Write failing tests**

Add REST tests covering:
- `POST /pets/{id}/delete-preview`
- `POST /medical-records/{id}/delete-preview`
- `POST /daily-logs/{id}/delete-preview`
- `POST /attachments/{id}/delete-preview`
- `POST /.../restore-preview`
- `POST /.../restore`
- `DELETE /...` requiring valid confirm token

**Step 2: Run targeted tests**

Run:
```sh
uv run pytest tests/test_soft_delete_visibility.py -q
```
Expected: FAIL due to missing routes or wrong payload requirements.

**Step 3: Implement routes**

Add routes:
- `POST /pets/{pet_id}/delete-preview`
- `POST /pets/{pet_id}/restore-preview`
- `POST /pets/{pet_id}/restore`
- same pattern for medical records, daily logs, attachments

Update existing `DELETE` routes to accept:
- `reason`
- `confirm_token`

Ensure response models surface visibility metadata.

**Step 4: Re-run tests**

Run:
```sh
uv run pytest tests/test_soft_delete_visibility.py -q
```
Expected: PASS for REST flow.

---

## Task 6: Expose delete preview and restore flows through MCP tool layer

**Objective:** Keep MCP feature parity with REST for agent-first workflows.

**Files:**
- Modify: `app/mcp/tool_layer.py`
- Possibly modify: `app/mcp/server.py` if tool listing behavior needs updates
- Test: `tests/test_mcp_delete_restore_preview.py`

**Step 1: Write failing tests**

Add MCP tests covering:
- `delete_pet_preview`
- `delete_medical_record_preview`
- `delete_daily_log_preview`
- `delete_attachment_preview`
- restore preview and restore tools
- direct delete failing without token
- include_deleted MCP reads returning visibility metadata

**Step 2: Run targeted tests**

Run:
```sh
uv run pytest tests/test_mcp_delete_restore_preview.py -q
```
Expected: FAIL because tools do not yet exist.

**Step 3: Implement MCP tools**

Update `list_tools()` and `_dispatch()` to add parity tools:
- `delete_pet_preview`
- `restore_pet_preview`
- `restore_pet`
- same pattern for medical record, daily log, attachment

Update existing delete tool dispatchers to require/pass `confirm_token`.

**Step 4: Re-run tests**

Run:
```sh
uv run pytest tests/test_mcp_delete_restore_preview.py -q
```
Expected: PASS for MCP flow.

---

## Task 7: Ensure timeline and search endpoints obey effective visibility consistently

**Objective:** Guarantee every read path shares the same ancestor-aware behavior.

**Files:**
- Modify: `app/services.py`
- Test: `tests/test_soft_delete_visibility.py`

**Step 1: Write failing tests**

Add tests for:
- deleted pet hides both medical and daily events from timeline by default
- `include_deleted=true` returns those events with visibility metadata in nested data payloads where applicable
- category filters do not accidentally expose hidden attachments/events

**Step 2: Run targeted tests**

Run:
```sh
uv run pytest tests/test_soft_delete_visibility.py -q
```
Expected: FAIL if timeline/search paths still use inconsistent visibility handling.

**Step 3: Implement consistency fixes**

Audit and update all service read paths so they all rely on the same visibility helpers.

**Step 4: Re-run tests**

Run:
```sh
uv run pytest tests/test_soft_delete_visibility.py -q
```
Expected: PASS.

---

## Task 8: Update docs to match the new contract

**Objective:** Bring README and docs in sync with Epic A behavior.

**Files:**
- Modify: `README.md`
- Modify: `docs/API.md`
- Modify: `docs/softwareArchitecture.md`

**Step 1: Document contract changes**

Update docs to explicitly state:
- delete now requires preview + confirm token
- restore exists and is symmetric with soft delete
- visibility is ancestor-aware
- child rows are not cascade-soft-deleted
- `include_deleted=true` includes ancestor-hidden items
- new REST endpoints and MCP tools

**Step 2: Verify docs reflect implementation**

Run a quick grep/check for:
- `delete-preview`
- `restore-preview`
- `confirm_token`
- `hidden_by_ancestor`
- `restore_`

Expected: all appear in docs where appropriate.

---

## Task 9: Final verification

**Objective:** Prove the implementation matches the plan and does not regress existing behavior.

**Files:**
- Review: all touched files
- Test: full suite

**Step 1: Run full test suite**

Run:
```sh
uv run pytest -q
```
Expected: all tests pass.

**Step 2: Review changed surface area**

Run:
```sh
git diff -- app/ tests/ README.md docs/
```
Expected: changes are limited to Epic A scope.

**Step 3: Review against locked decisions**

Confirm all are true:
- delete uses preview + confirm token
- restore exists
- no child cascade soft delete writes introduced
- effective visibility enforced across get/search/timeline/attachment paths
- docs updated

---

## Mandatory acceptance tests

At minimum, the final suite must prove all of these:

1. Delete preview returns confirm token and impact summary.
2. Delete without token fails.
3. Delete with invalid token fails.
4. Delete with valid token succeeds.
5. Restore preview returns confirm token and restore impact summary.
6. Restore with valid token succeeds.
7. Deleted pet hides medical records by default.
8. Deleted pet hides daily logs by default.
9. Deleted pet hides descendant attachments by default.
10. Deleted medical record hides its attachments by default.
11. `include_deleted=true` returns directly deleted and ancestor-hidden resources.
12. Restoring parent does not undelete children that were directly deleted.
13. Timeline obeys ancestor-aware visibility.
14. MCP tools support preview/delete/restore parity with REST.
15. README and docs describe the new contract accurately.

---

## Out of scope for Epic A v1

Do **not** add these unless required to satisfy the tests above:
- persistent token storage across process restarts
- audit trail/history tables
- hard delete
- bulk delete / bulk restore
- schema migration away from polymorphic attachments
- permissions/auth

---

## Suggested commit structure

1. `feat: add visibility metadata and ancestor-aware soft delete rules`
2. `feat: add delete and restore preview token flows`
3. `feat: expose delete/restore preview flows via REST and MCP`
4. `test: cover soft delete visibility and restore semantics`
5. `docs: document epic a delete visibility and restore contract`

---

## Final handoff note

Implementation is complete only when:
- plan file exists
- code is updated
- docs are updated
- tests pass
- final reviewer verifies the result matches the locked decisions above

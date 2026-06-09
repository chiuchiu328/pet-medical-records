---
name: pet-medical-records
description: Use when working with the pet medical records MCP service: creating pets, medical records, daily logs, attachments, timeline lookups, and status summaries. Use this skill to avoid mixing pet creation with medical-log creation and to follow the correct MCP workflow.
---

# Pet Medical Records

Use this skill when the task involves the `pet-medical-records` MCP tools.

## Resource guide

- Pet: basic profile for one animal. Use for identity and stable profile fields.
- Medical record: a clinic or treatment event. Use for diagnosis, prescription, hospital visit details, and visit-time weight.
- Daily log: day-to-day observations. Use for appetite, energy, stool, medication notes, symptoms, and home weight tracking.
- Media: files attached to either a medical record or a daily log. Use images or videos for blood tests, x-rays, ultrasound, prescriptions, daily condition photos, or notes.

## Core rules

- `create_pet` does not take `pet_id`. The database generates the pet id.
- `create_medical_record`, `create_daily_log`, and `get_pet_timeline` require an existing `pet_id`.
- `attach_media_to_medical_record` requires `record_id`.
- `attach_media_to_daily_log` requires `log_id`.
- Attachment tools use `file_path`; the file must be visible inside the runtime container.
- If the user asks to send an attached image back into chat, do not say you lack the tool. Fetch the attachment metadata and return a `MEDIA:` line.

## Safe workflow

1. If the pet does not exist, call `create_pet` first.
2. Save the returned `id`.
3. Use that id as `pet_id` for medical records, daily logs, timeline queries, and summaries.
4. If the user gives mixed data, split it by resource instead of forcing everything into `create_pet`.

## Field mapping

- Pet basics: `name`, `species`, `breed`, `sex`, `birth_date`, `microchip_number`, `notes`
- Medical record: `pet_id`, `visit_at`, `hospital_name`, `doctor_name`, `diagnosis`, `prescription`, `note`, `weight_value`, `weight_unit`, `tags`
- Daily log: `pet_id`, `logged_at`, `content`, `appetite`, `energy`, `stool`, `medication_note`, `weight_value`, `weight_unit`, `tags`

## Important limits

- `create_pet` does not currently store weight, coat color, neuter status, allergy history, or chronic disease as first-class pet fields.
- Put health history, medication, and symptom details into a medical record or daily log when needed.
- Use media categories intentionally: `blood_test`, `xray`, `ultrasound`, `prescription`, `note`, `daily`, `other`.
- If the user provides age instead of `birth_date`, ask for a date or clearly infer and state the assumption before writing.
- For attachments, prefer `local_file_path` for media return. `storage_path` is stored metadata and may be relative.

## Deletion rules

- Delete and restore use preview + confirm token.
- Call `*_preview` first, then pass `confirm_token` into the actual delete or restore tool.

## Image return format

- For an existing attachment image, final reply must include a standalone line:
  `MEDIA:<absolute_file_path>`
- Prefer absolute path in final output.
- Use attachment `local_file_path` directly when available.
- You may add one short sentence before or after the `MEDIA:` line.
- Do not reply with only prose like "photo is preserved" or "I cannot send images".

Example:

```text
這是剛剛那張照片。
MEDIA:/opt/data/pet-medical-records-data/uploads/daily_log/3/example.jpg
```

## Good behavior

- Prefer `list_pets` or `get_pet` before creating related records if pet identity is unclear.
- Reuse ids returned by tools; do not invent ids.
- If a required id is missing, stop and resolve it instead of guessing.
- When sending an existing attachment image to the user, fetch the attachment metadata first and use `local_file_path` in the `MEDIA:` line.

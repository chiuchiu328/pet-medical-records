from __future__ import annotations

import mimetypes
import secrets
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.config import Settings
from app.models import DailyLog, MediaAttachment, MedicalRecord, Pet, utc_now
from app.storage.local import copy_local_file, store_fileobj


class ResourceNotFound(Exception):
    pass


class InvalidRequest(Exception):
    pass


@dataclass(frozen=True)
class _PreviewToken:
    action: str
    resource_type: str
    resource_id: int
    expires_at: Any


_PREVIEW_TOKEN_TTL = timedelta(minutes=15)
_PREVIEW_TOKENS: dict[str, _PreviewToken] = {}


def _resource_identity(resource_type: str, resource_id: int) -> dict[str, Any]:
    return {"type": resource_type, "id": resource_id}


def _new_preview_token(
    *,
    action: str,
    resource_type: str,
    resource_id: int,
) -> tuple[str, Any]:
    token = secrets.token_urlsafe(32)
    expires_at = utc_now() + _PREVIEW_TOKEN_TTL
    _PREVIEW_TOKENS[token] = _PreviewToken(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        expires_at=expires_at,
    )
    return token, expires_at


def _consume_preview_token(
    token: str | None,
    *,
    action: str,
    resource_type: str,
    resource_id: int,
) -> None:
    if not token:
        raise InvalidRequest("confirm_token is required")
    payload = _PREVIEW_TOKENS.get(token)
    if payload is None:
        raise InvalidRequest("confirm_token is invalid or expired")
    if payload.expires_at <= utc_now():
        _PREVIEW_TOKENS.pop(token, None)
        raise InvalidRequest("confirm_token is invalid or expired")
    if (
        payload.action != action
        or payload.resource_type != resource_type
        or payload.resource_id != resource_id
    ):
        raise InvalidRequest("confirm_token does not match this action and resource")
    _PREVIEW_TOKENS.pop(token, None)


def _preview_response(
    *,
    action: str,
    resource_type: str,
    resource_id: int,
    summary: str,
    impact: dict[str, Any],
) -> schemas.PreviewTokenResponse:
    token, expires_at = _new_preview_token(
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    return schemas.PreviewTokenResponse(
        action=action,
        target=schemas.ResourceIdentity(type=resource_type, id=resource_id),
        summary=summary,
        impact=impact,
        confirm_token=token,
        expires_at=expires_at,
    )


def build_pet_visibility(pet: Pet) -> schemas.VisibilityInfo:
    return schemas.VisibilityInfo(
        deleted=pet.deleted_at is not None,
        hidden_by_ancestor=False,
        hidden_by=None,
    )


def build_medical_record_visibility(db: Session, record: MedicalRecord) -> schemas.VisibilityInfo:
    pet = db.get(Pet, record.pet_id)
    hidden_by = None
    if pet is None or pet.deleted_at is not None:
        hidden_by = _resource_identity("pet", record.pet_id)
    return schemas.VisibilityInfo(
        deleted=record.deleted_at is not None,
        hidden_by_ancestor=hidden_by is not None,
        hidden_by=hidden_by,
    )


def build_daily_log_visibility(db: Session, log: DailyLog) -> schemas.VisibilityInfo:
    pet = db.get(Pet, log.pet_id)
    hidden_by = None
    if pet is None or pet.deleted_at is not None:
        hidden_by = _resource_identity("pet", log.pet_id)
    return schemas.VisibilityInfo(
        deleted=log.deleted_at is not None,
        hidden_by_ancestor=hidden_by is not None,
        hidden_by=hidden_by,
    )


def build_attachment_visibility(db: Session, attachment: MediaAttachment) -> schemas.VisibilityInfo:
    hidden_by = None
    if attachment.owner_type == "medical_record":
        owner = db.get(MedicalRecord, attachment.owner_id)
        if owner is None:
            hidden_by = _resource_identity("medical_record", attachment.owner_id)
        elif owner.deleted_at is not None:
            hidden_by = _resource_identity("medical_record", owner.id)
        else:
            owner_visibility = build_medical_record_visibility(db, owner)
            hidden_by = owner_visibility.hidden_by if owner_visibility.hidden_by_ancestor else None
    elif attachment.owner_type == "daily_log":
        owner = db.get(DailyLog, attachment.owner_id)
        if owner is None:
            hidden_by = _resource_identity("daily_log", attachment.owner_id)
        elif owner.deleted_at is not None:
            hidden_by = _resource_identity("daily_log", owner.id)
        else:
            owner_visibility = build_daily_log_visibility(db, owner)
            hidden_by = owner_visibility.hidden_by if owner_visibility.hidden_by_ancestor else None
    else:
        hidden_by = _resource_identity(attachment.owner_type, attachment.owner_id)

    return schemas.VisibilityInfo(
        deleted=attachment.deleted_at is not None,
        hidden_by_ancestor=hidden_by is not None,
        hidden_by=hidden_by,
    )


def is_pet_effectively_visible(pet: Pet) -> bool:
    return pet.deleted_at is None


def is_medical_record_effectively_visible(db: Session, record: MedicalRecord) -> bool:
    visibility = build_medical_record_visibility(db, record)
    return not visibility.deleted and not visibility.hidden_by_ancestor


def is_daily_log_effectively_visible(db: Session, log: DailyLog) -> bool:
    visibility = build_daily_log_visibility(db, log)
    return not visibility.deleted and not visibility.hidden_by_ancestor


def is_attachment_effectively_visible(db: Session, attachment: MediaAttachment) -> bool:
    visibility = build_attachment_visibility(db, attachment)
    return not visibility.deleted and not visibility.hidden_by_ancestor


def _all_medical_records_for_pet(db: Session, pet_id: int) -> list[MedicalRecord]:
    return list(
        db.scalars(
            select(MedicalRecord)
            .where(MedicalRecord.pet_id == pet_id)
            .order_by(MedicalRecord.visit_at, MedicalRecord.id)
        ).all()
    )


def _all_daily_logs_for_pet(db: Session, pet_id: int) -> list[DailyLog]:
    return list(
        db.scalars(
            select(DailyLog).where(DailyLog.pet_id == pet_id).order_by(DailyLog.logged_at, DailyLog.id)
        ).all()
    )


def _all_attachments_for_owner(db: Session, owner_type: str, owner_id: int) -> list[MediaAttachment]:
    return list(
        db.scalars(
            select(MediaAttachment)
            .where(MediaAttachment.owner_type == owner_type, MediaAttachment.owner_id == owner_id)
            .order_by(MediaAttachment.created_at, MediaAttachment.id)
        ).all()
    )


def _apply_updates(instance: Any, payload: BaseModel) -> Any:
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(instance, key, value)
    instance.updated_at = utc_now()
    return instance


def _contains_keyword(parts: Iterable[Any], keyword: str | None) -> bool:
    if not keyword:
        return True
    lowered = keyword.casefold()
    return lowered in " ".join(str(part) for part in parts if part is not None).casefold()


def _sort_desc(sort: str | None, default_desc: bool = True) -> bool:
    if sort is None:
        return default_desc
    return sort in {"desc", "visit_at_desc", "logged_at_desc", "event_time_desc"} or sort.endswith("_desc")


def _paginate(items: list[Any], limit: int | None, page: int | None) -> list[Any]:
    if limit is None:
        limit = 100
    if limit < 1:
        raise InvalidRequest("limit must be greater than 0")
    if page is None:
        page = 1
    if page < 1:
        raise InvalidRequest("page must be greater than 0")
    start = (page - 1) * limit
    return items[start : start + limit]


def create_pet(db: Session, payload: schemas.PetCreate) -> Pet:
    pet = Pet(**payload.model_dump())
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


def list_pets(db: Session, *, keyword: str | None = None, include_deleted: bool = False) -> list[Pet]:
    stmt = select(Pet)
    if not include_deleted:
        stmt = stmt.where(Pet.deleted_at.is_(None))
    pets = list(db.scalars(stmt.order_by(Pet.name, Pet.id)).all())
    if keyword:
        pets = [
            pet
            for pet in pets
            if _contains_keyword(
                [pet.name, pet.species, pet.breed, pet.sex, pet.microchip_number, pet.notes],
                keyword,
            )
        ]
    return pets


def get_pet(db: Session, pet_id: int, *, include_deleted: bool = False) -> Pet:
    pet = db.get(Pet, pet_id)
    if pet is None or (pet.deleted_at is not None and not include_deleted):
        raise ResourceNotFound(f"Pet {pet_id} was not found")
    return pet


def update_pet(db: Session, pet_id: int, payload: schemas.PetUpdate) -> Pet:
    pet = get_pet(db, pet_id)
    _apply_updates(pet, payload)
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


def _pet_delete_impact(db: Session, pet_id: int) -> dict[str, Any]:
    records = _all_medical_records_for_pet(db, pet_id)
    logs = _all_daily_logs_for_pet(db, pet_id)
    visible_records = [record for record in records if record.deleted_at is None]
    visible_logs = [log for log in logs if log.deleted_at is None]
    visible_attachments = 0
    for record in visible_records:
        visible_attachments += sum(
            1
            for attachment in _all_attachments_for_owner(db, "medical_record", record.id)
            if attachment.deleted_at is None
        )
    for log in visible_logs:
        visible_attachments += sum(
            1
            for attachment in _all_attachments_for_owner(db, "daily_log", log.id)
            if attachment.deleted_at is None
        )
    return {
        "will_hide": {
            "medical_records": len(visible_records),
            "daily_logs": len(visible_logs),
            "attachments": visible_attachments,
        }
    }


def _pet_restore_impact(db: Session, pet: Pet) -> dict[str, Any]:
    records = _all_medical_records_for_pet(db, pet.id)
    logs = _all_daily_logs_for_pet(db, pet.id)
    pet_is_deleted = pet.deleted_at is not None
    restorable_records = [record for record in records if record.deleted_at is None]
    restorable_logs = [log for log in logs if log.deleted_at is None]
    hidden_records = [record for record in records if record.deleted_at is not None]
    hidden_logs = [log for log in logs if log.deleted_at is not None]
    restorable_attachments = 0
    hidden_attachments = 0
    for record in records:
        for attachment in _all_attachments_for_owner(db, "medical_record", record.id):
            if record.deleted_at is None and attachment.deleted_at is None:
                restorable_attachments += 1
            else:
                hidden_attachments += 1
    for log in logs:
        for attachment in _all_attachments_for_owner(db, "daily_log", log.id):
            if log.deleted_at is None and attachment.deleted_at is None:
                restorable_attachments += 1
            else:
                hidden_attachments += 1
    return {
        "will_restore": {
            "pet": 1 if pet_is_deleted else 0,
            "medical_records": len(restorable_records) if pet_is_deleted else 0,
            "daily_logs": len(restorable_logs) if pet_is_deleted else 0,
            "attachments": restorable_attachments if pet_is_deleted else 0,
        },
        "will_remain_hidden": {
            "medical_records": len(hidden_records),
            "daily_logs": len(hidden_logs),
            "attachments": hidden_attachments,
        },
    }


def build_delete_preview_pet(db: Session, pet_id: int) -> schemas.PreviewTokenResponse:
    get_pet(db, pet_id)
    return _preview_response(
        action="delete",
        resource_type="pet",
        resource_id=pet_id,
        summary="Deleting this pet will hide the pet and visible descendant records, logs, and attachments.",
        impact=_pet_delete_impact(db, pet_id),
    )


def build_restore_preview_pet(db: Session, pet_id: int) -> schemas.PreviewTokenResponse:
    pet = get_pet(db, pet_id, include_deleted=True)
    return _preview_response(
        action="restore",
        resource_type="pet",
        resource_id=pet_id,
        summary="Restoring this pet clears only the pet delete marker; directly deleted children stay deleted.",
        impact=_pet_restore_impact(db, pet),
    )


def delete_pet(
    db: Session,
    pet_id: int,
    reason: str | None = None,
    confirm_token: str | None = None,
) -> Pet:
    pet = get_pet(db, pet_id)
    _consume_preview_token(confirm_token, action="delete", resource_type="pet", resource_id=pet_id)
    pet.deleted_at = utc_now()
    pet.delete_reason = reason
    pet.updated_at = utc_now()
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


def restore_pet(db: Session, pet_id: int, confirm_token: str | None = None) -> Pet:
    pet = get_pet(db, pet_id, include_deleted=True)
    _consume_preview_token(confirm_token, action="restore", resource_type="pet", resource_id=pet_id)
    pet.deleted_at = None
    pet.delete_reason = None
    pet.updated_at = utc_now()
    db.add(pet)
    db.commit()
    db.refresh(pet)
    return pet


def create_medical_record(db: Session, pet_id: int, payload: schemas.MedicalRecordCreate) -> MedicalRecord:
    get_pet(db, pet_id)
    record = MedicalRecord(pet_id=pet_id, **payload.model_dump())
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_medical_record(db: Session, record_id: int, *, include_deleted: bool = False) -> MedicalRecord:
    record = db.get(MedicalRecord, record_id)
    if record is None or (not include_deleted and not is_medical_record_effectively_visible(db, record)):
        raise ResourceNotFound(f"Medical record {record_id} was not found")
    return record


def update_medical_record(db: Session, record_id: int, payload: schemas.MedicalRecordUpdate) -> MedicalRecord:
    record = get_medical_record(db, record_id)
    if payload.pet_id is not None:
        get_pet(db, payload.pet_id)
    _apply_updates(record, payload)
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def build_delete_preview_medical_record(
    db: Session,
    record_id: int,
) -> schemas.PreviewTokenResponse:
    record = get_medical_record(db, record_id)
    attachments = [
        attachment
        for attachment in _all_attachments_for_owner(db, "medical_record", record.id)
        if attachment.deleted_at is None
    ]
    return _preview_response(
        action="delete",
        resource_type="medical_record",
        resource_id=record_id,
        summary="Deleting this medical record will hide the record and visible attachments.",
        impact={"will_hide": {"attachments": len(attachments)}},
    )


def build_restore_preview_medical_record(
    db: Session,
    record_id: int,
) -> schemas.PreviewTokenResponse:
    record = get_medical_record(db, record_id, include_deleted=True)
    visibility = build_medical_record_visibility(db, record)
    owner_visible_after_restore = not visibility.hidden_by_ancestor
    attachments = _all_attachments_for_owner(db, "medical_record", record.id)
    restorable_attachments = [
        attachment for attachment in attachments if attachment.deleted_at is None and owner_visible_after_restore
    ]
    hidden_attachments = [attachment for attachment in attachments if attachment.deleted_at is not None]
    return _preview_response(
        action="restore",
        resource_type="medical_record",
        resource_id=record_id,
        summary="Restoring this medical record clears only the record delete marker.",
        impact={
            "will_restore": {
                "medical_records": 1 if record.deleted_at is not None and owner_visible_after_restore else 0,
                "attachments": len(restorable_attachments) if record.deleted_at is not None else 0,
            },
            "will_remain_hidden": {"attachments": len(hidden_attachments)},
        },
    )


def delete_medical_record(
    db: Session,
    record_id: int,
    reason: str | None = None,
    confirm_token: str | None = None,
) -> MedicalRecord:
    record = get_medical_record(db, record_id)
    _consume_preview_token(
        confirm_token,
        action="delete",
        resource_type="medical_record",
        resource_id=record_id,
    )
    record.deleted_at = utc_now()
    record.delete_reason = reason
    record.updated_at = utc_now()
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def restore_medical_record(
    db: Session,
    record_id: int,
    confirm_token: str | None = None,
) -> MedicalRecord:
    record = get_medical_record(db, record_id, include_deleted=True)
    _consume_preview_token(
        confirm_token,
        action="restore",
        resource_type="medical_record",
        resource_id=record_id,
    )
    record.deleted_at = None
    record.delete_reason = None
    record.updated_at = utc_now()
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def create_daily_log(db: Session, pet_id: int, payload: schemas.DailyLogCreate) -> DailyLog:
    get_pet(db, pet_id)
    log = DailyLog(pet_id=pet_id, **payload.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_daily_log(db: Session, log_id: int, *, include_deleted: bool = False) -> DailyLog:
    log = db.get(DailyLog, log_id)
    if log is None or (not include_deleted and not is_daily_log_effectively_visible(db, log)):
        raise ResourceNotFound(f"Daily log {log_id} was not found")
    return log


def update_daily_log(db: Session, log_id: int, payload: schemas.DailyLogUpdate) -> DailyLog:
    log = get_daily_log(db, log_id)
    if payload.pet_id is not None:
        get_pet(db, payload.pet_id)
    _apply_updates(log, payload)
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def build_delete_preview_daily_log(db: Session, log_id: int) -> schemas.PreviewTokenResponse:
    log = get_daily_log(db, log_id)
    attachments = [
        attachment
        for attachment in _all_attachments_for_owner(db, "daily_log", log.id)
        if attachment.deleted_at is None
    ]
    return _preview_response(
        action="delete",
        resource_type="daily_log",
        resource_id=log_id,
        summary="Deleting this daily log will hide the log and visible attachments.",
        impact={"will_hide": {"attachments": len(attachments)}},
    )


def build_restore_preview_daily_log(db: Session, log_id: int) -> schemas.PreviewTokenResponse:
    log = get_daily_log(db, log_id, include_deleted=True)
    visibility = build_daily_log_visibility(db, log)
    owner_visible_after_restore = not visibility.hidden_by_ancestor
    attachments = _all_attachments_for_owner(db, "daily_log", log.id)
    restorable_attachments = [
        attachment for attachment in attachments if attachment.deleted_at is None and owner_visible_after_restore
    ]
    hidden_attachments = [attachment for attachment in attachments if attachment.deleted_at is not None]
    return _preview_response(
        action="restore",
        resource_type="daily_log",
        resource_id=log_id,
        summary="Restoring this daily log clears only the log delete marker.",
        impact={
            "will_restore": {
                "daily_logs": 1 if log.deleted_at is not None and owner_visible_after_restore else 0,
                "attachments": len(restorable_attachments) if log.deleted_at is not None else 0,
            },
            "will_remain_hidden": {"attachments": len(hidden_attachments)},
        },
    )


def delete_daily_log(
    db: Session,
    log_id: int,
    reason: str | None = None,
    confirm_token: str | None = None,
) -> DailyLog:
    log = get_daily_log(db, log_id)
    _consume_preview_token(confirm_token, action="delete", resource_type="daily_log", resource_id=log_id)
    log.deleted_at = utc_now()
    log.delete_reason = reason
    log.updated_at = utc_now()
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def restore_daily_log(
    db: Session,
    log_id: int,
    confirm_token: str | None = None,
) -> DailyLog:
    log = get_daily_log(db, log_id, include_deleted=True)
    _consume_preview_token(confirm_token, action="restore", resource_type="daily_log", resource_id=log_id)
    log.deleted_at = None
    log.delete_reason = None
    log.updated_at = utc_now()
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def get_attachment(db: Session, attachment_id: int, *, include_deleted: bool = False) -> MediaAttachment:
    attachment = db.get(MediaAttachment, attachment_id)
    if attachment is None or (not include_deleted and not is_attachment_effectively_visible(db, attachment)):
        raise ResourceNotFound(f"Attachment {attachment_id} was not found")
    return attachment


def list_attachments_for_owner(
    db: Session,
    owner_type: str,
    owner_id: int,
    *,
    include_deleted: bool = False,
) -> list[MediaAttachment]:
    stmt = (
        select(MediaAttachment)
        .where(MediaAttachment.owner_type == owner_type, MediaAttachment.owner_id == owner_id)
        .order_by(MediaAttachment.created_at, MediaAttachment.id)
    )
    attachments = list(db.scalars(stmt).all())
    if include_deleted:
        return attachments
    return [
        attachment
        for attachment in attachments
        if is_attachment_effectively_visible(db, attachment)
    ]


def _ensure_owner(db: Session, owner_type: str, owner_id: int) -> None:
    if owner_type == "medical_record":
        get_medical_record(db, owner_id)
    elif owner_type == "daily_log":
        get_daily_log(db, owner_id)
    else:
        raise InvalidRequest(f"Unsupported attachment owner_type: {owner_type}")


def _normalized_ocr_status(payload: schemas.AttachmentCreate | schemas.AttachmentUpdate) -> str:
    status = getattr(payload, "ocr_status", None)
    if status and not (status == "none" and getattr(payload, "extracted_text", None)):
        return status
    if getattr(payload, "extracted_text", None):
        return "manual"
    return status or "none"


def create_attachment_from_fileobj(
    db: Session,
    settings: Settings,
    *,
    owner_type: str,
    owner_id: int,
    file_name: str,
    fileobj,
    mime_type: str | None,
    payload: schemas.AttachmentCreate,
) -> MediaAttachment:
    _ensure_owner(db, owner_type, owner_id)
    stored_path = store_fileobj(settings.upload_dir, owner_type, owner_id, file_name, fileobj)
    attachment = MediaAttachment(
        owner_type=owner_type,
        owner_id=owner_id,
        file_name=stored_path.name,
        storage_path=str(stored_path),
        mime_type=mime_type or mimetypes.guess_type(file_name)[0] or "application/octet-stream",
        media_type=payload.media_type,
        category=payload.category,
        captured_at=payload.captured_at,
        extracted_text=payload.extracted_text,
        ocr_status=_normalized_ocr_status(payload),
        note=payload.note,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def create_attachment_from_path(
    db: Session,
    settings: Settings,
    *,
    owner_type: str,
    owner_id: int,
    source_path: Path,
    payload: schemas.AttachmentCreate,
) -> MediaAttachment:
    _ensure_owner(db, owner_type, owner_id)
    stored_path = copy_local_file(settings.upload_dir, owner_type, owner_id, source_path)
    attachment = MediaAttachment(
        owner_type=owner_type,
        owner_id=owner_id,
        file_name=stored_path.name,
        storage_path=str(stored_path),
        mime_type=mimetypes.guess_type(source_path.name)[0] or "application/octet-stream",
        media_type=payload.media_type,
        category=payload.category,
        captured_at=payload.captured_at,
        extracted_text=payload.extracted_text,
        ocr_status=_normalized_ocr_status(payload),
        note=payload.note,
    )
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def update_attachment(db: Session, attachment_id: int, payload: schemas.AttachmentUpdate) -> MediaAttachment:
    attachment = get_attachment(db, attachment_id)
    updates = payload.model_dump(exclude_unset=True)
    if "ocr_status" not in updates and updates.get("extracted_text"):
        updates["ocr_status"] = "manual"
    for key, value in updates.items():
        setattr(attachment, key, value)
    attachment.updated_at = utc_now()
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def build_delete_preview_attachment(
    db: Session,
    attachment_id: int,
) -> schemas.PreviewTokenResponse:
    get_attachment(db, attachment_id)
    return _preview_response(
        action="delete",
        resource_type="attachment",
        resource_id=attachment_id,
        summary="Deleting this attachment will hide only the attachment.",
        impact={"will_hide": {}},
    )


def build_restore_preview_attachment(
    db: Session,
    attachment_id: int,
) -> schemas.PreviewTokenResponse:
    attachment = get_attachment(db, attachment_id, include_deleted=True)
    visibility = build_attachment_visibility(db, attachment)
    owner_visible_after_restore = not visibility.hidden_by_ancestor
    return _preview_response(
        action="restore",
        resource_type="attachment",
        resource_id=attachment_id,
        summary="Restoring this attachment clears only the attachment delete marker.",
        impact={
            "will_restore": {
                "attachments": 1
                if attachment.deleted_at is not None and owner_visible_after_restore
                else 0
            },
            "will_remain_hidden": {
                "attachments": 1
                if attachment.deleted_at is not None and not owner_visible_after_restore
                else 0
            },
        },
    )


def delete_attachment(
    db: Session,
    attachment_id: int,
    reason: str | None = None,
    confirm_token: str | None = None,
) -> MediaAttachment:
    attachment = get_attachment(db, attachment_id)
    _consume_preview_token(
        confirm_token,
        action="delete",
        resource_type="attachment",
        resource_id=attachment_id,
    )
    attachment.deleted_at = utc_now()
    attachment.delete_reason = reason
    attachment.updated_at = utc_now()
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def restore_attachment(
    db: Session,
    attachment_id: int,
    confirm_token: str | None = None,
) -> MediaAttachment:
    attachment = get_attachment(db, attachment_id, include_deleted=True)
    _consume_preview_token(
        confirm_token,
        action="restore",
        resource_type="attachment",
        resource_id=attachment_id,
    )
    attachment.deleted_at = None
    attachment.delete_reason = None
    attachment.updated_at = utc_now()
    db.add(attachment)
    db.commit()
    db.refresh(attachment)
    return attachment


def _attachment_parts(attachments: list[MediaAttachment]) -> list[Any]:
    parts: list[Any] = []
    for attachment in attachments:
        parts.extend(
            [
                attachment.category,
                attachment.media_type,
                attachment.file_name,
                attachment.mime_type,
                attachment.extracted_text,
                attachment.note,
            ]
        )
    return parts


def _record_matches(
    db: Session,
    record: MedicalRecord,
    *,
    keyword: str | None,
    tag: str | None,
    category: str | None,
    include_deleted: bool,
) -> bool:
    attachments = list_attachments_for_owner(
        db,
        "medical_record",
        record.id,
        include_deleted=include_deleted,
    )
    if tag and tag not in (record.tags or []):
        return False
    if category and not any(attachment.category == category for attachment in attachments):
        return False
    return _contains_keyword(
        [
            record.hospital_name,
            record.doctor_name,
            record.diagnosis,
            record.prescription,
            record.note,
            record.weight_value,
            record.weight_unit,
            *(record.tags or []),
            *_attachment_parts(attachments),
        ],
        keyword,
    )


def search_medical_records(
    db: Session,
    *,
    pet_id: int,
    start: Any = None,
    end: Any = None,
    keyword: str | None = None,
    tag: str | None = None,
    category: str | None = None,
    include_deleted: bool = False,
    sort: str | None = "visit_at_desc",
    limit: int | None = 100,
    page: int | None = 1,
) -> list[MedicalRecord]:
    pet = get_pet(db, pet_id, include_deleted=True)
    if not include_deleted and not is_pet_effectively_visible(pet):
        return []
    stmt = select(MedicalRecord).where(MedicalRecord.pet_id == pet_id)
    if not include_deleted:
        stmt = stmt.where(MedicalRecord.deleted_at.is_(None))
    if start is not None:
        stmt = stmt.where(MedicalRecord.visit_at >= start)
    if end is not None:
        stmt = stmt.where(MedicalRecord.visit_at <= end)
    records = list(db.scalars(stmt).all())
    if not include_deleted:
        records = [record for record in records if is_medical_record_effectively_visible(db, record)]
    records = [
        record
        for record in records
        if _record_matches(
            db,
            record,
            keyword=keyword,
            tag=tag,
            category=category,
            include_deleted=include_deleted,
        )
    ]
    records.sort(key=lambda record: (record.visit_at, record.id), reverse=_sort_desc(sort))
    return _paginate(records, limit, page)


def _log_matches(
    db: Session,
    log: DailyLog,
    *,
    keyword: str | None,
    tag: str | None,
    appetite: str | None,
    energy: str | None,
    category: str | None,
    include_deleted: bool,
) -> bool:
    attachments = list_attachments_for_owner(db, "daily_log", log.id, include_deleted=include_deleted)
    if tag and tag not in (log.tags or []):
        return False
    if appetite and log.appetite != appetite:
        return False
    if energy and log.energy != energy:
        return False
    if category and not any(attachment.category == category for attachment in attachments):
        return False
    return _contains_keyword(
        [
            log.content,
            log.appetite,
            log.energy,
            log.stool,
            log.medication_note,
            log.weight_value,
            log.weight_unit,
            *(log.tags or []),
            *_attachment_parts(attachments),
        ],
        keyword,
    )


def search_daily_logs(
    db: Session,
    *,
    pet_id: int,
    start: Any = None,
    end: Any = None,
    keyword: str | None = None,
    tag: str | None = None,
    appetite: str | None = None,
    energy: str | None = None,
    category: str | None = None,
    include_deleted: bool = False,
    sort: str | None = "logged_at_desc",
    limit: int | None = 100,
    page: int | None = 1,
) -> list[DailyLog]:
    pet = get_pet(db, pet_id, include_deleted=True)
    if not include_deleted and not is_pet_effectively_visible(pet):
        return []
    stmt = select(DailyLog).where(DailyLog.pet_id == pet_id)
    if not include_deleted:
        stmt = stmt.where(DailyLog.deleted_at.is_(None))
    if start is not None:
        stmt = stmt.where(DailyLog.logged_at >= start)
    if end is not None:
        stmt = stmt.where(DailyLog.logged_at <= end)
    logs = list(db.scalars(stmt).all())
    if not include_deleted:
        logs = [log for log in logs if is_daily_log_effectively_visible(db, log)]
    logs = [
        log
        for log in logs
        if _log_matches(
            db,
            log,
            keyword=keyword,
            tag=tag,
            appetite=appetite,
            energy=energy,
            category=category,
            include_deleted=include_deleted,
        )
    ]
    logs.sort(key=lambda log: (log.logged_at, log.id), reverse=_sort_desc(sort))
    return _paginate(logs, limit, page)


def pet_to_read(pet: Pet) -> schemas.PetRead:
    data = schemas.PetRead.model_validate(pet).model_dump()
    data["visibility"] = build_pet_visibility(pet)
    return schemas.PetRead(**data)


def attachment_to_read(
    attachment: MediaAttachment,
    db: Session | None = None,
) -> schemas.MediaAttachmentRead:
    data = schemas.MediaAttachmentRead.model_validate(attachment).model_dump()
    if db is None:
        visibility = schemas.VisibilityInfo(deleted=attachment.deleted_at is not None)
    else:
        visibility = build_attachment_visibility(db, attachment)
    data["visibility"] = visibility
    return schemas.MediaAttachmentRead(**data)


def medical_record_to_read(
    db: Session,
    record: MedicalRecord,
    *,
    include_deleted_attachments: bool = False,
) -> schemas.MedicalRecordRead:
    data = schemas.MedicalRecordRead.model_validate(record).model_dump()
    data["visibility"] = build_medical_record_visibility(db, record)
    data["attachments"] = [
        attachment_to_read(attachment, db)
        for attachment in list_attachments_for_owner(
            db,
            "medical_record",
            record.id,
            include_deleted=include_deleted_attachments,
        )
    ]
    return schemas.MedicalRecordRead(**data)


def daily_log_to_read(
    db: Session,
    log: DailyLog,
    *,
    include_deleted_attachments: bool = False,
) -> schemas.DailyLogRead:
    data = schemas.DailyLogRead.model_validate(log).model_dump()
    data["visibility"] = build_daily_log_visibility(db, log)
    data["attachments"] = [
        attachment_to_read(attachment, db)
        for attachment in list_attachments_for_owner(
            db,
            "daily_log",
            log.id,
            include_deleted=include_deleted_attachments,
        )
    ]
    return schemas.DailyLogRead(**data)


def _medical_summary(record: MedicalRecord) -> str:
    return " | ".join(
        part
        for part in [
            record.diagnosis,
            record.prescription,
            record.note,
            f"{record.weight_value:g}{record.weight_unit or ''}" if record.weight_value is not None else None,
        ]
        if part
    )


def _daily_summary(log: DailyLog) -> str:
    return " | ".join(
        part
        for part in [
            log.content,
            f"appetite={log.appetite}" if log.appetite else None,
            f"energy={log.energy}" if log.energy else None,
            log.medication_note,
            f"{log.weight_value:g}{log.weight_unit or ''}" if log.weight_value is not None else None,
        ]
        if part
    )


def get_pet_timeline(
    db: Session,
    *,
    pet_id: int,
    start: Any = None,
    end: Any = None,
    keyword: str | None = None,
    event_type: str = "all",
    category: str | None = None,
    include_deleted: bool = False,
    sort: str = "desc",
    limit: int | None = 100,
    page: int | None = 1,
) -> list[schemas.TimelineEventRead]:
    if event_type not in {"all", "medical", "daily"}:
        raise InvalidRequest("event_type must be one of all, medical, daily")

    events: list[schemas.TimelineEventRead] = []

    if event_type in {"all", "medical"}:
        records = search_medical_records(
            db,
            pet_id=pet_id,
            start=start,
            end=end,
            keyword=keyword,
            category=category,
            include_deleted=include_deleted,
            sort="visit_at_desc",
            limit=10_000,
            page=1,
        )
        for record in records:
            read_model = medical_record_to_read(
                db,
                record,
                include_deleted_attachments=include_deleted,
            )
            events.append(
                schemas.TimelineEventRead(
                    event_type="medical",
                    event_time=record.visit_at,
                    pet_id=record.pet_id,
                    source_id=record.id,
                    summary_text=_medical_summary(record),
                    tags=record.tags or [],
                    attachments=read_model.attachments,
                    data=read_model.model_dump(mode="json"),
                )
            )

    if event_type in {"all", "daily"}:
        logs = search_daily_logs(
            db,
            pet_id=pet_id,
            start=start,
            end=end,
            keyword=keyword,
            category=category,
            include_deleted=include_deleted,
            sort="logged_at_desc",
            limit=10_000,
            page=1,
        )
        for log in logs:
            read_model = daily_log_to_read(db, log, include_deleted_attachments=include_deleted)
            events.append(
                schemas.TimelineEventRead(
                    event_type="daily",
                    event_time=log.logged_at,
                    pet_id=log.pet_id,
                    source_id=log.id,
                    summary_text=_daily_summary(log),
                    tags=log.tags or [],
                    attachments=read_model.attachments,
                    data=read_model.model_dump(mode="json"),
                )
            )

    events.sort(key=lambda event: (event.event_time, event.source_id), reverse=_sort_desc(sort))
    return _paginate(events, limit, page)


def summarize_pet_status(
    db: Session,
    *,
    pet_id: int,
    start: Any = None,
    end: Any = None,
    include_deleted: bool = False,
) -> dict[str, Any]:
    pet = get_pet(db, pet_id, include_deleted=include_deleted)
    events = get_pet_timeline(
        db,
        pet_id=pet_id,
        start=start,
        end=end,
        include_deleted=include_deleted,
        limit=10_000,
        page=1,
    )
    weights: list[dict[str, Any]] = []
    medication_notes: list[str] = []
    appetite_values: list[str] = []
    energy_values: list[str] = []
    for event in events:
        data = event.data
        if data.get("weight_value") is not None:
            weights.append(
                {
                    "event_time": event.event_time,
                    "value": data["weight_value"],
                    "unit": data.get("weight_unit"),
                    "source": event.event_type,
                    "source_id": event.source_id,
                }
            )
        if data.get("medication_note"):
            medication_notes.append(data["medication_note"])
        if data.get("prescription"):
            medication_notes.append(data["prescription"])
        if data.get("appetite"):
            appetite_values.append(data["appetite"])
        if data.get("energy"):
            energy_values.append(data["energy"])

    return {
        "pet": pet_to_read(pet).model_dump(mode="json"),
        "event_count": len(events),
        "medical_record_count": sum(1 for event in events if event.event_type == "medical"),
        "daily_log_count": sum(1 for event in events if event.event_type == "daily"),
        "latest_weight": weights[0] if weights else None,
        "weights": weights,
        "medication_notes": medication_notes,
        "appetite_values": appetite_values,
        "energy_values": energy_values,
    }

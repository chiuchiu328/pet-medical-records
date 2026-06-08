from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Body, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app import schemas, services
from app.config import Settings
from app.dependencies import get_db, get_settings

router = APIRouter()


@router.post("/pets", response_model=schemas.PetRead, status_code=201)
def create_pet(payload: schemas.PetCreate, db: Session = Depends(get_db)) -> schemas.PetRead:
    return services.pet_to_read(services.create_pet(db, payload))


@router.get("/pets", response_model=list[schemas.PetRead])
def list_pets(
    keyword: str | None = None,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
) -> list[schemas.PetRead]:
    return [
        services.pet_to_read(pet)
        for pet in services.list_pets(db, keyword=keyword, include_deleted=include_deleted)
    ]


@router.get("/pets/{pet_id}", response_model=schemas.PetRead)
def get_pet(
    pet_id: int,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
) -> schemas.PetRead:
    return services.pet_to_read(services.get_pet(db, pet_id, include_deleted=include_deleted))


@router.patch("/pets/{pet_id}", response_model=schemas.PetRead)
def update_pet(
    pet_id: int,
    payload: schemas.PetUpdate,
    db: Session = Depends(get_db),
) -> schemas.PetRead:
    return services.pet_to_read(services.update_pet(db, pet_id, payload))


@router.delete("/pets/{pet_id}", response_model=schemas.PetRead)
def delete_pet(
    pet_id: int,
    payload: Annotated[schemas.DeleteConfirmRequest | None, Body()] = None,
    db: Session = Depends(get_db),
) -> schemas.PetRead:
    return services.pet_to_read(
        services.delete_pet(
            db,
            pet_id,
            payload.reason if payload else None,
            payload.confirm_token if payload else None,
        )
    )


@router.post("/pets/{pet_id}/delete-preview", response_model=schemas.PreviewTokenResponse)
def delete_pet_preview(
    pet_id: int,
    db: Session = Depends(get_db),
) -> schemas.PreviewTokenResponse:
    return services.build_delete_preview_pet(db, pet_id)


@router.post("/pets/{pet_id}/restore-preview", response_model=schemas.PreviewTokenResponse)
def restore_pet_preview(
    pet_id: int,
    db: Session = Depends(get_db),
) -> schemas.PreviewTokenResponse:
    return services.build_restore_preview_pet(db, pet_id)


@router.post("/pets/{pet_id}/restore", response_model=schemas.PetRead)
def restore_pet(
    pet_id: int,
    payload: schemas.RestoreConfirmRequest,
    db: Session = Depends(get_db),
) -> schemas.PetRead:
    return services.pet_to_read(services.restore_pet(db, pet_id, payload.confirm_token))


@router.post(
    "/pets/{pet_id}/medical-records",
    response_model=schemas.MedicalRecordRead,
    status_code=201,
)
def create_medical_record(
    pet_id: int,
    payload: schemas.MedicalRecordCreate,
    db: Session = Depends(get_db),
) -> schemas.MedicalRecordRead:
    record = services.create_medical_record(db, pet_id, payload)
    return services.medical_record_to_read(db, record)


@router.get("/pets/{pet_id}/medical-records", response_model=list[schemas.MedicalRecordRead])
def search_medical_records(
    pet_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
    keyword: str | None = None,
    tag: str | None = None,
    category: schemas.AttachmentCategory | None = None,
    include_deleted: bool = False,
    sort: str = "visit_at_desc",
    limit: int | None = 100,
    page: int | None = 1,
    db: Session = Depends(get_db),
) -> list[schemas.MedicalRecordRead]:
    records = services.search_medical_records(
        db,
        pet_id=pet_id,
        start=start,
        end=end,
        keyword=keyword,
        tag=tag,
        category=category,
        include_deleted=include_deleted,
        sort=sort,
        limit=limit,
        page=page,
    )
    return [
        services.medical_record_to_read(
            db,
            record,
            include_deleted_attachments=include_deleted,
        )
        for record in records
    ]


@router.get("/medical-records/{record_id}", response_model=schemas.MedicalRecordRead)
def get_medical_record(
    record_id: int,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
) -> schemas.MedicalRecordRead:
    record = services.get_medical_record(db, record_id, include_deleted=include_deleted)
    return services.medical_record_to_read(
        db,
        record,
        include_deleted_attachments=include_deleted,
    )


@router.patch("/medical-records/{record_id}", response_model=schemas.MedicalRecordRead)
def update_medical_record(
    record_id: int,
    payload: schemas.MedicalRecordUpdate,
    db: Session = Depends(get_db),
) -> schemas.MedicalRecordRead:
    record = services.update_medical_record(db, record_id, payload)
    return services.medical_record_to_read(db, record)


@router.delete("/medical-records/{record_id}", response_model=schemas.MedicalRecordRead)
def delete_medical_record(
    record_id: int,
    payload: Annotated[schemas.DeleteConfirmRequest | None, Body()] = None,
    db: Session = Depends(get_db),
) -> schemas.MedicalRecordRead:
    record = services.delete_medical_record(
        db,
        record_id,
        payload.reason if payload else None,
        payload.confirm_token if payload else None,
    )
    return services.medical_record_to_read(db, record)


@router.post(
    "/medical-records/{record_id}/delete-preview",
    response_model=schemas.PreviewTokenResponse,
)
def delete_medical_record_preview(
    record_id: int,
    db: Session = Depends(get_db),
) -> schemas.PreviewTokenResponse:
    return services.build_delete_preview_medical_record(db, record_id)


@router.post(
    "/medical-records/{record_id}/restore-preview",
    response_model=schemas.PreviewTokenResponse,
)
def restore_medical_record_preview(
    record_id: int,
    db: Session = Depends(get_db),
) -> schemas.PreviewTokenResponse:
    return services.build_restore_preview_medical_record(db, record_id)


@router.post("/medical-records/{record_id}/restore", response_model=schemas.MedicalRecordRead)
def restore_medical_record(
    record_id: int,
    payload: schemas.RestoreConfirmRequest,
    db: Session = Depends(get_db),
) -> schemas.MedicalRecordRead:
    record = services.restore_medical_record(db, record_id, payload.confirm_token)
    return services.medical_record_to_read(db, record)


@router.post("/pets/{pet_id}/daily-logs", response_model=schemas.DailyLogRead, status_code=201)
def create_daily_log(
    pet_id: int,
    payload: schemas.DailyLogCreate,
    db: Session = Depends(get_db),
) -> schemas.DailyLogRead:
    log = services.create_daily_log(db, pet_id, payload)
    return services.daily_log_to_read(db, log)


@router.get("/pets/{pet_id}/daily-logs", response_model=list[schemas.DailyLogRead])
def search_daily_logs(
    pet_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
    keyword: str | None = None,
    tag: str | None = None,
    appetite: schemas.Appetite | None = None,
    energy: schemas.Energy | None = None,
    category: schemas.AttachmentCategory | None = None,
    include_deleted: bool = False,
    sort: str = "logged_at_desc",
    limit: int | None = 100,
    page: int | None = 1,
    db: Session = Depends(get_db),
) -> list[schemas.DailyLogRead]:
    logs = services.search_daily_logs(
        db,
        pet_id=pet_id,
        start=start,
        end=end,
        keyword=keyword,
        tag=tag,
        appetite=appetite,
        energy=energy,
        category=category,
        include_deleted=include_deleted,
        sort=sort,
        limit=limit,
        page=page,
    )
    return [
        services.daily_log_to_read(
            db,
            log,
            include_deleted_attachments=include_deleted,
        )
        for log in logs
    ]


@router.get("/daily-logs/{log_id}", response_model=schemas.DailyLogRead)
def get_daily_log(
    log_id: int,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
) -> schemas.DailyLogRead:
    log = services.get_daily_log(db, log_id, include_deleted=include_deleted)
    return services.daily_log_to_read(db, log, include_deleted_attachments=include_deleted)


@router.patch("/daily-logs/{log_id}", response_model=schemas.DailyLogRead)
def update_daily_log(
    log_id: int,
    payload: schemas.DailyLogUpdate,
    db: Session = Depends(get_db),
) -> schemas.DailyLogRead:
    log = services.update_daily_log(db, log_id, payload)
    return services.daily_log_to_read(db, log)


@router.delete("/daily-logs/{log_id}", response_model=schemas.DailyLogRead)
def delete_daily_log(
    log_id: int,
    payload: Annotated[schemas.DeleteConfirmRequest | None, Body()] = None,
    db: Session = Depends(get_db),
) -> schemas.DailyLogRead:
    log = services.delete_daily_log(
        db,
        log_id,
        payload.reason if payload else None,
        payload.confirm_token if payload else None,
    )
    return services.daily_log_to_read(db, log)


@router.post("/daily-logs/{log_id}/delete-preview", response_model=schemas.PreviewTokenResponse)
def delete_daily_log_preview(
    log_id: int,
    db: Session = Depends(get_db),
) -> schemas.PreviewTokenResponse:
    return services.build_delete_preview_daily_log(db, log_id)


@router.post("/daily-logs/{log_id}/restore-preview", response_model=schemas.PreviewTokenResponse)
def restore_daily_log_preview(
    log_id: int,
    db: Session = Depends(get_db),
) -> schemas.PreviewTokenResponse:
    return services.build_restore_preview_daily_log(db, log_id)


@router.post("/daily-logs/{log_id}/restore", response_model=schemas.DailyLogRead)
def restore_daily_log(
    log_id: int,
    payload: schemas.RestoreConfirmRequest,
    db: Session = Depends(get_db),
) -> schemas.DailyLogRead:
    log = services.restore_daily_log(db, log_id, payload.confirm_token)
    return services.daily_log_to_read(db, log)


def _attachment_payload(
    *,
    media_type: schemas.MediaType,
    category: schemas.AttachmentCategory,
    captured_at: datetime | None,
    extracted_text: str | None,
    ocr_status: schemas.OcrStatus | None,
    note: str | None,
) -> schemas.AttachmentCreate:
    return schemas.AttachmentCreate(
        media_type=media_type,
        category=category,
        captured_at=captured_at,
        extracted_text=extracted_text,
        ocr_status=ocr_status or ("manual" if extracted_text else "none"),
        note=note,
    )


@router.post(
    "/medical-records/{record_id}/attachments",
    response_model=schemas.MediaAttachmentRead,
    status_code=201,
)
def attach_media_to_medical_record(
    record_id: int,
    file: UploadFile = File(...),
    media_type: schemas.MediaType = Form(...),
    category: schemas.AttachmentCategory = Form(...),
    captured_at: datetime | None = Form(None),
    extracted_text: str | None = Form(None),
    ocr_status: schemas.OcrStatus | None = Form(None),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.MediaAttachmentRead:
    attachment = services.create_attachment_from_fileobj(
        db,
        settings,
        owner_type="medical_record",
        owner_id=record_id,
        file_name=file.filename or "upload",
        fileobj=file.file,
        mime_type=file.content_type,
        payload=_attachment_payload(
            media_type=media_type,
            category=category,
            captured_at=captured_at,
            extracted_text=extracted_text,
            ocr_status=ocr_status,
            note=note,
        ),
    )
    return services.attachment_to_read(attachment, db)


@router.post(
    "/daily-logs/{log_id}/attachments",
    response_model=schemas.MediaAttachmentRead,
    status_code=201,
)
def attach_media_to_daily_log(
    log_id: int,
    file: UploadFile = File(...),
    media_type: schemas.MediaType = Form(...),
    category: schemas.AttachmentCategory = Form(...),
    captured_at: datetime | None = Form(None),
    extracted_text: str | None = Form(None),
    ocr_status: schemas.OcrStatus | None = Form(None),
    note: str | None = Form(None),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> schemas.MediaAttachmentRead:
    attachment = services.create_attachment_from_fileobj(
        db,
        settings,
        owner_type="daily_log",
        owner_id=log_id,
        file_name=file.filename or "upload",
        fileobj=file.file,
        mime_type=file.content_type,
        payload=_attachment_payload(
            media_type=media_type,
            category=category,
            captured_at=captured_at,
            extracted_text=extracted_text,
            ocr_status=ocr_status,
            note=note,
        ),
    )
    return services.attachment_to_read(attachment, db)


@router.get("/attachments/{attachment_id}", response_model=schemas.MediaAttachmentRead)
def get_attachment(
    attachment_id: int,
    include_deleted: bool = False,
    db: Session = Depends(get_db),
) -> schemas.MediaAttachmentRead:
    return services.attachment_to_read(
        services.get_attachment(db, attachment_id, include_deleted=include_deleted),
        db,
    )


@router.patch("/attachments/{attachment_id}", response_model=schemas.MediaAttachmentRead)
def update_attachment(
    attachment_id: int,
    payload: schemas.AttachmentUpdate,
    db: Session = Depends(get_db),
) -> schemas.MediaAttachmentRead:
    return services.attachment_to_read(services.update_attachment(db, attachment_id, payload), db)


@router.delete("/attachments/{attachment_id}", response_model=schemas.MediaAttachmentRead)
def delete_attachment(
    attachment_id: int,
    payload: Annotated[schemas.DeleteConfirmRequest | None, Body()] = None,
    db: Session = Depends(get_db),
) -> schemas.MediaAttachmentRead:
    return services.attachment_to_read(
        services.delete_attachment(
            db,
            attachment_id,
            payload.reason if payload else None,
            payload.confirm_token if payload else None,
        ),
        db,
    )


@router.post("/attachments/{attachment_id}/delete-preview", response_model=schemas.PreviewTokenResponse)
def delete_attachment_preview(
    attachment_id: int,
    db: Session = Depends(get_db),
) -> schemas.PreviewTokenResponse:
    return services.build_delete_preview_attachment(db, attachment_id)


@router.post(
    "/attachments/{attachment_id}/restore-preview",
    response_model=schemas.PreviewTokenResponse,
)
def restore_attachment_preview(
    attachment_id: int,
    db: Session = Depends(get_db),
) -> schemas.PreviewTokenResponse:
    return services.build_restore_preview_attachment(db, attachment_id)


@router.post("/attachments/{attachment_id}/restore", response_model=schemas.MediaAttachmentRead)
def restore_attachment(
    attachment_id: int,
    payload: schemas.RestoreConfirmRequest,
    db: Session = Depends(get_db),
) -> schemas.MediaAttachmentRead:
    return services.attachment_to_read(
        services.restore_attachment(db, attachment_id, payload.confirm_token),
        db,
    )


@router.get("/pets/{pet_id}/timeline", response_model=list[schemas.TimelineEventRead])
def get_pet_timeline(
    pet_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
    keyword: str | None = None,
    event_type: str = "all",
    category: schemas.AttachmentCategory | None = None,
    include_deleted: bool = False,
    sort: str = "desc",
    limit: int | None = 100,
    page: int | None = 1,
    db: Session = Depends(get_db),
) -> list[schemas.TimelineEventRead]:
    return services.get_pet_timeline(
        db,
        pet_id=pet_id,
        start=start,
        end=end,
        keyword=keyword,
        event_type=event_type,
        category=category,
        include_deleted=include_deleted,
        sort=sort,
        limit=limit,
        page=page,
    )

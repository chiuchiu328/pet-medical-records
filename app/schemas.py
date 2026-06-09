from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


MediaType = Literal["image", "video"]
AttachmentCategory = Literal[
    "blood_test",
    "xray",
    "ultrasound",
    "prescription",
    "note",
    "daily",
    "other",
]
OcrStatus = Literal["none", "manual", "pending", "done"]
Appetite = Literal["good", "normal", "poor", "unknown"]
Energy = Literal["high", "normal", "low", "unknown"]
Stool = Literal["normal", "soft", "diarrhea", "constipation", "none", "unknown"]
OwnerType = Literal["medical_record", "daily_log"]


class TagsMixin(BaseModel):
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value


class DeleteRequest(BaseModel):
    reason: str | None = None


class DeleteConfirmRequest(BaseModel):
    reason: str | None = None
    confirm_token: str | None = None


class RestoreConfirmRequest(BaseModel):
    confirm_token: str | None = None


class ResourceIdentity(BaseModel):
    type: str
    id: int


class VisibilityInfo(BaseModel):
    deleted: bool = False
    hidden_by_ancestor: bool = False
    hidden_by: dict[str, Any] | None = None


class PreviewTokenResponse(BaseModel):
    action: Literal["delete", "restore"]
    target: ResourceIdentity
    summary: str
    impact: dict[str, Any] = Field(default_factory=dict)
    confirm_token: str
    expires_at: datetime


class PetCreate(BaseModel):
    name: str
    species: str | None = None
    breed: str | None = None
    sex: str | None = None
    birth_date: date | None = None
    microchip_number: str | None = None
    notes: str | None = None


class PetUpdate(BaseModel):
    name: str | None = None
    species: str | None = None
    breed: str | None = None
    sex: str | None = None
    birth_date: date | None = None
    microchip_number: str | None = None
    notes: str | None = None


class PetRead(PetCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    delete_reason: str | None = None
    visibility: VisibilityInfo = Field(default_factory=VisibilityInfo)


class MedicalRecordCreate(TagsMixin):
    visit_at: datetime
    hospital_name: str | None = None
    doctor_name: str | None = None
    diagnosis: str | None = None
    prescription: str | None = None
    note: str | None = None
    weight_value: float | None = None
    weight_unit: str | None = "kg"


class MedicalRecordUpdate(TagsMixin):
    pet_id: int | None = None
    visit_at: datetime | None = None
    hospital_name: str | None = None
    doctor_name: str | None = None
    diagnosis: str | None = None
    prescription: str | None = None
    note: str | None = None
    weight_value: float | None = None
    weight_unit: str | None = None
    tags: list[str] | None = None


class DailyLogCreate(TagsMixin):
    logged_at: datetime
    content: str | None = None
    appetite: Appetite | None = None
    energy: Energy | None = None
    stool: Stool | None = None
    medication_note: str | None = None
    weight_value: float | None = None
    weight_unit: str | None = "kg"


class DailyLogUpdate(TagsMixin):
    pet_id: int | None = None
    logged_at: datetime | None = None
    content: str | None = None
    appetite: Appetite | None = None
    energy: Energy | None = None
    stool: Stool | None = None
    medication_note: str | None = None
    weight_value: float | None = None
    weight_unit: str | None = None
    tags: list[str] | None = None


class AttachmentCreate(BaseModel):
    media_type: MediaType
    category: AttachmentCategory
    captured_at: datetime | None = None
    extracted_text: str | None = None
    ocr_status: OcrStatus = "none"
    note: str | None = None


class AttachmentUpdate(BaseModel):
    media_type: MediaType | None = None
    category: AttachmentCategory | None = None
    captured_at: datetime | None = None
    extracted_text: str | None = None
    ocr_status: OcrStatus | None = None
    note: str | None = None


class MediaAttachmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_type: OwnerType
    owner_id: int
    media_type: MediaType
    category: AttachmentCategory
    file_name: str
    storage_path: str
    local_file_path: str
    mime_type: str | None = None
    captured_at: datetime | None = None
    extracted_text: str | None = None
    ocr_status: OcrStatus
    note: str | None = None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    delete_reason: str | None = None
    visibility: VisibilityInfo = Field(default_factory=VisibilityInfo)


class MedicalRecordRead(MedicalRecordCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pet_id: int
    attachments: list[MediaAttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    delete_reason: str | None = None
    visibility: VisibilityInfo = Field(default_factory=VisibilityInfo)


class DailyLogRead(DailyLogCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    pet_id: int
    attachments: list[MediaAttachmentRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None = None
    delete_reason: str | None = None
    visibility: VisibilityInfo = Field(default_factory=VisibilityInfo)


class TimelineEventRead(BaseModel):
    event_type: Literal["medical", "daily"]
    event_time: datetime
    pet_id: int
    source_id: int
    summary_text: str
    tags: list[str] = Field(default_factory=list)
    attachments: list[MediaAttachmentRead] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)

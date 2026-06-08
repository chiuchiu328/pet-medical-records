from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder

from app import schemas, services
from app.config import Settings
from app.database import Database


class MCPToolLayer:
    def __init__(self, settings: Settings | None = None, database: Database | None = None) -> None:
        self.settings = settings or Settings.from_env()
        self.settings.upload_dir.mkdir(parents=True, exist_ok=True)
        self.database = database or Database(self.settings.database_url)
        self.database.create_all()

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            self._tool("create_pet", "Create a pet profile."),
            self._tool("list_pets", "List pets, optionally including soft-deleted pets."),
            self._tool("get_pet", "Get a pet by id."),
            self._tool("update_pet", "Update a pet profile."),
            self._tool("delete_pet_preview", "Preview pet soft delete impact and return a confirm token."),
            self._tool("delete_pet", "Soft delete a pet."),
            self._tool("restore_pet_preview", "Preview pet restore impact and return a confirm token."),
            self._tool("restore_pet", "Restore a soft-deleted pet."),
            self._tool("create_medical_record", "Create a medical record for a pet."),
            self._tool("search_medical_records", "Search medical records by pet, time, keyword, tag, or attachment category."),
            self._tool("get_medical_record", "Get a medical record by id."),
            self._tool("update_medical_record", "Update a medical record."),
            self._tool("delete_medical_record_preview", "Preview medical record soft delete impact and return a confirm token."),
            self._tool("delete_medical_record", "Soft delete a medical record."),
            self._tool("restore_medical_record_preview", "Preview medical record restore impact and return a confirm token."),
            self._tool("restore_medical_record", "Restore a soft-deleted medical record."),
            self._tool("create_daily_log", "Create a daily log for a pet."),
            self._tool("search_daily_logs", "Search daily logs by pet, time, keyword, state, tag, or attachment category."),
            self._tool("get_daily_log", "Get a daily log by id."),
            self._tool("update_daily_log", "Update a daily log."),
            self._tool("delete_daily_log_preview", "Preview daily log soft delete impact and return a confirm token."),
            self._tool("delete_daily_log", "Soft delete a daily log."),
            self._tool("restore_daily_log_preview", "Preview daily log restore impact and return a confirm token."),
            self._tool("restore_daily_log", "Restore a soft-deleted daily log."),
            self._tool("attach_media_to_medical_record", "Attach a local file path to a medical record."),
            self._tool("attach_media_to_daily_log", "Attach a local file path to a daily log."),
            self._tool("get_attachment", "Get attachment metadata."),
            self._tool("update_attachment", "Update attachment metadata, category, note, or manual OCR text."),
            self._tool("delete_attachment_preview", "Preview attachment soft delete impact and return a confirm token."),
            self._tool("delete_attachment", "Soft delete an attachment."),
            self._tool("restore_attachment_preview", "Preview attachment restore impact and return a confirm token."),
            self._tool("restore_attachment", "Restore a soft-deleted attachment."),
            self._tool("get_pet_timeline", "Get a unified medical/daily timeline for a pet."),
            self._tool("summarize_pet_status", "Return a lightweight structured summary for a pet."),
        ]

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        arguments = arguments or {}
        with self.database.SessionLocal() as db:
            result = self._dispatch(db, name, arguments)
            return jsonable_encoder(result)

    def _dispatch(self, db, name: str, arguments: dict[str, Any]) -> Any:
        if name == "create_pet":
            return services.pet_to_read(services.create_pet(db, schemas.PetCreate(**arguments)))
        if name == "list_pets":
            return [
                services.pet_to_read(pet)
                for pet in services.list_pets(
                    db,
                    keyword=arguments.get("keyword"),
                    include_deleted=arguments.get("include_deleted", False),
                )
            ]
        if name == "get_pet":
            return services.pet_to_read(
                services.get_pet(
                    db,
                    arguments["pet_id"],
                    include_deleted=arguments.get("include_deleted", False),
                )
            )
        if name == "update_pet":
            pet_id = arguments.pop("pet_id")
            return services.pet_to_read(services.update_pet(db, pet_id, schemas.PetUpdate(**arguments)))
        if name == "delete_pet_preview":
            return services.build_delete_preview_pet(db, arguments["pet_id"])
        if name == "delete_pet":
            return services.pet_to_read(
                services.delete_pet(
                    db,
                    arguments["pet_id"],
                    arguments.get("reason"),
                    arguments.get("confirm_token"),
                )
            )
        if name == "restore_pet_preview":
            return services.build_restore_preview_pet(db, arguments["pet_id"])
        if name == "restore_pet":
            return services.pet_to_read(
                services.restore_pet(db, arguments["pet_id"], arguments.get("confirm_token"))
            )

        if name == "create_medical_record":
            pet_id = arguments.pop("pet_id")
            record = services.create_medical_record(
                db,
                pet_id,
                schemas.MedicalRecordCreate(**arguments),
            )
            return services.medical_record_to_read(db, record)
        if name == "search_medical_records":
            records = services.search_medical_records(db, **arguments)
            return [
                services.medical_record_to_read(
                    db,
                    record,
                    include_deleted_attachments=arguments.get("include_deleted", False),
                )
                for record in records
            ]
        if name == "get_medical_record":
            record = services.get_medical_record(
                db,
                arguments["record_id"],
                include_deleted=arguments.get("include_deleted", False),
            )
            return services.medical_record_to_read(
                db,
                record,
                include_deleted_attachments=arguments.get("include_deleted", False),
            )
        if name == "update_medical_record":
            record_id = arguments.pop("record_id")
            record = services.update_medical_record(
                db,
                record_id,
                schemas.MedicalRecordUpdate(**arguments),
            )
            return services.medical_record_to_read(db, record)
        if name == "delete_medical_record_preview":
            return services.build_delete_preview_medical_record(db, arguments["record_id"])
        if name == "delete_medical_record":
            record = services.delete_medical_record(
                db,
                arguments["record_id"],
                arguments.get("reason"),
                arguments.get("confirm_token"),
            )
            return services.medical_record_to_read(db, record)
        if name == "restore_medical_record_preview":
            return services.build_restore_preview_medical_record(db, arguments["record_id"])
        if name == "restore_medical_record":
            record = services.restore_medical_record(
                db,
                arguments["record_id"],
                arguments.get("confirm_token"),
            )
            return services.medical_record_to_read(db, record)

        if name == "create_daily_log":
            pet_id = arguments.pop("pet_id")
            log = services.create_daily_log(db, pet_id, schemas.DailyLogCreate(**arguments))
            return services.daily_log_to_read(db, log)
        if name == "search_daily_logs":
            logs = services.search_daily_logs(db, **arguments)
            return [
                services.daily_log_to_read(
                    db,
                    log,
                    include_deleted_attachments=arguments.get("include_deleted", False),
                )
                for log in logs
            ]
        if name == "get_daily_log":
            log = services.get_daily_log(
                db,
                arguments["log_id"],
                include_deleted=arguments.get("include_deleted", False),
            )
            return services.daily_log_to_read(
                db,
                log,
                include_deleted_attachments=arguments.get("include_deleted", False),
            )
        if name == "update_daily_log":
            log_id = arguments.pop("log_id")
            log = services.update_daily_log(db, log_id, schemas.DailyLogUpdate(**arguments))
            return services.daily_log_to_read(db, log)
        if name == "delete_daily_log_preview":
            return services.build_delete_preview_daily_log(db, arguments["log_id"])
        if name == "delete_daily_log":
            log = services.delete_daily_log(
                db,
                arguments["log_id"],
                arguments.get("reason"),
                arguments.get("confirm_token"),
            )
            return services.daily_log_to_read(db, log)
        if name == "restore_daily_log_preview":
            return services.build_restore_preview_daily_log(db, arguments["log_id"])
        if name == "restore_daily_log":
            log = services.restore_daily_log(
                db,
                arguments["log_id"],
                arguments.get("confirm_token"),
            )
            return services.daily_log_to_read(db, log)

        if name == "attach_media_to_medical_record":
            record_id = arguments.pop("record_id")
            return self._attach_media_from_path(
                db,
                owner_type="medical_record",
                owner_id=record_id,
                arguments=arguments,
            )
        if name == "attach_media_to_daily_log":
            log_id = arguments.pop("log_id")
            return self._attach_media_from_path(
                db,
                owner_type="daily_log",
                owner_id=log_id,
                arguments=arguments,
            )
        if name == "get_attachment":
            return services.attachment_to_read(
                services.get_attachment(
                    db,
                    arguments["attachment_id"],
                    include_deleted=arguments.get("include_deleted", False),
                ),
                db,
            )
        if name == "update_attachment":
            attachment_id = arguments.pop("attachment_id")
            return services.attachment_to_read(
                services.update_attachment(db, attachment_id, schemas.AttachmentUpdate(**arguments)),
                db,
            )
        if name == "delete_attachment_preview":
            return services.build_delete_preview_attachment(db, arguments["attachment_id"])
        if name == "delete_attachment":
            return services.attachment_to_read(
                services.delete_attachment(
                    db,
                    arguments["attachment_id"],
                    arguments.get("reason"),
                    arguments.get("confirm_token"),
                ),
                db,
            )
        if name == "restore_attachment_preview":
            return services.build_restore_preview_attachment(db, arguments["attachment_id"])
        if name == "restore_attachment":
            return services.attachment_to_read(
                services.restore_attachment(
                    db,
                    arguments["attachment_id"],
                    arguments.get("confirm_token"),
                ),
                db,
            )

        if name == "get_pet_timeline":
            return services.get_pet_timeline(db, **arguments)
        if name == "summarize_pet_status":
            return services.summarize_pet_status(db, **arguments)

        raise services.InvalidRequest(f"Unknown MCP tool: {name}")

    def _attach_media_from_path(
        self,
        db,
        *,
        owner_type: str,
        owner_id: int,
        arguments: dict[str, Any],
    ) -> schemas.MediaAttachmentRead:
        file_path = Path(arguments.pop("file_path"))
        payload = schemas.AttachmentCreate(**arguments)
        attachment = services.create_attachment_from_path(
            db,
            self.settings,
            owner_type=owner_type,
            owner_id=owner_id,
            source_path=file_path,
            payload=payload,
        )
        return services.attachment_to_read(attachment, db)

    @staticmethod
    def _tool(name: str, description: str) -> dict[str, Any]:
        return {
            "name": name,
            "description": description,
            "inputSchema": {
                "type": "object",
                "additionalProperties": True,
            },
        }

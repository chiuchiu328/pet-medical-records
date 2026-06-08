from __future__ import annotations

import pytest

from app.config import Settings
from app.mcp.tool_layer import MCPToolLayer
from app.services import InvalidRequest, ResourceNotFound


def _layer(tmp_path) -> MCPToolLayer:
    return MCPToolLayer(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'mcp-epic-a.db'}",
            upload_dir=tmp_path / "uploads",
        )
    )


def _create_pet_record_log_and_attachment(layer: MCPToolLayer, tmp_path):
    source_file = tmp_path / "attachment.txt"
    source_file.write_text("attachment text", encoding="utf-8")
    pet = layer.call_tool("create_pet", {"name": "Momo", "species": "cat"})
    record = layer.call_tool(
        "create_medical_record",
        {
            "pet_id": pet["id"],
            "visit_at": "2026-06-07T14:30:00+08:00",
            "diagnosis": "checkup",
            "prescription": "patros 50mg",
        },
    )
    log = layer.call_tool(
        "create_daily_log",
        {
            "pet_id": pet["id"],
            "logged_at": "2026-06-07T20:32:00+08:00",
            "content": "daily note",
            "medication_note": "patros 50mg",
        },
    )
    attachment = layer.call_tool(
        "attach_media_to_medical_record",
        {
            "record_id": record["id"],
            "file_path": str(source_file),
            "media_type": "image",
            "category": "blood_test",
        },
    )
    return pet, record, log, attachment


def test_mcp_tools_expose_delete_restore_preview_parity(tmp_path):
    layer = _layer(tmp_path)
    names = {tool["name"] for tool in layer.list_tools()}

    for resource in ["pet", "medical_record", "daily_log", "attachment"]:
        assert f"delete_{resource}_preview" in names
        assert f"restore_{resource}_preview" in names
        assert f"restore_{resource}" in names


def test_mcp_pet_preview_confirm_visibility_and_restore(tmp_path):
    layer = _layer(tmp_path)
    pet, record, log, attachment = _create_pet_record_log_and_attachment(layer, tmp_path)

    with pytest.raises(InvalidRequest):
        layer.call_tool("delete_pet", {"pet_id": pet["id"], "reason": "missing token"})

    preview = layer.call_tool("delete_pet_preview", {"pet_id": pet["id"]})
    assert preview["action"] == "delete"
    assert preview["target"] == {"type": "pet", "id": pet["id"]}
    assert preview["confirm_token"]
    assert preview["impact"]["will_hide"] == {
        "medical_records": 1,
        "daily_logs": 1,
        "attachments": 1,
    }

    with pytest.raises(InvalidRequest):
        layer.call_tool(
            "delete_pet",
            {"pet_id": pet["id"], "reason": "bad token", "confirm_token": "wrong"},
        )

    deleted = layer.call_tool(
        "delete_pet",
        {
            "pet_id": pet["id"],
            "reason": "archive",
            "confirm_token": preview["confirm_token"],
        },
    )
    assert deleted["deleted_at"] is not None
    assert deleted["visibility"]["deleted"] is True

    with pytest.raises(ResourceNotFound):
        layer.call_tool("get_medical_record", {"record_id": record["id"]})
    with pytest.raises(ResourceNotFound):
        layer.call_tool("get_daily_log", {"log_id": log["id"]})
    with pytest.raises(ResourceNotFound):
        layer.call_tool("get_attachment", {"attachment_id": attachment["id"]})

    included = layer.call_tool(
        "get_medical_record",
        {"record_id": record["id"], "include_deleted": True},
    )
    assert included["visibility"]["hidden_by_ancestor"] is True
    assert included["visibility"]["hidden_by"] == {"type": "pet", "id": pet["id"]}

    restore_preview = layer.call_tool("restore_pet_preview", {"pet_id": pet["id"]})
    assert restore_preview["action"] == "restore"
    assert restore_preview["confirm_token"]
    assert restore_preview["impact"]["will_restore"]["medical_records"] == 1

    restored = layer.call_tool(
        "restore_pet",
        {"pet_id": pet["id"], "confirm_token": restore_preview["confirm_token"]},
    )
    assert restored["deleted_at"] is None
    assert layer.call_tool("get_medical_record", {"record_id": record["id"]})["id"] == record["id"]


def test_mcp_record_daily_and_attachment_preview_restore_tools(tmp_path):
    layer = _layer(tmp_path)
    pet, record, log, attachment = _create_pet_record_log_and_attachment(layer, tmp_path)

    record_preview = layer.call_tool("delete_medical_record_preview", {"record_id": record["id"]})
    assert record_preview["impact"]["will_hide"] == {"attachments": 1}
    deleted_record = layer.call_tool(
        "delete_medical_record",
        {
            "record_id": record["id"],
            "reason": "wrong record",
            "confirm_token": record_preview["confirm_token"],
        },
    )
    assert deleted_record["deleted_at"] is not None
    with pytest.raises(ResourceNotFound):
        layer.call_tool("get_attachment", {"attachment_id": attachment["id"]})

    record_restore_preview = layer.call_tool(
        "restore_medical_record_preview",
        {"record_id": record["id"]},
    )
    assert record_restore_preview["impact"]["will_restore"]["attachments"] == 1
    restored_record = layer.call_tool(
        "restore_medical_record",
        {"record_id": record["id"], "confirm_token": record_restore_preview["confirm_token"]},
    )
    assert restored_record["deleted_at"] is None

    daily_preview = layer.call_tool("delete_daily_log_preview", {"log_id": log["id"]})
    deleted_log = layer.call_tool(
        "delete_daily_log",
        {
            "log_id": log["id"],
            "reason": "wrong log",
            "confirm_token": daily_preview["confirm_token"],
        },
    )
    assert deleted_log["deleted_at"] is not None
    daily_restore_preview = layer.call_tool("restore_daily_log_preview", {"log_id": log["id"]})
    restored_log = layer.call_tool(
        "restore_daily_log",
        {"log_id": log["id"], "confirm_token": daily_restore_preview["confirm_token"]},
    )
    assert restored_log["deleted_at"] is None

    attachment_preview = layer.call_tool(
        "delete_attachment_preview",
        {"attachment_id": attachment["id"]},
    )
    deleted_attachment = layer.call_tool(
        "delete_attachment",
        {
            "attachment_id": attachment["id"],
            "reason": "wrong file",
            "confirm_token": attachment_preview["confirm_token"],
        },
    )
    assert deleted_attachment["deleted_at"] is not None
    attachment_restore_preview = layer.call_tool(
        "restore_attachment_preview",
        {"attachment_id": attachment["id"]},
    )
    restored_attachment = layer.call_tool(
        "restore_attachment",
        {
            "attachment_id": attachment["id"],
            "confirm_token": attachment_restore_preview["confirm_token"],
        },
    )
    assert restored_attachment["deleted_at"] is None

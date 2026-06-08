from __future__ import annotations

import pytest

from app.config import Settings
from app.mcp.tool_layer import MCPToolLayer
from app.services import ResourceNotFound


def test_mcp_tool_layer_supports_agent_first_workflow(tmp_path):
    layer = MCPToolLayer(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'mcp.db'}",
            upload_dir=tmp_path / "uploads",
        )
    )
    source_file = tmp_path / "blood-test.txt"
    source_file.write_text("血檢報告：摸摸 WBC normal", encoding="utf-8")

    pet = layer.call_tool(
        "create_pet",
        {
            "name": "摸摸",
            "species": "cat",
            "breed": "米克斯",
            "sex": "female",
            "birth_date": "2021-03-12",
        },
    )
    assert pet["name"] == "摸摸"

    record = layer.call_tool(
        "create_medical_record",
        {
            "pet_id": pet["id"],
            "visit_at": "2026-06-07T14:30:00+08:00",
            "hospital_name": "安心動物醫院",
            "doctor_name": "王醫師",
            "diagnosis": "腸胃不適",
            "prescription": "patros 50mg bid",
            "weight_value": 4.3,
            "weight_unit": "kg",
            "tags": ["血檢"],
        },
    )
    assert record["pet_id"] == pet["id"]

    attachment = layer.call_tool(
        "attach_media_to_medical_record",
        {
            "record_id": record["id"],
            "file_path": str(source_file),
            "media_type": "image",
            "category": "blood_test",
            "extracted_text": "血檢 WBC normal",
        },
    )
    assert attachment["category"] == "blood_test"
    assert attachment["ocr_status"] == "manual"

    log = layer.call_tool(
        "create_daily_log",
        {
            "pet_id": pet["id"],
            "logged_at": "2026-06-07T20:32:00+08:00",
            "content": "摸摸今天食慾不振，沒有太多活動力",
            "appetite": "poor",
            "energy": "low",
            "medication_note": "patros 50mg, xxx 100mg",
            "weight_value": 4.3,
            "weight_unit": "kg",
            "tags": ["食慾", "用藥"],
        },
    )
    assert log["appetite"] == "poor"

    timeline = layer.call_tool(
        "get_pet_timeline",
        {"pet_id": pet["id"], "keyword": "patros"},
    )
    assert [event["event_type"] for event in timeline] == ["daily", "medical"]

    summary = layer.call_tool("summarize_pet_status", {"pet_id": pet["id"]})
    assert summary["event_count"] == 2
    assert summary["latest_weight"]["value"] == 4.3
    assert "poor" in summary["appetite_values"]


def test_mcp_tool_layer_update_get_delete_and_missing_attachment_path(tmp_path):
    layer = MCPToolLayer(
        Settings(
            database_url=f"sqlite:///{tmp_path / 'mcp-update.db'}",
            upload_dir=tmp_path / "uploads",
        )
    )

    pet = layer.call_tool(
        "create_pet",
        {
            "name": "摸摸",
            "species": "cat",
            "breed": "米克斯",
            "sex": "female",
            "birth_date": "2021-03-12",
        },
    )
    record = layer.call_tool(
        "create_medical_record",
        {
            "pet_id": pet["id"],
            "visit_at": "2026-06-07T14:30:00+08:00",
            "hospital_name": "安心動物醫院",
            "doctor_name": "王醫師",
            "diagnosis": "腸胃不適",
            "prescription": "patros 50mg bid",
            "weight_value": 4.3,
            "weight_unit": "kg",
            "tags": ["腸胃"],
        },
    )
    log = layer.call_tool(
        "create_daily_log",
        {
            "pet_id": pet["id"],
            "logged_at": "2026-06-07T20:32:00+08:00",
            "content": "摸摸晚上 8:32 使用 patros 50mg",
            "appetite": "poor",
            "energy": "low",
            "medication_note": "patros 50mg",
            "weight_value": 4.3,
            "weight_unit": "kg",
            "tags": ["用藥"],
        },
    )

    with pytest.raises(FileNotFoundError):
        layer.call_tool(
            "attach_media_to_medical_record",
            {
                "record_id": record["id"],
                "file_path": str(tmp_path / "missing-blood-test.jpg"),
                "media_type": "image",
                "category": "blood_test",
            },
        )

    updated = layer.call_tool(
        "update_daily_log",
        {
            "log_id": log["id"],
            "logged_at": "2026-06-07T20:22:00+08:00",
            "content": "剛剛那筆不是晚上 8:32，是 8:22",
            "energy": "normal",
            "medication_note": "patros 25mg",
            "tags": ["用藥", "修正"],
        },
    )
    assert updated["energy"] == "normal"
    assert updated["medication_note"] == "patros 25mg"

    fetched = layer.call_tool("get_daily_log", {"log_id": log["id"]})
    assert fetched["tags"] == ["用藥", "修正"]

    delete_preview = layer.call_tool("delete_daily_log_preview", {"log_id": log["id"]})
    deleted = layer.call_tool(
        "delete_daily_log",
        {
            "log_id": log["id"],
            "reason": "重複的用藥紀錄",
            "confirm_token": delete_preview["confirm_token"],
        },
    )
    assert deleted["deleted_at"] is not None

    with pytest.raises(ResourceNotFound):
        layer.call_tool("get_daily_log", {"log_id": log["id"]})

    included = layer.call_tool(
        "get_daily_log",
        {"log_id": log["id"], "include_deleted": True},
    )
    assert included["delete_reason"] == "重複的用藥紀錄"

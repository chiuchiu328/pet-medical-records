from __future__ import annotations

from tests.helpers import delete_with_preview, restore_with_preview


def _create_medical_record(client, pet_id: int, **overrides):
    payload = {
        "visit_at": "2026-06-07T14:30:00+08:00",
        "diagnosis": "checkup",
        "prescription": "patros 50mg",
        "tags": ["checkup"],
    }
    payload.update(overrides)
    response = client.post(f"/pets/{pet_id}/medical-records", json=payload)
    assert response.status_code == 201
    return response.json()


def _create_daily_log(client, pet_id: int, **overrides):
    payload = {
        "logged_at": "2026-06-07T20:32:00+08:00",
        "content": "evening medication",
        "appetite": "normal",
        "energy": "normal",
        "medication_note": "patros 50mg",
        "tags": ["daily"],
    }
    payload.update(overrides)
    response = client.post(f"/pets/{pet_id}/daily-logs", json=payload)
    assert response.status_code == 201
    return response.json()


def _attach_to_medical_record(client, record_id: int, *, category: str = "blood_test"):
    response = client.post(
        f"/medical-records/{record_id}/attachments",
        data={"media_type": "image", "category": category, "note": "record attachment"},
        files={"file": (f"{category}.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 201
    return response.json()


def _attach_to_daily_log(client, log_id: int, *, category: str = "daily"):
    response = client.post(
        f"/daily-logs/{log_id}/attachments",
        data={"media_type": "image", "category": category, "note": "daily attachment"},
        files={"file": (f"{category}.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 201
    return response.json()


def test_pet_delete_preview_token_and_ancestor_hidden_descendants(client, momo_pet):
    pet_id = momo_pet["id"]
    record = _create_medical_record(client, pet_id)
    log = _create_daily_log(client, pet_id)
    record_attachment = _attach_to_medical_record(client, record["id"])
    log_attachment = _attach_to_daily_log(client, log["id"])

    pet_read = client.get(f"/pets/{pet_id}")
    assert pet_read.status_code == 200
    assert pet_read.json()["visibility"] == {
        "deleted": False,
        "hidden_by_ancestor": False,
        "hidden_by": None,
    }

    preview = client.post(f"/pets/{pet_id}/delete-preview")
    assert preview.status_code == 200
    preview_data = preview.json()
    assert preview_data["target"] == {"type": "pet", "id": pet_id}
    assert preview_data["action"] == "delete"
    assert preview_data["confirm_token"]
    assert preview_data["expires_at"]
    assert preview_data["impact"]["will_hide"] == {
        "medical_records": 1,
        "daily_logs": 1,
        "attachments": 2,
    }

    missing_token = client.request(
        "DELETE",
        f"/pets/{pet_id}",
        json={"reason": "missing token"},
    )
    assert missing_token.status_code == 400

    wrong_token = client.request(
        "DELETE",
        f"/pets/{pet_id}",
        json={"reason": "wrong token", "confirm_token": "not-a-real-token"},
    )
    assert wrong_token.status_code == 400

    deleted = client.request(
        "DELETE",
        f"/pets/{pet_id}",
        json={"reason": "duplicate pet", "confirm_token": preview_data["confirm_token"]},
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted_at"] is not None
    assert deleted.json()["visibility"]["deleted"] is True

    assert client.get(f"/medical-records/{record['id']}").status_code == 404
    assert client.get(f"/daily-logs/{log['id']}").status_code == 404
    assert client.get(f"/attachments/{record_attachment['id']}").status_code == 404
    assert client.get(f"/attachments/{log_attachment['id']}").status_code == 404

    hidden_records = client.get(f"/pets/{pet_id}/medical-records")
    assert hidden_records.status_code == 200
    assert hidden_records.json() == []

    included_record = client.get(
        f"/medical-records/{record['id']}",
        params={"include_deleted": "true"},
    )
    assert included_record.status_code == 200
    record_data = included_record.json()
    assert record_data["visibility"]["deleted"] is False
    assert record_data["visibility"]["hidden_by_ancestor"] is True
    assert record_data["visibility"]["hidden_by"] == {"type": "pet", "id": pet_id}
    assert record_data["attachments"][0]["visibility"]["hidden_by_ancestor"] is True

    included_log = client.get(
        f"/daily-logs/{log['id']}",
        params={"include_deleted": "true"},
    )
    assert included_log.status_code == 200
    assert included_log.json()["visibility"]["hidden_by_ancestor"] is True

    included_attachment = client.get(
        f"/attachments/{record_attachment['id']}",
        params={"include_deleted": "true"},
    )
    assert included_attachment.status_code == 200
    assert included_attachment.json()["visibility"]["hidden_by_ancestor"] is True
    assert included_attachment.json()["visibility"]["hidden_by"] == {"type": "pet", "id": pet_id}


def test_record_delete_hides_attachment_and_restore_makes_it_visible(client, momo_pet):
    record = _create_medical_record(client, momo_pet["id"])
    attachment = _attach_to_medical_record(client, record["id"], category="xray")

    preview = client.post(f"/medical-records/{record['id']}/delete-preview")
    assert preview.status_code == 200
    assert preview.json()["impact"]["will_hide"] == {"attachments": 1}

    deleted = client.request(
        "DELETE",
        f"/medical-records/{record['id']}",
        json={"reason": "wrong record", "confirm_token": preview.json()["confirm_token"]},
    )
    assert deleted.status_code == 200

    assert client.get(f"/attachments/{attachment['id']}").status_code == 404

    included_attachment = client.get(
        f"/attachments/{attachment['id']}",
        params={"include_deleted": "true"},
    )
    assert included_attachment.status_code == 200
    assert included_attachment.json()["visibility"]["hidden_by_ancestor"] is True
    assert included_attachment.json()["visibility"]["hidden_by"] == {
        "type": "medical_record",
        "id": record["id"],
    }

    restore_preview = client.post(f"/medical-records/{record['id']}/restore-preview")
    assert restore_preview.status_code == 200
    assert restore_preview.json()["impact"]["will_restore"]["attachments"] == 1

    restored = client.post(
        f"/medical-records/{record['id']}/restore",
        json={"confirm_token": restore_preview.json()["confirm_token"]},
    )
    assert restored.status_code == 200
    assert restored.json()["deleted_at"] is None

    visible_attachment = client.get(f"/attachments/{attachment['id']}")
    assert visible_attachment.status_code == 200
    assert visible_attachment.json()["visibility"]["hidden_by_ancestor"] is False


def test_parent_restore_does_not_undelete_directly_deleted_children(client, momo_pet):
    pet_id = momo_pet["id"]
    record = _create_medical_record(client, pet_id)
    log = _create_daily_log(client, pet_id)

    deleted_record = delete_with_preview(
        client,
        f"/medical-records/{record['id']}",
        reason="bad child row",
    )
    assert deleted_record.status_code == 200
    assert deleted_record.json()["deleted_at"] is not None

    deleted_pet = delete_with_preview(client, f"/pets/{pet_id}", reason="archive pet")
    assert deleted_pet.status_code == 200

    restore_preview = client.post(f"/pets/{pet_id}/restore-preview")
    assert restore_preview.status_code == 200
    assert restore_preview.json()["impact"]["will_restore"]["daily_logs"] == 1
    assert restore_preview.json()["impact"]["will_remain_hidden"]["medical_records"] == 1

    restored_pet = client.post(
        f"/pets/{pet_id}/restore",
        json={"confirm_token": restore_preview.json()["confirm_token"]},
    )
    assert restored_pet.status_code == 200
    assert restored_pet.json()["deleted_at"] is None

    assert client.get(f"/daily-logs/{log['id']}").status_code == 200
    assert client.get(f"/medical-records/{record['id']}").status_code == 404

    included_record = client.get(
        f"/medical-records/{record['id']}",
        params={"include_deleted": "true"},
    )
    assert included_record.status_code == 200
    assert included_record.json()["visibility"] == {
        "deleted": True,
        "hidden_by_ancestor": False,
        "hidden_by": None,
    }


def test_daily_log_and_attachment_preview_restore_endpoints(client, momo_pet):
    log = _create_daily_log(client, momo_pet["id"])
    attachment = _attach_to_daily_log(client, log["id"], category="daily")

    daily_preview = client.post(f"/daily-logs/{log['id']}/delete-preview")
    assert daily_preview.status_code == 200
    assert daily_preview.json()["impact"]["will_hide"] == {"attachments": 1}

    deleted_log = client.request(
        "DELETE",
        f"/daily-logs/{log['id']}",
        json={"reason": "wrong daily log", "confirm_token": daily_preview.json()["confirm_token"]},
    )
    assert deleted_log.status_code == 200

    restored_log = restore_with_preview(client, f"/daily-logs/{log['id']}")
    assert restored_log.status_code == 200
    assert restored_log.json()["deleted_at"] is None

    attachment_preview = client.post(f"/attachments/{attachment['id']}/delete-preview")
    assert attachment_preview.status_code == 200
    assert attachment_preview.json()["impact"]["will_hide"] == {}

    deleted_attachment = client.request(
        "DELETE",
        f"/attachments/{attachment['id']}",
        json={
            "reason": "wrong file",
            "confirm_token": attachment_preview.json()["confirm_token"],
        },
    )
    assert deleted_attachment.status_code == 200
    assert client.get(f"/attachments/{attachment['id']}").status_code == 404

    restored_attachment = restore_with_preview(client, f"/attachments/{attachment['id']}")
    assert restored_attachment.status_code == 200
    assert restored_attachment.json()["deleted_at"] is None


def test_timeline_obeys_ancestor_visibility_and_include_deleted(client, momo_pet):
    pet_id = momo_pet["id"]
    record = _create_medical_record(client, pet_id, diagnosis="xray followup")
    _attach_to_medical_record(client, record["id"], category="xray")
    log = _create_daily_log(client, pet_id, content="daily food note")
    _attach_to_daily_log(client, log["id"], category="daily")

    deleted_pet = delete_with_preview(client, f"/pets/{pet_id}", reason="archive pet")
    assert deleted_pet.status_code == 200

    hidden_timeline = client.get(f"/pets/{pet_id}/timeline")
    assert hidden_timeline.status_code == 200
    assert hidden_timeline.json() == []

    hidden_xray = client.get(f"/pets/{pet_id}/timeline", params={"category": "xray"})
    assert hidden_xray.status_code == 200
    assert hidden_xray.json() == []

    included_timeline = client.get(
        f"/pets/{pet_id}/timeline",
        params={"include_deleted": "true"},
    )
    assert included_timeline.status_code == 200
    assert {event["event_type"] for event in included_timeline.json()} == {"medical", "daily"}
    assert all(event["data"]["visibility"]["hidden_by_ancestor"] for event in included_timeline.json())
    assert all(
        attachment["visibility"]["hidden_by_ancestor"]
        for event in included_timeline.json()
        for attachment in event["attachments"]
    )

    included_xray = client.get(
        f"/pets/{pet_id}/timeline",
        params={"category": "xray", "include_deleted": "true"},
    )
    assert included_xray.status_code == 200
    assert [(event["event_type"], event["source_id"]) for event in included_xray.json()] == [
        ("medical", record["id"])
    ]

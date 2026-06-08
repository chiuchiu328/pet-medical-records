from __future__ import annotations

from pathlib import Path

from tests.helpers import delete_with_preview


def test_pet_medical_daily_attachment_timeline_workflow(client, momo_pet):
    pet_id = momo_pet["id"]

    medical_response = client.post(
        f"/pets/{pet_id}/medical-records",
        json={
            "visit_at": "2026-06-07T14:30:00+08:00",
            "hospital_name": "安心動物醫院",
            "doctor_name": "王醫師",
            "diagnosis": "腸胃不適",
            "prescription": "patros 50mg bid",
            "note": "食慾差，建議觀察三天",
            "weight_value": 4.3,
            "weight_unit": "kg",
            "tags": ["腸胃", "回診"],
        },
    )
    assert medical_response.status_code == 201
    record = medical_response.json()
    assert record["pet_id"] == pet_id
    assert record["weight_value"] == 4.3

    blood_attachment_response = client.post(
        f"/medical-records/{record['id']}/attachments",
        data={
            "media_type": "image",
            "category": "blood_test",
            "extracted_text": "血檢 WBC 正常，肝腎指數待追蹤",
            "note": "摸摸今天的血檢",
        },
        files={"file": ("blood-test.jpg", b"fake-image", "image/jpeg")},
    )
    assert blood_attachment_response.status_code == 201
    blood_attachment = blood_attachment_response.json()
    assert blood_attachment["ocr_status"] == "manual"
    assert Path(blood_attachment["storage_path"]).exists()

    xray_attachment_response = client.post(
        f"/medical-records/{record['id']}/attachments",
        data={
            "media_type": "image",
            "category": "xray",
            "note": "這是 X 光，請歸類成 xray",
        },
        files={"file": ("xray.png", b"fake-xray", "image/png")},
    )
    assert xray_attachment_response.status_code == 201

    daily_response = client.post(
        f"/pets/{pet_id}/daily-logs",
        json={
            "logged_at": "2026-06-07T20:32:00+08:00",
            "content": "今天食慾不振，活動力偏低",
            "appetite": "poor",
            "energy": "low",
            "stool": "normal",
            "medication_note": "patros 50mg, xxx 100mg",
            "weight_value": 4.3,
            "weight_unit": "kg",
            "tags": ["食慾", "用藥"],
        },
    )
    assert daily_response.status_code == 201
    daily_log = daily_response.json()
    assert daily_log["appetite"] == "poor"
    assert daily_log["energy"] == "low"

    ultrasound_response = client.post(
        f"/daily-logs/{daily_log['id']}/attachments",
        data={
            "media_type": "video",
            "category": "ultrasound",
            "note": "這段影片是超音波",
        },
        files={"file": ("ultrasound.mp4", b"fake-video", "video/mp4")},
    )
    assert ultrasound_response.status_code == 201

    patros_logs = client.get(f"/pets/{pet_id}/daily-logs", params={"keyword": "patros"})
    assert patros_logs.status_code == 200
    assert [item["id"] for item in patros_logs.json()] == [daily_log["id"]]

    blood_records = client.get(f"/pets/{pet_id}/medical-records", params={"category": "blood_test"})
    assert blood_records.status_code == 200
    assert [item["id"] for item in blood_records.json()] == [record["id"]]
    assert blood_records.json()[0]["attachments"][0]["category"] == "blood_test"

    timeline = client.get(
        f"/pets/{pet_id}/timeline",
        params={
            "start": "2026-06-07T00:00:00+08:00",
            "end": "2026-06-08T00:00:00+08:00",
        },
    )
    assert timeline.status_code == 200
    events = timeline.json()
    assert [event["event_type"] for event in events] == ["daily", "medical"]
    assert "patros 50mg" in events[0]["summary_text"]
    assert "腸胃不適" in events[1]["summary_text"]

    ultrasound_timeline = client.get(
        f"/pets/{pet_id}/timeline",
        params={"category": "ultrasound"},
    )
    assert ultrasound_timeline.status_code == 200
    assert [event["event_type"] for event in ultrasound_timeline.json()] == ["daily"]


def test_soft_delete_hides_records_by_default_and_keeps_reason(client, momo_pet):
    pet_id = momo_pet["id"]
    create_response = client.post(
        f"/pets/{pet_id}/daily-logs",
        json={
            "logged_at": "2026-06-07T07:40:00+08:00",
            "content": "摸摸早上 7:40 使用 patros 50mg",
            "medication_note": "patros 50mg",
            "tags": ["用藥"],
        },
    )
    assert create_response.status_code == 201
    log_id = create_response.json()["id"]

    delete_response = delete_with_preview(
        client,
        f"/daily-logs/{log_id}",
        reason="重複的用藥紀錄",
    )
    assert delete_response.status_code == 200
    deleted = delete_response.json()
    assert deleted["deleted_at"] is not None
    assert deleted["delete_reason"] == "重複的用藥紀錄"

    hidden = client.get(f"/pets/{pet_id}/daily-logs", params={"keyword": "patros"})
    assert hidden.status_code == 200
    assert hidden.json() == []

    included = client.get(
        f"/pets/{pet_id}/daily-logs",
        params={"keyword": "patros", "include_deleted": "true"},
    )
    assert included.status_code == 200
    assert [item["id"] for item in included.json()] == [log_id]

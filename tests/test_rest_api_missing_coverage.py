from __future__ import annotations

from tests.helpers import delete_with_preview


def _create_pet(client, **overrides):
    payload = {
        "name": "小花",
        "species": "dog",
        "breed": "柴犬",
        "sex": "female",
        "birth_date": "2020-11-02",
        "microchip_number": "910000000000002",
        "notes": "另一隻寵物，術後觀察",
    }
    payload.update(overrides)
    response = client.post("/pets", json=payload)
    assert response.status_code == 201
    return response.json()


def _create_medical_record(client, pet_id: int, **overrides):
    payload = {
        "visit_at": "2026-06-07T14:30:00+08:00",
        "hospital_name": "安心動物醫院",
        "doctor_name": "王醫師",
        "diagnosis": "腸胃不適",
        "prescription": "patros 50mg bid",
        "note": "食慾差，建議觀察三天",
        "weight_value": 4.3,
        "weight_unit": "kg",
        "tags": ["腸胃", "回診"],
    }
    payload.update(overrides)
    response = client.post(f"/pets/{pet_id}/medical-records", json=payload)
    assert response.status_code == 201
    return response.json()


def _create_daily_log(client, pet_id: int, **overrides):
    payload = {
        "logged_at": "2026-06-07T20:32:00+08:00",
        "content": "摸摸今天食慾不振，活動力偏低",
        "appetite": "poor",
        "energy": "low",
        "stool": "normal",
        "medication_note": "patros 50mg, xxx 100mg",
        "weight_value": 4.3,
        "weight_unit": "kg",
        "tags": ["食慾", "用藥"],
    }
    payload.update(overrides)
    response = client.post(f"/pets/{pet_id}/daily-logs", json=payload)
    assert response.status_code == 201
    return response.json()


def _attach_to_medical_record(client, record_id: int, *, category: str = "blood_test", **overrides):
    data = {
        "media_type": "image",
        "category": category,
        "note": f"摸摸的 {category} 附件",
    }
    data.update(overrides)
    response = client.post(
        f"/medical-records/{record_id}/attachments",
        data=data,
        files={"file": (f"{category}.jpg", b"fake-image", "image/jpeg")},
    )
    assert response.status_code == 201
    return response.json()


def _attach_to_daily_log(client, log_id: int, *, category: str = "ultrasound", **overrides):
    data = {
        "media_type": "video",
        "category": category,
        "note": f"摸摸的 {category} 附件",
    }
    data.update(overrides)
    response = client.post(
        f"/daily-logs/{log_id}/attachments",
        data=data,
        files={"file": (f"{category}.mp4", b"fake-video", "video/mp4")},
    )
    assert response.status_code == 201
    return response.json()


def test_pet_crud_list_keyword_and_include_deleted(client, momo_pet):
    other_pet = _create_pet(client)

    listed = client.get("/pets")
    assert listed.status_code == 200
    assert {pet["id"] for pet in listed.json()} == {momo_pet["id"], other_pet["id"]}

    fetched = client.get(f"/pets/{momo_pet['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["name"] == "摸摸"

    updated = client.patch(
        f"/pets/{momo_pet['id']}",
        json={"breed": "橘貓", "notes": "patros 50mg 需留意，體重約 4.3kg"},
    )
    assert updated.status_code == 200
    assert updated.json()["breed"] == "橘貓"

    keyword = client.get("/pets", params={"keyword": "patros"})
    assert keyword.status_code == 200
    assert [pet["id"] for pet in keyword.json()] == [momo_pet["id"]]

    deleted = delete_with_preview(
        client,
        f"/pets/{other_pet['id']}",
        reason="重複建立另一隻寵物",
    )
    assert deleted.status_code == 200
    assert deleted.json()["deleted_at"] is not None

    hidden = client.get("/pets")
    assert hidden.status_code == 200
    assert {pet["id"] for pet in hidden.json()} == {momo_pet["id"]}

    include_deleted = client.get("/pets", params={"include_deleted": "true", "keyword": "術後"})
    assert include_deleted.status_code == 200
    assert [pet["id"] for pet in include_deleted.json()] == [other_pet["id"]]

    deleted_get = client.get(f"/pets/{other_pet['id']}")
    assert deleted_get.status_code == 404

    deleted_get_included = client.get(
        f"/pets/{other_pet['id']}",
        params={"include_deleted": "true"},
    )
    assert deleted_get_included.status_code == 200
    assert deleted_get_included.json()["delete_reason"] == "重複建立另一隻寵物"


def test_medical_record_get_update_delete_and_include_deleted(client, momo_pet):
    pet_id = momo_pet["id"]
    record = _create_medical_record(client, pet_id)

    fetched = client.get(f"/medical-records/{record['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["diagnosis"] == "腸胃不適"

    updated = client.patch(
        f"/medical-records/{record['id']}",
        json={
            "diagnosis": "腸胃炎追蹤",
            "prescription": "patros 25mg bid",
            "tags": ["腸胃", "劑量修正"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["prescription"] == "patros 25mg bid"
    assert updated.json()["tags"] == ["腸胃", "劑量修正"]

    deleted = delete_with_preview(
        client,
        f"/medical-records/{record['id']}",
        reason="時間輸入錯誤",
    )
    assert deleted.status_code == 200
    assert deleted.json()["delete_reason"] == "時間輸入錯誤"

    assert client.get(f"/medical-records/{record['id']}").status_code == 404

    included_get = client.get(
        f"/medical-records/{record['id']}",
        params={"include_deleted": "true"},
    )
    assert included_get.status_code == 200
    assert included_get.json()["deleted_at"] is not None

    hidden_search = client.get(f"/pets/{pet_id}/medical-records", params={"keyword": "patros"})
    assert hidden_search.status_code == 200
    assert hidden_search.json() == []

    included_search = client.get(
        f"/pets/{pet_id}/medical-records",
        params={"keyword": "patros", "include_deleted": "true"},
    )
    assert included_search.status_code == 200
    assert [item["id"] for item in included_search.json()] == [record["id"]]


def test_daily_log_get_update_and_appetite_energy_tag_filters(client, momo_pet):
    pet_id = momo_pet["id"]
    log = _create_daily_log(client, pet_id)
    _create_daily_log(
        client,
        pet_id,
        logged_at="2026-06-08T08:10:00+08:00",
        content="摸摸早上精神明顯較好，願意吃完早餐",
        appetite="good",
        energy="high",
        medication_note=None,
        tags=["活動力"],
    )

    fetched = client.get(f"/daily-logs/{log['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["weight_value"] == 4.3

    updated = client.patch(
        f"/daily-logs/{log['id']}",
        json={
            "content": "剛剛那筆不是晚上 8:32，是 8:22",
            "logged_at": "2026-06-07T20:22:00+08:00",
            "energy": "normal",
            "tags": ["食慾", "用藥", "修正"],
        },
    )
    assert updated.status_code == 200
    assert updated.json()["energy"] == "normal"

    appetite = client.get(f"/pets/{pet_id}/daily-logs", params={"appetite": "poor"})
    assert appetite.status_code == 200
    assert [item["id"] for item in appetite.json()] == [log["id"]]

    energy = client.get(f"/pets/{pet_id}/daily-logs", params={"energy": "normal"})
    assert energy.status_code == 200
    assert [item["id"] for item in energy.json()] == [log["id"]]

    tag = client.get(f"/pets/{pet_id}/daily-logs", params={"tag": "修正"})
    assert tag.status_code == 200
    assert [item["id"] for item in tag.json()] == [log["id"]]


def test_attachment_get_update_delete_and_manual_ocr(client, momo_pet):
    record = _create_medical_record(client, momo_pet["id"])
    attachment = _attach_to_medical_record(client, record["id"], category="blood_test")
    assert attachment["ocr_status"] == "none"

    fetched = client.get(f"/attachments/{attachment['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["category"] == "blood_test"

    updated = client.patch(
        f"/attachments/{attachment['id']}",
        json={
            "extracted_text": "血檢 WBC 正常，肝腎指數待追蹤",
            "note": "手動補上 OCR 文字",
        },
    )
    assert updated.status_code == 200
    assert updated.json()["ocr_status"] == "manual"
    assert "WBC" in updated.json()["extracted_text"]

    deleted = delete_with_preview(
        client,
        f"/attachments/{attachment['id']}",
        reason="附件上傳錯誤",
    )
    assert deleted.status_code == 200
    assert deleted.json()["delete_reason"] == "附件上傳錯誤"

    assert client.get(f"/attachments/{attachment['id']}").status_code == 404

    included = client.get(
        f"/attachments/{attachment['id']}",
        params={"include_deleted": "true"},
    )
    assert included.status_code == 200
    assert included.json()["deleted_at"] is not None

    record_default = client.get(f"/medical-records/{record['id']}")
    assert record_default.status_code == 200
    assert record_default.json()["attachments"] == []

    record_with_deleted = client.get(
        f"/medical-records/{record['id']}",
        params={"include_deleted": "true"},
    )
    assert record_with_deleted.status_code == 200
    assert [item["id"] for item in record_with_deleted.json()["attachments"]] == [attachment["id"]]


def test_multi_pet_isolation_for_records_logs_and_timeline(client, momo_pet):
    other_pet = _create_pet(client, name="小花", notes="另一隻寵物也有用藥紀錄")
    momo_record = _create_medical_record(client, momo_pet["id"], diagnosis="腸胃不適")
    other_record = _create_medical_record(
        client,
        other_pet["id"],
        diagnosis="耳朵感染",
        prescription="patros 50mg qd",
        tags=["耳朵"],
    )
    momo_log = _create_daily_log(client, momo_pet["id"])
    other_log = _create_daily_log(
        client,
        other_pet["id"],
        content="小花晚上使用 patros 50mg",
        appetite="normal",
        energy="normal",
        tags=["用藥"],
    )

    momo_records = client.get(
        f"/pets/{momo_pet['id']}/medical-records",
        params={"keyword": "patros"},
    )
    assert momo_records.status_code == 200
    assert [item["id"] for item in momo_records.json()] == [momo_record["id"]]
    assert other_record["id"] not in [item["id"] for item in momo_records.json()]

    other_logs = client.get(
        f"/pets/{other_pet['id']}/daily-logs",
        params={"keyword": "patros"},
    )
    assert other_logs.status_code == 200
    assert [item["id"] for item in other_logs.json()] == [other_log["id"]]
    assert momo_log["id"] not in [item["id"] for item in other_logs.json()]

    timeline = client.get(f"/pets/{momo_pet['id']}/timeline", params={"keyword": "patros"})
    assert timeline.status_code == 200
    assert {event["pet_id"] for event in timeline.json()} == {momo_pet["id"]}


def test_timeline_event_type_include_deleted_and_category_interactions(client, momo_pet):
    pet_id = momo_pet["id"]
    blood_record = _create_medical_record(client, pet_id)
    _attach_to_medical_record(client, blood_record["id"], category="blood_test")
    daily_log = _create_daily_log(client, pet_id)
    _attach_to_daily_log(client, daily_log["id"], category="ultrasound")
    deleted_xray_record = _create_medical_record(
        client,
        pet_id,
        visit_at="2026-06-06T11:00:00+08:00",
        diagnosis="作廢的 X 光病歷",
        prescription=None,
        tags=["xray"],
    )
    _attach_to_medical_record(client, deleted_xray_record["id"], category="xray")
    delete_response = delete_with_preview(
        client,
        f"/medical-records/{deleted_xray_record['id']}",
        reason="那筆病歷打錯了，請作廢",
    )
    assert delete_response.status_code == 200

    medical_only = client.get(f"/pets/{pet_id}/timeline", params={"event_type": "medical"})
    assert medical_only.status_code == 200
    assert [event["source_id"] for event in medical_only.json()] == [blood_record["id"]]

    daily_only = client.get(f"/pets/{pet_id}/timeline", params={"event_type": "daily"})
    assert daily_only.status_code == 200
    assert [event["source_id"] for event in daily_only.json()] == [daily_log["id"]]

    blood_timeline = client.get(f"/pets/{pet_id}/timeline", params={"category": "blood_test"})
    assert blood_timeline.status_code == 200
    assert [(event["event_type"], event["source_id"]) for event in blood_timeline.json()] == [
        ("medical", blood_record["id"])
    ]

    ultrasound_timeline = client.get(f"/pets/{pet_id}/timeline", params={"category": "ultrasound"})
    assert ultrasound_timeline.status_code == 200
    assert [(event["event_type"], event["source_id"]) for event in ultrasound_timeline.json()] == [
        ("daily", daily_log["id"])
    ]

    assert client.get(f"/pets/{pet_id}/timeline", params={"category": "xray"}).json() == []
    assert (
        client.get(
            f"/pets/{pet_id}/timeline",
            params={"event_type": "daily", "category": "blood_test"},
        ).json()
        == []
    )

    included_xray = client.get(
        f"/pets/{pet_id}/timeline",
        params={"category": "xray", "include_deleted": "true"},
    )
    assert included_xray.status_code == 200
    assert [(event["event_type"], event["source_id"]) for event in included_xray.json()] == [
        ("medical", deleted_xray_record["id"])
    ]
    assert included_xray.json()[0]["data"]["deleted_at"] is not None
    assert included_xray.json()[0]["attachments"][0]["category"] == "xray"


def test_validation_and_not_found_errors(client, momo_pet):
    assert client.get("/pets/999").status_code == 404
    assert client.get("/medical-records/999").status_code == 404
    assert client.get("/daily-logs/999").status_code == 404
    assert client.get("/attachments/999").status_code == 404

    bad_pet_owner = client.post(
        "/pets/999/daily-logs",
        json={
            "logged_at": "2026-06-07T20:32:00+08:00",
            "content": "不存在寵物的日常紀錄",
        },
    )
    assert bad_pet_owner.status_code == 404

    invalid_daily_enum = client.post(
        f"/pets/{momo_pet['id']}/daily-logs",
        json={
            "logged_at": "2026-06-07T20:32:00+08:00",
            "content": "摸摸今天食慾不振",
            "appetite": "ravenous",
        },
    )
    assert invalid_daily_enum.status_code == 422

    record = _create_medical_record(client, momo_pet["id"])
    invalid_attachment_enum = client.post(
        f"/medical-records/{record['id']}/attachments",
        data={"media_type": "image", "category": "ct_scan"},
        files={"file": ("scan.jpg", b"fake-image", "image/jpeg")},
    )
    assert invalid_attachment_enum.status_code == 422

    assert (
        client.get(f"/pets/{momo_pet['id']}/medical-records", params={"limit": 0}).status_code
        == 400
    )
    assert (
        client.get(f"/pets/{momo_pet['id']}/daily-logs", params={"page": 0}).status_code
        == 400
    )
    assert client.get(f"/pets/{momo_pet['id']}/timeline", params={"limit": 0}).status_code == 400

# API / MCP 規格（第一版草稿）

本文件定義第一版以 agent 操作為主的 API / MCP tool 邊界。第一版重點不是前端 UI，而是讓 agent 能穩定地寫入、讀取、查詢、整理寵物健康資料。

註：以下內容已依目前程式碼實作更新。若文件中的「建議」與行為描述衝突，以目前列出的已實作行為為準。

## 設計原則

1. 以 MCP tool 為主要操作介面
2. API 命名以資源導向為主，MCP tool 命名以任務導向為主
3. 資料操作要支援多寵物
4. 查詢要支援時間、關鍵字、分類
5. 刪除採 soft delete
6. 預留 OCR 相關欄位，但第一版不做自動 OCR

---

## 一、主要資料資源

### 1. Pet
欄位建議：
- id
- name
- species
- breed
- sex
- birth_date
- microchip_number
- notes
- created_at
- updated_at
- deleted_at (nullable)
- delete_reason (nullable)

### 2. MedicalRecord
欄位建議：
- id
- pet_id
- visit_at
- hospital_name
- doctor_name
- diagnosis
- prescription
- note
- weight_value
- weight_unit
- tags[]
- created_at
- updated_at
- deleted_at (nullable)
- delete_reason (nullable)

### 3. DailyLog
欄位建議：
- id
- pet_id
- logged_at
- content
- appetite
- energy
- stool
- medication_note
- weight_value
- weight_unit
- tags[]
- created_at
- updated_at
- deleted_at (nullable)
- delete_reason (nullable)

### 4. MediaAttachment
欄位建議：
- id
- owner_type (medical_record / daily_log)
- owner_id
- media_type (image / video)
- category (blood_test / xray / ultrasound / prescription / note / daily / other)
- file_name
- storage_path
- local_file_path
- mime_type
- captured_at (nullable)
- extracted_text (nullable)
- ocr_status (none / manual / pending / done)
- note (nullable)
- created_at
- updated_at
- deleted_at (nullable)
- delete_reason (nullable)

### Read response visibility metadata
所有主要 read response 目前都包含 `visibility`：
```json
{
  "deleted": false,
  "hidden_by_ancestor": false,
  "hidden_by": null
}
```

`include_deleted=true` 會回傳直接 soft-deleted 的資源，也會回傳因祖先資源被刪除而預設不可見的子資源。後者會標示 `hidden_by_ancestor=true` 與 `hidden_by`。

---

## 二、REST API 草稿

### Pets

#### POST /pets
建立寵物資料。

Request body 範例：
```json
{
  "name": "摸摸",
  "species": "cat",
  "breed": "米克斯",
  "sex": "female",
  "birth_date": "2021-03-12",
  "microchip_number": "900123456789012",
  "notes": "對某些藥物較敏感"
}
```

#### GET /pets
列出所有未刪除寵物。

可支援 query：
- keyword
- include_deleted=false

#### GET /pets/{pet_id}
取得單一寵物詳細資料。

Query：
- include_deleted=false

#### PATCH /pets/{pet_id}
修改寵物資料。

#### DELETE /pets/{pet_id}
soft delete 寵物。

必須先呼叫：
- `POST /pets/{pet_id}/delete-preview`

刪除 request body：
```json
{
  "reason": "重複建立",
  "confirm_token": "preview-token"
}
```

目前行為：
- `reason` 可省略
- `confirm_token` 必填，且為一次性 token
- 回傳 soft delete 後的 pet 資料

Restore：
- `POST /pets/{pet_id}/restore-preview`
- `POST /pets/{pet_id}/restore`，body 為 `{"confirm_token": "preview-token"}`

---

### Medical Records

#### POST /pets/{pet_id}/medical-records
建立病歷。

Request body 範例：
```json
{
  "visit_at": "2026-06-07T14:30:00+08:00",
  "hospital_name": "安心動物醫院",
  "doctor_name": "王醫師",
  "diagnosis": "腸胃不適",
  "prescription": "patros 50mg bid",
  "note": "食慾差，建議觀察三天",
  "weight_value": 4.3,
  "weight_unit": "kg",
  "tags": ["腸胃", "回診"]
}
```

#### GET /pets/{pet_id}/medical-records
查詢某寵物病歷。

Query 建議：
- start
- end
- keyword
- tag
- category
- include_deleted=false
- sort=visit_at_desc
- limit（預設 100）
- page（預設 1）

目前已實作：
- `sort` 目前支援 descending / ascending 語意；預設 `visit_at_desc`
- `limit` / `page` 為目前正式分頁方式，尚未實作 cursor

#### GET /medical-records/{record_id}
取得單筆病歷。

Query：
- include_deleted=false

#### PATCH /medical-records/{record_id}
修改病歷。

#### DELETE /medical-records/{record_id}
soft delete 病歷。

Request body：
```json
{
  "reason": "時間輸入錯誤",
  "confirm_token": "preview-token"
}
```

目前行為：
- 需先呼叫 `POST /medical-records/{record_id}/delete-preview`
- `reason` 可省略
- `confirm_token` 必填，且為一次性 token
- 回傳 soft delete 後的病歷資料

Restore：
- `POST /medical-records/{record_id}/restore-preview`
- `POST /medical-records/{record_id}/restore`

---

### Daily Logs

#### POST /pets/{pet_id}/daily-logs
建立日常紀錄。

Request body 範例：
```json
{
  "logged_at": "2026-06-07T20:32:00+08:00",
  "content": "今天食慾不振，活動力偏低",
  "appetite": "poor",
  "energy": "low",
  "stool": "normal",
  "medication_note": "patros 50mg, xxx 100mg",
  "weight_value": 4.3,
  "weight_unit": "kg",
  "tags": ["食慾", "用藥"]
}
```

#### GET /pets/{pet_id}/daily-logs
查詢某寵物日常紀錄。

Query 建議：
- start
- end
- keyword
- tag
- appetite
- energy
- include_deleted=false
- sort=logged_at_desc
- category
- limit（預設 100）
- page（預設 1）

目前已實作：
- 可依 `appetite` / `energy` / `tag` / `category` 過濾
- `limit` / `page` 為目前正式分頁方式，尚未實作 cursor

#### GET /daily-logs/{log_id}
取得單筆日常紀錄。

Query：
- include_deleted=false

#### PATCH /daily-logs/{log_id}
修改日常紀錄。

#### DELETE /daily-logs/{log_id}
soft delete 日常紀錄。

目前行為：
- 需先呼叫 `POST /daily-logs/{log_id}/delete-preview`
- `reason` 可省略
- `confirm_token` 必填，且為一次性 token
- 回傳 soft delete 後的日常紀錄資料

Restore：
- `POST /daily-logs/{log_id}/restore-preview`
- `POST /daily-logs/{log_id}/restore`

---

### Media Attachments

#### POST /medical-records/{record_id}/attachments
上傳病歷附件。

上傳方式：
- multipart/form-data
- 檔案實際存於 storage / uploads
- 資料庫保留 metadata

欄位建議：
- file
- media_type
- category
- captured_at
- extracted_text (可選，手動填)
- note

#### POST /daily-logs/{log_id}/attachments
上傳日常紀錄附件。

#### GET /attachments/{attachment_id}
取得附件 metadata。

補充：
- `storage_path` 為儲存中的 metadata 路徑，可能是相對路徑
- `local_file_path` 為 server 解析後的絕對本機路徑，適合 agent 需要以 `MEDIA:<path>` 形式回傳圖片或影片到聊天平台時使用

Query：
- include_deleted=false

#### PATCH /attachments/{attachment_id}
修改附件分類、備註、手動 OCR 文字。

目前已實作：
- 可更新 `media_type`
- 可更新 `category`
- 可更新 `captured_at`
- 可更新 `extracted_text`
- 可更新 `ocr_status`
- 可更新 `note`

補充：
- REST upload 若有帶 `extracted_text` 且未指定 `ocr_status`，系統會自動將 `ocr_status` 設為 `manual`

#### DELETE /attachments/{attachment_id}
soft delete 附件。

目前行為：
- 需先呼叫 `POST /attachments/{attachment_id}/delete-preview`
- `reason` 可省略
- `confirm_token` 必填，且為一次性 token
- 回傳 soft delete 後的附件 metadata

Restore：
- `POST /attachments/{attachment_id}/restore-preview`
- `POST /attachments/{attachment_id}/restore`

---

### Timeline / Unified Query

#### GET /pets/{pet_id}/timeline
取得某隻寵物的統一健康時間軸。

Query 建議：
- start
- end
- keyword
- event_type=medical|daily|all
- category
- include_deleted=false
- sort=desc
- limit（預設 100）
- page（預設 1）

回傳應將 MedicalRecord 與 DailyLog 正規化成可統一顯示的 event schema。

---

## 三、MCP Tools 草稿

以下為建議的第一版 MCP tool 名稱與用途。

### Pet 相關
- create_pet
- list_pets
- get_pet
- update_pet
- delete_pet_preview
- delete_pet
- restore_pet_preview
- restore_pet

### Medical Record 相關
- create_medical_record
- search_medical_records
- get_medical_record
- update_medical_record
- delete_medical_record_preview
- delete_medical_record
- restore_medical_record_preview
- restore_medical_record

### Daily Log 相關
- create_daily_log
- search_daily_logs
- get_daily_log
- update_daily_log
- delete_daily_log_preview
- delete_daily_log
- restore_daily_log_preview
- restore_daily_log

### Attachment 相關
- attach_media_to_medical_record
- attach_media_to_daily_log
- get_attachment
- update_attachment
- delete_attachment_preview
- delete_attachment
- restore_attachment_preview
- restore_attachment

### Timeline / Summary
- get_pet_timeline
- summarize_pet_status

Attachment 相關工具：
- `attach_media_to_medical_record`
- `attach_media_to_daily_log`

目前在 MCP layer 中是以 `file_path` 指向本機檔案，不是 multipart upload。

---

## 四、MCP Tool 輸入輸出建議

### create_daily_log
Input 範例：
```json
{
  "pet_id": "pet_123",
  "logged_at": "2026-06-07T20:32:00+08:00",
  "content": "今天食慾不振，活動力偏低",
  "appetite": "poor",
  "energy": "low",
  "stool": "normal",
  "medication_note": "patros 50mg, xxx 100mg",
  "weight_value": 4.3,
  "weight_unit": "kg",
  "tags": ["食慾", "活動力", "用藥"]
}
```

Output 範例：
```json
{
  "id": "daily_001",
  "pet_id": "pet_123",
  "logged_at": "2026-06-07T20:32:00+08:00",
  "status": "created"
}
```

### search_medical_records
Input 範例：
```json
{
  "pet_id": "pet_123",
  "start": "2026-05-01T00:00:00+08:00",
  "end": "2026-06-30T23:59:59+08:00",
  "keyword": "血檢",
  "category": "blood_test",
  "include_deleted": false
}
```

### summarize_pet_status
Input 範例：
```json
{
  "pet_id": 1,
  "start": "2026-06-01T00:00:00+08:00",
  "end": "2026-06-30T23:59:59+08:00",
  "include_deleted": false
}
```

Output 會回傳結構化摘要，至少包含：
- `pet`
- `event_count`
- `medical_record_count`
- `daily_log_count`
- `latest_weight`
- `weights`
- `medication_notes`
- `appetite_values`
- `energy_values`

### MCP 附件工具輸入補充
`attach_media_to_medical_record` / `attach_media_to_daily_log` 目前輸入重點：
```json
{
  "record_id": 1,
  "file_path": "/absolute/path/to/blood-test.jpg",
  "media_type": "image",
  "category": "blood_test",
  "note": "2026-06-07 回診血檢"
}
```

`daily_log` 版本則改用 `log_id`。

---

## 五、刪除防呆建議

目前狀態：
- 已實作 soft delete
- 已實作 preview token / confirm token 的兩段式刪除與 restore

刪除與還原都採兩段式：
1. 先呼叫 `delete_*_preview` 或 `restore_*_preview`
2. preview 回傳 `target`、`action`、`summary`、`impact`、`confirm_token`、`expires_at`
3. 再呼叫 `delete_*` 或 `restore_*` 並帶入 `confirm_token`

Restore 只清除目標資源自己的 soft-delete 欄位，不會直接清除子資源的 `deleted_at`。

---

## 六、列舉值建議

### appetite
- good
- normal
- poor
- unknown

### energy
- high
- normal
- low
- unknown

### stool
- normal
- soft
- diarrhea
- constipation
- none
- unknown

### media_type
- image
- video

### attachment category
- blood_test
- xray
- ultrasound
- prescription
- note
- daily
- other

---

## 七、第一版不處理
- 自動 OCR pipeline
- 複雜權限控管
- 多使用者協作
- 報表匯出格式標準化
- LINE rich UI schema

---

## 八、與未來 LINE robot 的關係

第一版 API / MCP 設計應避免綁死在聊天平台表現層。LINE robot 可作為第二階段的 adapter：
- LINE 負責接收自然語言與上傳檔案
- Agent 負責理解與整理需求
- MCP tool / backend 負責資料存取與摘要

因此第一版 API / MCP 應優先追求：
- 穩定資料模型
- 清楚工具介面
- 可查詢與可摘要

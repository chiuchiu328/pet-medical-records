# Pet Medical Records

寵物健康／病歷管理系統（第一版規格草稿）。

本專案是給單一使用者自用的系統，但需要支援多隻寵物。第一版優先提供給 agent 透過 MCP tool 操作；未來再擴充成可搭配 LINE robot 的互動與更精美的報表呈現。

## 專案目標

建立一個可管理多隻寵物的健康紀錄系統，將「病歷」與「日常狀態」統一整理成可查詢、可追蹤、可摘要的健康時間軸。

第一版重點：
- 支援多隻寵物
- 支援病歷紀錄與日常紀錄
- 支援圖片／影片附件
- 支援依時間、寵物、關鍵字查詢
- 支援體重與用藥等可隨時間變化的資訊
- 支援 soft delete，避免誤刪資料
- 以 MCP tool 為主要操作介面

## 使用情境

此系統主要是為了記錄：
- 寵物看診病歷
- 日常觀察
- 用藥狀態
- 體重變化
- 血檢、X 光、超音波等附件資料

未來 agent 應能協助完成：
- 幫某隻貓新增病歷
- 查詢最近 30 天內的所有病歷與日常紀錄
- 找出特定檢查類型（例如血檢、X 光）
- 整理近期食慾、精神、用藥與體重狀態
- 生成摘要報告給使用者或 LINE robot 呈現

## 核心設計原則

### 1. 多寵物支援
雖然只有一位使用者，但會管理多隻寵物，因此所有病歷與日常紀錄都必須明確綁定到特定寵物。

### 2. 健康時間軸
整個系統可視為「寵物健康時間軸系統」，其中包含兩種主要事件：
- Medical Record：醫療事件
- Daily Log：日常事件

### 3. 附件分成兩種概念
附件需要同時記錄：
- 媒體格式：image / video
- 內容分類：blood_test / xray / ultrasound / prescription / note / daily / other

### 4. OCR 第一版不自動化
第一版先不做自動 OCR，但會預留欄位讓使用者或 agent 可手動補入擷取文字。

### 5. 刪除採 soft delete
醫療與日常資料都不建議第一版做永久刪除，應採用 soft delete：
- 預設查詢不顯示已刪除資料
- 仍保留復原可能
- 記錄刪除時間與原因

## 第一版功能範圍

### A. 寵物資料管理
每隻寵物至少包含：
- 名字
- 品種
- 性別
- 生日
- 晶片號碼
- 備註（可選）

注意：
- 體重不是單純靜態欄位
- 體重要能在病歷與日常紀錄中隨時間記錄
- 若未來要加 current_weight，可當快取欄位使用，但資料真實來源仍應是歷史紀錄

### B. 病歷紀錄
每筆病歷建議包含：
- 寵物 ID
- 看診日期時間
- 醫院名稱
- 醫生名稱
- 診斷結果
- 用藥／處方箋
- 備註／病摘
- 體重（可選）
- 關鍵字／標籤（可選）
- 附件（圖片／影片）
- OCR 預留欄位（例如 extracted_text）

病歷附件可能是：
- 血檢資料圖片
- X 光圖片
- 超音波圖片／影片
- 醫生病摘圖片
- 處方箋圖片

### C. 日常紀錄
每筆日常紀錄建議包含：
- 寵物 ID
- 紀錄時間
- 自由文字內容
- 食慾
- 精神
- 排便
- 用藥
- 體重
- 附件（圖片／影片）
- 關鍵字／標籤（可選）

日常紀錄範例：
- 摸摸早上 7:40 使用 patros 50mg
- 摸摸晚上 8:32 使用 patros 50mg, xxx 100mg
- 摸摸 體重 4.3kg
- 摸摸今天食慾不振，沒有太多活動力

### D. 查詢能力
第一版至少要支援：
- 依寵物查詢
- 依時間區間查詢
- 依關鍵字查詢
- 依紀錄類型查詢（病歷 / 日常）
- 依附件分類查詢（例如血檢、X 光、超音波）

### E. 修改與刪除
第一版建議支援：
- 編輯病歷
- 編輯日常紀錄
- 作廢／刪除紀錄（soft delete）
- 記錄 deleted_at / delete_reason

## 第一版不做的事
以下功能先不納入第一版，但需在架構上保留擴充可能：
- 自動 OCR
- 匯出正式報表
- 醫療時間軸 UI
- 疫苗／用藥提醒
- LINE robot 精美回覆
- 權限與多使用者系統

## 文件索引

- `docs/API.md`：第一版 API / MCP 規格
- `docs/scenario.md`：使用情境與 use case
- `docs/softwareArchitecture.md`：軟體架構草稿

## 第一版實作與執行

目前已包含第一版可執行後端：

- Python 3.13
- `uv` + `pyproject.toml`
- FastAPI REST API
- SQLite
- 本地 `uploads/` 附件儲存
- 最小 MCP-style stdio tool layer
- pytest 測試

目前已實作的功能重點：

- Pet / Medical Record / Daily Log / Attachment 的 REST CRUD
- Timeline 統一查詢（整合 medical + daily）
- preview + confirm token 的 safe soft delete / restore
- ancestor-aware `include_deleted` 與 `visibility` metadata
- `page` / `limit` 分頁
- keyword / tag / category / appetite / energy 等篩選
- MCP tools 對齊主要資料操作與摘要查詢
- `summarize_pet_status` 提供給 agent 的結構化摘要
- MCP 附件工具支援以本機 `file_path` 匯入檔案

安裝依賴：

```sh
uv sync
```

啟動 REST API：

```sh
uv run uvicorn app.main:app --reload
```

預設會使用：

- SQLite database: `pet_medical_records.db`
- Upload directory: `uploads/`

可用環境變數覆蓋：

```sh
PET_MEDICAL_RECORDS_DATABASE_URL=sqlite:///./local.db
PET_MEDICAL_RECORDS_UPLOAD_DIR=./uploads
```

FastAPI 文件頁在：

- `http://127.0.0.1:8000/docs`

啟動 MCP-style stdio server：

```sh
uv run python -m app.mcp.server
```

此 server 支援 `initialize`、`tools/list`、`tools/call` JSON-RPC 方法，工具名稱對齊 `docs/API.md` 的第一版 MCP tools，例如：

- `create_pet` / `list_pets` / `get_pet` / `update_pet` / `delete_pet`
- `create_medical_record` / `search_medical_records` / `get_medical_record` / `update_medical_record` / `delete_medical_record`
- `create_daily_log` / `search_daily_logs` / `get_daily_log` / `update_daily_log` / `delete_daily_log`
- `attach_media_to_medical_record` / `attach_media_to_daily_log`
- `get_attachment` / `update_attachment` / `delete_attachment`
- `get_pet_timeline`
- `summarize_pet_status`

其中 MCP 的附件工具目前使用 `file_path` 指向本機檔案，由 server 複製到 `uploads/` 並建立 metadata；REST API 則維持 multipart upload。

執行測試：

```sh
uv run pytest
```

## 第一版成功標準

若第一版完成，至少應能讓 agent 透過 MCP tool：
- 建立與查詢多隻寵物
- 新增病歷與日常紀錄
- 為紀錄附加圖片／影片
- 查詢某隻寵物某時間區間內的醫療與日常資料
- 根據關鍵字或附件分類找出特定資料
- 在誤輸入時安全地編輯或作廢資料

## 後續方向

第二版可逐步擴充：
- 自動 OCR / 文字擷取流程
- 體重、用藥、食慾等摘要整理
- 可分享或可視化的報表輸出
- LINE robot 整合與精美回覆
- 醫療時間軸與趨勢分析

# Software Architecture（第一版草稿）

本文件描述第一版的軟體架構方向。第一版以 agent + MCP tool 為主，不急著做完整前端 UI，而是先建立穩定、可擴充的資料與服務層。

## 一、架構目標

第一版架構要滿足：
- 支援多隻寵物
- 支援病歷與日常紀錄
- 支援圖片／影片附件
- 支援 agent 透過 MCP tool 操作
- 支援未來接 LINE robot
- 支援未來加入 OCR、摘要、報表與提醒功能

---

## 二、整體架構概念

建議採用分層式架構：

1. Interface Layer
2. Application Layer
3. Domain Layer
4. Infrastructure Layer
5. Storage Layer

### 1. Interface Layer
負責接收外部操作請求。

第一版主要包含：
- MCP server / MCP tools
- REST API（若需要直接對接）

未來可新增：
- LINE robot adapter
- Web UI / admin UI

### 2. Application Layer
負責用例流程與服務協調，例如：
- 建立寵物
- 建立病歷
- 新增日常紀錄
- 附件上傳
- 時間軸查詢
- 摘要資料整理

這一層的重點是：
- 不直接綁死前端形式
- 把業務流程封裝成清楚的 service

### 3. Domain Layer
負責核心商業概念與規則。

主要 domain objects：
- Pet
- MedicalRecord
- DailyLog
- MediaAttachment
- TimelineEvent（查詢投影模型）

核心規則例如：
- 所有紀錄都必須屬於某隻寵物
- 附件必須掛在病歷或日常紀錄上
- 刪除預設為 soft delete
- 體重為可隨時間變化之資料，不作為單一真值欄位

### 4. Infrastructure Layer
負責技術實作細節，例如：
- 資料庫存取
- ORM / repository
- 本地檔案儲存
- 未來 OCR adapter
- 未來 LINE adapter

### 5. Storage Layer
包含：
- SQLite（第一版）
- 本地檔案系統 uploads/

未來可替換為：
- PostgreSQL
- Object Storage（S3 相容）

---

## 三、建議元件

### A. Pet Service
負責：
- 建立寵物
- 修改寵物
- 查詢寵物
- 刪除／作廢寵物

### B. Medical Record Service
負責：
- 建立病歷
- 查詢病歷
- 修改病歷
- 作廢病歷
- 關聯附件

### C. Daily Log Service
負責：
- 建立日常紀錄
- 查詢日常紀錄
- 修改日常紀錄
- 作廢日常紀錄
- 關聯附件

### D. Attachment Service
負責：
- 檔案接收
- 檔案儲存
- metadata 寫入資料庫
- 分類／備註／手動 OCR 文字更新
- soft delete

### E. Timeline Query Service
負責：
- 將 Medical Record 與 Daily Log 做統一查詢
- 依時間排序
- 可依關鍵字、分類篩選
- 輸出適合 agent 摘要的資料格式

### F. Summary Service（可先留介面）
第一版可先不完整實作，但建議預留：
- 寵物近期健康摘要
- 體重趨勢摘要
- 用藥整理摘要
- 看診前後對照摘要

---

## 四、資料模型關係

建議核心關係如下：

- Pet 1:N MedicalRecord
- Pet 1:N DailyLog
- MedicalRecord 1:N MediaAttachment
- DailyLog 1:N MediaAttachment

其中 MediaAttachment 可透過 owner_type + owner_id 或明確外鍵方式設計。

### 選項 A：Polymorphic association
欄位：
- owner_type
- owner_id

優點：
- 彈性高
- 容易擴充到更多事件類型

缺點：
- 關聯完整性需要額外控制

### 選項 B：兩種 nullable foreign keys
欄位：
- medical_record_id nullable
- daily_log_id nullable

優點：
- 關聯明確
- 比較直觀

缺點：
- 若未來事件類型變多，schema 容易膨脹

第一版若求簡潔，我傾向：
- 若 ORM 支援得好，可用 polymorphic association
- 若優先考量實作直觀，可先用兩種 nullable foreign keys

---

## 五、查詢模型

### 1. 原始資料查詢
分別查：
- medical_records
- daily_logs
- attachments

### 2. 統一時間軸查詢
建立一個 application-level projection：
- event_type
- event_time
- pet_id
- summary_text
- tags
- attachments
- source_id

這樣 agent 可直接用同一種 schema 讀取病歷與日常資料。

---

## 六、刪除策略

所有主要資源已支援：
- deleted_at
- delete_reason

查詢預設：
- 不顯示直接 deleted 資料
- 不顯示因祖先被 deleted 而失去有效可見性的資料

必要時可使用：
- include_deleted=true
- read response 的 visibility metadata
- delete-preview / delete confirm token
- restore-preview / restore confirm token

Restore 只清除目標資源自己的 delete marker，不會 cascade 還原子資源。Pet 被刪除時不會 cascade 寫入子資源；service layer 以有效可見性規則隱藏 MedicalRecord、DailyLog 與附件。

---

## 七、OCR 設計預留

第一版不自動做 OCR，但架構要能承接未來流程。

建議附件欄位預留：
- extracted_text
- ocr_status
- ocr_source
- ocr_updated_at

未來可加的流程：
1. 附件上傳
2. OCR worker / service 處理
3. 擷取結果寫回 attachment
4. 讓 agent 可搜尋與摘要

第一版則先允許：
- 手動填入 extracted_text

---

## 八、MCP 與 LINE 的關係

### 第一版
主要操作路徑：
- User -> Agent -> MCP Tool -> Application Service -> Database / Storage

### 第二版
可增加：
- User -> LINE robot -> Agent -> MCP Tool -> Backend

因此 backend 不應依賴特定聊天平台。

MCP tool 的角色應是：
- 暴露穩定、清楚、可被 agent 理解的操作邊界
- 將自然語言互動與資料儲存切開

---

## 九、技術選型建議（第一版）

### 建議
- Language: Python 3.13
- API framework: FastAPI
- Database: SQLite
- ORM: SQLAlchemy / SQLModel（二選一）
- Validation: Pydantic
- File storage: local filesystem
- Test: pytest
- Dependency management: uv

### 原因
- Python + FastAPI 對 MCP / agent 生態整合友善
- SQLite 足夠應付第一版自用場景
- 本地檔案儲存適合先快速落地
- 後續仍可平滑升級到 PostgreSQL + object storage

---

## 十、目錄建議

第一版建議目錄可朝這方向：

```text
project/
  README.md
  docs/
    API.md
    scenario.md
    softwareArchitecture.md
  app/
    main.py
    api/
    services/
    domain/
    repositories/
    models/
    schemas/
    storage/
    mcp/
  uploads/
  tests/
```

說明：
- `api/`：REST route
- `services/`：application services
- `domain/`：核心業務模型與規則
- `repositories/`：資料存取
- `models/`：ORM models
- `schemas/`：Pydantic request / response schemas
- `storage/`：附件檔案處理
- `mcp/`：MCP tool 定義與 adapter

---

## 十一、風險與注意事項

### 1. 自由文字過多
若所有內容都只用自由文字，未來搜尋與摘要會較弱。
因此第一版日常紀錄保留固定欄位（食慾、精神、排便、用藥、體重）是正確方向。

### 2. 附件很多時的存取
第一版用本地檔案系統可行，但之後可能需要：
- 檔名規則
- 目錄分層
- metadata 一致性檢查

### 3. 體重來源多處出現
體重可能出現在：
- 病歷
- 日常紀錄

這是合理的，但摘要層需要能統一整理成趨勢資料。

### 4. 刪除與修正的語意
對醫療相關紀錄，建議系統語意偏向：
- 作廢
- 修正
而不是無痕永久刪除。

---

## 十二、第一版結論

第一版最重要的不是 UI，而是建立一個：
- 穩定的資料模型
- 清楚的 MCP / API 邊界
- 可支援時間軸查詢的健康資料後端

只要這一層做好，之後：
- Agent 摘要
- OCR
- 報表
- LINE robot
都能自然地疊加上去。

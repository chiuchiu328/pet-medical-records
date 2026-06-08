# Runtime Environment Guide

本文件整理 `pet-medical-records` 的建議執行環境配置，特別針對目前的使用方式：

- 開發環境與執行環境分離
- Hermes 為主要 agent 執行環境
- MCP 維持 stdio，不改成 HTTP
- SQLite 與附件需要持久化保存

## 目標

目前建議將系統拆成兩個環境：

1. 開發環境
2. Hermes 執行環境

這樣做的目的：

- Hermes 不會直接讀到開發中的未完成變更
- 開發者可以先在本地驗證，再將穩定版本部署到 Hermes
- MCP server、資料庫、附件路徑都能固定，較接近 production 思維

## 環境分工

### 開發環境

建議用途：

- 修改程式碼
- 執行測試
- 驗證 REST API 與 MCP 行為

建議位置範例：

- `/home/alvis/docker/pet-medical-records`

開發環境可接受：

- 使用 repo 目錄下的本地 SQLite
- 使用 repo 目錄下的 `uploads/`
- 快速重啟與反覆修改

### Hermes 執行環境

建議用途：

- 提供 Hermes agent 使用 MCP tools
- 作為較穩定的執行中版本
- 只在驗證完成後更新

Hermes 執行環境中的 repo 應視為部署副本，而不是主要開發工作區。

## 建議目錄規劃

Hermes 的持久化根目錄目前為：

- `/opt/data`

建議將「程式碼」與「資料」分開：

```text
/opt/data/
  pet-medical-records/              # Hermes 執行中的 repo
  pet-medical-records-data/
    pet_medical_records.db          # SQLite 資料庫
    uploads/                        # 附件目錄
```

對應的 host bind mount 若為：

- `/home/alvis/.hermes:/opt/data`

則資料會實際持久化在：

- `/home/alvis/.hermes/pet-medical-records-data/pet_medical_records.db`
- `/home/alvis/.hermes/pet-medical-records-data/uploads/`

## 為什麼資料不要放在 repo 裡

雖然目前專案預設資料庫位置是 repo 下的 `pet_medical_records.db`，但在 Hermes 執行環境中，不建議繼續使用這個預設。

建議原因：

- repo 會更新，資料不應與部署程式碼混在一起
- `git pull`、切 branch、重建 repo 時比較不容易碰到資料
- SQLite 與附件檔案的備份位置更清楚
- 未來若改成 Web service 或其他部署方式，資料路徑更容易沿用

## MCP 為什麼維持 stdio

目前建議 MCP server 維持 stdio 方式，由 Hermes 直接啟動子程序：

- 不需要額外開 port
- 不需要額外做 HTTP 暴露
- 不需要在目前階段處理 API 認證、TLS、reverse proxy、CORS
- Hermes 是唯一 consumer 時，邊界最單純

這同時也有安全上的好處，因為：

- MCP server 不直接暴露在網路上
- 攻擊面比 HTTP service 小
- 目前不需要處理其他系統跨主機呼叫

除非未來有明確需求，例如：

- 其他系統也要直接調用 MCP
- 需要跨主機部署
- 要把 MCP server 與 Hermes 完全拆成獨立服務

否則第一版不建議將 MCP 改成 HTTP。

## Hermes MCP 設定建議

Hermes 應透過 `config.yaml` 中的 `mcp_servers` 啟動本專案的 stdio MCP server。

建議配置如下：

```yaml
mcp_servers:
  pet_medical_records:
    command: "/opt/data/pet-medical-records/.venv/bin/python"
    args: ["-m", "app.mcp.server"]
    cwd: "/opt/data/pet-medical-records"
    timeout: 120
    connect_timeout: 60
    env:
      PET_MEDICAL_RECORDS_DATABASE_URL: "sqlite:////opt/data/pet-medical-records-data/pet_medical_records.db"
      PET_MEDICAL_RECORDS_UPLOAD_DIR: "/opt/data/pet-medical-records-data/uploads"
```

說明：

- `command` 使用 Hermes 執行環境 repo 中的 Python
- `cwd` 固定在 Hermes 執行環境 repo
- `PET_MEDICAL_RECORDS_DATABASE_URL` 指向持久化資料庫
- `PET_MEDICAL_RECORDS_UPLOAD_DIR` 指向持久化附件目錄

## 更新流程建議

建議的工作流程如下：

1. 在開發環境修改程式碼
2. 在開發環境執行測試與驗證
3. commit 並推送穩定版本
4. 在 Hermes 執行環境 repo 中 `git pull`
5. 視需要更新依賴
6. 重新載入 MCP 或重啟 Hermes 相關流程

這種流程能保留：

- 開發中的自由度
- 執行中的穩定性
- 部署步驟的可預測性

## 需要持續注意的事項

### 1. SQLite 併發限制

第一版使用 SQLite 對單一使用者情境通常足夠，但之後如果同時有：

- Hermes agent 查詢或寫入
- Web UI 查詢或寫入
- 多筆附件上傳

就要開始留意 SQLite 的鎖競爭與寫入併發問題。

若未來 Web 使用量或資料操作頻率增加，可考慮改為 PostgreSQL。

### 2. 附件路徑必須讓 Hermes 看得到

目前 MCP 附件工具使用 `file_path`。

因此 Hermes 呼叫：

- `attach_media_to_medical_record`
- `attach_media_to_daily_log`

時，提供的檔案路徑必須是 Hermes container 內可存取的路徑。

若未來附件來源不只一處，需一併規劃 bind mount 或統一路徑。

### 3. Web 功能先保留擴充性，不先暴露

目前尚未決定是否要開發 Web，因此第一版建議：

- 先把 backend 與資料持久化整理好
- 先讓 Hermes + MCP 工作穩定
- Web 是否對外暴露、開哪些 port，等實際要做 Web 時再定

此時不需要為 Web 預先暴露新的對外 port。

## 目前結論

以目前需求來看，最穩定的執行方式是：

- 開發環境與 Hermes 執行環境分離
- Hermes 透過 stdio 啟動 MCP server
- SQLite 與 `uploads/` 放在 `/opt/data` 下的獨立資料目錄持久化
- 程式碼更新採「開發驗證完成後，再到 Hermes pull 更新」

這樣可以在不過度提前設計 Web 與外部安全機制的前提下，先把第一版系統的執行邊界與資料邊界整理清楚。

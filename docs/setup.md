# 部署與環境建置

## 前置服務

1. **[kime541200/ai-pose-gallery-zh](https://github.com/kime541200/ai-pose-gallery-zh)**：提供姿勢、服裝、人像 JSON 索引與圖片靜態資源的後端服務。
2. **ComfyUI**（選用，執行 `generate_image` 或 `prepare_comfyui_workflow` 時需要）：
   - 需安裝 `ComfyUI-GGUF` 與 `comfyui_controlnet_aux` 節點，以及 `Qwen-Image-Edit-2509` 模型（詳見 [ai-pose-gallery-zh 的 ComfyUI 配置說明](https://github.com/kime541200/ai-pose-gallery-zh/blob/main/docs/comfyui.md)）。
   - 若使用 [kime541200/comfyui-deploy](https://github.com/kime541200/comfyui-deploy)，可以 `PROFILE=pose-gallery docker compose up -d --build` 啟動。

## 1. 設定環境變數（`.env`）

複製 `.env.example` 為 `.env`，並依你的服務實際佈署的主機與 Port 調整：

```bash
cp .env.example .env
```

| 變數 | 預設值 | 說明 |
| --- | --- | --- |
| `PORT` | `8090` | 本 MCP Server 在宿主機對外發布的 Port（端點為 `http://127.0.0.1:${PORT}/mcp`） |
| `GALLERY_URL` | `http://host.docker.internal:8080` | MCP 容器連往 [ai-pose-gallery-zh](https://github.com/kime541200/ai-pose-gallery-zh) 的位址。若圖庫佈署在其他 Port（例如 `3000`）或遠端主機，請改為對應 URL |
| `GALLERY_PUBLIC_URL` | 自動由 `GALLERY_URL` 推導 | 回傳給使用者瀏覽器開啟的圖片網址前綴。留空時會自動將 `GALLERY_URL` 的 `host.docker.internal` 換成 `127.0.0.1` 並保留原 Port |
| `COMFYUI_URL` | `http://host.docker.internal:8188` | MCP 容器連往 ComfyUI 的位址（供上傳參考圖與執行生圖） |
| `COMFYUI_PUBLIC_URL` | 自動由 `COMFYUI_URL` 推導 | 回傳給使用者瀏覽器預覽生成結果的 ComfyUI 網址前綴 |
| `WORKFLOW_HOST_DIR` | `./tmp` | 匯出 ComfyUI API Workflow JSON 的宿主機目錄（掛載至容器內 `/app/workflows`） |

## 2. 以 Docker 啟動 MCP Server（Streamable HTTP）

```bash
docker compose up -d --build
curl -s http://127.0.0.1:${PORT:-8090}/health
```

健康檢查應回傳 `{"status":"ok","service":"ai-pose-gallery-mcp",...}`。

## 3. Agent MCP 設定

參考 `mcp_config.example.json`，在你的 Agent（如 Antigravity、Claude Code、Cursor 等）設定檔加入：

```json
{
  "mcpServers": {
    "ai-pose-gallery": {
      "url": "http://127.0.0.1:8090/mcp"
    }
  }
}
```

> 若修改過 `.env` 的 `PORT`，請將 `8090` 改為對應埠號。

## 4. 本地開發（不使用 Docker）

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e .

# Streamable HTTP 模式（可透過參數或環境變數指定圖庫與 ComfyUI 位址）
.venv/bin/ai-pose-gallery-mcp \
  --transport streamable-http \
  --port 8090 \
  --gallery-url http://127.0.0.1:8080 \
  --comfyui-url http://127.0.0.1:8188

# 或 stdio 模式
.venv/bin/ai-pose-gallery-mcp --transport stdio --gallery-url http://127.0.0.1:8080
```

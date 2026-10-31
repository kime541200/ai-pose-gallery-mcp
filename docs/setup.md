# 環境建置

前提：
- 已安裝 `uv`。
- `ai-pose-gallery-zh` 已啟動於 `http://127.0.0.1:8080`（或本機存在 `../ai-pose-gallery-zh/data`）。
- 若要執行 `prepare_comfyui_workflow`，`comfyui-deploy` 的 ComfyUI 容器（`PROFILE=pose-gallery`）須啟動於 `http://127.0.0.1:8188`。

## 1. 安裝套件

```bash
uv venv .venv
uv pip install --python .venv/bin/python -e .
```

## 2. MCP 設定

產生設定檔並放入所用 harness 的設定位置（設定完成後重啟 harness）：

```bash
mkdir -p .agents
sed "s|<REPO_DIR>|$PWD|g" mcp_config.example.json > .agents/mcp_config.json
```

環境變數：
- `GALLERY_URL`：`ai-pose-gallery-zh` 服務位址（預設 `http://127.0.0.1:8080`）。
- `GALLERY_DIR`：本機 `ai-pose-gallery-zh` 目錄路徑（當 HTTP 服務未啟動時作為讀取 fallback，並提供 `local_path` 方便 Agent 直接檢視圖檔）。
- `COMFYUI_URL`：ComfyUI 容器位址（預設 `http://127.0.0.1:8188`，供上傳參考圖使用）。

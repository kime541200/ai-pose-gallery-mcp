# ai-pose-gallery-mcp

為 [kime541200/ai-pose-gallery-zh](https://github.com/kime541200/ai-pose-gallery-zh)（AI 繪畫姿勢／服裝／人像參考圖庫）提供 **Streamable HTTP MCP Server**，讓 Coding Agent 或 LLM 客戶端能：

1. **模糊搜尋與互動挑選**：以自然語言（繁／簡中文、多關鍵詞、口語同義詞）檢索姿勢、服裝、人像參考圖，將候選圖片網址交由使用者確認。
2. **ComfyUI 多圖角色合成**：將選定的人像、服裝、姿勢參考圖自動上傳至使用者的 ComfyUI，透過 **Qwen-Image-Edit-2509** 直接執行生圖（`generate_image`）或匯出 API workflow JSON（`prepare_comfyui_workflow`）。

## 前置需求

使用本 MCP Server 需搭配以下服務：

1. **圖庫後端服務（必備）**：佈署並啟動 [kime541200/ai-pose-gallery-zh](https://github.com/kime541200/ai-pose-gallery-zh)。
2. **ComfyUI 服務（使用生圖功能時必備）**：自備已安裝 `Qwen-Image-Edit-2509` 相關模型與節點的 ComfyUI（可參考 [ai-pose-gallery-zh 的 ComfyUI 說明](https://github.com/kime541200/ai-pose-gallery-zh/blob/main/docs/comfyui.md)，或直接使用 [kime541200/comfyui-deploy](https://github.com/kime541200/comfyui-deploy) 的 `PROFILE=pose-gallery` 佈署）。

## 快速啟動（Docker）

```bash
cp .env.example .env
# 編輯 .env，將 GALLERY_URL 與 COMFYUI_URL 改為你實際佈署的位址與 Port
docker compose up -d --build
curl -s http://127.0.0.1:8090/health
```

在 Agent 的 `mcp_config.json` 加入 Streamable HTTP 端點：

```json
{
  "mcpServers": {
    "ai-pose-gallery": {
      "url": "http://127.0.0.1:8090/mcp"
    }
  }
}
```

- 完整佈署、環境變數與進階配置請見 [`docs/setup.md`](docs/setup.md)。
- Agent 操作規範請見 [`AGENTS.md`](AGENTS.md)。

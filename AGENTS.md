# ai-pose-gallery-mcp

透過 `ai-pose-gallery` MCP（Streamable HTTP）檢索 [kime541200/ai-pose-gallery-zh](https://github.com/kime541200/ai-pose-gallery-zh) 的人像、服裝、姿勢素材，並呼叫 ComfyUI 執行 `FLUX 3 Image Klein Distilled`（預設）或 `Qwen-Image-Edit-2509`（備選）多圖角色合成。若服務無法連線或回報找不到圖庫／ComfyUI，先讀 `docs/setup.md` 檢查 `.env` 的 `GALLERY_URL` 與 `COMFYUI_URL`。

## 互動與生圖流程

### 1. 模糊需求：先篩選、請使用者確認後再生圖

1. 呼叫 `get_facets` 取得可用的體系、分類、角度、髮長與畫風預設（`style_presets`）。
2. 依使用者描述分別呼叫 `search_portraits`、`search_costumes`、`search_poses`（各取 3–5 筆候選）。搜尋支援繁簡中文、多關鍵詞與口語同義詞。
3. 將候選清單的名稱、ID 與圖片連結（`image_url`）列給使用者確認；必要時呼叫 `compose_recipe_prompt` 預覽合成提示詞。
4. 使用者選定 ID 後，進入下方「明確需求」流程。

### 2. 明確需求：執行 ComfyUI 多圖合成生圖

依環境選擇以下任一方式執行：

- **方式 A（直接生圖，預設推薦）**：
  直接呼叫本 MCP 的 `generate_image(portrait_id, costume_id, pose_id, style_preset, ...)`。工具會自動從 `GALLERY_URL` 取得參考圖、轉成 PNG 上傳至 `COMFYUI_URL`、送出 workflow 並等待完成，回傳生成圖片的 `image_url`。
- **方式 B（匯出 Workflow 交由外部 ComfyUI MCP 執行）**：
  若環境另有配置 ComfyUI 管理 MCP（如 [kime541200/comfyui-agent](https://github.com/kime541200/comfyui-agent) 的 `comfyui-local`），可呼叫 `prepare_comfyui_workflow(...)` 取得 `workflow_path`，再交由外部 MCP 驗證與執行。

## 工作流注意事項

- 姿勢圖（素體白模）在 workflow 內會自動經 `DepthAnythingV2Preprocessor` 轉為 3D 深度輪廓圖（抹除素體關節線並完整保留立體朝向、極限透視與雙人交錯結構），ComfyUI 端須安裝 `comfyui_controlnet_aux`（若使用 `qwen-edit` 備選引擎則另需 `ComfyUI-GGUF`，見 [ai-pose-gallery-zh 的 ComfyUI 說明](https://github.com/kime541200/ai-pose-gallery-zh/blob/main/docs/comfyui.md) 或 [kime541200/comfyui-deploy](https://github.com/kime541200/comfyui-deploy) 的 `PROFILE=pose-gallery`）。
- 預設引擎為 `workflow_engine="flux3-klein"`（`FLUX 3 Image Klein Distilled (Int8)`，預設 `steps=16`、`cfg=1.0`）；若需切換為備選引擎可傳入 `workflow_engine="qwen-edit"`（4 步 Lightning LoRA，預設 `steps=4`、`cfg=1.0`）。

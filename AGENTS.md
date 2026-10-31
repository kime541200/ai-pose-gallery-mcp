# ai-pose-gallery-mcp

讓 Agent 經 `ai-pose-gallery` MCP 檢索 `ai-pose-gallery-zh` 的人像、服裝、姿勢素材，組出 `Qwen-Image-Edit-2509` 多圖合成 workflow，再交給 `comfyui-local` MCP（見 `../comfyui-agent/AGENTS.md`）執行生圖。MCP 無法連線或找不到圖庫時先讀 `docs/setup.md`。

## 互動與生圖流程

### 1. 模糊需求：先篩選、請使用者確認後再生圖

1. 呼叫 `get_facets` 取得可用的體系、分類、角度、髮長與畫風預設（`style_presets`）。
2. 依使用者描述分別呼叫 `search_portraits`、`search_costumes`、`search_poses`（各取 3–5 筆候選）。搜尋支援繁簡中文、多關鍵詞與口語同義詞。
3. 將候選清單的名稱、ID 與圖片連結（`local_path` 或 `image_url`）列給使用者確認；必要時呼叫 `compose_recipe_prompt` 預覽合成提示詞。
4. 使用者選定 ID 後，進入下方「明確需求」流程。

### 2. 明確需求：直接準備 workflow 並交給 ComfyUI 生圖

1. 呼叫 `prepare_comfyui_workflow(portrait_id, costume_id, pose_id, style_preset, ...)`：工具會自動將參考圖轉成 PNG 並上傳至 ComfyUI，寫出 workflow JSON 至 `workflow_path`（預設 `../comfyui-agent/tmp/pose-gallery-workflow.json`）。
2. 依 `../comfyui-agent/AGENTS.md` 流程，呼叫 `comfyui-local` MCP：
   - `validate_workflow(workflow_path=...)`（確認 `valid: true`、`error_count: 0`）
   - `run_workflow(workflow_path=..., wait=False)` → `job(action="wait")`

## 工作流注意事項

- 姿勢圖（素體白模）在 workflow 內會自動經 `DepthAnythingV2Preprocessor` → `DWPreprocessor` 轉為 OpenPose 關鍵點骨架，需要 ComfyUI 安裝 `comfyui_controlnet_aux`（對應 `comfyui-deploy` 的 `PROFILE=pose-gallery`）。
- 預設使用 4 步 Lightning LoRA（`steps=4`、`cfg=1.0`）。

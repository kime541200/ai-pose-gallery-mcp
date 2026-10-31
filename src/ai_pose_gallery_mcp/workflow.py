from __future__ import annotations

import copy
import io
import json
import os
import random
from pathlib import Path
from typing import Any

import httpx
from PIL import Image

from .catalog import GalleryCatalog

STYLE_PRESETS: dict[str, dict[str, str]] = {
    "none": {"label": "无预设（跟随参考图）", "prompt": ""},
    "realistic": {
        "label": "写实人像写真",
        "prompt": "写实商业摄影级质感，85mm 人像镜头，自然柔和光影，真实肌肤纹理与织物细节，8k 高清画质。",
    },
    "fashion": {
        "label": "日韩杂志画报",
        "prompt": "日韩时尚穿搭杂志画报风格，干净极简摄影棚背景，高级色调，突出人物颜值与服装剪裁。",
    },
    "film": {
        "label": "复古胶片写真",
        "prompt": "35mm 富士胶片摄影质感，轻微胶片颗粒，柔和复古暖调，自然街拍光影与电影呼吸感。",
    },
    "semi_real": {
        "label": "2.5D 游戏原画立绘",
        "prompt": "2.5D 半写实高精度游戏角色原画，唯美厚涂光影，精致五官与华丽布料金属质感。",
    },
    "anime": {
        "label": "日系二次元插画",
        "prompt": "日系精致二次元插画风格，细腻赛璐璐与厚涂光影过渡，动漫角色立绘质感，色彩通透干净。",
    },
    "cel_anime": {
        "label": "新海诚感动画电影",
        "prompt": "动画电影级画面质感，清澈高饱和光影，细腻体积光与发丝高光，干净唯美的动漫色彩。",
    },
    "manga": {
        "label": "日式黑白漫画网点",
        "prompt": "日本黑白漫画原稿风格，利落精准的G笔线稿，细腻漫画网点纸阴影与层次对比。",
    },
    "render3d": {
        "label": "3D 次世代角色渲染",
        "prompt": "Unreal Engine 5 / Octane Render 次世代 3D 角色渲染，细腻次表面散射肌肤材质，电影级布光。",
    },
    "chibi_box": {
        "label": "3D 潮玩手办质感",
        "prompt": "高品质 PVC 涂装完成品手办质感，柔和摄影棚柔光箱布光，精致材质高光与微距景深。",
    },
    "cyberpunk": {
        "label": "赛博朋克霓虹",
        "prompt": "赛博朋克科幻视觉风格，雨夜霓虹冷暖双色轮廓光，未来感材质反光与电影级氛围。",
    },
    "concept_sheet": {
        "label": "角色设定集立绘（纯白底）",
        "prompt": "标准角色设定集全身立绘，纯白干净无杂物背景，均匀漫反射布光，清晰展示全身服装结构与配饰细节。",
    },
}

WORKFLOW_TEMPLATE: dict[str, dict[str, Any]] = {
    "1": {
        "class_type": "UnetLoaderGGUF",
        "inputs": {"unet_name": "qwen-image-edit/Qwen-Image-Edit-2509-Q4_K_M.gguf"},
    },
    "2": {
        "class_type": "CLIPLoader",
        "inputs": {
            "clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
            "type": "qwen_image",
            "device": "default",
        },
    },
    "3": {
        "class_type": "VAELoader",
        "inputs": {"vae_name": "qwen_image_vae.safetensors"},
    },
    "4": {
        "class_type": "LoraLoaderModelOnly",
        "inputs": {
            "model": ["1", 0],
            "lora_name": "qwen-image-edit/Qwen-Image-Edit-2509-Lightning-4steps-V1.0-bf16.safetensors",
            "strength_model": 1,
        },
    },
    "5": {
        "class_type": "ModelSamplingAuraFlow",
        "inputs": {"model": ["4", 0], "shift": 3},
    },
    "6": {
        "class_type": "CFGNorm",
        "inputs": {"model": ["5", 0], "strength": 1},
    },
    "10": {"class_type": "LoadImage", "inputs": {"image": "image1.png"}},
    "11": {"class_type": "LoadImage", "inputs": {"image": "image2.png"}},
    "12": {"class_type": "LoadImage", "inputs": {"image": "image3.png"}},
    "13": {
        "class_type": "ImageScaleToTotalPixels",
        "inputs": {
            "image": ["10", 0],
            "upscale_method": "lanczos",
            "megapixels": 1,
            "resolution_steps": 1,
        },
    },
    "14": {
        "class_type": "ImageScaleToTotalPixels",
        "inputs": {
            "image": ["11", 0],
            "upscale_method": "lanczos",
            "megapixels": 1,
            "resolution_steps": 1,
        },
    },
    "15": {
        "class_type": "ImageScaleToTotalPixels",
        "inputs": {
            "image": ["17", 0],
            "upscale_method": "lanczos",
            "megapixels": 1,
            "resolution_steps": 1,
        },
    },
    "16": {
        "class_type": "DepthAnythingV2Preprocessor",
        "inputs": {
            "image": ["12", 0],
            "ckpt_name": "depth_anything_v2_vitl.pth",
            "resolution": 768,
        },
    },
    "17": {
        "class_type": "DWPreprocessor",
        "inputs": {
            "image": ["16", 0],
            "detect_hand": "enable",
            "detect_body": "enable",
            "detect_face": "disable",
            "resolution": 768,
            "bbox_detector": "yolox_l.onnx",
            "pose_estimator": "dw-ll_ucoco_384_bs5.torchscript.pt",
            "scale_stick_for_xinsr_cn": "disable",
        },
    },
    "20": {
        "class_type": "TextEncodeQwenImageEditPlus",
        "inputs": {
            "clip": ["2", 0],
            "prompt": "",
            "vae": ["3", 0],
            "image1": ["13", 0],
            "image2": ["14", 0],
            "image3": ["15", 0],
        },
    },
    "21": {
        "class_type": "TextEncodeQwenImageEditPlus",
        "inputs": {
            "clip": ["2", 0],
            "prompt": "",
            "vae": ["3", 0],
            "image1": ["13", 0],
            "image2": ["14", 0],
            "image3": ["15", 0],
        },
    },
    "22": {
        "class_type": "EmptySD3LatentImage",
        "inputs": {"width": 832, "height": 1216, "batch_size": 1},
    },
    "23": {
        "class_type": "KSampler",
        "inputs": {
            "model": ["6", 0],
            "positive": ["20", 0],
            "negative": ["21", 0],
            "latent_image": ["22", 0],
            "seed": 0,
            "steps": 4,
            "cfg": 1,
            "sampler_name": "euler",
            "scheduler": "simple",
            "denoise": 1,
        },
    },
    "24": {
        "class_type": "VAEDecode",
        "inputs": {"samples": ["23", 0], "vae": ["3", 0]},
    },
    "25": {
        "class_type": "SaveImage",
        "inputs": {"images": ["24", 0], "filename_prefix": "pose-gallery/mcp"},
    },
}

IMAGE_SLOTS = [
    {"load": "10", "scale": "13", "input": "image1"},
    {"load": "11", "scale": "14", "input": "image2"},
    {"load": "12", "scale": "15", "input": "image3"},
]


def build_recipe_prompt(
    portrait: dict[str, Any] | None,
    costume: dict[str, Any] | None,
    pose: dict[str, Any] | None,
    style_preset: str = "realistic",
    extra_instruction: str = "",
) -> str:
    style_info = STYLE_PRESETS.get(style_preset, STYLE_PRESETS["realistic"])
    clauses: list[str] = []
    idx = 1

    if portrait:
        hair_orig = portrait.get("原发型") or portrait.get("原发长") or ""
        clauses.append(
            f"• 【图{idx}（人像参考）】：保持图{idx}人物五官脸型与气质一致，发型为「{portrait.get('标题')}」（{hair_orig}）。"
        )
        idx += 1
    if costume:
        clauses.append(
            f"• 【图{idx}（服装参考）】：穿上图{idx}中的完整服饰「{costume.get('服装名称')}」（{costume.get('关键词')}），还原面料质感与剪裁。"
        )
        idx += 1
    if pose:
        clauses.append(
            f"• 【图{idx}（姿势参考）】：身体姿态与镜头透视遵循图{idx}「{pose.get('姿势名称')}」【{pose.get('角度')}】（仅参考骨架动作，忽略素体白模材质）。"
        )
        idx += 1

    if not clauses:
        raise ValueError("請至少指定 portrait_id、costume_id 或 pose_id 其中一項")

    lines = [
        f"请结合提供的 {len(clauses)} 张参考图，融合成一张完整的人物图像：",
        *clauses,
    ]
    if extra_instruction.strip():
        lines.append(f"• 【补充要求】：{extra_instruction.strip()}")
    if style_info["prompt"]:
        lines.append(
            f"• 【画风要求】：{style_info['prompt']} 人物比例协调，手部与五官自然，光影统一。"
        )
    return "\n".join(lines)


def _to_png_bytes(raw_bytes: bytes, max_side: int = 1024) -> bytes:
    with Image.open(io.BytesIO(raw_bytes)) as im:
        rgb = im.convert("RGB")
        rgb.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        buf = io.BytesIO()
        rgb.save(buf, format="PNG")
        return buf.getvalue()


def upload_to_comfyui(comfyui_url: str, png_bytes: bytes, filename: str) -> str:
    root = comfyui_url.rstrip("/")
    with httpx.Client(timeout=30.0) as client:
        resp = client.post(
            f"{root}/upload/image",
            data={"type": "input", "overwrite": "true"},
            files={"image": (filename, png_bytes, "image/png")},
        )
        resp.raise_for_status()
        data = resp.json()
        sub = data.get("subfolder", "")
        name = data["name"]
        return f"{sub}/{name}" if sub else name


def prepare_workflow(
    catalog: GalleryCatalog,
    portrait_id: str | None = None,
    costume_id: str | None = None,
    pose_id: str | None = None,
    style_preset: str = "realistic",
    extra_instruction: str = "",
    custom_prompt: str | None = None,
    output_path: str | None = None,
    comfyui_url: str | None = None,
    width: int = 832,
    height: int = 1216,
    steps: int = 4,
    cfg: float = 1.0,
    seed: int | None = None,
) -> dict[str, Any]:
    comfy_root = (
        comfyui_url or os.environ.get("COMFYUI_URL") or "http://127.0.0.1:8188"
    ).rstrip("/")

    portrait_raw: dict[str, Any] | None = None
    costume_raw: dict[str, Any] | None = None
    pose_raw: dict[str, Any] | None = None
    selected_meta: dict[str, Any] = {}
    sources: list[tuple[str, str, dict[str, Any]]] = []

    if portrait_id:
        kind, portrait_raw = catalog.get_raw_item(portrait_id)
        if kind != "portrait":
            raise ValueError(f"{portrait_id} 不是人像 ID（實際為 {kind}）")
        selected_meta["portrait"] = catalog.get_item(portrait_id)
        sources.append(("portrait", portrait_id, portrait_raw))

    if costume_id:
        kind, costume_raw = catalog.get_raw_item(costume_id)
        if kind != "costume":
            raise ValueError(f"{costume_id} 不是服裝 ID（實際為 {kind}）")
        selected_meta["costume"] = catalog.get_item(costume_id)
        sources.append(("costume", costume_id, costume_raw))

    if pose_id:
        kind, pose_raw = catalog.get_raw_item(pose_id)
        if kind != "pose":
            raise ValueError(f"{pose_id} 不是姿勢 ID（實際為 {kind}）")
        selected_meta["pose"] = catalog.get_item(pose_id)
        sources.append(("pose", pose_id, pose_raw))

    if not sources:
        raise ValueError("請至少提供一個有效的資源 ID（portrait_id / costume_id / pose_id）")

    prompt = (
        custom_prompt.strip()
        if custom_prompt and custom_prompt.strip()
        else build_recipe_prompt(
            portrait_raw,
            costume_raw,
            pose_raw,
            style_preset=style_preset,
            extra_instruction=extra_instruction,
        )
    )

    uploaded_names: list[str] = []
    pose_slot_index: int | None = None

    for idx, (slot_kind, item_id, raw) in enumerate(sources):
        rel = raw.get("预览图") or raw.get("原图") or raw.get("缩略图")
        img_bytes = catalog.fetch_image_bytes(rel)
        png_bytes = _to_png_bytes(img_bytes)
        safe_id = item_id.replace("/", "_")
        uploaded = upload_to_comfyui(comfy_root, png_bytes, f"pose_gallery_{slot_kind}_{safe_id}.png")
        uploaded_names.append(uploaded)
        if slot_kind == "pose":
            pose_slot_index = idx

    wf = copy.deepcopy(WORKFLOW_TEMPLATE)
    for i, slot in enumerate(IMAGE_SLOTS):
        if i < len(uploaded_names):
            wf[slot["load"]]["inputs"]["image"] = uploaded_names[i]
            wf[slot["scale"]]["inputs"]["image"] = [slot["load"], 0]
        else:
            del wf[slot["load"]]
            del wf[slot["scale"]]
            del wf["20"]["inputs"][slot["input"]]
            del wf["21"]["inputs"][slot["input"]]

    if pose_slot_index is not None:
        pose_slot = IMAGE_SLOTS[pose_slot_index]
        wf["16"]["inputs"]["image"] = [pose_slot["load"], 0]
        wf[pose_slot["scale"]]["inputs"]["image"] = ["17", 0]
    else:
        del wf["16"]
        del wf["17"]

    wf["20"]["inputs"]["prompt"] = prompt
    wf["22"]["inputs"]["width"] = width
    wf["22"]["inputs"]["height"] = height
    wf["23"]["inputs"]["seed"] = seed if seed is not None else random.randint(0, 2**32 - 1)
    wf["23"]["inputs"]["steps"] = steps
    wf["23"]["inputs"]["cfg"] = cfg

    default_out = (
        Path(__file__).resolve().parents[3]
        / "comfyui-agent"
        / "tmp"
        / "pose-gallery-workflow.json"
    )
    out_file = Path(output_path) if output_path else default_out
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(json.dumps(wf, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "workflow_path": str(out_file),
        "prompt": prompt,
        "uploaded_images": uploaded_names,
        "selected": {
            k: {key: val for key, val in v.items() if key != "raw"}
            for k, v in selected_meta.items()
        },
        "next_step": (
            f"請使用 comfyui-local MCP 的 validate_workflow(workflow_path='{out_file}') "
            f"驗證後，呼叫 run_workflow(workflow_path='{out_file}', wait=False) 並以 job(action='wait') 等待完成。"
        ),
    }

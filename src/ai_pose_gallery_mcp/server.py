from __future__ import annotations

import json
from typing import Any

try:
    from mcp.server.mcpserver import MCPServer as FastMCP
except ImportError:
    from mcp.server.fastmcp import FastMCP

from .catalog import GalleryCatalog
from .workflow import STYLE_PRESETS, build_recipe_prompt, prepare_workflow

mcp = FastMCP(
    "ai-pose-gallery",
    instructions=(
        "檢索 ai-pose-gallery-zh 三大圖庫（姿勢 / 服裝 / 人像），"
        "協助使用者挑選參考圖並產生可供 comfyui-local 執行的 ComfyUI 多圖合成 workflow。"
    ),
)

_catalog = GalleryCatalog()


def _dump(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


@mcp.tool()
def get_facets(kind: str = "all") -> str:
    """列出圖庫可用的篩選維度（體系、分類、角度、髮長、熱門標籤）與畫風預設（style_presets）。

    Args:
        kind: 'all' | 'poses' | 'costumes' | 'portraits'
    """
    facets = _catalog.get_facets(kind)
    facets["style_presets"] = {k: v["label"] for k, v in STYLE_PRESETS.items()}
    return _dump(facets)


@mcp.tool()
def search_poses(
    query: str = "",
    system: str = "",
    category: str = "",
    angle: str = "",
    group_by_pose: bool = True,
    limit: int = 8,
) -> str:
    """搜尋姿勢參考庫（支援繁簡中文、多關鍵詞與口語同義詞，如「站姿 叉腰」「比耶」「雙人」）。

    Args:
        query: 關鍵詞（可留空，僅依篩選條件列出）
        system: 體系篩選（全身单人・标准系 / 全身单人・性感系 / 上半身单人 / 双人缠绵）
        category: 動作分類（如 站姿、坐姿、趴卧、可爱系、跪立 等，可由 get_facets 查詢）
        angle: 視角篩選（正面 / 斜侧 / 侧面 / 俯视 / 仰视）
        group_by_pose: 是否合併同一姿勢的 5 個角度（預設 True，並在 angle_ids 附上各角度 ID）
        limit: 回傳筆數上限（預設 8）
    """
    items = _catalog.search_poses(
        query=query,
        system=system,
        category=category,
        angle=angle,
        group_by_pose=group_by_pose,
        limit=max(1, min(limit, 50)),
    )
    return _dump({"count": len(items), "items": items})


@mcp.tool()
def search_costumes(
    query: str = "",
    category: str = "",
    tags: list[str] | None = None,
    limit: int = 8,
) -> str:
    """搜尋服裝穿搭庫（支援繁簡中文、英文關鍵詞與單品標籤，如「白色 荷葉邊 牛仔裙」「黑色 禮服」）。

    Args:
        query: 關鍵詞（顏色、款式、材質、單品名稱或英文關鍵詞）
        category: 分類篩選（春季穿搭 / 夏季穿搭 / 秋季穿搭 / 冬季穿搭 / 内衣・睡衣 / 派对・礼服 / 泳装・度假 / 性感穿搭）
        tags: 必須同時包含的標籤陣列（如 ["黑色", "连衣裙"]）
        limit: 回傳筆數上限（預設 8）
    """
    items = _catalog.search_costumes(
        query=query,
        category=category,
        tags=tags,
        limit=max(1, min(limit, 50)),
    )
    return _dump({"count": len(items), "items": items})


@mcp.tool()
def search_portraits(
    query: str = "",
    section: str = "",
    hair_length: str = "",
    hairstyle: str = "",
    only_hot: bool = False,
    limit: int = 8,
) -> str:
    """搜尋人像顏值庫（支援繁簡中文髮型描述，如「短髮 空氣瀏海」「黑髮 波波頭」）。

    Args:
        query: 關鍵詞（髮型、瀏海、氣質等描述）
        section: 分區篩選（正脸参考 / 造型氛围）
        hair_length: 髮長篩選（短发 / 中发 / 中长发 / 长发）
        hairstyle: 髮型名稱子字串篩選
        only_hot: 是否只列出 Top 熱門人像
        limit: 回傳筆數上限（預設 8）
    """
    items = _catalog.search_portraits(
        query=query,
        section=section,
        hair_length=hair_length,
        hairstyle=hairstyle,
        only_hot=only_hot,
        limit=max(1, min(limit, 50)),
    )
    return _dump({"count": len(items), "items": items})


@mcp.tool()
def get_item(item_id: str) -> str:
    """依資源 ID 取得單筆姿勢、服裝或人像的完整資訊與圖片網址／本地路徑。"""
    return _dump(_catalog.get_item(item_id))


@mcp.tool()
def compose_recipe_prompt(
    portrait_id: str = "",
    costume_id: str = "",
    pose_id: str = "",
    style_preset: str = "realistic",
    extra_instruction: str = "",
) -> str:
    """預覽「人像＋服裝＋姿勢」配方的結構化提示詞與所選素材摘要（適合先給使用者確認，確認後再呼叫 prepare_comfyui_workflow）。"""
    portrait = _catalog.get_raw_item(portrait_id)[1] if portrait_id else None
    costume = _catalog.get_raw_item(costume_id)[1] if costume_id else None
    pose = _catalog.get_raw_item(pose_id)[1] if pose_id else None
    prompt = build_recipe_prompt(
        portrait,
        costume,
        pose,
        style_preset=style_preset,
        extra_instruction=extra_instruction,
    )
    selected: dict[str, Any] = {}
    for k, iid in (("portrait", portrait_id), ("costume", costume_id), ("pose", pose_id)):
        if iid:
            info = _catalog.get_item(iid)
            info.pop("raw", None)
            selected[k] = info
    return _dump({"prompt": prompt, "style_preset": style_preset, "selected": selected})


@mcp.tool()
def prepare_comfyui_workflow(
    portrait_id: str = "",
    costume_id: str = "",
    pose_id: str = "",
    style_preset: str = "realistic",
    extra_instruction: str = "",
    custom_prompt: str = "",
    output_path: str = "",
    width: int = 832,
    height: int = 1216,
    steps: int = 4,
    cfg: float = 1.0,
    seed: int | None = None,
) -> str:
    """從 ai-pose-gallery 取得所選參考圖並上傳至 ComfyUI，產生可交由 comfyui-local (validate_workflow -> run_workflow) 執行的 Qwen-Image-Edit-2509 workflow JSON 檔案。"""
    res = prepare_workflow(
        catalog=_catalog,
        portrait_id=portrait_id or None,
        costume_id=costume_id or None,
        pose_id=pose_id or None,
        style_preset=style_preset,
        extra_instruction=extra_instruction,
        custom_prompt=custom_prompt or None,
        output_path=output_path or None,
        width=width,
        height=height,
        steps=steps,
        cfg=cfg,
        seed=seed,
    )
    return _dump(res)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()

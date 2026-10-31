from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path
from typing import Any

import httpx
from opencc import OpenCC

_t2s = OpenCC("t2s")

# 常見口語／繁體詞彙對應到圖庫實際使用的簡體詞條
SYNONYMS: dict[str, list[str]] = {
    "连身裙": ["连衣裙"],
    "洋装": ["连衣裙"],
    "短裙": ["迷你", "半身裙"],
    "百褶裙": ["百褶", "半身裙"],
    "牛仔裙": ["牛仔", "半身裙"],
    "风衣": ["大衣", "外套"],
    "西装": ["夹克", "西装外套"],
    "毛衣": ["针织"],
    "丝袜": ["长筒丝袜", "连裤袜"],
    "黑丝": ["黑色", "长筒丝袜", "连裤袜"],
    "白丝": ["白色", "长筒丝袜", "连裤袜"],
    "过膝袜": ["长筒丝袜", "短袜"],
    "及膝袜": ["短袜", "长筒丝袜"],
    "球鞋": ["运动鞋"],
    "布鞋": ["运动鞋"],
    "泳衣": ["泳装"],
    "比基尼": ["泳装", "比基尼"],
    "睡衣": ["内衣・睡衣"],
    "内衣": ["内衣・睡衣"],
    "礼服": ["派对・礼服", "连衣裙"],
    "晚礼服": ["派对・礼服", "连衣裙"],
    "包包": ["包"],
    "手提包": ["包"],
    "比耶": ["比v", "v"],
    "剪刀手": ["比v", "v"],
    "比心": ["比心"],
    "爱心": ["比心"],
    "卖萌": ["可爱系", "撒娇"],
    "俏皮": ["可爱系"],
    "害羞": ["害羞"],
    "趴着": ["趴卧", "俯卧"],
    "趴卧": ["趴卧", "俯卧"],
    "躺着": ["仰卧", "侧卧", "趴卧"],
    "仰躺": ["仰卧"],
    "侧躺": ["侧卧"],
    "跪着": ["跪立", "单膝跪"],
    "蹲着": ["蹲姿"],
    "站着": ["站姿", "站立", "立位"],
    "站姿": ["站姿", "站立"],
    "坐着": ["坐姿", "侧坐", "正坐", "女孩坐", "坐位"],
    "叉腰": ["扶腰", "掐腰"],
    "扶腰": ["扶腰", "掐腰"],
    "拨头发": ["撩发", "抚发", "挽至耳后"],
    "撩头发": ["撩发", "抚发"],
    "抱头": ["抱头", "抱后脑", "抚后脑"],
    "扶头": ["抚后脑", "抱头"],
    "回头": ["回头", "回眸"],
    "托腮": ["托腮", "捧脸"],
    "情侣": ["双人缠绵"],
    "双人": ["双人缠绵"],
    "拥抱": ["贴身", "双人缠绵"],
    "半身": ["上半身单人"],
    "全身": ["全身单人"],
    "正脸": ["正脸参考"],
    "大头": ["正脸参考"],
    "头像": ["正脸参考"],
    "氛围": ["造型氛围"],
    "波波头": ["波波头"],
    "短发": ["短发"],
    "长发": ["长发"],
    "中长发": ["中长发"],
    "中发": ["中发"],
    "刘海": ["刘海"],
    "空气刘海": ["空气刘海"],
    "无刘海": ["无刘海"],
    "卷发": ["卷"],
    "直发": ["直发"],
    "黑发": ["黑发"],
}


def normalize(text: str) -> str:
    """轉簡體並小寫，統一常見異體／多音字。"""
    if not text:
        return ""
    s = _t2s.convert(text.strip()).lower()
    for a, b in (("著", "着"), ("裡", "里"), ("裏", "里"), ("髮", "发"), ("繫", "系")):
        s = s.replace(a, b)
    return s


def tokenize_query(query: str) -> list[str]:
    """將查詢拆成關鍵詞並展開同義詞；對長中文詞補充雙字詞（bigram）以容納模糊描述。"""
    norm = normalize(query)
    if not norm:
        return []
    expanded: list[str] = []
    # 先比對整句中的同義詞（避免「站着」的「着」被當成虛詞刪掉）
    for k, vals in SYNONYMS.items():
        if k in norm:
            expanded.extend(vals)
    # 移除常見無意義虛詞
    for stop in ("的", "了", "穿着", "戴着", "一个", "一张", "女生", "女孩", "女人", "人物", "角色", "姿势", "动作", "衣服", "服装", "穿搭", "发型", "感觉", "风格", "有点", "比较"):
        norm = norm.replace(stop, " ")
    raw_tokens = [t for t in re.split(r"[\s,，、。・/|+＋;；:：()（）【】\[\]]+", norm) if t]
    for tok in raw_tokens:
        expanded.append(tok)
        for k, vals in SYNONYMS.items():
            if k in tok:
                expanded.extend(vals)
        # 若為 3 字以上純中文，拆出 2-gram 提升模糊命中率
        if len(tok) >= 3 and re.fullmatch(r"[\u4e00-\u9fff]+", tok):
            for i in range(len(tok) - 1):
                bg = tok[i : i + 2]
                expanded.append(bg)
                if bg in SYNONYMS:
                    expanded.extend(SYNONYMS[bg])
    # 去重保序
    seen: set[str] = set()
    result: list[str] = []
    for t in expanded:
        if t and t not in seen:
            seen.add(t)
            result.append(t)
    return result


def score_text(tokens: list[str], primary: str, secondary: str = "") -> float:
    """依 token 命中率對主欄位（標題/名稱/標籤）與次欄位（檢索全文）計分。"""
    if not tokens:
        return 1.0
    p = normalize(primary)
    s = normalize(secondary)
    score = 0.0
    for tok in tokens:
        weight = 2.0 if len(tok) >= 2 else 0.8
        if tok in p:
            score += weight * 2.0
        elif tok in s:
            score += weight * 1.0
    return score


class GalleryCatalog:
    """讀取並檢索 ai-pose-gallery-zh 的三大圖庫（優先走 HTTP 服務，亦可讀本地目錄）。"""

    def __init__(
        self,
        gallery_url: str | None = None,
        gallery_dir: str | None = None,
    ) -> None:
        raw_url = (
            gallery_url or os.environ.get("GALLERY_URL") or "http://127.0.0.1:8080"
        ).rstrip("/")
        self.gallery_url = raw_url
        pub_url = os.environ.get("GALLERY_PUBLIC_URL", "").strip()
        if pub_url:
            self.gallery_public_url = pub_url.rstrip("/")
        else:
            self.gallery_public_url = raw_url.replace(
                "://host.docker.internal", "://127.0.0.1"
            )
        env_dir = (gallery_dir or os.environ.get("GALLERY_DIR") or "").strip()
        self.gallery_dir = Path(env_dir) if env_dir else None

        self._poses: list[dict[str, Any]] | None = None
        self._costumes: list[dict[str, Any]] | None = None
        self._portraits: list[dict[str, Any]] | None = None
        self._by_id: dict[str, tuple[str, dict[str, Any]]] = {}

    def _load_json(self, rel_path: str) -> Any:
        # 1. 嘗試透過 HTTP 向 ai-pose-gallery 服務拉取
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get(f"{self.gallery_url}/{rel_path.lstrip('/')}")
                if resp.status_code == 200:
                    return resp.json()
        except Exception:
            pass
        # 2. Fallback 讀取本地目錄
        if self.gallery_dir:
            p = self.gallery_dir / rel_path
            if p.is_file():
                return json.loads(p.read_text(encoding="utf-8"))
        raise RuntimeError(
            f"無法載入 {rel_path}：請確認 ai-pose-gallery 服務已啟動於 {self.gallery_url} 或設定 GALLERY_DIR"
        )

    def fetch_image_bytes(self, rel_path: str) -> bytes:
        clean = rel_path.lstrip("/")
        try:
            with httpx.Client(timeout=15.0) as client:
                resp = client.get(f"{self.gallery_url}/{clean}")
                if resp.status_code == 200:
                    return resp.content
        except Exception:
            pass
        if self.gallery_dir:
            p = self.gallery_dir / clean
            if p.is_file():
                return p.read_bytes()
        raise RuntimeError(f"無法讀取圖片 {rel_path}（已嘗試 {self.gallery_url}/{clean} 與本地目錄）")

    def _ensure_loaded(self) -> None:
        if self._poses is not None:
            return
        self._poses = self._load_json("data/pose-zh.json")
        self._costumes = self._load_json("data/costume-zh.json")
        self._portraits = self._load_json("data/portrait-zh.json")
        for it in self._poses or []:
            self._by_id[it["id"]] = ("pose", it)
        for it in self._costumes or []:
            self._by_id[it["id"]] = ("costume", it)
        for it in self._portraits or []:
            self._by_id[it["id"]] = ("portrait", it)

    def _enrich_urls(self, kind: str, item: dict[str, Any]) -> dict[str, Any]:
        thumb = item.get("缩略图", "")
        orig = item.get("预览图") or item.get("原图", "")
        out = {
            "id": item["id"],
            "kind": kind,
            "thumb_url": f"{self.gallery_public_url}/{thumb.lstrip('/')}" if thumb else None,
            "image_url": f"{self.gallery_public_url}/{orig.lstrip('/')}" if orig else None,
        }
        if self.gallery_dir and orig:
            local_p = self.gallery_dir / orig.lstrip("/")
            if local_p.exists():
                out["local_path"] = str(local_p)
        if kind == "pose":
            out.update(
                {
                    "system": item.get("体系"),
                    "code": item.get("姿势编号"),
                    "category": item.get("分类"),
                    "name": item.get("姿势名称"),
                    "angle": item.get("角度"),
                }
            )
        elif kind == "costume":
            out.update(
                {
                    "category": item.get("分类"),
                    "name": item.get("服装名称"),
                    "tags": item.get("标签", []),
                    "keywords": item.get("关键词"),
                }
            )
        elif kind == "portrait":
            out.update(
                {
                    "section": item.get("分区"),
                    "hair_length": item.get("发长"),
                    "hairstyle": item.get("发型名称"),
                    "title": item.get("标题"),
                    "hot": item.get("热门", False),
                    "featured": item.get("精选", False),
                }
            )
        return out

    def get_facets(self, kind: str = "all") -> dict[str, Any]:
        self._ensure_loaded()
        res: dict[str, Any] = {}
        if kind in ("all", "poses"):
            res["poses"] = {
                "total": len(self._poses or []),
                "systems": dict(Counter(x["体系"] for x in (self._poses or []))),
                "categories": dict(Counter(x["分类"] for x in (self._poses or [])).most_common()),
                "angles": ["正面", "斜侧", "侧面", "俯视", "仰视"],
            }
        if kind in ("all", "costumes"):
            tags = Counter(t for x in (self._costumes or []) for t in x.get("标签", []))
            res["costumes"] = {
                "total": len(self._costumes or []),
                "categories": dict(Counter(x["分类"] for x in (self._costumes or [])).most_common()),
                "top_tags": dict(tags.most_common(50)),
            }
        if kind in ("all", "portraits"):
            res["portraits"] = {
                "total": len(self._portraits or []),
                "sections": dict(Counter(x["分区"] for x in (self._portraits or []))),
                "hair_lengths": dict(Counter(x["发长"] for x in (self._portraits or []))),
                "top_hairstyles": dict(
                    Counter(x["发型名称"] for x in (self._portraits or [])).most_common(40)
                ),
            }
        return res

    def search_poses(
        self,
        query: str = "",
        system: str = "",
        category: str = "",
        angle: str = "",
        group_by_pose: bool = True,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        self._ensure_loaded()
        tokens = tokenize_query(query)
        sys_n = normalize(system)
        cat_n = normalize(category)
        ang_n = normalize(angle)

        scored: list[tuple[float, dict[str, Any]]] = []
        for it in self._poses or []:
            if sys_n and sys_n not in normalize(it.get("体系", "")):
                continue
            if cat_n and cat_n not in normalize(it.get("分类", "")):
                continue
            if ang_n and ang_n != normalize(it.get("角度", "")):
                continue
            s = score_text(
                tokens,
                f"{it.get('姿势名称', '')} {it.get('分类', '')}",
                f"{it.get('体系', '')} {it.get('检索', '')}",
            )
            if tokens and s <= 0:
                continue
            scored.append((s, it))

        scored.sort(key=lambda x: (-x[0], x[1]["id"]))

        if not group_by_pose:
            return [
                {**self._enrich_urls("pose", it), "score": round(sc, 2)}
                for sc, it in scored[:limit]
            ]

        # 依（體系, 姿勢編號）分組，避免同一姿勢 5 個角度佔滿結果
        grouped: dict[str, dict[str, Any]] = {}
        for sc, it in scored:
            gkey = f"{it.get('体系')}:{it.get('姿势编号')}"
            if gkey not in grouped:
                enriched = self._enrich_urls("pose", it)
                enriched["score"] = round(sc, 2)
                enriched["angle_ids"] = {it.get("角度"): it["id"]}
                grouped[gkey] = enriched
            else:
                grouped[gkey]["angle_ids"][it.get("角度")] = it["id"]
                # 預設優先展示「正面」代表圖
                if not ang_n and it.get("角度") == "正面":
                    front = self._enrich_urls("pose", it)
                    front["score"] = grouped[gkey]["score"]
                    front["angle_ids"] = grouped[gkey]["angle_ids"]
                    grouped[gkey] = front
            if len(grouped) >= limit and not ang_n:
                # 繼續補齊已入選群組的其他角度 ID
                pass

        return list(grouped.values())[:limit]

    def search_costumes(
        self,
        query: str = "",
        category: str = "",
        tags: list[str] | None = None,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        self._ensure_loaded()
        tokens = tokenize_query(query)
        cat_n = normalize(category)
        req_tags = [normalize(t) for t in (tags or []) if t.strip()]

        scored: list[tuple[float, dict[str, Any]]] = []
        for it in self._costumes or []:
            if cat_n and cat_n not in normalize(it.get("分类", "")):
                continue
            item_tags_norm = [normalize(t) for t in it.get("标签", [])]
            if req_tags and not all(
                any(rt in it_t for it_t in item_tags_norm) for rt in req_tags
            ):
                continue
            s = score_text(
                tokens,
                f"{it.get('服装名称', '')} {' '.join(it.get('标签', []))}",
                f"{it.get('分类', '')} {it.get('关键词', '')} {it.get('检索', '')}",
            )
            if tokens and s <= 0:
                continue
            scored.append((s, it))

        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        return [
            {**self._enrich_urls("costume", it), "score": round(sc, 2)}
            for sc, it in scored[:limit]
        ]

    def search_portraits(
        self,
        query: str = "",
        section: str = "",
        hair_length: str = "",
        hairstyle: str = "",
        only_hot: bool = False,
        limit: int = 10,
    ) -> list[dict[str, Any]]:
        self._ensure_loaded()
        tokens = tokenize_query(query)
        sec_n = normalize(section)
        len_n = normalize(hair_length)
        sty_n = normalize(hairstyle)

        scored: list[tuple[float, dict[str, Any]]] = []
        for it in self._portraits or []:
            if sec_n and sec_n not in normalize(it.get("分区", "")):
                continue
            if len_n and len_n != normalize(it.get("发长", "")):
                continue
            if sty_n and sty_n not in normalize(it.get("发型名称", "")):
                continue
            if only_hot and not it.get("热门", False):
                continue
            s = score_text(
                tokens,
                f"{it.get('标题', '')} {it.get('发型名称', '')} {it.get('发长', '')}",
                f"{it.get('分区', '')} {it.get('原发型', '')} {it.get('检索', '')}",
            )
            if tokens and s <= 0:
                continue
            # 熱門與精選微幅加權
            if it.get("热门"):
                s += 0.3
            if it.get("精选"):
                s += 0.2
            scored.append((s, it))

        scored.sort(key=lambda x: (-x[0], x[1]["id"]))
        return [
            {**self._enrich_urls("portrait", it), "score": round(sc, 2)}
            for sc, it in scored[:limit]
        ]

    def get_raw_item(self, item_id: str) -> tuple[str, dict[str, Any]]:
        self._ensure_loaded()
        if item_id not in self._by_id:
            raise KeyError(f"找不到資源 ID：{item_id}")
        return self._by_id[item_id]

    def get_item(self, item_id: str) -> dict[str, Any]:
        kind, raw = self.get_raw_item(item_id)
        return {**self._enrich_urls(kind, raw), "raw": raw}

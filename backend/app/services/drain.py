"""排水设施业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.seed import DRAIN_ROADS
from app.store import store

MODULE = "drain"
REQUIRED_FIELDS = ["设施编号", "设施类型", "所在道路"]
STATUS_ORDER = ["待清疏", "正常使用", "堵塞待修", "已停用"]
ACTION_RULES = {"安排清疏": "正常使用", "确认正常": "堵塞待修", "停用设施": "已停用"}
NEGATIVE_ACTIONS = ["停用设施"]

# 分布视图画布：与 seed 里道路走向、设施坐标同一套平面示意坐标。
MAP_CANVAS = {"width": 1200, "height": 720}


def _missing_fields(row: dict[str, Any]) -> list[str]:
    """标出单个设施在分布视图上缺什么：缺坐标、还没清掏过，逐点说明而不是让整图空白。"""
    missing: list[str] = []
    coord = row.get("坐标")
    if not (isinstance(coord, (list, tuple)) and len(coord) == 2):
        missing.append("缺坐标")
    if not str(row.get("上次清疏日") or "").strip():
        missing.append("未清掏")
    return missing


class DrainService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("设施编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        entry.update({field: values.get(field) for field in REQUIRED_FIELDS})
        entry["status"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"排水设施 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于排水设施可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"排水设施已{action}"

    def map_payload(self) -> dict[str, Any]:
        """分布视图数据：按所在道路把排水设施与雨水口铺到一张图上。

        每个点都带上「缺失」说明：缺坐标或还没清掏过的点照常返回，
        由前端决定怎么标，而不是因为个别点缺数据就让整图空白。
        """
        facilities: list[dict[str, Any]] = []
        for row in store.rows(MODULE):
            coord = row.get("坐标")
            facilities.append({
                "id": row.get("id"),
                "设施编号": row.get("设施编号"),
                "设施类型": row.get("设施类型"),
                "所在道路": row.get("所在道路"),
                "status": row.get("status"),
                "坐标": list(coord) if isinstance(coord, (list, tuple)) and len(coord) == 2 else None,
                "上次清疏日": row.get("上次清疏日") or None,
                "积水次数": int(row.get("积水次数") or 0),
                "缺失": _missing_fields(row),
            })
        road_names = {str(row.get("所在道路") or "") for row in store.rows(MODULE)}
        roads = [dict(road) for road in DRAIN_ROADS if road["name"] in road_names]
        known = {road["name"] for road in roads}
        for name in sorted(road_names - known):
            # 台账里新登记的道路没有示意线时，也占一条泳道，保证设施仍能按道路归组。
            roads.append({"name": name, "path": []})
        return {"canvas": MAP_CANVAS, "roads": roads, "facilities": facilities}

    def entry_profile(self, entry_id: int) -> tuple[dict[str, Any] | None, str]:
        """单处设施详情：排水管走向与关联的诉求记录。"""
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"排水设施 {entry_id} 不存在或已归档"
        code = str(entry.get("设施编号") or "")
        road = str(entry.get("所在道路") or "")
        complaints = [
            row for row in store.rows("complaint")
            if (code and code in str(row.get("涉及设施") or ""))
            or (road and road in str(row.get("涉及设施") or ""))
        ]
        profile = {
            "entry": entry,
            "pipes": entry.get("管线") or [],
            "complaints": complaints,
            "缺失": _missing_fields(entry),
        }
        return profile, "ok"

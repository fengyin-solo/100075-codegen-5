"""排水设施业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "drain"
INLET_MODULE = "drain_inlet"
COMPLAINT_MODULE = "complaint"
REQUIRED_FIELDS = ["设施编号", "设施类型", "所在道路"]
STATUS_ORDER = ["待清疏", "正常使用", "堵塞待修", "已停用"]
ACTION_RULES = {"安排清疏": "正常使用", "确认正常": "堵塞待修", "停用设施": "已停用"}
NEGATIVE_ACTIONS = ["停用设施"]

# 示意图底图道路：坐标系为前端 SVG 画布坐标，与设施坐标同一套口径。
ROAD_GEOMETRY: list[dict[str, Any]] = [
    {"name": "滨河路", "path": [[60, 180], [560, 160], [920, 260]]},
    {"name": "云杉大道", "path": [[260, 300], [260, 560], [760, 470], [900, 500]]},
    {"name": "解放大街", "path": [[90, 730], [600, 680], [920, 710]]},
]


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

    # ---- 分布视图 -------------------------------------------------------

    def map_overview(self, road: str | None = None) -> dict[str, Any]:
        """按道路汇总排水设施与雨水口，供分布视图一次铺图。

        没有坐标或从未清掏的点照样返回，前端据缺失字段单独标注，
        保证个别点资料不全时整张图不空白。
        """
        facilities = [dict(row) for row in store.rows(MODULE)]
        inlets = [dict(row) for row in store.rows(INLET_MODULE)]
        if road:
            facilities = [row for row in facilities if row.get("所在道路") == road]
            inlets = [row for row in inlets if row.get("所在道路") == road]

        roads = [
            {"name": item["name"], "path": item["path"]}
            for item in ROAD_GEOMETRY
            if not road or item["name"] == road
        ]

        points = [self._facility_point(row) for row in facilities]
        points.extend(self._inlet_point(row) for row in inlets)

        missing_coord = [
            {"kind": point["kind"], "id": point["id"], "code": point["code"],
             "road": point["road"], "missing": ["坐标"]}
            for point in points if not point["hasCoord"]
        ]
        never_cleaned = [
            {"kind": point["kind"], "id": point["id"], "code": point["code"],
             "road": point["road"]}
            for point in points if point["hasCoord"] and point["lastClean"] is None
        ]
        return {
            "roads": roads,
            "points": points,
            "summary": {
                "facilityCount": len(facilities),
                "inletCount": len(inlets),
                "missingCoordCount": len(missing_coord),
                "neverCleanedCount": len(never_cleaned),
            },
        }

    def map_detail(self, kind: str, entry_id: int) -> dict[str, Any] | None:
        """点开某处时返回它的排水管走向与关联诉求记录。"""
        if kind == "facility":
            row = store.find(MODULE, entry_id)
            if row is None:
                return None
            point = self._facility_point(dict(row))
            link_codes = [str(row.get("设施编号", ""))]
        elif kind == "inlet":
            row = store.find(INLET_MODULE, entry_id)
            if row is None:
                return None
            point = self._inlet_point(dict(row))
            # 雨水口自身与所属排水设施的诉求都算关联
            link_codes = [str(row.get("雨水口编号", ""))]
            facility_code = row.get("关联设施编号")
            if facility_code:
                link_codes.append(str(facility_code))
        else:
            return None

        complaints = [
            dict(item)
            for item in store.rows(COMPLAINT_MODULE)
            if str(item.get("涉及设施", "")) in link_codes
        ]
        point["complaints"] = complaints
        point["missing"] = list(point["missing"])
        return point

    def _facility_point(self, row: dict[str, Any]) -> dict[str, Any]:
        coord = self._valid_coord(row.get("坐标"))
        missing: list[str] = []
        if coord is None:
            missing.append("坐标")
        last_clean = self._clean_date(row.get("上次清疏日"))
        if last_clean is None:
            missing.append("上次清疏")
        path = row.get("管段走向")
        if not (isinstance(path, list) and path and all(self._is_xy(node) for node in path)):
            path = None
            if coord is not None:
                missing.append("管段走向")
        return {
            "kind": "facility",
            "id": int(row.get("id", 0)),
            "code": row.get("设施编号"),
            "name": row.get("设施类型"),
            "road": row.get("所在道路"),
            "status": row.get("status"),
            "coord": coord,
            "hasCoord": coord is not None,
            "lastClean": last_clean,
            "floodCount": self._non_negative_int(row.get("积水历史次数")),
            "pipePath": path,
            "crew": row.get("责任班组"),
            "missing": missing,
        }

    def _inlet_point(self, row: dict[str, Any]) -> dict[str, Any]:
        coord = self._valid_coord(row.get("坐标"))
        missing: list[str] = []
        if coord is None:
            missing.append("坐标")
        last_clean = self._clean_date(row.get("上次清掏日"))
        if last_clean is None:
            missing.append("上次清掏")
        return {
            "kind": "inlet",
            "id": int(row.get("id", 0)),
            "code": row.get("雨水口编号"),
            "name": row.get("雨水口形式"),
            "road": row.get("所在道路"),
            "status": row.get("status"),
            "coord": coord,
            "hasCoord": coord is not None,
            "lastClean": last_clean,
            "floodCount": self._non_negative_int(row.get("积水历史次数")),
            "pipePath": None,
            "facilityCode": row.get("关联设施编号"),
            "missing": missing,
        }

    @staticmethod
    def _valid_coord(value: Any) -> dict[str, int] | None:
        if not isinstance(value, dict):
            return None
        try:
            x = float(value.get("x"))
            y = float(value.get("y"))
        except (TypeError, ValueError):
            return None
        return {"x": int(x), "y": int(y)}

    @staticmethod
    def _is_xy(value: Any) -> bool:
        return (
            isinstance(value, (list, tuple))
            and len(value) == 2
            and all(isinstance(n, (int, float)) for n in value)
        )

    @staticmethod
    def _clean_date(value: Any) -> str | None:
        """清掏/清疏日：空值或非日期占位都视为从未清掏。"""
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        # 种子里早期出现过“排水设施样例1”之类的占位，不能当成有效日期
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            return text[:10]
        return None

    @staticmethod
    def _non_negative_int(value: Any) -> int:
        try:
            number = int(value)
        except (TypeError, ValueError):
            return 0
        return max(number, 0)

"""
线路模型：区段、车站、道岔、轨道区段（只定义数据结构，具体线路数据在 configs/*.yaml）

================================================================================
 Y 型线路拓扑图（从左往右，对应 configs/line_demo.yaml）
================================================================================

位置(m):  0        500        1000       1500       2000       2500       3000       3500
          |----------|----------|----------|----------|----------|----------|----------|
          │          │          │          │          │          │          │          │
          │          │          │          │          │          │          │          │

主线main  ●──────────[A]────────[B]──────────●─SW1───────●───────[D]───────●
(上行)    │          500        1500        2000        2200    3400      3500
(22m/s)   │                                       │
          │                                       │
          │                                       │  (道岔 @2000m)
          │                                       │
          │                                       │
支线branch │                                      ●──────[E]───────●
(下行)    │                                      2000   3100     3200
(18m/s,   │
 +1%)     │
          │
          └──────────── common 共线段 (0~2000m, 22m/s) ─────────────┘

================================================================================
 轨道区段（sections）划分（用于联锁的空闲/占用判定）
================================================================================

  S1      [0,    500]   common   ← 起点 → A 站
  S2      [500,  1500]  common   ← A → B 站
  S3      [1500, 2000]  common   ← B → 道岔 SW1（含 SW1）
  S4m     [2000, 2200]  main     ← 主线道岔区
  S5m     [2200, 3500]  main     ← 主线高速段（含 D 站）
  S4b     [2000, 2200]  branch   ← 支线道岔区
  S5b     [2200, 3200]  branch   ← 支线段（含 E 站）

================================================================================
 关键说明
================================================================================

1. 共线段 (common, 0 ~ 2000m, 限速 22 m/s)
   - A 站 (500m)、B 站 (1500m) 都在这里
   - 所有列车都必须经过，因此 Step 6 会引入"进路冲突"概念
   - 列车从起点出发，一直沿 common 分支前进，直到 2000m 遇到道岔 SW1

2. 道岔 SW1 @ 2000m
   - 定位 (normal)  → 通往 main 分支   → D 站 @3400m
   - 反位 (reverse) → 通往 branch 分支 → E 站 @3100m
   - 只有 CI (计算机联锁) 有权切换道岔状态
   - 道岔区 (2000 ~ 2200m) 限速降到 10 m/s

3. 主线 main (2000 ~ 3500m)
   - 2000 ~ 2200m: 道岔区，限速 10 m/s (36 km/h)
   - 2200 ~ 3500m: 正线，限速 22 m/s (80 km/h)
   - 终点 D 站 @ 3400m，之后还有 100m 保护区段到 3500m

4. 支线 branch (2000 ~ 3200m)
   - 2000 ~ 2200m: 道岔区，限速 10 m/s
   - 2200 ~ 3200m: 支线，限速 18 m/s (65 km/h)，坡度 +1% (上坡)
   - 终点 E 站 @ 3100m，之后还有 100m 到 3200m

5. 列车分支切换逻辑 (在 Simulation._update_branches 中)
   - 当 train.position >= switch.position (2000m) 时触发
   - 目标分支由 CI 的道岔状态决定：
       switch_state == "normal"  → train.current_branch = "main"
       switch_state == "reverse" → train.current_branch = "branch"
   - 一旦切换，列车会在新分支上读取限速、坡道、阻力等

6. MA 与进路的关系
   - 有进路 (route_end 由 CI 提供)：MA 直接延伸到进路终点
   - 无进路：MA 被限制在"当前分支末端"或"下一个道岔前"

================================================================================
 待实现 (Step 6+)
================================================================================
 - 保护进路 (Overlap)：进路终点后延 50~100m
 - 进路冲突检测：两车的进路都经过 SW1 时的仲裁（排队 / 拒绝）
 - 侧冲防护：道岔区的侧面撞击防护
 - 侧线停车：列车停在 main / branch 时，其他列车不能进入 common 末端
"""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Segment:
    """一段线路：从 start 到 end，限速 speed_limit，坡度 gradient，属于哪个分支"""
    start: float
    end: float
    speed_limit: float
    gradient: float = 0.0
    branch: str = "common"

    @property
    def length(self) -> float:
        return self.end - self.start


@dataclass
class Station:
    """车站：位置 + 分支 + 停站时间 + 停车窗"""
    name: str
    position: float
    branch: str = "common"
    dwell_time: float = 20.0
    stop_window: float = 0.5


@dataclass
class Switch:
    """道岔：位于 position，定位通往 normal_branch，反位通往 reverse_branch"""
    name: str
    position: float
    normal_branch: str
    reverse_branch: str


@dataclass
class Section:
    """
    轨道区段：用于联锁的区段空闲/占用判定。
    与 Segment 的区别：
      - Segment 描述"线路的物理走向和限速"，用于列车动力学
      - Section  描述"联锁的检测单元"，用于进路排列、道岔转换
    两者是不同维度的概念，虽然经常重叠。
    """
    name: str
    start: float
    end: float
    branch: str = "common"

    @property
    def length(self) -> float:
        return self.end - self.start

    def contains(self, pos: float) -> bool:
        return self.start <= pos < self.end


class Line:
    """
    线路模型：包含所有分支的区段、车站、道岔、轨道区段。
    """

    def __init__(self, segments, stations=None, switches=None,
                 sections=None, name="Line"):
        self.segments = sorted(segments, key=lambda s: (s.branch, s.start))
        self.stations = sorted(stations or [], key=lambda s: s.position)
        self.switches = sorted(switches or [], key=lambda s: s.position)
        self.sections = sorted(sections or [], key=lambda s: (s.start, s.branch))
        self.name = name
        self._validate()

    def _validate(self):
        """校验：每条分支的区段必须连续"""
        by_branch = {}
        for seg in self.segments:
            by_branch.setdefault(seg.branch, []).append(seg)

        for br, segs in by_branch.items():
            segs = sorted(segs, key=lambda s: s.start)
            for i in range(len(segs) - 1):
                if abs(segs[i].end - segs[i + 1].start) > 1e-6:
                    raise ValueError(
                        f"分支 {br} 区段不连续: "
                        f"{segs[i].end} -> {segs[i + 1].start}"
                    )

    # ------------------------------------------------------------------
    # 分支查询
    # ------------------------------------------------------------------
    def branch_length(self, branch: str) -> float:
        """该分支的最远位置"""
        max_end = 0.0
        for seg in self.segments:
            if seg.branch == branch and seg.end > max_end:
                max_end = seg.end
        return max_end

    def branches(self) -> List[str]:
        """所有分支名"""
        return sorted({seg.branch for seg in self.segments})

    # ------------------------------------------------------------------
    # 位置查询
    # ------------------------------------------------------------------
    def _seg_at(self, pos: float, branch: str) -> Optional[Segment]:
        for seg in self.segments:
            if seg.branch == branch and seg.start <= pos < seg.end:
                return seg
        return None

    def speed_limit_at(self, pos: float, branch: str = "common") -> float:
        seg = self._seg_at(pos, branch)
        return seg.speed_limit if seg else 0.0

    def gradient_at(self, pos: float, branch: str = "common") -> float:
        seg = self._seg_at(pos, branch)
        return seg.gradient if seg else 0.0

    def min_speed_limit_between(self, pos_a: float, pos_b: float,
                                branch: str = "common") -> float:
        """[pos_a, pos_b] 区间内的最小限速（同分支）"""
        if pos_b <= pos_a:
            return 0.0
        limit = float("inf")
        for seg in self.segments:
            if seg.branch != branch:
                continue
            if seg.end > pos_a and seg.start < pos_b:
                limit = min(limit, seg.speed_limit)
        return 0.0 if limit == float("inf") else limit

    # ------------------------------------------------------------------
    # 车站 / 道岔查询
    # ------------------------------------------------------------------
    def station_by_index(self, idx: int) -> Optional[Station]:
        if 0 <= idx < len(self.stations):
            return self.stations[idx]
        return None

    def station_by_name(self, name: str) -> Optional[Station]:
        for st in self.stations:
            if st.name == name:
                return st
        return None

    def first_switch_ahead(self, pos: float) -> Optional[Switch]:
        """返回 pos 前方（含）第一个道岔"""
        for sw in self.switches:
            if sw.position >= pos:
                return sw
        return None

    # ------------------------------------------------------------------
    # 轨道区段查询
    # ------------------------------------------------------------------
    def sections_between(self, pos_a: float, pos_b: float,
                         branch: Optional[str] = None) -> List[Section]:
        """
        返回 [pos_a, pos_b] 范围内的所有区段（按 start 排序）。
        如果指定 branch，只返回该分支的区段。
        """
        result = []
        for sec in self.sections:
            if sec.end <= pos_a or sec.start >= pos_b:
                continue
            if branch is not None and sec.branch != branch:
                continue
            result.append(sec)
        return sorted(result, key=lambda s: s.start)

    def section_containing(self, pos: float,
                           branch: Optional[str] = None) -> Optional[Section]:
        """返回包含 pos 的区段"""
        for sec in self.sections:
            if sec.contains(pos):
                if branch is None or sec.branch == branch:
                    return sec
        return None

    def section_by_name(self, name: str) -> Optional[Section]:
        for sec in self.sections:
            if sec.name == name:
                return sec
        return None

    # ------------------------------------------------------------------
    # 数据加载
    # ------------------------------------------------------------------
    @classmethod
    def from_yaml(cls, path: str) -> "Line":
        import yaml
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        segments = [
            Segment(s["start"], s["end"], s["speed_limit"],
                    s.get("gradient", 0.0), s.get("branch", "common"))
            for s in data["segments"]
        ]
        stations = [
            Station(st["name"], st["position"], st.get("branch", "common"),
                    st.get("dwell_time", 20.0), st.get("stop_window", 0.5))
            for st in data.get("stations", [])
        ]
        switches = [
            Switch(sw["name"], sw["position"],
                   sw["normal_branch"], sw["reverse_branch"])
            for sw in data.get("switches", [])
        ]
        sections = [
            Section(sec["name"], sec["start"], sec["end"],
                    sec.get("branch", "common"))
            for sec in data.get("sections", [])
        ]
        return cls(segments, stations, switches, sections,
                   data.get("name", "Line"))

    def __repr__(self):
        return (f"Line({self.name}, branches={self.branches()}, "
                f"stations={[s.name for s in self.stations]}, "
                f"switches={[s.name for s in self.switches]}, "
                f"sections={[s.name for s in self.sections]})")
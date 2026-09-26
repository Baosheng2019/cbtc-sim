"""车载 ATP：制动曲线计算 + 超速监督"""
import math
from dataclasses import dataclass
from .core import MovementAuthority, get_logger

log = get_logger("ATP")


def braking_curve_speed(distance: float, decel: float,
                        v_target: float = 0.0) -> float:
    """从 distance 处以 decel 减速到 v_target，当前允许的最大速度"""
    if distance <= 0.0:
        return v_target
    return math.sqrt(v_target ** 2 + 2.0 * decel * distance)


@dataclass
class ATPLimits:
    v_eb: float = 0.0
    v_sb: float = 0.0
    v_line: float = 0.0
    eb_active: bool = False
    sb_active: bool = False
    sb_demand: float = 0.0
    ma: MovementAuthority = None
    distance_to_ma: float = 0.0


class ATP:
    def __init__(self, train, line, cfg: dict = None):
        cfg = cfg or {}
        self.train = train
        self.line = line
        self.eb_decel = cfg.get("eb_decel", 1.0)             # 紧急制动保证减速度
        self.sb_decel = cfg.get("sb_decel", 0.5)             # 常用制动减速度（更保守）
        self.reaction_time = cfg.get("reaction_time", 1.0)   # 反应时间 (s)
        self.safety_margin = cfg.get("safety_margin", 10.0)  # 安全余量 (m)
        self.tolerance = cfg.get("tolerance", 0.3)           # 超速容差 (m/s)

    def evaluate(self, ma: MovementAuthority) -> ATPLimits:
        t = self.train
        p = t.position
        v = t.speed
        lim = ATPLimits(ma=ma)

        # --- 1. 对 MA 终点 ---
        d_to_end = ma.end_position - p
        lim.distance_to_ma = d_to_end

        d_eb = d_to_end - self.safety_margin
        lim.v_eb = braking_curve_speed(d_eb, self.eb_decel, ma.end_speed)

        d_sb = d_to_end - self.safety_margin - v * self.reaction_time
        lim.v_sb = braking_curve_speed(d_sb, self.sb_decel, ma.end_speed)

        # --- 2. 线路限速 ---
        lim.v_line = self.line.speed_limit_at(p, self.train.current_branch)

        # --- 3. MA 沿途限速点 ---
        for (r_pos, r_v) in ma.restrictions:
            d_r = r_pos - p
            if d_r < 0:
                continue
            v_eb_r = braking_curve_speed(d_r - self.safety_margin,
                                         self.eb_decel, r_v)
            v_sb_r = braking_curve_speed(
                d_r - self.safety_margin - v * self.reaction_time,
                self.sb_decel, r_v)
            lim.v_eb = min(lim.v_eb, v_eb_r)
            lim.v_sb = min(lim.v_sb, v_sb_r)

        # 线路限速也参与（取最严）
        lim.v_eb = min(lim.v_eb, lim.v_line)
        lim.v_sb = min(lim.v_sb, lim.v_line)

        # --- 4. 触发判断 ---
        if v > lim.v_eb + self.tolerance:
            lim.eb_active = True
            log.warning("%s 触发紧急制动: v=%.2f > v_eb=%.2f",
                        t.p.name, v, lim.v_eb)
        elif v > lim.v_sb + self.tolerance:
            lim.sb_active = True
            lim.sb_demand = min(1.0, max(0.0, (v - lim.v_sb) / 2.0))

        return lim
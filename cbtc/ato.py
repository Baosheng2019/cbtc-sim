"""车载 ATO：自动驾驶 + 动态前瞻限速 + 精确停车到运营停车点"""
import math


class ATO:
    def __init__(self, cfg: dict = None):
        cfg = cfg or {}
        self.kp = cfg.get("kp", 0.8)
        self.v_margin = cfg.get("v_margin", 0.95)
        self.dead_band = cfg.get("dead_band", 0.5)

        self.lookahead_distance = cfg.get("lookahead_distance", 2000.0)
        self.comfort_decel = cfg.get("comfort_decel", 0.5)

        self.stop_decel = cfg.get("stop_decel", 0.8)
        self.stop_zone = cfg.get("stop_zone", 0.3)

        self.count_stop_out_of_ma = 0

    def _compute_dynamic_speed_limit(self, train, line):
        v_limit = line.speed_limit_at(train.position, train.current_branch)
        for seg in line.segments:
            if (train.position < seg.start
                    <= train.position + self.lookahead_distance):
                if seg.speed_limit < v_limit:
                    d = seg.start - train.position
                    v_allowed = math.sqrt(seg.speed_limit ** 2
                                          + 2 * self.comfort_decel * d)
                    v_limit = min(v_limit, v_allowed)
        return v_limit

    def compute(self, train, line, ma, limits, next_stop_position=None):
        v = train.speed
        d_to_ma = ma.end_position - train.position

        # --- 安全边界：接近 MA 终点强制抱死 ---
        if d_to_ma <= self.stop_zone:
            return 0.0, 1.0

        # --- 目标位置 ---
        target = ma.end_position
        if next_stop_position is not None:
            if next_stop_position > ma.end_position:
                self.count_stop_out_of_ma += 1
                target = ma.end_position
            else:
                target = next_stop_position
        d_to_target = target - train.position

        # --- 常规巡航目标速度 ---
        v_dynamic = self._compute_dynamic_speed_limit(train, line)
        v_cruise = min(limits.v_sb, v_dynamic) * self.v_margin

        # ============================================================
        # 模式判定：只有当前制动曲线 <= 巡航目标速度时，才进入精确停车模式
        # ============================================================
        if next_stop_position is not None:
            d_eff = max(d_to_target - self.stop_zone, 0.0)
            v_approach = math.sqrt(2 * self.stop_decel * d_eff)

            # 制动曲线已经低于巡航速度（或非常接近）：精确停车模式
            if v_approach <= v_cruise + 0.3:
                # 已到达或越过：抱死
                if d_to_target <= self.stop_zone:
                    return 0.0, 1.0

                # 超速：直接制动
                if v > v_approach + 0.05:
                    brake = min(1.0, max(0.5, (v - v_approach) * 2.0))
                    return 0.0, brake

                # 明显低于曲线：极轻牵引
                if v < v_approach - 0.3:
                    return 0.10, 0.0

                # 贴合曲线：惰行
                return 0.0, 0.0

        # ============================================================
        # 巡航模式：常规 P 控制器
        # ============================================================
        if v < 0.05 and d_to_target > 20.0:
            return 0.15, 0.0

        err = v_cruise - v
        if err > self.dead_band:
            return min(1.0, self.kp * err), 0.0
        elif err < -self.dead_band:
            return 0.0, min(1.0, self.kp * (-err))
        else:
            return 0.0, 0.0
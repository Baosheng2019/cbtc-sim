"""区域控制器 ZC：安全 MA 计算（含道岔约束）"""
from .core import MovementAuthority, get_logger

log = get_logger("ZC")


class ZC:
    def __init__(self, line, cfg: dict = None):
        cfg = cfg or {}
        self.line = line
        self.safety_distance = cfg.get("safety_distance", 50.0)
        self.pos_uncertainty = cfg.get("pos_uncertainty", 5.0)

    def compute_ma(self, train, leading_train=None, route_end=None):
        """
        MA 计算：
          - 有进路时：MA 直接延伸到进路终点（跨分支）
          - 无进路时：MA 不超过当前分支末端，且在道岔前停下
          - 前车约束：始终生效
        """
        # 1. 基础 MA
        if route_end is not None:
            # 有进路：直接延伸到进路终点
            ma_end = route_end
        else:
            # 无进路：保守，只到当前分支末端
            ma_end = self.line.branch_length(train.current_branch)

        # 2. 前车约束
        if leading_train is not None:
            ma_end = min(ma_end,
                         leading_train.tail_position
                         - self.safety_distance
                         - 2 * self.pos_uncertainty)

        # 3. 无进路时，还要考虑道岔前停下
        if route_end is None:
            for sw in self.line.switches:
                if train.position < sw.position:
                    ma_end = min(ma_end, sw.position)
                    break

        ma_end = max(ma_end, train.position)
        return MovementAuthority(end_position=ma_end, end_speed=0.0)
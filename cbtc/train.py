"""列车动力学模型"""
from dataclasses import dataclass


@dataclass
class TrainParams:
    name: str = "T1"
    length: float = 120.0
    mass: float = 300_000.0
    max_traction_accel: float = 1.0
    max_brake_accel: float = 1.2
    davis_a0: float = 0.02
    davis_a1: float = 0.0003
    davis_a2: float = 0.00002


class Train:
    def __init__(self, params: TrainParams, line,
                 position: float = 0.0, speed: float = 0.0,
                 mode: str = "cbtc"):
        """
        mode:
            "cbtc"      通信列车，位置由车地通信提供，位置精度高
            "non_cbtc"  非通信列车，位置靠计轴/轨道电路，位置精度低
        """
        self.p = params
        self.line = line
        self.mode = mode
        self.position = position
        self.speed = speed
        self.accel = 0.0
        self.cmd_traction = 0.0
        self.cmd_brake = 0.0
        self.eb_active = False
        self.sb_active = False
        self.total_distance = 0.0
        # Y 型线路：分支跟踪
        self.current_branch = "common"
        self.passed_switches = set()

        # 全局位置上限（所有分支的最大值）
        self._max_position = max(
            (line.branch_length(br) for br in
             {seg.branch for seg in line.segments}),
            default=line.branch_length("common")
        )

    @property
    def tail_position(self) -> float:
        return self.position - self.p.length

    @property
    def is_cbtc(self) -> bool:
        return self.mode == "cbtc"

    def resistance_accel(self, v: float) -> float:
        v = abs(v)
        return self.p.davis_a0 + self.p.davis_a1 * v + self.p.davis_a2 * v * v

    def set_command(self, traction: float, brake: float):
        self.cmd_traction = max(0.0, min(1.0, traction))
        self.cmd_brake = max(0.0, min(1.0, brake))

    def update(self, dt: float):
        v = self.speed
        a_tract = self.cmd_traction * self.p.max_traction_accel
        a_brake = self.cmd_brake * self.p.max_brake_accel
        a_res = self.resistance_accel(v)
        grad = self.line.gradient_at(self.position, self.current_branch)
        a_grad = 9.81 * grad

        a = a_tract - a_brake - a_res - a_grad
        v_new = v + a * dt
        if v_new < 0.0:
            v_new = 0.0
            a = (v_new - v) / dt if dt > 0 else 0.0

        ds = (v + v_new) * 0.5 * dt
        self.position += ds
        self.total_distance += ds
        self.speed = v_new
        self.accel = a

        # 位置上限用"所有分支的最大值"，允许列车在进路允许时跨越道岔
        if self.position > self._max_position:
            self.position = self._max_position
            self.speed = 0.0

    def __repr__(self):
        return (f"Train({self.p.name}, pos={self.position:8.1f}m, "
                f"v={self.speed:6.2f}m/s, a={self.accel:+.3f}, "
                f"branch={self.current_branch}, mode={self.mode})")
"""仿真核心：时钟、日志、数据结构"""
import logging
from dataclasses import dataclass, field
from typing import List, Tuple


# ======================================================================
# 日志系统
#
# - root logger 上挂两个 handler：StreamHandler（终端）+ FileHandler（文件）
# - 每个模块的 logger 通过 propagate=True 把日志交给 root
# - 文件用 UTF-8，中文不会乱码
# - 注意：print 的输出只走终端，不进文件；要进文件请用 log.info
# ======================================================================

_ROOT_READY = False


def _configure_root(log_file="cbtc_sim.log"):
    global _ROOT_READY
    if _ROOT_READY:
        return

    root = logging.getLogger()
    root.setLevel(logging.INFO)

    fmt = logging.Formatter(
        "%(asctime)s [%(name)-5s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S")

    # 终端
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)

    # 文件（追加 + 每次运行加分隔线）
    if log_file:
        import datetime
        with open(log_file, "a", encoding="utf-8") as f:
            f.write("\n")
            f.write("#" * 80 + "\n")
            f.write(f"# New run at {datetime.datetime.now()}\n")
            f.write("#" * 80 + "\n")

        fh = logging.FileHandler(log_file, mode="a", encoding="utf-8")
        fh.setFormatter(fmt)
        root.addHandler(fh)

    _ROOT_READY = True

def get_logger(name, level=logging.INFO, log_file="cbtc_sim.log"):
    _configure_root(log_file)
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.propagate = True
    return logger


# ======================================================================
# 仿真时钟
# ======================================================================

class Clock:
    """固定步长仿真时钟"""

    def __init__(self, dt: float = 0.1, t_max: float = 600.0):
        self.dt = dt
        self.t_max = t_max
        self.t = 0.0

    def step(self):
        self.t += self.dt

    def done(self) -> bool:
        return self.t >= self.t_max

    def __repr__(self):
        return f"Clock(t={self.t:.2f}, dt={self.dt})"


# ======================================================================
# 数据结构
# ======================================================================

@dataclass
class MovementAuthority:
    """
    移动授权（MA）：ZC 发给车载 ATP 的行车许可

    属性：
      - end_position: 车头最远可达位置 (m)
      - end_speed:    终点允许速度 (m/s)，通常为 0（停车点）
      - restrictions: [(位置, 限速), ...] 沿途限速点（预留）
    """
    end_position: float
    end_speed: float = 0.0
    restrictions: List[Tuple[float, float]] = field(default_factory=list)

    def __repr__(self):
        return (f"MA(end={self.end_position:.1f}m, "
                f"v_end={self.end_speed:.1f}m/s, "
                f"n_restr={len(self.restrictions)})")
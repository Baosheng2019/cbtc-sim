"""
Step 2: 两车 + 移动闭塞 + MA 动态更新
目标：
  1. 后车 T2 通过 ZC 获取动态 MA
  2. 验证移动闭塞：MA 终点随前车实时移动
  3. 观察 T2 如何保持安全间隔追踪 T1
"""
from cbtc.core import get_logger
from cbtc.track import Line, Segment
from cbtc.train import Train, TrainParams
from cbtc.sim import Simulation
from cbtc.viz import plot_detailed_results, plot_position_diagnostics

log = get_logger("Step2")


def build_line():
    """构建一条演示线路，包含限速变化与坡度"""
    return Line([
        Segment(0,    800,  22.0, gradient=0.0),    # 平路
        Segment(800,  1500, 16.0, gradient=0.01),   # 上坡 1%，限速 58km/h
        Segment(1500, 2500, 22.0, gradient=0.0),
        Segment(2500, 3000, 8.0,  gradient=-0.02),  # 下坡 2%，进站限速
        Segment(3000, 3500, 22.0, gradient=0.0),
    ], name="Demo Line")


def main():
    line = build_line()

    # T1 在前方，T2 在后方
    t1 = Train(TrainParams(name="T1"), line, position=600.0, speed=15.0)
    t2 = Train(TrainParams(name="T2"), line, position=0.0,   speed=0.0)

    sim = Simulation(
        line, [t2, t1],   # 注意：T2 排前面方便日志显示，不影响逻辑
        cfg={
            "dt": 0.1,
            "t_max": 300.0,
            # ZC 配置：安全距离和定位误差
            "zc":  {"safety_distance": 50.0, "pos_uncertainty": 5.0},
            # ATP 配置
            "atp": {"eb_decel": 1.0, "sb_decel": 0.5,
                    "reaction_time": 1.0, "safety_margin": 10.0},
            # ATO 配置：带动态前瞻
            "ato": {
                "kp": 0.8,
                "v_margin": 0.95,
                "dead_band": 0.5,
                "lookahead_distance": 2000.0,
                "comfort_decel": 0.5,
            },
        }
    )

    def cb(s):
        if int(s.clock.t) % 20 == 0:
            gap = t1.tail_position - t2.position
            ma_end = getattr(t2, "current_ma", None)
            ma_str = f"{ma_end.end_position:7.1f}" if ma_end else "  --   "
            log.info(
                "t=%5.1f | T1 p=%6.1f v=%5.2f | T2 p=%6.1f v=%5.2f | "
                "gap=%6.1f | MA_end=%s",
                s.clock.t,
                t1.position, t1.speed,
                t2.position, t2.speed,
                gap, ma_str
            )

    sim.run(callback=cb)

    # 结束统计
    gap = t1.tail_position - t2.position
    print("\n===== Step 2 结果 =====")
    print(f"T1 最终: pos={t1.position:7.1f} m, v={t1.speed:5.2f} m/s")
    print(f"T2 最终: pos={t2.position:7.1f} m, v={t2.speed:5.2f} m/s")
    print(f"最终车距 (T1 车尾 - T2 车头): {gap:6.1f} m")
    print(f"EB 触发次数: T1={sum(h['T1_eb'] for h in sim.history)}, "
          f"T2={sum(h['T2_eb'] for h in sim.history)}")
    print(f"SB 触发次数: T1={sum(h['T1_sb'] for h in sim.history)}, "
          f"T2={sum(h['T2_sb'] for h in sim.history)}")

    # 出图
    plot_detailed_results(sim.history, line, [t1, t2],
                          save_path="step2_detailed.png")
    plot_position_diagnostics(sim.history, line, [t1, t2],
                              save_path="step2_position_diag.png")


if __name__ == "__main__":
    main()
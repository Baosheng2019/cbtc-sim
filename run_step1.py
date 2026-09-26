"""
Step 1: 单车 + 线路限速 + ATP 制动曲线
目标：理解 ATP 如何根据线路限速和 MA 计算制动曲线，ATO 如何控车
"""
from cbtc.core import get_logger
from cbtc.track import Line, Segment
from cbtc.train import Train, TrainParams
from cbtc.sim import Simulation
from cbtc.viz import plot_detailed_results, plot_position_diagnostics

log = get_logger("Step1")


def build_line():
    return Line([
        Segment(0,    500,  22.0),    # ~80 km/h
        Segment(500,  1200, 16.0),    # ~58 km/h 弯道
        Segment(1200, 2000, 22.0),
        Segment(2000, 2400, 8.0),     # 进站限速
        Segment(2400, 2500, 22.0),
    ], name="Demo Line")


def main():
    line = build_line()
    train = Train(TrainParams(name="T1"), line, position=0.0, speed=0.0)

    sim = Simulation(
        line, [train],
        cfg={
            "dt": 0.1,
            "t_max": 250.0,
            "atp": {"eb_decel": 1.0, "sb_decel": 0.5,
                    "reaction_time": 1.0, "safety_margin": 10.0},
            # 修改 ATO 配置，加入动态前瞻参数
            "ato": {
                "kp": 0.8, 
                "v_margin": 0.95,
                "dead_band": 0.5,               # 加大死区，进一步抑制抖振
                "lookahead_distance": 2000.0,   # 向前看 2000m
                "comfort_decel": 0.5            # 舒适减速度 0.5 m/s^2
            },
        }
    )

    def cb(s):
        if int(s.clock.t) % 20 == 0:
            log.info("%s", train)

    sim.run(callback=cb)

    print(f"\n最终位置: {train.position:.1f} m / {line.length:.1f} m")
    print(f"最终速度: {train.speed:.3f} m/s")
    print(f"仿真时长: {sim.clock.t:.1f} s")


    # 生成原有的详细诊断图（6图）
    plot_detailed_results(sim.history, line, [train], save_path="step1_detailed.png")
    
    # 新增：生成以距离为横轴的诊断图（2图）
    plot_position_diagnostics(sim.history, line, [train], save_path="step1_position_diag.png")

if __name__ == "__main__":
    main()
"""Step 5B：Y 型线路 + CI + 进路排列"""
from cbtc.core import get_logger
from cbtc.track import Line
from cbtc.train import Train, TrainParams
from cbtc.sim import Simulation
from cbtc.viz import plot_detailed_results, plot_position_diagnostics

log = get_logger("Step5B")


def main():
    line = Line.from_yaml("configs/line_demo.yaml")
    log.info("加载线路: %s", line.name)

    train = Train(TrainParams(name="T1"), line, position=0.0, speed=0.0)

    sim = Simulation(
        line, [train],
        cfg={
            "dt": 0.1,
            "t_max": 700.0,
            "zc":  {"safety_distance": 50.0, "pos_uncertainty": 5.0},
            "atp": {"eb_decel": 1.0, "sb_decel": 0.5,
                    "reaction_time": 1.0, "safety_margin": 0.0},
            "ato": {
                "kp": 0.8, "v_margin": 0.95, "dead_band": 0.5,
                "lookahead_distance": 2000.0, "comfort_decel": 0.5,
                "stop_decel": 0.8, "stop_zone": 0.3,
            },
        }
    )

    # 关键：注册服务计划（改 ["A","B","E"] 就能跑支线）
    sim.ats.register_train(train, service_plan=["A", "B", "D"])

    def cb(s):
        if int(s.clock.t) % 30 == 0:
            station = sim.ats._current_station(train)
            nxt = (f"{station.name}@{station.position:.0f}({station.branch})"
                   if station else "None")
            log.info("%s | next=%s | MA_end=%.0f | route_end=%s | dwell=%s",
                     train, nxt,
                     getattr(train, "current_ma",
                             type("X", (), {"end_position": 0})()).end_position,
                     sim.ci.route_end_for(train),
                     sim.ats.is_dwelling(train))

    sim.run(callback=cb)

    print("\n===== Step 5B Result =====")
    print(f"Final position: {train.position:.2f} m")
    print(f"Current branch: {train.current_branch}")
    print(f"Switch states:  {sim.ci.switch_states}")
    print(f"Passed switches: {sorted(train.passed_switches)}")

    plot_detailed_results(sim.history, line, [train],
                          save_path="step5b_detailed.png")
    plot_position_diagnostics(sim.history, line, [train],
                              save_path="step5b_position_diag.png")


if __name__ == "__main__":
    main()

import sys
import io
# 让 stdout/stderr 强制用 UTF-8
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if sys.stderr.encoding != "utf-8":
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")   
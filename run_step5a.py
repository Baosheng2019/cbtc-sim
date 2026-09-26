"""Step 5A：Y 型线路拓扑，验证道岔约束"""
from cbtc.core import get_logger
from cbtc.track import Line
from cbtc.train import Train, TrainParams
from cbtc.sim import Simulation
from cbtc.viz import plot_detailed_results, plot_position_diagnostics

log = get_logger("Step5A")


def main():
    line = Line.from_yaml("configs/line_demo.yaml")
    log.info("加载线路: %s", line.name)
    for br in {"common", "main", "branch"}:
        log.info("  分支 %-7s 长度=%.0fm", br, line.branch_length(br))
    for sw in line.switches:
        log.info("  道岔 %s @ %.0fm (定位→%s, 反位→%s)",
                 sw.name, sw.position, sw.normal_branch, sw.reverse_branch)

    train = Train(TrainParams(name="T1"), line, position=0.0, speed=0.0)

    sim = Simulation(
        line, [train],
        cfg={
            "dt": 0.1,
            "t_max": 600.0,
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

    def cb(s):
        if int(s.clock.t) % 30 == 0:
            state = sim.ats.schedule[train]
            station = line.station_by_index(state["next_station_idx"])
            nxt = f"{station.name}@{station.position:.0f}({station.branch})" \
                if station else "None"
            log.info("%s | next=%s | MA_end=%.0f | dwelling=%s",
                     train, nxt,
                     getattr(train, "current_ma",
                             type("X", (), {"end_position": 0})()).end_position,
                     sim.ats.is_dwelling(train))

    sim.run(callback=cb)

    print("\n===== Step 5A 结果 =====")
    print(f"最终位置: {train.position:.2f} m")
    print(f"当前分支: {train.current_branch}")
    print(f"过道岔: {sorted(train.passed_switches)}")

    plot_detailed_results(sim.history, line, [train],
                          save_path="step5a_detailed.png")
    plot_position_diagnostics(sim.history, line, [train],
                              save_path="step5a_position_diag.png")


if __name__ == "__main__":
    main()
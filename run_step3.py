"""
Step 3: 车站 + 精确停车 + 停站/发车
线路数据来自 configs/line_demo.yaml
"""
from cbtc.core import get_logger
from cbtc.track import Line
from cbtc.train import Train, TrainParams
from cbtc.sim import Simulation
from cbtc.viz import plot_detailed_results, plot_position_diagnostics

log = get_logger("Step3")


def main():
    line = Line.from_yaml("configs/line_demo.yaml")
    log.info("加载线路: %s, 长度=%.0fm, 车站数=%d",
             line.name, line.length, len(line.stations))

    train = Train(TrainParams(name="T1"), line, position=0.0, speed=0.0)

    sim = Simulation(
        line, [train],
        cfg={
            "dt": 0.1,
            "t_max": 900.0,       # <-- 改大
            "zc":  {"safety_distance": 50.0, "pos_uncertainty": 5.0},
            "atp": {"eb_decel": 1.0, "sb_decel": 0.5,
                    "reaction_time": 1.0, "safety_margin": 0.0},
            "ato": {
                "kp": 0.8, "v_margin": 0.95, "dead_band": 0.5,
                "lookahead_distance": 2000.0, "comfort_decel": 0.5,
                "stop_decel": 0.8,
                "stop_zone": 0.3,
            },
        }
    )

    def cb(s):
        if int(s.clock.t) % 20 == 0:
            state = sim.ats.schedule[train]
            station = line.station_by_index(state["next_station_idx"])
            next_stop = station.position if station else line.length
            log.info("%s | next_stop=%.0f | MA_end=%.0f | dwelling=%s",
                     train, next_stop,
                     getattr(train, "current_ma",
                             type("X", (), {"end_position": 0})()).end_position,
                     sim.ats.is_dwelling(train))

    sim.run(callback=cb)

    print("\n===== Step 3 结果 =====")
    for st in line.stations:
        print(f"  车站 {st.name} @ {st.position:.0f}m 停站 {st.dwell_time}s")
    print(f"最终位置: {train.position:.2f} m / 线路 {line.length:.0f} m")

    plot_detailed_results(sim.history, line, [train],
                          save_path="step3_detailed.png")
    plot_position_diagnostics(sim.history, line, [train],
                              save_path="step3_position_diag.png")


if __name__ == "__main__":
    main()
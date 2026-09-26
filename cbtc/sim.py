"""仿真主循环（Step 5B：含 CI）"""
from .core import Clock, get_logger
from .zc import ZC
from .atp import ATP
from .ato import ATO
from .ats import ATS
from .ci import CI

log = get_logger("Sim")


class Simulation:
    def __init__(self, line, trains, cfg=None):
        cfg = cfg or {}
        self.line = line
        self.trains = trains
        self.clock = Clock(cfg.get("dt", 0.1), cfg.get("t_max", 300.0))
        self.ci = CI(line, cfg.get("ci", {}))
        self.zc = ZC(line, cfg.get("zc", {}))
        self.atps = [ATP(t, line, cfg.get("atp", {})) for t in trains]
        self.atos = [ATO(cfg.get("ato", {})) for _ in trains]
        self.ats = ATS(line, ci=self.ci, cfg=cfg.get("ats", {}))
        self.history = []
        self.record()

    def _find_leading(self, train):
        ahead = [t for t in self.trains
                 if t is not train and t.position > train.position]
        if not ahead:
            return None
        return min(ahead, key=lambda t: t.position - train.position)

    def _update_branches(self):
        """列车过道岔时切换分支"""
        for t in self.trains:
            for sw in self.line.switches:
                if sw.name in t.passed_switches:
                    continue
                if t.position >= sw.position:
                    new_branch = (
                        sw.normal_branch
                        if self.ci.switch_states[sw.name] == "normal"
                        else sw.reverse_branch
                    )
                    log.info("[Sim] %s 过道岔 %s：%s → %s",
                             t.p.name, sw.name, t.current_branch, new_branch)
                    t.current_branch = new_branch
                    t.passed_switches.add(sw.name)

    def step(self):
        dt = self.clock.dt
        self.ats.tick(dt)
        self._update_branches()

        # ZC 计算 MA（route_end 来自 CI）
        mas = []
        for t in self.trains:
            lead = self._find_leading(t)
            route_end = self.ci.route_end_for(t)
            ma = self.zc.compute_ma(t, lead, route_end=route_end)
            mas.append(ma)
            t.current_ma = ma

        for t, atp, ato, ma in zip(self.trains, self.atps, self.atos, mas):
            if self.ats.is_dwelling(t):
                t.eb_active = False
                t.sb_active = False
                t.set_command(0.0, 0.5)
                continue

            next_stop = self.ats.next_stop_position(t)
            limits = atp.evaluate(ma)
            traction, brake = ato.compute(t, self.line, ma, limits,
                                          next_stop_position=next_stop)

            if limits.eb_active:
                t.eb_active = True
                t.sb_active = False
                traction, brake = 0.0, 1.0
            elif limits.sb_active:
                t.eb_active = False
                t.sb_active = True
                traction = 0.0
                brake = max(brake, limits.sb_demand)
            else:
                t.eb_active = False
                t.sb_active = False

            t.set_command(traction, brake)

            station = self.ats._current_station(t)
            if station is not None:
                if (t.speed < 0.15
                        and abs(t.position - station.position) <= station.stop_window
                        and t.current_branch == station.branch):
                    self.ats.on_train_stopped(t)

        for t in self.trains:
            t.update(dt)

        self.clock.step()
        self.record()

    def record(self):
        row = {"t": self.clock.t}
        for t in self.trains:
            name = t.p.name
            row[f"{name}_pos"] = t.position
            row[f"{name}_v"] = t.speed
            row[f"{name}_a"] = t.accel
            row[f"{name}_eb"] = t.eb_active
            row[f"{name}_sb"] = t.sb_active
            row[f"{name}_grad"] = self.line.gradient_at(t.position,
                                                        t.current_branch)
            ma = getattr(t, 'current_ma', None)
            row[f"{name}_ma_end"] = ma.end_position if ma else 0.0
            row[f"{name}_dwelling"] = self.ats.is_dwelling(t)
            next_stop = self.ats.next_stop_position(t)
            row[f"{name}_stop"] = next_stop if next_stop is not None else 0.0
            row[f"{name}_branch"] = t.current_branch
        self.history.append(row)

    def run(self, callback=None, cb_every=10):
        while not self.clock.done():
            self.step()
            if callback and len(self.history) % cb_every == 0:
                callback(self)
        return self.history
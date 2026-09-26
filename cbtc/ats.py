"""ATS：列车自动监控（服务计划 + 进路申请）"""
from .core import get_logger

log = get_logger("ATS")


class ATS:
    def __init__(self, line, ci=None, cfg=None):
        cfg = cfg or {}
        self.line = line
        self.ci = ci
        self.schedule = {}   # train -> {"next_station_idx", "dwell_remaining"}
        self.plans = {}      # train -> [Station, ...]

    def register_train(self, train, service_plan):
        """
        service_plan: 站点名列表，例如 ["A", "B", "D"]
        """
        stations = []
        for name in service_plan:
            st = self.line.station_by_name(name)
            if st is None:
                raise ValueError(f"未知站点: {name}")
            stations.append(st)
        self.plans[train] = stations
        self.schedule[train] = {"next_station_idx": 0, "dwell_remaining": 0.0}
        log.info("[ATS] 注册列车 %s，服务计划=%s",
                 train.p.name, [s.name for s in stations])

        # 申请第一条进路：从起点到计划中的第一站
        if stations:
            self._request_route(train, from_station=None,
                                to_station=stations[0])

    def _current_station(self, train):
        """返回本车计划里的下一站"""
        state = self.schedule.get(train)
        if state is None:
            return None
        plan = self.plans.get(train, [])
        idx = state["next_station_idx"]
        if 0 <= idx < len(plan):
            return plan[idx]
        return None

    def next_stop_position(self, train):
        st = self._current_station(train)
        return st.position if st else None

    def on_train_stopped(self, train):
        st = self._current_station(train)
        if st is None:
            return
        state = self.schedule[train]
        if state["dwell_remaining"] > 0:
            return
        state["dwell_remaining"] = st.dwell_time
        log.info("[ATS] %s 到达 %s，停站 %.1fs",
                 train.p.name, st.name, st.dwell_time)

    def is_dwelling(self, train):
        state = self.schedule.get(train)
        return state is not None and state["dwell_remaining"] > 0

    def tick(self, dt):
        for train, state in self.schedule.items():
            if state["dwell_remaining"] > 0:
                state["dwell_remaining"] -= dt
                if state["dwell_remaining"] <= 0:
                    state["dwell_remaining"] = 0.0

                    # 释放旧进路
                    if self.ci:
                        self.ci.release_route(train)

                    # 前进到下一站
                    prev = self._current_station(train)
                    state["next_station_idx"] += 1
                    nxt = self._current_station(train)
                    if nxt is None:
                        log.info("[ATS] %s 服务计划已完成", train.p.name)
                        continue

                    # 申请新进路
                    self._request_route(train, from_station=prev,
                                        to_station=nxt)
                    log.info("[ATS] %s 发车，目标 %s",
                             train.p.name, nxt.name)

    def _request_route(self, train, from_station, to_station):
        if self.ci is None:
            return
        self.ci.request_route(train, from_station, to_station)
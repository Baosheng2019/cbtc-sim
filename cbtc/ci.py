"""CI：计算机联锁（含区段占用融合与故障处理）"""
from .core import get_logger

log = get_logger("CI")


class Route:
    """一条进路"""
    def __init__(self, route_id, from_station, to_station,
                 switch_settings, end_position,
                 route_type="cbtc", covered_sections=None):
        self.route_id = route_id
        self.from_station = from_station
        self.to_station = to_station
        self.switch_settings = switch_settings
        self.end_position = end_position
        self.route_type = route_type
        self.covered_sections = covered_sections or []
        self.locked = False
        self.owner = None


class CI:
    def __init__(self, line, cfg=None):
        cfg = cfg or {}
        self.line = line
        # 初始所有道岔在定位
        self.switch_states = {sw.name: "normal" for sw in line.switches}
        self.routes = {}
        self.active_route = {}   # train -> Route

        # 每个区段的运行时状态
        self.section_state = {
            sec.name: {
                "physical": False,      # 物理采集：计轴/轨道电路
                "logical": False,       # 逻辑采集：ZC 上报的 CBTC 占用
                "fault_type": None,     # None / "ARB"
                "locked_by": None,      # 被哪条进路锁闭
            }
            for sec in line.sections
        }

    # ==================================================================
    # 故障注入 API（供实验调用）
    # ==================================================================
    def inject_fault(self, section_name, fault_type=None,
                     physical=None, logical=None):
        """向指定区段注入故障/占用状态"""
        st = self.section_state.get(section_name)
        if st is None:
            log.warning("[CI] 未知区段: %s", section_name)
            return False
        if fault_type is not None:
            st["fault_type"] = fault_type
        if physical is not None:
            st["physical"] = physical
        if logical is not None:
            st["logical"] = logical
        log.info("[CI] 注入故障: %s fault=%s phys=%s logic=%s",
                 section_name, st["fault_type"], st["physical"], st["logical"])
        return True

    def clear_fault(self, section_name):
        st = self.section_state.get(section_name)
        if st is None:
            return False
        st["physical"] = False
        st["logical"] = False
        st["fault_type"] = None
        return True

    # ==================================================================
    # 区段占用融合（核心）
    # ==================================================================
    def _fuse_section_state(self, section_name, purpose="route_setup"):
        """
        融合判定：
          - 安全侧：任何一路报占用 → safe_occupied = True
          - ARB 绕过：已确认 ARB + 逻辑空闲 + purpose 允许 → 允许
          purpose:
            "route_setup"   进路建立（CBTC 不检查被跳过的区段，
                            但被检查的区段一律保守）
            "switch_throw"  道岔转换（ARB + 逻辑空闲 → 允许转换）
        """
        st = self.section_state.get(section_name)
        if st is None:
            return {
                "effective_occupied": False,
                "safe_occupied": False,
                "physical": False,
                "logical": False,
                "is_arb": False,
                "arb_bypassable": False,
                "display": "unknown",
            }

        physical = st["physical"]
        logical = st["logical"]
        is_arb = (st["fault_type"] == "ARB")

        # 与占用原则：任何一路报占用，安全状态即为占用
        safe_occupied = physical or logical

        # ARB 绕过条件：已确认 ARB + 逻辑空闲
        arb_bypassable = is_arb and not logical

        # 只有 purpose="switch_throw" 时，ARB + 逻辑空闲才允许绕过
        if purpose == "switch_throw" and arb_bypassable:
            effective_occupied = False
        else:
            effective_occupied = safe_occupied

        # HMI 显示优先级
        if physical and logical:
            display = "conflict"       # 物理逻辑都占用（最严重）
        elif physical and is_arb:
            display = "arb"            # 物理 ARB
        elif physical:
            display = "physical"       # 真实物理占用
        elif logical:
            display = "cbtc"           # CBTC 逻辑占用
        else:
            display = "clear"

        return {
            "effective_occupied": effective_occupied,
            "safe_occupied": safe_occupied,
            "physical": physical,
            "logical": logical,
            "is_arb": is_arb,
            "arb_bypassable": arb_bypassable,
            "display": display,
        }

    # ==================================================================
    # 进路覆盖区段
    # ==================================================================
    def _covered_sections(self, from_pos, to_pos, to_branch):
        """
        计算进路覆盖的区段：
          - 只考虑 common 分支 + 目标分支（避免误匹配另一条支线）
          - 位置范围要与 [from_pos, to_pos] 有交集
        """
        valid_branches = {"common", to_branch}
        result = []
        for sec in self.line.sections:
            if sec.end <= from_pos or sec.start >= to_pos:
                continue
            if sec.branch not in valid_branches:
                continue
            result.append(sec.name)
        return result

    # ==================================================================
    # 进路空闲检查（按进路类型分级）
    # ==================================================================
    def _check_route_free(self, covered_sections, route_type):
        """
        返回 (ok, failures)
          - CBTC：只检查第一个区段
          - 非CBTC：检查整条进路
        """
        if not covered_sections:
            return True, []

        if route_type == "cbtc":
            check_list = covered_sections[:1]     # 只查第一区段
        else:
            check_list = covered_sections         # 整条

        failures = []
        for name in check_list:
            fuse = self._fuse_section_state(name, purpose="route_setup")
            if fuse["effective_occupied"]:
                failures.append((name, fuse))
        return len(failures) == 0, failures

    # ==================================================================
    # 道岔查询
    # ==================================================================
    def _find_switches_between(self, from_pos, to_pos, to_branch):
        """找出 [from_pos, to_pos] 间需要操作的道岔及其目标状态"""
        settings = {}
        for sw in self.line.switches:
            if from_pos < sw.position <= to_pos:
                if to_branch == sw.normal_branch:
                    settings[sw.name] = "normal"
                elif to_branch == sw.reverse_branch:
                    settings[sw.name] = "reverse"
        return settings

    def _section_of_switch(self, sw_name):
        """找出道岔所在区段（哪个区段包含了道岔的位置）"""
        sw_pos = None
        for sw in self.line.switches:
            if sw.name == sw_name:
                sw_pos = sw.position
                break
        if sw_pos is None:
            return None
        for sec in self.line.sections:
            if sec.start < sw_pos <= sec.end:
                return sec.name
        return None

    # ==================================================================
    # 进路排列
    # ==================================================================
    def request_route(self, train, from_station, to_station,
                      route_type="cbtc"):
        """
        ATS 申请进路：从 from_station 到 to_station
        route_type: "cbtc" / "non_cbtc"
        """
        from_pos = (train.position if from_station is None
                    else from_station.position)
        to_pos = to_station.position

        # 1. 计算覆盖区段
        covered = self._covered_sections(from_pos, to_pos, to_station.branch)

        # 2. 按进路类型检查空闲
        ok, failures = self._check_route_free(covered, route_type)
        if not ok:
            log.warning("[CI] 进路排列失败 (%s): %d 个区段占用",
                        route_type, len(failures))
            for name, fuse in failures:
                log.warning(
                    "[CI]   区段 %s: display=%s physical=%s logical=%s arb=%s",
                    name, fuse["display"], fuse["physical"],
                    fuse["logical"], fuse["is_arb"])
            return None

        # 3. 处理道岔（switch_throw 语义下允许 ARB 绕过）
        settings = self._find_switches_between(from_pos, to_pos,
                                               to_station.branch)
        for sw_name, target in settings.items():
            sw_section = self._section_of_switch(sw_name)
            if sw_section:
                fuse = self._fuse_section_state(sw_section,
                                                purpose="switch_throw")
                if fuse["effective_occupied"]:
                    log.warning(
                        "[CI] 道岔 %s 所在区段 %s 占用，拒绝进路",
                        sw_name, sw_section)
                    return None
                if fuse["arb_bypassable"]:
                    log.info(
                        "[CI] 道岔 %s 所在区段 %s 处于 ARB，降级允许",
                        sw_name, sw_section)

            if self.switch_states[sw_name] != target:
                log.info("[CI] 道岔 %s: %s → %s",
                         sw_name, self.switch_states[sw_name], target)
                self.switch_states[sw_name] = target

        # 4. 建立进路
        from_name = from_station.name if from_station else "起点"
        route_id = f"{from_name}->{to_station.name}"
        route = Route(route_id, from_station, to_station,
                      settings, to_pos,
                      route_type=route_type,
                      covered_sections=covered)
        route.locked = True
        route.owner = train
        self.routes[route_id] = route
        self.active_route[train] = route

        # 5. 锁闭覆盖区段
        for name in covered:
            if name in self.section_state:
                self.section_state[name]["locked_by"] = route_id

        log.info("[CI] 排列进路 %s [%s] → 终点=%.0fm (%s), 道岔=%s, 覆盖=%s",
                 route_id, route_type, to_station.position,
                 to_station.branch, settings or "无", covered)
        return route

    # ==================================================================
    # 道岔转换（独立 API，供实验直接调用）
    # ==================================================================
    def throw_switch(self, switch, target_position):
        sec_name = self._section_of_switch(switch.name)
        if sec_name:
            fuse = self._fuse_section_state(sec_name, purpose="switch_throw")
            if fuse["effective_occupied"]:
                log.warning("[CI] 道岔 %s 无法转换: 区段 %s %s",
                            switch.name, sec_name, fuse["display"])
                return False
            if fuse["arb_bypassable"]:
                log.info("[CI] 道岔 %s 转换: 区段 %s 处于 ARB，降级允许",
                         switch.name, sec_name)
        self.switch_states[switch.name] = target_position
        log.info("[CI] 道岔 %s → %s", switch.name, target_position)
        return True

    # ==================================================================
    # 进路释放
    # ==================================================================
    def route_end_for(self, train):
        """ZC 询问：这列车当前的进路终点在哪？"""
        route = self.active_route.get(train)
        return route.end_position if route else None

    def release_route(self, train):
        """列车到达目的地后释放进路"""
        route = self.active_route.pop(train, None)
        if route:
            route.locked = False
            for name in route.covered_sections:
                if name in self.section_state:
                    self.section_state[name]["locked_by"] = None
            log.info("[CI] 释放进路 %s", route.route_id)
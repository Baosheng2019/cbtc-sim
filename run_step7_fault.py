"""Step 7：故障占用场景对照实验（CBTC / 非CBTC / ARB）"""
from cbtc.core import get_logger
from cbtc.track import Line
from cbtc.train import Train, TrainParams
from cbtc.ci import CI

log = get_logger("Step7")


def make_train(line, name, pos, mode="cbtc"):
    t = Train(TrainParams(name=name), line, position=pos, speed=0.0, mode=mode)
    return t


def report(label, route):
    status = "OK 成功" if route else "XX 失败"
    log.info("  %-52s → %s", label, status)


def scenario_1_failed_vacant():
    log.info("=" * 72)
    log.info(" 实验 1：Failed Vacant（物理空闲、逻辑占用）")
    log.info("=" * 72)
    log.info(" 背景：T1(CBTC) 停在 S2(1000m)，计轴故障导致 S2 物理显示空闲")
    log.info("      但 ZC 知道 T1 在那里（逻辑占用）")

    line = Line.from_yaml("configs/line_demo.yaml")
    ci = CI(line)

    # S2 = Failed Vacant
    ci.inject_fault("S2", fault_type=None, physical=False, logical=True)

    applicant = make_train(line, "T2", 0.0, mode="cbtc")
    station_B = line.station_by_name("B")

    log.info("  场景 1a：CBTC 列车请求 起点→B 进路")
    route = ci.request_route(applicant, None, station_B, route_type="cbtc")
    report("CBTC 模式 起点→B", route)

    log.info("  场景 1b：非CBTC 列车请求 起点→B 进路")
    route = ci.request_route(applicant, None, station_B, route_type="non_cbtc")
    report("非CBTC 模式 起点→B", route)

    log.info("  预期：")
    log.info("    CBTC 成功 → 只检查始端第一区段(S1)，S1 空闲")
    log.info("    非CBTC 失败 → 检查整条进路(S1+S2)，S2 逻辑占用")


def scenario_2_arb_switch():
    log.info("=" * 72)
    log.info(" 实验 2：ARB 场景下的道岔转换")
    log.info("=" * 72)
    log.info(" 背景：S3 触发 ARB（物理占用、逻辑空闲、已确认故障）")

    line = Line.from_yaml("configs/line_demo.yaml")
    ci = CI(line)
    sw1 = line.switches[0]

    # 场景 2a：ARB + 逻辑空闲
    ci.inject_fault("S3", fault_type="ARB", physical=True, logical=False)
    log.info("  场景 2a：ARB + 逻辑空闲 → 转换 SW1 到 reverse")
    ok = ci.throw_switch(sw1, "reverse")
    log.info("  转换 SW1 → reverse  → %s", "OK 允许" if ok else "XX 禁止")

    # 场景 2b：ARB + 逻辑占用
    ci.inject_fault("S3", logical=True)
    log.info("  场景 2b：ARB + 逻辑占用（有 CBTC 车）→ 转换 SW1 到 normal")
    ok = ci.throw_switch(sw1, "normal")
    log.info("  转换 SW1 → normal   → %s", "OK 允许" if ok else "XX 禁止")

    log.info("  预期：")
    log.info("    ARB + 逻辑空闲：允许（融合空闲）")
    log.info("    ARB + 逻辑占用：禁止（逻辑优先）")


def scenario_3_arb_route():
    log.info("=" * 72)
    log.info(" 实验 3：ARB 场景下的进路排列")
    log.info("=" * 72)
    log.info(" 背景：S3 触发 ARB（物理占用、逻辑空闲）")

    line = Line.from_yaml("configs/line_demo.yaml")
    ci = CI(line)

    ci.inject_fault("S3", fault_type="ARB", physical=True, logical=False)

    applicant = make_train(line, "T2", 0.0, mode="cbtc")
    station_D = line.station_by_name("D")

    log.info("  场景 3a：CBTC 列车请求 起点→D 进路（经过 S3、道岔 SW1）")
    route = ci.request_route(applicant, None, station_D, route_type="cbtc")
    report("CBTC 模式 起点→D", route)

    log.info("  场景 3b：非CBTC 列车请求 起点→D 进路")
    route = ci.request_route(applicant, None, station_D, route_type="non_cbtc")
    report("非CBTC 模式 起点→D", route)

    log.info("  预期：")
    log.info("    CBTC 成功（只查第一区段，ARB 区段不查）")
    log.info("    非CBTC 失败（检查整条进路，ARB 区段物理占用 → 拒绝）")
    log.info("    注：ARB 豁免只针对道岔转换，不针对进路建立")


def scenario_4_arb_vs_real_occupancy():
    log.info("=" * 72)
    log.info(" 实验 4：ARB vs 真实占用（对非CBTC 进路）")
    log.info("=" * 72)

    line = Line.from_yaml("configs/line_demo.yaml")
    ci = CI(line)

    applicant = make_train(line, "T2", 0.0, mode="non_cbtc")
    station_B = line.station_by_name("B")

    # 4a：真实占用
    ci.inject_fault("S2", fault_type=None, physical=True, logical=True)
    log.info("  场景 4a：S2 真实占用（有车）→ 非CBTC 请求 起点→B")
    route = ci.request_route(applicant, None, station_B, route_type="non_cbtc")
    report("非CBTC 起点→B（S2 真实占用）", route)

    # 4b：ARB
    ci.inject_fault("S2", fault_type="ARB", physical=True, logical=False)
    log.info("  场景 4b：S2 是 ARB（已确认故障、逻辑空闲）→ 非CBTC 请求 起点→B")
    route = ci.request_route(applicant, None, station_B, route_type="non_cbtc")
    report("非CBTC 起点→B（S2 是 ARB）", route)

    log.info("  预期：")
    log.info("    真实占用 → 拒绝（任何模式）")
    log.info("    ARB     → 非CBTC 进路同样拒绝（无法确认区段安全）")


def main():
    log.info("#" * 72)
    log.info("#  CBTC 故障占用场景对照实验 (Step 7)")
    log.info("#" * 72)

    scenario_1_failed_vacant()
    scenario_2_arb_switch()
    scenario_3_arb_route()
    scenario_4_arb_vs_real_occupancy()

    log.info("#" * 72)
    log.info("#  实验结束")
    log.info("#" * 72)


if __name__ == "__main__":
    main()
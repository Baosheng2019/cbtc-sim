"""可视化：位置、速度、加速度曲线"""
import matplotlib
matplotlib.use("Agg")   # 无 GUI 环境。本地有显示可以删掉这行
import matplotlib.pyplot as plt
import numpy as np


def plot_results(history, line, trains, save_path="result.png"):
    t = np.array([h["t"] for h in history])
    fig, axes = plt.subplots(2, 2, figsize=(14, 8))

    for tr in trains:
        name = tr.p.name
        pos = np.array([h[f"{name}_pos"] for h in history])
        v = np.array([h[f"{name}_v"] for h in history])
        a = np.array([h[f"{name}_a"] for h in history])

        axes[0, 0].plot(t, pos, label=name)
        axes[0, 1].plot(t, v, label=name)
        axes[1, 0].plot(pos, v, label=name, lw=1)
        axes[1, 1].plot(t, a, label=name)

    segs = line.segments
    xs = [s.start for s in segs] + [segs[-1].end]
    ys = [s.speed_limit for s in segs] + [segs[-1].speed_limit]
    axes[1, 0].step(xs, ys, where="post", color="red", ls="--", label="Line Limit")

    axes[0, 0].set_xlabel("Time [s]"); axes[0, 0].set_ylabel("Position [m]")
    axes[0, 0].set_title("Position vs Time")
    axes[0, 0].grid(True); axes[0, 0].legend()

    axes[0, 1].set_xlabel("Time [s]"); axes[0, 1].set_ylabel("Speed [m/s]")
    axes[0, 1].set_title("Speed vs Time")
    axes[0, 1].grid(True); axes[0, 1].legend()

    axes[1, 0].set_xlabel("Position [m]"); axes[1, 0].set_ylabel("Speed [m/s]")
    axes[1, 0].set_title("Speed Profile vs Position")
    axes[1, 0].grid(True); axes[1, 0].legend()

    axes[1, 1].set_xlabel("Time [s]"); axes[1, 1].set_ylabel("Accel [m/s^2]")
    axes[1, 1].set_title("Acceleration vs Time")
    axes[1, 1].grid(True); axes[1, 1].legend()

    plt.tight_layout()
    plt.savefig(save_path, dpi=120)
    print(f"[viz] Saved to {save_path}")
    plt.close()


def plot_detailed_results(history, line, trains, save_path="detailed_result.png"):
    t = np.array([h["t"] for h in history])
    
    fig, axes = plt.subplots(3, 2, figsize=(16, 12))
    
    for tr in trains:
        name = tr.p.name
        pos = np.array([h[f"{name}_pos"] for h in history])
        v = np.array([h[f"{name}_v"] for h in history])
        a = np.array([h[f"{name}_a"] for h in history])
        eb = np.array([h[f"{name}_eb"] for h in history], dtype=bool)
        sb = np.array([h[f"{name}_sb"] for h in history], dtype=bool)
        ma_end = np.array([h[f"{name}_ma_end"] for h in history])
        grad = np.array([h[f"{name}_grad"] for h in history]) * 100  # 转为百分比
        
        # --- 图1: 速度-位置曲线（带 EB/SB 标记） ---
        ax1 = axes[0, 0]
        ax1.plot(pos, v, label=f"{name} Speed", lw=1.5)
        if np.any(eb):
            ax1.scatter(pos[eb], v[eb], color='red', s=15, label='EB Trigger', zorder=5)
        if np.any(sb):
            ax1.scatter(pos[sb], v[sb], color='orange', s=10, label='SB Trigger', zorder=5)
        ax1.set_xlabel("Position [m]")
        ax1.set_ylabel("Speed [m/s]")
        ax1.set_title(f"Speed Profile vs Position ({name})")
        ax1.grid(True)
        ax1.legend()
        
        # --- 图2: 坡度-位置曲线 ---
        ax2 = axes[0, 1]
        ax2.plot(pos, grad, color='green', lw=1)
        ax2.axhline(0, color='black', linestyle='--', lw=0.8)
        ax2.set_xlabel("Position [m]")
        ax2.set_ylabel("Gradient [%]")
        ax2.set_title(f"Gradient Profile ({name})")
        ax2.grid(True)
        
        # --- 图3: 加速度-时间曲线（带 EB/SB 背景色） ---
        ax3 = axes[1, 0]
        ax3.plot(t, a, label=f"{name} Accel", lw=1)
        ax3.fill_between(t, -2, 2, where=eb, color='red', alpha=0.3, label='EB Active')
        ax3.fill_between(t, -2, 2, where=sb, color='orange', alpha=0.3, label='SB Active')
        ax3.set_xlabel("Time [s]")
        ax3.set_ylabel("Accel [m/s^2]")
        ax3.set_title(f"Acceleration vs Time ({name})")
        ax3.grid(True)
        ax3.legend()
        
        # --- 图4: MA 终点-位置曲线 ---
        ax4 = axes[1, 1]
        ax4.plot(pos, ma_end, color='purple', lw=1.5, label="MA End")
        ax4.plot(pos, pos, color='gray', linestyle='--', lw=1, label="Train Head")
        ax4.set_xlabel("Train Position [m]")
        ax4.set_ylabel("MA End Position [m]")
        ax4.set_title(f"MA End vs Train Position ({name})")
        ax4.grid(True)
        ax4.legend()

        # --- 图5: EB/SB 状态-时间阶梯图 ---
        ax5 = axes[2, 0]
        ax5.step(t, eb.astype(int), where='post', color='red', label='EB Active')
        ax5.step(t, sb.astype(int), where='post', color='orange', label='SB Active')
        ax5.set_xlabel("Time [s]")
        ax5.set_ylabel("State (0/1)")
        ax5.set_title(f"Brake State vs Time ({name})")
        ax5.set_ylim(-0.1, 1.1)
        ax5.grid(True)
        ax5.legend()

        # --- 图6: 速度-时间曲线 ---
        ax6 = axes[2, 1]
        ax6.plot(t, v, label=f"{name} Speed", lw=1.5)
        ax6.set_xlabel("Time [s]")
        ax6.set_ylabel("Speed [m/s]")
        ax6.set_title(f"Speed vs Time ({name})")
        ax6.grid(True)
        ax6.legend()

    plt.tight_layout()
    plt.savefig(save_path, dpi=120)
    print(f"[viz] Detailed result saved to {save_path}")
    plt.close()

def plot_position_diagnostics(history, line, trains, save_path="position_diagnostics.png"):
    """绘制以距离为横轴的：限速+车速+加速度，以及车速+加速度双轴图"""
    fig, axes = plt.subplots(2, 1, figsize=(14, 10))
    
    for tr in trains:
        name = tr.p.name
        pos = np.array([h[f"{name}_pos"] for h in history])
        v = np.array([h[f"{name}_v"] for h in history])
        a = np.array([h[f"{name}_a"] for h in history])
        
        # ================= 图 1：线路限速 + 车速 + 加速度 =================
        ax1 = axes[0]
        # 左侧 Y 轴：速度和限速
        ax1.plot(pos, v, label=f"{name} Speed", color='blue', lw=1.5)
        
        # 绘制线路限速阶梯图
        segs = line.segments
        xs = [s.start for s in segs] + [segs[-1].end]
        ys = [s.speed_limit for s in segs] + [segs[-1].speed_limit]
        ax1.step(xs, ys, where="post", color='red', linestyle="--", lw=1.5, label="Line Limit")
        
        ax1.set_xlabel("Position [m]")
        ax1.set_ylabel("Speed [m/s]", color='blue')
        ax1.tick_params(axis='y', labelcolor='blue')
        ax1.set_title(f"Speed, Line Limit & Acceleration vs Position ({name})")
        ax1.grid(True)
        
        # 右侧 Y 轴：加速度
        ax1_r = ax1.twinx()
        ax1_r.plot(pos, a, label=f"{name} Accel", color='orange', lw=1, alpha=0.8)
        ax1_r.set_ylabel("Accel [m/s^2]", color='orange')
        ax1_r.tick_params(axis='y', labelcolor='orange')
        
        # 合并图例
        lines1, labels1 = ax1.get_legend_handles_labels()
        lines2, labels2 = ax1_r.get_legend_handles_labels()
        ax1.legend(lines1 + lines2, labels1 + labels2, loc='upper right')
        
        # ================= 图 2：车速 + 加速度（合在一起） =================
        ax2 = axes[1]
        # 左侧 Y 轴：车速
        ax2.plot(pos, v, label=f"{name} Speed", color='blue', lw=1.5)
        ax2.set_xlabel("Position [m]")
        ax2.set_ylabel("Speed [m/s]", color='blue')
        ax2.tick_params(axis='y', labelcolor='blue')
        ax2.set_title(f"Speed & Acceleration vs Position ({name})")
        ax2.grid(True)
        
        # 右侧 Y 轴：加速度
        ax2_r = ax2.twinx()
        ax2_r.plot(pos, a, label=f"{name} Accel", color='orange', lw=1, alpha=0.8)
        ax2_r.set_ylabel("Accel [m/s^2]", color='orange')
        ax2_r.tick_params(axis='y', labelcolor='orange')
        
        # 合并图例
        lines1, labels1 = ax2.get_legend_handles_labels()
        lines2, labels2 = ax2_r.get_legend_handles_labels()
        ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

    plt.tight_layout()
    plt.savefig(save_path, dpi=120)
    print(f"[viz] Position diagnostics saved to {save_path}")
    plt.close()
"""
Generate an orbital camera path for Metashape.
Run inside Metashape Python console: Tools > Run Script

所有參數用現實世界單位 (公尺/度)。
腳本在 ECEF 座標系做軌道計算，正確處理地理座標的「上」方向。

Usage:
  1. 填入下方參數
  2. Tools > Run Script 執行
  3. View > Animation > Import Track 匯入 orbit_path.path
"""

import Metashape
import math
import os

# ============================================================
# 使用者參數
# ============================================================

RADIUS_M  = 3    # 水平環繞半徑 (公尺)
TILT_DEG  = 45.0   # 往下看的角度: 0=水平, 45=斜45°, 75=很陡, 89=幾乎正上方

NUM_KEYFRAMES = 36   # 一圈的 keyframe 數量
TOTAL_FRAMES  = 300  # 動畫總幀數
FPS           = 30.0

OUTPUT_PATH = "orbit_path.path"

# ============================================================

def normalize(x, y, z):
    l = math.sqrt(x*x + y*y + z*z)
    return x/l, y/l, z/l

def cross(ax, ay, az, bx, by, bz):
    return (ay*bz - az*by, az*bx - ax*bz, ax*by - ay*bx)

def world_dir_to_internal(T_inv, ecef_ref, dx, dy, dz):
    """ECEF 方向向量 → Metashape 內部方向向量"""
    ref = Metashape.Vector(ecef_ref)
    p1  = T_inv.mulp(ref + Metashape.Vector([dx, dy, dz]))
    p2  = T_inv.mulp(ref)
    d   = p1 - p2
    return normalize(d.x, d.y, d.z)

def main():
    doc   = Metashape.app.document
    chunk = doc.chunk
    if chunk is None:
        print("錯誤: 請先開啟專案")
        return

    T     = chunk.transform.matrix   # internal → ECEF (公尺)
    T_inv = T.inv()

    # 模型中心轉換到 ECEF
    internal_center = chunk.region.center
    ecef_c = T.mulp(internal_center)
    ecx, ecy, ecz = ecef_c.x, ecef_c.y, ecef_c.z

    # 在此 ECEF 位置計算本地 ENU 座標軸
    # Up = 地球中心向外的法線方向
    upx, upy, upz = normalize(ecx, ecy, ecz)
    # East = cross(Z_ecef, up) = cross((0,0,1), up)
    ex, ey, ez = normalize(-upy, upx, 0.0)
    # North = cross(up, east)
    nx, ny, nz = cross(upx, upy, upz, ex, ey, ez)

    # 印出 CRS 座標確認位置
    if chunk.crs is not None:
        crs_c = chunk.crs.project(ecef_c)
        print(f"模型中心 (CRS): lon={crs_c.x:.6f}  lat={crs_c.y:.6f}  elev={crs_c.z:.3f}m")
    print(f"模型中心 (ECEF): ({ecx:.1f}, {ecy:.1f}, {ecz:.1f}) m")

    # 相機高度沿 Up 方向
    height_m = RADIUS_M * math.tan(math.radians(TILT_DEG))
    print(f"水平半徑: {RADIUS_M}m  高度偏移: {height_m:.2f}m  俯視角: {TILT_DEG}°")

    if not chunk.camera_track:
        chunk.camera_track = Metashape.CameraTrack()
    track = chunk.camera_track
    track.keyframes.clear()

    duration = TOTAL_FRAMES / FPS
    ecef_ref = (ecx, ecy, ecz)

    for i in range(NUM_KEYFRAMES):
        angle = 2.0 * math.pi * i / NUM_KEYFRAMES
        t     = duration * i / NUM_KEYFRAMES

        ca, sa = math.cos(angle), math.sin(angle)

        # 相機位置 (ECEF): 中心 + 水平偏移(East/North) + 垂直偏移(Up)
        cam_ex = ecx + RADIUS_M*(ca*ex + sa*nx) + height_m*upx
        cam_ey = ecy + RADIUS_M*(ca*ey + sa*ny) + height_m*upy
        cam_ez = ecz + RADIUS_M*(ca*ez + sa*nz) + height_m*upz

        # 轉換到內部座標
        cam_int = T_inv.mulp(Metashape.Vector([cam_ex, cam_ey, cam_ez]))

        # Forward: 相機 → 模型中心 (ECEF)
        ffx, ffy, ffz = normalize(ecx - cam_ex, ecy - cam_ey, ecz - cam_ez)

        # Right: forward × up_local
        rrx, rry, rrz = normalize(*cross(ffx, ffy, ffz, upx, upy, upz))

        # Camera up: right × forward
        cux, cuy, cuz = cross(rrx, rry, rrz, ffx, ffy, ffz)

        # 三個軸轉換到內部座標
        frx, fry, frz = world_dir_to_internal(T_inv, ecef_ref, rrx, rry, rrz)
        fux, fuy, fuz = world_dir_to_internal(T_inv, ecef_ref, cux, cuy, cuz)
        fwx, fwy, fwz = world_dir_to_internal(T_inv, ecef_ref, ffx, ffy, ffz)

        transform = Metashape.Matrix([
            [ frx,  fry,  frz,  0],
            [-fux, -fuy, -fuz,  0],
            [ fwx,  fwy,  fwz,  0],
            [cam_int.x, cam_int.y, cam_int.z, 1]
        ])

        track.keyframes.append((t, transform))

        if chunk.crs is not None:
            crs_p = chunk.crs.project(Metashape.Vector([cam_ex, cam_ey, cam_ez]))
            print(f"  KF {i:2d}: t={t:.1f}s  lon={crs_p.x:.5f} lat={crs_p.y:.5f} elev={crs_p.z:.2f}m")
        else:
            print(f"  KF {i:2d}: t={t:.1f}s  ECEF=({cam_ex:.1f}, {cam_ey:.1f}, {cam_ez:.1f})")

    track.duration = duration

    out = os.path.abspath(OUTPUT_PATH)
    track.save(out)
    print(f"\n已儲存: {out}")
    print(f"共 {NUM_KEYFRAMES} keyframes, {duration:.1f} 秒 @ {FPS:.0f}fps")

    Metashape.app.update()


if __name__ == "__main__":
    main()

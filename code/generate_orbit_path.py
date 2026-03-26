"""
Generate an orbital camera path for Metashape.
Creates a top-down circular orbit around the model center,
suitable for coral reef models.

Usage:
  - Run inside Metashape Python console, or
  - Run as external script with Metashape module available

Parameters you can adjust:
  - TILT_ANGLE_DEG: 俯視角度 (0=水平, 90=正上方), 珊瑚礁建議 60~75
  - RADIUS_SCALE: 環繞半徑相對於模型大小的倍率
  - NUM_KEYFRAMES: 環繞一圈的關鍵幀數量
  - TOTAL_FRAMES: 動畫總幀數 (影響輸出影片長度)
"""

import Metashape
import math

# ============================================================
# 使用者可調參數
# ============================================================

TILT_ANGLE_DEG = 65        # 俯視角度 (度): 0=水平, 90=正上方
                            # 珊瑚礁建議 60~75 度
RADIUS_SCALE = 1.5          # 環繞半徑 = 模型對角線長度 * RADIUS_SCALE
                            # 越大相機離越遠, 建議 1.0 ~ 2.5
RADIUS_OVERRIDE = None      # 若要手動指定半徑 (公尺), 設為數值, 例如 5.0
                            # 設為 None 則自動計算

HEIGHT_OVERRIDE = None      # 若要手動指定相機高度 (相對於中心點, 公尺), 例如 8.0
                            # 設為 None 則由俯視角度和半徑自動計算
                            # 注意: 設定此值時, 俯視角度會被重新計算

NUM_KEYFRAMES = 36          # 環繞一圈的關鍵幀數量 (每 10 度一個 keyframe)
TOTAL_FRAMES = 300          # 動畫總幀數 (30fps 時 = 10 秒影片)

CENTER_OVERRIDE = None      # 若要手動指定中心點, 設為 Metashape.Vector([x, y, z])
                            # 設為 None 則自動取模型中心


# ============================================================
# 主程式
# ============================================================

def get_model_center_and_size(chunk):
    """從 chunk 的 region 取得模型中心和大小"""
    region = chunk.region
    center = region.center
    size = region.size
    # 對角線長度作為模型大小參考
    diagonal = math.sqrt(size.x**2 + size.y**2 + size.z**2)
    print(f"模型中心 (內部座標): {center}")
    print(f"模型 Region 大小: {size.x:.2f} x {size.y:.2f} x {size.z:.2f}")
    print(f"模型對角線長度: {diagonal:.2f}")
    return center, diagonal


def build_orbit_keyframes(center, radius, tilt_deg, num_keyframes, height_override=None):
    """
    產生環繞一圈的 keyframe 位置和朝向。

    Args:
        center: 環繞中心點 (Metashape.Vector)
        radius: 環繞半徑
        tilt_deg: 俯視角度 (度)
        num_keyframes: 關鍵幀數量
        height_override: 手動指定高度 (若設定, 會覆蓋由 tilt_deg 計算的高度)

    Returns:
        list of (position, lookat_matrix) tuples
    """
    tilt_rad = math.radians(tilt_deg)
    keyframes = []

    for i in range(num_keyframes):
        # 環繞角度 (0 ~ 2π)
        angle = 2.0 * math.pi * i / num_keyframes

        # 相機位置: 以中心點為圓心, 在水平面上做圓, 並抬高
        if height_override is not None:
            height = height_override
            horizontal_r = math.sqrt(max(radius**2 - height**2, 0.01))
        else:
            horizontal_r = radius * math.cos(tilt_rad)  # 水平投影半徑
            height = radius * math.sin(tilt_rad)         # 相機高度 (相對中心)

        cam_x = center.x + horizontal_r * math.cos(angle)
        cam_y = center.y + horizontal_r * math.sin(angle)
        cam_z = center.z + height

        cam_pos = Metashape.Vector([cam_x, cam_y, cam_z])

        # 相機朝向: 看向中心點
        # 計算 look-at 旋轉矩陣
        forward = center - cam_pos
        forward = forward.normalized()

        # 使用世界 Z 軸作為 up 的參考
        world_up = Metashape.Vector([0, 0, 1])

        # 計算右向量 (right = forward × up)
        right = Metashape.Vector([
            forward.y * world_up.z - forward.z * world_up.y,
            forward.z * world_up.x - forward.x * world_up.z,
            forward.x * world_up.y - forward.y * world_up.x
        ])
        right = right.normalized()

        # 重新計算 up (up = right × forward)
        up = Metashape.Vector([
            right.y * forward.z - right.z * forward.y,
            right.z * forward.x - right.x * forward.z,
            right.x * forward.y - right.y * forward.x
        ])

        # 建立 4x4 變換矩陣 (Metashape 的相機座標系: -Z 朝前, Y 朝上)
        # Metashape camera convention: X-right, Y-down, Z-forward(into scene)
        rot = Metashape.Matrix([
            [right.x,    right.y,    right.z,    0],
            [-up.x,      -up.y,      -up.z,      0],
            [forward.x,  forward.y,  forward.z,  0],
            [cam_pos.x,  cam_pos.y,  cam_pos.z,  1]
        ])

        keyframes.append((i, cam_pos, rot))

    return keyframes


def apply_camera_track(chunk, keyframes, total_frames):
    """
    將 keyframes 設定到 chunk 的 camera track。

    Args:
        chunk: Metashape.Chunk
        keyframes: list of (index, position, transform_matrix)
        total_frames: 動畫總幀數
    """
    # 確保 camera track 存在
    if not chunk.camera_track:
        chunk.camera_track = Metashape.CameraTrack()

    track = chunk.camera_track
    track.keyframes.clear()

    num_kf = len(keyframes)

    for idx, (kf_idx, pos, transform) in enumerate(keyframes):
        # 計算此 keyframe 對應的幀號
        frame = int(total_frames * idx / num_kf)

        kf = Metashape.CameraTrack.Keyframe()
        kf.frame = frame
        kf.transform = transform

        track.keyframes.append(kf)
        print(f"  Keyframe {idx}: frame={frame}, pos=({pos.x:.2f}, {pos.y:.2f}, {pos.z:.2f})")

    # 設定總幀數
    track.frame_count = total_frames

    print(f"\n已建立 {num_kf} 個 keyframes, 總計 {total_frames} 幀")


def main():
    doc = Metashape.app.document
    chunk = doc.chunk

    if chunk is None:
        print("錯誤: 沒有可用的 chunk, 請先開啟一個專案")
        return

    # 取得模型中心和大小
    center, diagonal = get_model_center_and_size(chunk)

    # 決定中心點
    if CENTER_OVERRIDE is not None:
        center = CENTER_OVERRIDE
        print(f"使用手動指定中心點: {center}")

    # 決定半徑
    if RADIUS_OVERRIDE is not None:
        radius = RADIUS_OVERRIDE
        print(f"使用手動指定半徑: {radius}")
    else:
        radius = diagonal * RADIUS_SCALE
        print(f"自動計算半徑: {diagonal:.2f} * {RADIUS_SCALE} = {radius:.2f}")

    # 決定高度
    if HEIGHT_OVERRIDE is not None:
        print(f"使用手動指定高度: {HEIGHT_OVERRIDE} (俯視角度將由高度和半徑重新計算)")
        effective_tilt = math.degrees(math.atan2(HEIGHT_OVERRIDE, math.sqrt(max(radius**2 - HEIGHT_OVERRIDE**2, 0.01))))
        print(f"實際俯視角度: {effective_tilt:.1f}°")
    else:
        print(f"俯視角度: {TILT_ANGLE_DEG}°")
        height_calc = radius * math.sin(math.radians(TILT_ANGLE_DEG))
        print(f"計算出的相機高度 (相對中心): {height_calc:.2f}")

    print(f"關鍵幀數量: {NUM_KEYFRAMES}")
    print(f"總幀數: {TOTAL_FRAMES}")
    print()

    # 產生 keyframes
    keyframes = build_orbit_keyframes(center, radius, TILT_ANGLE_DEG, NUM_KEYFRAMES, HEIGHT_OVERRIDE)

    # 套用到 camera track
    apply_camera_track(chunk, keyframes, TOTAL_FRAMES)

    print("\n完成! 你現在可以:")
    print("  1. 在 Metashape 中 View > Camera Track 預覽路徑")
    print("  2. 使用 File > Export > Export Video 輸出影片")
    print("  3. 或用以下程式碼輸出影片:")
    print('     chunk.exportVideo("output.mp4", frame_size=(1920, 1080))')


# 如果在 Metashape 中執行
if __name__ == "__main__":
    main()

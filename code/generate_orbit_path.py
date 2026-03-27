import math
import numpy as np
from scipy.spatial.transform import Rotation as R

def generate_circular_path(filename, center_lon, center_lat, center_alt, 
                           radius_m, relative_height_m, 
                           fixed_pitch_deg, fixed_roll_deg, fixed_yaw_offset_deg=0.0,
                           num_points=50, total_time=30.0):
    """
    生成環繞中心點的圓形軌跡檔案
    """
    # 1. 經緯度與公尺的轉換係數 (近似值)
    # 緯度 1 度約為 111,320 公尺
    lat_to_m = 111320.0
    # 經度 1 度在不同緯度上的距離不同，需乘上 cos(緯度)
    lon_to_m = 111320.0 * math.cos(math.radians(center_lat))
    
    # 2. 準備時間與圓的切分角度
    times = np.linspace(0, total_time, num_points)
    angles = np.linspace(0, 2 * np.pi, num_points, endpoint=False) # 0 到 360 度
    
    # 打開檔案準備寫入
    with open(filename, 'w') as f:
        for t, theta in zip(times, angles):
            # 3. 計算當前的 X, Y 位置 (相對於中心的偏移，單位：公尺)
            delta_x_m = radius_m * math.cos(theta)
            delta_y_m = radius_m * math.sin(theta)
            
            # 將公尺轉換回經緯度並加上中心座標
            x = center_lon + (delta_x_m / lon_to_m)
            y = center_lat + (delta_y_m / lat_to_m)
            
            # 高度 Z
            z = center_alt + relative_height_m
            
            # 4. 計算姿態 (Yaw, Pitch, Roll)
            # Roll 和 Pitch 套用使用者的固定值
            roll = fixed_roll_deg
            pitch = fixed_pitch_deg
            
            # Yaw 需要自動計算以朝向中心點。
            # 目前位置相對於中心是 (cos, sin)，所以中心相對於目前位置是 (-cos, -sin)
            # math.atan2(y, x) 可以算出朝向中心的水平夾角
            yaw_to_center_rad = math.atan2(-delta_y_m, -delta_x_m)
            yaw = math.degrees(yaw_to_center_rad) + fixed_yaw_offset_deg
            
            # 5. 計算對準中心的基礎姿態
            rot_base = R.from_euler('ZYX', [yaw, pitch, roll], degrees=True)
            
            # 新增：讓鏡頭在原地進行自轉 (Spin) 來改變畫面的水平/垂直構圖
            # 如果轉 90 度方向反了（畫面顛倒），請改成 -90
            # 通常 3D 視覺軟體的鏡頭軸是 'z' 軸；如果是其他軟體沒反應，可嘗試改為 'x'
            rot_spin = R.from_euler('z', -90, degrees=True) 
            
            # 將基礎姿態與原地自轉合併 (矩陣相乘)
            rot_final = rot_base * rot_spin
            
            # 輸出最終四元數
            qx, qy, qz, qw = rot_final.as_quat()
            
            # 6. 寫入檔案 (以空格分隔)
            # 格式：Time X Y Z Qx Qy Qz Qw
            line = f"{t:.9g} {x:.9f} {y:.9f} {z:.9f} {qx:.10f} {qy:.10f} {qz:.10f} {qw:.10f}\n"
            f.write(line)
            
    print(f"✅ 檔案已成功生成：{filename}")
    print(f"生成的軌跡共 {num_points} 個點，總時長 {total_time} 秒。")

# ==========================================
# 在這裡設定您的參數
# ==========================================
if __name__ == "__main__":
    # 中心點座標 (您可替換成實際的經緯度與高度)
    CENTER_LON = 145.44747284619777   # 中心經度 (X)
    CENTER_LAT = -14.699229968143483   # 中心緯度 (Y)
    CENTER_ALT = -2.3644810379176153          # 中心高度 (Z)
    
    # 幾何參數
    RADIUS_M = 10           # 繞行半徑 (公尺)
    RELATIVE_HEIGHT_M = 3  # 相對於中心點的高度 (公尺)
    
    # 姿態參數
    PITCH_DEG = -70.0         # 俯仰角：例如 -30 度代表鏡頭稍微往下看著中心
    ROLL_DEG = 0            # 翻滾角：0 代表水平
    YAW_OFFSET_DEG = 0      # 偏航角偏移：若發現鏡頭沒對準中心，可微調這個數值 (例如 90 或 -90)

    # 執行生成
    generate_circular_path(
        filename="circle_trajectory.txt", # 輸出的檔案名稱
        center_lon=CENTER_LON,
        center_lat=CENTER_LAT,
        center_alt=CENTER_ALT,
        radius_m=RADIUS_M,
        relative_height_m=RELATIVE_HEIGHT_M,
        fixed_pitch_deg=PITCH_DEG,
        fixed_roll_deg=ROLL_DEG,
        fixed_yaw_offset_deg=YAW_OFFSET_DEG,
        num_points=50,       # 共生成 50 個點
        total_time=30.0      # 時間從 0 到 30
    )
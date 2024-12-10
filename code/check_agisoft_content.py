import Metashape
import os


# 或是開啟一個現有的專案
# Load Existing Project and Check Status (載入已存在的專案並檢查狀態)
# 開啟已存在的Metashape專案文件
existing_project_path = r"D:\3D_workshop\indoor_demo\tg_ortho_20\agisoft\tg_ortho_20.psx"
doc = Metashape.Document()
doc.open(existing_project_path)
chunk = doc.chunk

# 檢查專案狀態，例如相機數量和照片對齊狀態
print(f"相機數量: {len(chunk.cameras)}")
# 顯示未對齊的相機
unaligned_cameras = [camera.label for camera in chunk.cameras if not camera.transform]
if unaligned_cameras:
    print(f"未對齊的相機: {', '.join(unaligned_cameras)}")
else:
    print("所有相機均已對齊")
# 檢查 Tie Points，以及其點數量
if chunk.tie_points:
    num_points = len(chunk.tie_points.points)
    print(f"稀疏點雲存在，包含 {num_points} 個點")
else:
    print("稀疏點雲不存在或沒有點")


# 檢查並打印當前 reference 中有多少個標記
num_markers = len(chunk.markers)
print(f"目前專案中有 {num_markers} 個標記")

# 打印目前的比例尺數量及其長度
num_scalebars = len(chunk.scalebars)
print(f"目前專案中有 {num_scalebars} 個比例尺")


"""
# 刪除專案中的所有標記
for marker in list(chunk.markers):
    chunk.remove(marker)
print("所有標記已被刪除")
"""

"""
# 刪除專案中的所有比例尺
for scale_bar in list(chunk.scalebars):
    chunk.remove(scale_bar)
"""


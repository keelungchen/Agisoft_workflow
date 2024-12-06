import Metashape
import os

print(Metashape.app.version)

# Step 1: 建立一個新的Metashape專案並設定路徑
# 定義專案儲存的位置
project_folder = r"D:\3D_workshop\indoor_demo\tg_ortho_20\agisoft"
project_name = os.path.basename(os.path.dirname(project_folder))  # 用資料夾名稱作為專案名稱
project_path = os.path.join(project_folder, f"{project_name}.psx")  # 設定專案檔案名稱及副檔名

# Step 2: 初始化Metashape Document物件
# 這個Document物件用來存儲及管理Metashape的所有項目（如照片、點雲等）
doc = Metashape.Document()
doc.save(path=project_path)  # 儲存專案文件到指定路徑

'''
# 或是開啟一個現有的專案
# Load Existing Project and Check Status (載入已存在的專案並檢查狀態)
# 開啟已存在的Metashape專案文件
existing_project_path = r"D:\3D_workshop\indoor_demo\tg_ortho_20\agisoft\tg_ortho_20.psx"
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
'''

# Step 3: 建立一個新的Chunk
# 在Metashape中，Chunk是處理工作的一個單位，包括對應、生成點雲、建模等
chunk = doc.addChunk()
doc.save()  # 每次操作後都保存專案

# Step 4: 匯入照片
# 定義照片所在的資料夾並匯入所有照片
photo_folder = r"D:\3D_workshop\indoor_demo\tg_ortho_20\photos"
photos = [os.path.join(photo_folder, f) for f in os.listdir(photo_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff'))]
# 將照片添加到chunk中
chunk.addPhotos(photos)
doc.save()  # 保存專案

# Step 5: Align Photos（對齊照片）
# 使用Metashape的align功能來對齊照片，形成稀疏點雲
# 設定參數：高精度、啟用Generic預選、排除靜態連接點、啟用相機模型自適應擬合
chunk.matchPhotos(
    downscale=1,
    generic_preselection=True,
    reference_preselection=False,
    filter_mask=False,
    filter_stationary_points=True,
    keypoint_limit=50000,
    tiepoint_limit=0,
    reset_matches=True,
    progress=lambda p: print(f'Processing: {p :.2f}% complete')
)
chunk.alignCameras(adaptive_fitting=True, reset_alignment=True, progress=lambda p: print(f'Processing: {p :.2f}% complete'))
doc.save()  # 保存對齊結果
# 顯示對齊過程
print("照片對齊中，參數：精度=高，Generic預選=True，排除靜態連接點=True，自適應相機擬合=True，Key點數量=50000，Tie點數量=0")

# 優化對齊
chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, \
    fit_b1=True, fit_b2=True, fit_k1=True, fit_k2=True, fit_k3=True, \
    fit_k4=True, fit_p1=True, fit_p2=True, fit_p3=True, fit_p4=True, tiepoint_covariance=True)
doc.save()

# Step 6: Gradual Selection and Remove Points (逐步選擇並刪除點)
# 在稀疏點雲中執行逐步選擇，選取誤差較大的點，level 設定為 15
f = Metashape.TiePoints.Filter()
f.init(chunk, criterion=Metashape.TiePoints.Filter.ReconstructionUncertainty)
f.selectPoints(threshold=15)
# 刪除選取的點
chunk.tie_points.removeSelectedPoints()
doc.save()

# Step 6.1: Gradual Selection by Projection Accuracy and Optimize Alignment
# 使用投影精度進步選擇tie points，設定為 5
f.init(chunk, criterion=Metashape.TiePoints.Filter.ProjectionAccuracy)
f.selectPoints(threshold=5)
# 刪除選取的點
chunk.tie_points.removeSelectedPoints()
# 優化對齊
chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, \
    fit_b1=True, fit_b2=True, fit_k1=True, fit_k2=True, fit_k3=True, \
    fit_k4=True, fit_p1=True, fit_p2=True, fit_p3=True, fit_p4=True, tiepoint_covariance=True)
doc.save()


# Step 8: Detect Markers (檢測標記)
# 在照片中檢測標記以便進一步使用
# 在照片中檢測 Circular 12bit 標記，並設定 tolerance 為 20
chunk.detectMarkers(
    target_type=Metashape.TargetType.CircularTarget12bit,
    tolerance=20,
    progress=lambda p: print(f'Processing: {p :.2f}% complete')
)
# 檢查並打印當前 reference 中有多少個標記
num_markers = len(chunk.markers)
print(f"目前專案中有 {num_markers} 個標記")
doc.save()  # 保存檢測標記結果
"""
# 刪除專案中的所有標記
for marker in list(chunk.markers):
    chunk.remove(marker)
print("所有標記已被刪除")
"""

# Step 9: Set Reference to Local Coordinate System (設定參考為在地坐標系)
# 設定專案的參考為在地坐標系
chunk.crs = None  # 設定為在地坐標系，無投影的本地座標系統
# 設定 target 1、target 2、target 3 的 XYZ 值
marker_names = ['target 1', 'target 2', 'target 3']
marker_coordinates = [(0, 0, 0), (0, 0.0582, 0), (0.0579, 0, 0)]
for marker_name, coordinates in zip(marker_names, marker_coordinates):
    marker = next((m for m in chunk.markers if m.label == marker_name), None)
    if marker:
        marker.reference.location = coordinates
# 更新 Transform
chunk.updateTransform()
doc.save()
"""
# 刪除專案中的所有比例尺
for scale_bar in list(chunk.scalebars):
    chunk.remove(scale_bar)
"""
# 打印目前的比例尺數量及其長度
num_scalebars = len(chunk.scalebars)
print(f"目前專案中有 {num_scalebars} 個比例尺")
# 為 target 9 - target 10、target 49 - target 50、target 55 - target 56 建立比例尺，並將長度設定為 0.0582、0.0558
scale_bar_pairs = [
    ("target 9", "target 10", 0.0582),
    ("target 49", "target 50", 0.0558),
    ("target 55", "target 56", 0.0558)
]

for target1_label, target2_label, length in scale_bar_pairs:
    target1 = next((m for m in chunk.markers if m.label == target1_label), None)
    target2 = next((m for m in chunk.markers if m.label == target2_label), None)
    if target1 and target2:
        scale_bar = chunk.addScalebar(target1, target2)
        scale_bar.reference.distance = length
        print(f"建立比例尺: {target1_label} - {target2_label}，長度為 {length} 米")
# 更新 Transform
chunk.updateTransform()
doc.save()

# 計算比例尺誤差
total_error = 0.0
for scalebar in chunk.scalebars:
    dist_source = scalebar.reference.distance
    if not dist_source:
        continue  # 跳過沒有來源值的比例尺
    if type(scalebar.point0) == Metashape.Camera:
        if not (scalebar.point0.center and scalebar.point1.center):
            continue  # 跳過端點未定義的比例尺
        dist_estimated = round((scalebar.point0.center - scalebar.point1.center).norm() * chunk.transform.scale, 5)
    else:
        if not (scalebar.point0.position and scalebar.point1.position):
            continue  # 跳過端點未定義的比例尺
        dist_estimated = round((scalebar.point0.position - scalebar.point1.position).norm() * chunk.transform.scale, 5)
    dist_error = dist_estimated - dist_source
    total_error += dist_error
    print(f"比例尺 {scalebar.label}: 長度 = {dist_source} 米, 預估長度 = {dist_estimated:.5f} 米, 誤差 = {dist_error:.5f}")

print(f"比例尺的總誤差為: {total_error:.5f}")
# 更新 Transform
chunk.updateTransform()
doc.save()


# Step 6: 儲存最終專案
# 保存包含已對齊照片的完整專案
doc.save()
# 顯示完成信息
print("專案已儲存至:", project_path)

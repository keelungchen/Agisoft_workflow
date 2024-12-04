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
    reset_matchs=True,
    progress=lambda p: print(f'Processing: {p :.2f}% complete')
)
chunk.alignCameras(adaptive_fitting=True, reset_alignment=True, progress=lambda p: print(f'Processing: {p :.2f}% complete'))
doc.save()  # 保存對齊結果
# 顯示對齊過程
print("照片對齊中，參數：精度=高，Generic預選=True，排除靜態連接點=True，自適應相機擬合=True，Key點數量=50000，Tie點數量=0")

# Step 6: Gradual Selection and Remove Points (逐步選擇並刪除點)
# 在稀疏點雲中執行逐步選擇，選取誤差較大的點，level 設定為 15
f = Metashape.TiePoints.Filter()
f.init(chunk, criterion=Metashape.TiePoints.Filter.ReconstructionUncertainty)
f.selectPoints(threshold=15)
# 刪除選取的點
chunk.tie_points.removeSelectedPoints()

#------
# Step 7: Load Existing Project and Check Status (載入已存在的專案並檢查狀態)
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




# Step 6: 儲存最終專案
# 保存包含已對齊照片的完整專案
doc.save()
# 顯示完成信息
print("照片匯入並對齊完成，專案已儲存至:", project_path)

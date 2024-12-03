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
chunk.matchPhotos(downscale=1, generic_preselection=True, reference_preselection=False, filter_mask=False, filter_stationary_points=True, keypoint_limit=50000, tiepoint_limit=0,progress=lambda p: print(f'Processing: {p * 100:.2f}% complete'))
chunk.alignCameras(adaptive_fitting=True, progress=lambda p: print(f'Processing: {p * 100:.2f}% complete'))
doc.save()  # 保存對齊結果


import Metashape
import os
import pandas as pd

print(Metashape.app.version)

# 定義根資料夾路徑
base_folder = r"D:\3D_workshop\indoor_demo"
logo_folder = r"D:\3D_workshop\logo" # 輸出report時顯示在pdf上logo的檔案位置

# 定義比例尺資訊與在地坐標檔案路徑
scale_bar_file = r"D:\3D_workshop\scale_bars\scale_bars_info.xlsx"
local_coordinates_file = r"D:\3D_workshop\scale_bars\local_coordinates_info.xlsx"
# 讀取比例尺與在地坐標資訊
scale_bar_data = pd.read_excel(scale_bar_file)
local_coordinates_data = pd.read_excel(local_coordinates_file)

# 列出所有資料夾名稱並排除特定資料夾
all_folders = [folder for folder in os.listdir(base_folder) if os.path.isdir(os.path.join(base_folder, folder)) and folder not in excluded_folders]
print("要處理的資料夾:\n" + "\n".join(all_folders))
excluded_folders = {"DSLR","samsung", "tg_ortho_30","tg_spiral", "another_folder_to_exclude"}  # 定義要排除的資料夾

# 過濾完成的資料夾
for folder in all_folders:
    folder_path = os.path.join(base_folder, folder)

    # 定義子資料夾路徑
    photos_folder = os.path.join(folder_path, "photos")
    agisoft_folder = os.path.join(folder_path, "agisoft")
    products_folder = os.path.join(folder_path, "products")

    # 確認子資料夾是否存在
    if not all(os.path.exists(subfolder) for subfolder in [photos_folder, agisoft_folder, products_folder]):
        print(f"警告: {folder} 資料夾結構不完整，跳過處理。")
        continue

    # 檢查 `agisoft` 資料夾中是否已存在 `.psx` 檔案
    psx_files = [file for file in os.listdir(agisoft_folder) if file.endswith(".psx")]
    if psx_files:
        print(f"跳過 {folder}，因為已有 Metashape 專案檔案: {', '.join(psx_files)}")
        continue

    # Step 1: 建立一個新的Metashape專案並設定路徑
    # 設定 Metashape 專案相關路徑
    project_name = os.path.basename(folder_path)  # 以資料夾名稱作為專案名稱
    project_path = os.path.join(agisoft_folder, f"{project_name}.psx")  # 專案檔案路徑

    # Step 2: 初始化Metashape Document物件
    # 這個Document物件用來存儲及管理Metashape的所有項目（如照片、點雲等）
    doc = Metashape.Document()
    doc.save(path=project_path)  # 儲存專案文件到指定路徑

    # Step 3: 建立一個新的Chunk
    # 在Metashape中，Chunk是處理工作的一個單位，包括對應、生成點雲、建模等
    chunk = doc.addChunk()
    doc.save()  # 每次操作後都保存專案

    # Step 4: 匯入照片
    photos = [os.path.join(photos_folder, f) for f in os.listdir(photos_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff'))]
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
        progress=lambda p: print(f'Processing {folder} matchPhotos: {p :.2f}% complete')
    )
    chunk.alignCameras(adaptive_fitting=True, reset_alignment=True, progress=lambda p: print(f'Processing {folder} alignCameras: {p :.2f}% complete'))
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
        progress=lambda p: print(f'Processing {folder}: {p :.2f}% complete')
    )
    doc.save()  # 保存檢測標記結果
   
    # Step 9: create scale bars (建立比例尺)
    # 使用CSV檔案中讀取的資訊建立比例尺
    for index, row in scale_bar_data.iterrows():
        target1_label = row['scale_bar_1']
        target2_label = row['scale_bar_2']
        length = row['length']

        # 嘗試從當前 Chunk 中找到對應標記
        target1 = next((m for m in chunk.markers if m.label == target1_label), None)
        target2 = next((m for m in chunk.markers if m.label == target2_label), None)

        # 如果找不到標記，輸出警告並跳過該比例尺的建立
        if not target1 or not target2:
            print(f"警告: 找不到標記 {target1_label} 或 {target2_label}，無法建立比例尺")
            continue

        try:
            # 建立比例尺並設置其參考距離
            scale_bar = chunk.addScalebar(target1, target2)
            scale_bar.reference.distance = length
            print(f"成功建立比例尺: {target1_label} - {target2_label}，長度為 {length} 公尺")
        except Exception as e:
            print(f"錯誤: 無法為標記 {target1_label} 和 {target2_label} 建立比例尺。原因: {e}")

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
            dist_estimated = round((scalebar.point0.center - scalebar.point1.center).norm() * chunk.transform.scale, 6)
        else:
            if not (scalebar.point0.position and scalebar.point1.position):
                continue  # 跳過端點未定義的比例尺
            dist_estimated = round((scalebar.point0.position - scalebar.point1.position).norm() * chunk.transform.scale, 6)
        dist_error = dist_estimated - dist_source
        total_error += dist_error
        print(f"比例尺 {scalebar.label}: 長度 = {dist_source} 米, 預估長度 = {dist_estimated:.6f} 米, 誤差 = {dist_error:.6f}")

    print(f"比例尺的總誤差為: {total_error:.6f}")

    # Step 9.1: Projection Error and Optimize Alignment
    # 使用Projection Error選擇tie points，設定為 0.5
    f.init(chunk, criterion=Metashape.TiePoints.Filter.ReprojectionError)
    f.selectPoints(threshold=0.5)
    # 刪除選取的點
    chunk.tie_points.removeSelectedPoints()
    # 優化對齊
    chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, \
        fit_b1=True, fit_b2=True, fit_k1=True, fit_k2=True, fit_k3=True, \
        fit_k4=True, fit_p1=True, fit_p2=True, fit_p3=True, fit_p4=True, tiepoint_covariance=True)
    doc.save()

    # Step 10: Build Dense Cloud (建立密集點雲)
    # 須先進行 Build Depth Maps (建立深度圖)
    # 設定參數：品質=中等，計算深度
    chunk.buildDepthMaps(
        downscale=4,
        progress=lambda p: print(f'Processing {folder} buildDepthMaps: {p :.2f}% complete')
    )
    doc.save()
    # 設定參數：根據深度圖計算密集顏色點
    chunk.buildPointCloud(
        point_confidence=True,
        progress=lambda p: print(f'Processing {folder} buildPointCloud: {p :.2f}% complete')
    )
    doc.save()

    # Step 10.1: Filter Dense Cloud by Confidence (根據信度過濾密集點雲)
    # 選取信度在 0 到 1 之間的密集點雲點並刪除
    chunk.point_cloud.setConfidenceFilter(0, 1)
    chunk.point_cloud.removePoints(list(range(128))) #removes all "visible" points of the dense cloud
    chunk.point_cloud.resetFilters()
    doc.save()


    # Step 11: Set Reference to Local Coordinate System (設定參考為在地坐標系)
    # 設定專案的參考為在地坐標系
    chunk.crs = None  # 設定為在地坐標系，無投影的本地座標系統
    # 設定 target 1、target 2、target 3 的 XYZ 值
    marker_names = ['target 1', 'target 2', 'target 3']
    for _, row in local_coordinates_data.iterrows():
        marker_name = row['marker_name']
        coordinates = (row['x'], row['y'], row['z'])

        marker = next((m for m in chunk.markers if m.label == marker_name), None)
        if marker:
            marker.reference.location = coordinates
            print(f"成功設置標記 {marker_name} 的坐標為 {coordinates}")
        else:
            print(f"警告: 找不到標記 {marker_name}，無法設置坐標")
    # 更新 Transform
    chunk.updateTransform()
    doc.save()

    # Step 12: Build DEM (建立數字高程模型)
    # 使用密集點雲來建立DEM
    chunk.buildDem(
        source_data=Metashape.DataSource.PointCloudData,
        interpolation=Metashape.EnabledInterpolation,
        progress=lambda p: print(f'Processing {folder} buildDem: {p :.2f}% complete')
    )
    doc.save()

    # Step 12: Build Orthomosaic (建立正射影像)
    # 使用DEM來建立正射影像
    chunk.buildOrthomosaic(
        surface_data=Metashape.DataSource.ElevationData,
        blending_mode=Metashape.BlendingMode.MosaicBlending,
        fill_holes=True,
        ghosting_filter=True,
        resolution=0.0005,
        progress=lambda p: print(f'Processing {folder} buildOrthomosaic: {p :.2f}% complete')
    )
    doc.save()

    # Step 13: Generate Report (生成報告)
    # 生成項目報告，包括關鍵的重建信息和數據統計
    report_path = os.path.join(products_folder, f"{project_name}_report.pdf")
    chunk.exportReport(
        path=report_path,
        title=f"{project_name} Report",
        logo_path=os.path.join(logo_folder, "report_logo.png"),
        description="Generated using Metashape Python API @Guan-Yan Chen"
    )
    report_path = os.path.join(products_folder, f"{project_name}_report.html")
    chunk.exportReport(
        path=report_path,
        title=f"{project_name} Report",
        logo_path=os.path.join(logo_folder, "report_logo.png"),
        description="Generated using Metashape Python API @Guan-Yan Chen"
    )
    print("PDF與HTML報告已生成: ", report_path)

    # 儲存最終專案
    # 保存包含已對齊照片的完整專案
    doc.save()
    # 顯示完成信息
    print("專案已儲存至:", project_path)

print("所有資料夾的處理完成！")
    


import Metashape
import os

# ==========================================
# 🛠️ 使用者設定區
# ==========================================
# 1. 你的 Metashape 專案檔案路徑 (.psx)
PROJECT_PATH = r"\\jmadinlab\hawaii\reef_records\2025\k1a\metashape_files\rr-k1a-2025_08.psx"
# 2. 你想要輸出的 Shapefile 路徑 (.shp)
OUTPUT_SHP_PATH = r"\\jmadinlab\hawaii\reef_records\2025\k1a\products\k1a_2508_camera_positions.shp"
SAVE_PROJECT = False

# ==========================================
# 程式執行區
# ==========================================
def export_cameras_to_shp_standalone(project_path, output_path, save_project):
    if not os.path.exists(project_path):
        print(f"錯誤：找不到專案檔案 {project_path}")
        return

    print(f"正在開啟專案: {project_path} ...")
    
    doc = Metashape.Document()
    try:
        doc.open(project_path, ignore_lock=True)
    except Exception as e:
        print(f"開啟專案失敗，請確認檔案未損毀且沒有被其他程式鎖住。錯誤訊息: {e}")
        return

    chunk = doc.chunk
    if not chunk:
        print("錯誤：專案中沒有任何 Chunk。")
        return
        
    if not chunk.crs:
        print("錯誤：目前的 Chunk 尚未設定座標系統 (CRS)。")
        return

    # 確保 Chunk 中有 Shapes 容器
    if not chunk.shapes:
        chunk.shapes = Metashape.Shapes()
        chunk.shapes.crs = chunk.crs

    # 建立一個新的 Shape Group
    layer = chunk.shapes.addGroup()
    layer.label = "Camera_Positions_With_Angles" 

    camera_count = 0
    T = chunk.transform.matrix 
    
    for camera in chunk.cameras:
        if not camera.transform:
            continue 
            
        pos_internal = camera.center
        if pos_internal is None:
            continue
            
        # 1. 座標轉換
        pos_geoccs = T.mulp(pos_internal)
        coord = chunk.crs.project(pos_geoccs)
        altitude = coord[2]

        # 2. 計算相機姿態角度
        local_transform = chunk.crs.localframe(pos_geoccs) * T * camera.transform
        ypr = Metashape.utils.mat2ypr(local_transform.rotation())

        # 3. 建立點圖徵
        shape = chunk.shapes.addShape()
        shape.geometry = Metashape.Geometry.Point(coord)
        shape.group = layer
        
        # 💡 關鍵修復：防範路徑字串過長 (Shapefile 文字欄位極限為 254 字元)
        # 若路徑過長，匯出成 DBF 時會發生記憶體溢位而覆蓋到上一個欄位 (Pitch)
        photo_path_str = str(camera.photo.path)
        if len(photo_path_str) > 250:
            photo_path_str = "..." + photo_path_str[-247:]
        
        # 4. 寫入屬性資料 (Metashape 規定屬性值必須為字串型態)
        # 💡 關鍵修復：欄位名稱縮短確保安全 (Shapefile 欄位名稱極限為 10 個字元)
        shape.attributes["Photo_Name"] = str(camera.label)
        shape.attributes["Altitude"] = str(altitude)
        shape.attributes["Yaw"] = str(ypr[0])
        shape.attributes["Pitch"] = str(ypr[1])
        shape.attributes["Roll"] = str(ypr[2])
        shape.attributes["Path"] = photo_path_str
        
        camera_count += 1

    print(f"已成功建立 {camera_count} 個相機點位。")

    # 輸出成 Shapefile
    if camera_count > 0:
        chunk.exportShapes(
            path=output_path,
            save_points=True,
            save_polylines=False,
            save_polygons=False,
            groups=[layer],
            crs=chunk.crs
        )
        print(f"🎉 成功輸出 Shapefile: {output_path}")
        
        if save_project:
            doc.save()
            print("💾 專案已儲存。")
    else:
        print("沒有成功轉換任何相機座標 (請確認照片是否已成功對齊)。")

# 執行函式
export_cameras_to_shp_standalone(PROJECT_PATH, OUTPUT_SHP_PATH, SAVE_PROJECT)
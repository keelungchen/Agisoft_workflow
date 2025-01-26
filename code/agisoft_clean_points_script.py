import Metashape
import os
import pandas as pd

# 定義根資料夾路徑
base_folder = r"F:\Kenting field trip 2412"

# 定義比例尺資訊路徑
scale_bar_file = r"F:\Kenting field trip 2412\scale_bars.xlsx"
# 讀取比例尺與資訊
scale_bar_data = pd.read_excel(scale_bar_file)
   
doc = Metashape.Document()
doc.open(project_path)
chunk = doc.chunk

# 檢查專案狀態，例如相機數量和照片對齊狀態
print(f"相機數量: {len(chunk.cameras)}")

# Step 6: Gradual Selection and Remove Points (逐步選擇並刪除點)
# 在稀疏點雲中執行逐步選擇，選取誤差較大的點，level 設定為 16
f = Metashape.TiePoints.Filter()
f.init(chunk, criterion=Metashape.TiePoints.Filter.ReconstructionUncertainty)
f.selectPoints(threshold=16)
# 刪除選取的點
chunk.tie_points.removeSelectedPoints()
doc.save()

# 優化對齊
chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, \
    fit_b1=True, fit_b2=True, fit_k1=True, fit_k2=True, fit_k3=True, \
    fit_k4=True, fit_p1=True, fit_p2=True, fit_p3=True, fit_p4=True, tiepoint_covariance=True)
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

# 顯示完成信息
print("專案已儲存至:", project_path)

print("所有資料夾的處理完成！")
import Metashape
import os

print(f"Metashape 版本: {Metashape.app.version}")

# 定義根資料夾路徑
base_folder = r"E:\island\2023_11"
logo_folder = r"E:\report_logo"

# 列出所有資料夾名稱並排除特定資料夾
excluded_folders = {"folder_to_exclude", "another_folder_to_exclude"}
all_folders = [folder for folder in os.listdir(base_folder) if os.path.isdir(os.path.join(base_folder, folder)) and folder not in excluded_folders]
print("要處理的資料夾:\n" + "\n".join(all_folders))

# 遍歷資料夾
for folder in all_folders:
    folder_path = os.path.join(base_folder, folder)

    # 定義子資料夾路徑
    agisoft_folder = os.path.join(folder_path, "metashape_files") #設定agisoft檔案位置
    products_folder = os.path.join(folder_path, "products") #設定產出的html結果位置

    # 確認子資料夾是否存在
    if not all(os.path.exists(subfolder) for subfolder in [agisoft_folder, products_folder]):
        print(f"警告: {folder} 資料夾結構不完整，跳過處理。")
        continue

    # 搜尋 metashape_files 中的 .psx 檔案，忽略 `._` 開頭的檔案
    psx_files = [f for f in os.listdir(agisoft_folder) if f.endswith(".psx") and not f.startswith("._")]
    if not psx_files:
        print(f"警告: 在 {agisoft_folder} 中未找到任何 .psx 檔案，跳過處理。")
        continue

    # 假設只有一個 .psx 檔案
    project_name = os.path.splitext(psx_files[0])[0]
    project_path = os.path.join(agisoft_folder, psx_files[0])

    # 確認檔案是否存在
    if not os.path.exists(project_path):
        print(f"錯誤: {project_path} 檔案不存在，跳過處理。")
        continue

    # 嘗試打開 .psx 檔案
    try:
        doc = Metashape.Document()
        doc.open(project_path)  # 嘗試打開專案
        chunk = doc.chunk

        # 生成項目報告
        report_path = os.path.join(products_folder, f"{project_name}_report.html")
        chunk.exportReport(
            path=report_path,
            title=f"{project_name} Report",
            logo_path=os.path.join(logo_folder, "report_logo.png"),
            description="Generated using Metashape Python API @Guan-Yan Chen"
        )
        print("HTML報告已生成: ", report_path)

    except RuntimeError as e:
        print(f"無法打開 {project_path}，錯誤訊息: {e}")
        continue

print("所有資料夾的處理完成！")

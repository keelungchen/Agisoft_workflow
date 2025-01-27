import Metashape
import os
import pandas as pd

print(Metashape.app.version)

# 定義根資料夾路徑
base_folder = r"E:\island\2014_04"
logo_folder = r"E:\report_logo" # 輸出report時顯示在pdf上logo的檔案位置

# 列出所有資料夾名稱並排除特定資料夾
excluded_folders = {"folder_to_exclude", "another_folder_to_exclude"}  # 定義要排除的資料夾
all_folders = [folder for folder in os.listdir(base_folder) if os.path.isdir(os.path.join(base_folder, folder)) and folder not in excluded_folders]
print("要處理的資料夾:\n" + "\n".join(all_folders))

# 過濾完成的資料夾
for folder in all_folders:
    folder_path = os.path.join(base_folder, folder)

    # 定義子資料夾路徑
    agisoft_folder = os.path.join(folder_path, "metashape_files")
    products_folder = os.path.join(folder_path, "products_old")

    # 確認子資料夾是否存在
    if not all(os.path.exists(subfolder) for subfolder in [agisoft_folder, products_folder]):
        print(f"警告: {folder} 資料夾結構不完整，跳過處理。")
        continue

# 搜尋 metashape_files 中的 .psx 檔案
    psx_files = [f for f in os.listdir(agisoft_folder) if f.endswith(".psx")]
    if not psx_files:
        print(f"警告: 在 {agisoft_folder} 中未找到任何 .psx 檔案，跳過處理。")
        continue

    # 假設只有一個 .psx 檔案，使用該檔案名稱作為 project_name
    project_name = os.path.splitext(psx_files[0])[0]  # 去掉檔案副檔名
    project_path = os.path.join(agisoft_folder, psx_files[0])  # 完整的專案檔案路徑
   
    doc = Metashape.Document()
    doc.open(project_path)
    chunk = doc.chunk


# 生成項目報告，包括關鍵的重建信息和數據統計
    report_path = os.path.join(products_folder, f"{project_name}_report.html")
    chunk.exportReport(
        path=report_path,
        title=f"{project_name} Report",
        logo_path=os.path.join(logo_folder, "report_logo.png"),
        description="Generated using Metashape Python API @Guan-Yan Chen"
    )
    print("PDF與HTML報告已生成: ", report_path)


print("所有資料夾的處理完成！") 
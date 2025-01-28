import os
from bs4 import BeautifulSoup
import csv
import re

# 定義父資料夾路徑
base_folder = r"E:\island\2023_11"
output_csv = os.path.join(base_folder, "summary_results.csv")

# 定義提取數值和單位的函數
def extract_value_and_unit(text):
    """
    提取數值和單位，支持 "2.56 mm/pix" 格式。
    """
    match = re.match(r"([0-9,.]+)\s*(.*)", text.strip())
    if match:
        return float(match.group(1).replace(",", "")), match.group(2)
    return text.strip(), ""

# 定義提取 SVG 中 <text> 資料的函數
def extract_svg_text(soup, keyword):
    """
    提取 <text> 標籤中的資料，根據關鍵字匹配。
    """
    text_tag = soup.find('text', string=re.compile(keyword, re.IGNORECASE))
    if text_tag:
        next_text = text_tag.find_next('text')
        return next_text.text.strip() if next_text else "N/A"
    return "N/A"

# 定義結果表頭
headers = [
    "Folder Name",
    "Camera Stations",
    "Flying Altitude",
    "Ground Resolution",
    "Coverage Area",
    "Reprojection Error",
    "Tie Points",
    "Scale Bar Error",
    "Coordinate System",
    "Alignment Accuracy",
    "Depth Maps Quality",
    "Average Tie Point Multiplicity"
]

# 初始化結果列表
results = []

# 遍歷所有資料夾
for folder_name in os.listdir(base_folder):
    folder_path = os.path.join(base_folder, folder_name)

    # 確保處理的對象是資料夾
    if not os.path.isdir(folder_path):
        continue

    products_path = os.path.join(folder_path, "products") #設定Html資料夾位置
    # 確保產品資料夾存在
    if not os.path.exists(products_path):
        results.append([folder_name] + ["N/A"] * (len(headers) - 1))
        print(f"警告: 找不到 {products_path}，跳過資料夾 {folder_name}。")
        continue

    # 搜尋 `products_old` 資料夾中的 .html 檔案
    html_files = [f for f in os.listdir(products_path) if f.endswith(".html")]
    if not html_files:
        results.append([folder_name] + ["N/A"] * (len(headers) - 1))
        print(f"警告: 在 {products_path} 中未找到任何 .html 檔案，跳過資料夾 {folder_name}。")
        continue

    # 使用第一個找到的 .html 檔案
    html_file_path = os.path.join(products_path, html_files[0])

    # 讀取 HTML 檔案
    with open(html_file_path, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')

    try:
        # 提取資料
        camera_stations = extract_svg_text(soup, r"Camera stations")
        flying_altitude = extract_svg_text(soup, r"Flying altitude")
        ground_resolution = extract_svg_text(soup, r"Ground resolution")
        coverage_area = extract_svg_text(soup, r"Coverage area")
        tie_points = extract_svg_text(soup, r"Tie points")

        reprojection_error = soup.find('td', string=re.compile(r'Reprojection error', re.IGNORECASE))
        reprojection_error_value, _ = extract_value_and_unit(reprojection_error.find_next('td').text) if reprojection_error else ("N/A", "")

        scale_bar_error_table = soup.find('h1', string=re.compile(r'Scale Bars', re.IGNORECASE))
        if scale_bar_error_table:
            total_row = scale_bar_error_table.find_next('table').find('td', string=re.compile(r'Total', re.IGNORECASE)).find_parent('tr')
            total_scale_bar_error = total_row.find_all('td')[-1].text.strip()
            total_scale_bar_error_value = float(total_scale_bar_error.replace(",", ""))
        else:
            total_scale_bar_error_value = "N/A"

        coordinate_system = soup.find('td', string=re.compile(r'Coordinate system', re.IGNORECASE))
        coordinate_system_value = coordinate_system.find_next('td').text.strip() if coordinate_system else "N/A"

        alignment_accuracy = soup.find('td', string=re.compile(r'Accuracy', re.IGNORECASE))
        alignment_accuracy_value = alignment_accuracy.find_next('td').text.strip() if alignment_accuracy else "N/A"

        depth_maps_quality = soup.find('td', string=re.compile(r'Quality', re.IGNORECASE))
        depth_maps_quality_value = depth_maps_quality.find_next('td').text.strip() if depth_maps_quality else "N/A"

        average_tie_point_multiplicity = soup.find('td', string=re.compile(r'Average tie point multiplicity', re.IGNORECASE))
        average_tie_point_multiplicity_value = average_tie_point_multiplicity.find_next('td').text.strip() if average_tie_point_multiplicity else "N/A"

        # 添加提取結果
        results.append([
            folder_name,
            camera_stations,
            flying_altitude,
            ground_resolution,
            coverage_area,
            reprojection_error_value,
            tie_points,
            total_scale_bar_error_value,
            coordinate_system_value,
            alignment_accuracy_value,
            depth_maps_quality_value,
            average_tie_point_multiplicity_value
        ])
    except Exception as e:
        print(f"錯誤: 在 {html_file_path} 處理時發生錯誤 -> {e}")
        results.append([folder_name] + ["Error"] * (len(headers) - 1))

# 將結果寫入總 CSV
with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(headers)  # 寫入表頭
    writer.writerows(results)  # 寫入資料

print(f"資料已成功彙總至 {output_csv}")

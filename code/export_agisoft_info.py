import os
from bs4 import BeautifulSoup
import csv
import re

# 定義父資料夾路徑
base_folder = r"D:\\3D_workshop\\indoor_demo"
output_csv = os.path.join(base_folder, "summary_results.csv")

# 提取相關資訊函數，去除單位並返回數值和單位
def extract_value_and_unit(text):
    match = re.match(r"([0-9,.]+)\s*(.*)", text)
    if match:
        return match.group(1), match.group(2)
    return text, ""

# 定義結果表頭
headers = [
    "Folder Name",
    "Camera Stations",
    "Flying Altitude",
    "Ground Resolution",
    "Coverage Area",
    "Reprojection Error",
    "Tie Points",
    "Scale Bar Error"
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

    products_path = os.path.join(folder_path, "products")
    html_file = os.path.join(products_path, f"{folder_name}_report.html")

    # 如果產品資料夾或 HTML 檔不存在，跳過
    if not os.path.exists(products_path) or not os.path.exists(html_file):
        results.append([folder_name] + ["N/A"] * (len(headers) - 1))
        continue

    # 讀取 HTML 檔案
    with open(html_file, 'r', encoding='utf-8') as file:
        soup = BeautifulSoup(file, 'html.parser')

    # 提取資訊
    try:
        camera_stations = soup.find('text', string='Camera stations:').find_next('text').text
        camera_stations_value, _ = camera_stations, ""

        flying_altitude = soup.find('text', string='Flying altitude:').find_next('text').text
        flying_altitude_value, _ = extract_value_and_unit(flying_altitude)

        ground_resolution = soup.find('text', string='Ground resolution:').find_next('text').text
        ground_resolution_value, _ = extract_value_and_unit(ground_resolution)

        coverage_area = soup.find('text', string='Coverage area:').find_next('text').text
        coverage_area_value, _ = extract_value_and_unit(coverage_area)

        reprojection_error = soup.find('text', string='Reprojection error:').find_next('text').text
        reprojection_error_value, _ = extract_value_and_unit(reprojection_error)

        tie_points = soup.find('text', string='Tie points:').find_next('text').text
        tie_points_value, _ = tie_points, ""

        scale_bar_error_table = soup.find('h1', string='Scale Bars').find_next('table')
        total_row = scale_bar_error_table.find('td', string='Total').find_parent('tr')
        total_scale_bar_error = total_row.find_all('td')[-1].text
        total_scale_bar_error_value = float(total_scale_bar_error)

        # 提取 Processing Parameters
        coordinate_system = soup.find('td', string='Coordinate system').find_next('td').text
        alignment_accuracy = soup.find('td', string='Accuracy').find_next('td').text
        depth_maps_quality = soup.find('td', string='Quality').find_next('td').text
        average_tie_point_multiplicity = soup.find('td', string='Average tie point multiplicity').find_next('td').text

        # 添加提取結果
        results.append([
            folder_name,
            camera_stations_value,
            flying_altitude_value,
            ground_resolution_value,
            coverage_area_value,
            reprojection_error_value,
            tie_points_value,
            total_scale_bar_error_value,
            coordinate_system,
            alignment_accuracy,
            depth_maps_quality,
            average_tie_point_multiplicity
        ])
    except Exception as e:
        results.append([folder_name] + ["Error"] * (len(headers) - 1))

# 將結果寫入總 CSV
with open(output_csv, 'w', newline='', encoding='utf-8') as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(headers)  # 寫入表頭
    writer.writerows(results)  # 寫入資料

print(f"資料已成功彙總至 {output_csv}")

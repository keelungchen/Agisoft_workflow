from bs4 import BeautifulSoup
import pandas as pd
import os

# 設定項目資料夾路徑及產品資料夾
project_folder = r"D:\\3D_workshop\\indoor_demo\\tg_ortho_20\\agisoft"
project_name = os.path.basename(os.path.dirname(project_folder))  # 使用資料夾名稱作為項目名稱
output_folder = r"D:\\3D_workshop\\indoor_demo\\tg_ortho_20\\products"
report_path = os.path.join(output_folder, f"{project_name}_report.html")

# 閱讀 HTML 文件
html_file = report_path  # 替換為您的 HTML 文件路徑
if not os.path.exists(html_file):
    print(f"文件 {html_file} 不存在！請檢查路徑。")
    exit()

with open(html_file, 'r', encoding='utf-8') as file:
    soup = BeautifulSoup(file, 'html.parser')

# 定義需要提取的資訊欄位
fields = [
    "Aligned images",
    "Quality",
    "Flying altitude",
    "Ground resolution",
    "Coverage area",
    "Tie points",
    "Scale Bars"
]

# 存儲提取的資訊
data = {}

# 提取指定欄位的資訊
for field in fields:
    element = soup.find(text=field)  # 搜尋欄位
    if element:
        next_sibling = element.find_next()  # 取得欄位後的資訊
        data[field] = next_sibling.get_text(strip=True) if next_sibling else "N/A"
    else:
        data[field] = "N/A"

# 特別處理 Scale Bars 中的 total error
scale_bars = soup.find(text="Scale Bars")
if scale_bars:
    total_error = scale_bars.find_next(text="total")
    if total_error:
        total_error_value = total_error.find_next().get_text(strip=True)
        data["Scale Bars Total Error"] = total_error_value
    else:
        data["Scale Bars Total Error"] = "N/A"
else:
    data["Scale Bars Total Error"] = "N/A"

# 提取 <svg> 標籤中的 <text> 元素資訊
svg_texts = soup.find_all("text")  # 找到所有 <text> 元素
svg_data = {}

# 依序處理 <text> 元素成對資訊
for i in range(0, len(svg_texts), 2):
    try:
        key = svg_texts[i].get_text(strip=True)  # 第 i 個元素為欄位名稱
        value = svg_texts[i + 1].get_text(strip=True)  # 第 i+1 個元素為欄位值
        svg_data[key] = value
    except IndexError:
        print(f"解析 <text> 標籤時發生錯誤，無法處理索引 {i}")
        continue

# 將提取的資訊合併到 data 字典中
data.update(svg_data)

# 轉換為 DataFrame
try:
    df = pd.DataFrame([data])
except Exception as e:
    print(f"轉換 DataFrame 時發生錯誤：{e}")
    exit()

# 輸出表格並存儲為 CSV
csv_file = os.path.join(output_folder, f"{project_name}_info.csv")  # 替換為您的輸出路徑
try:
    df.to_csv(csv_file, index=False)
    print(f"提取的資訊已存儲至 {csv_file}")
except Exception as e:
    print(f"存檔 CSV 時發生錯誤：{e}")
    exit()

# 列印表格供參考
print(df)

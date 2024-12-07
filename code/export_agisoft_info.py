from bs4 import BeautifulSoup
import pandas as pd

project_folder = r"D:\3D_workshop\indoor_demo\tg_ortho_20\agisoft"
project_name = os.path.basename(os.path.dirname(project_folder))  # 用資料夾名稱作為專案名稱
output_folder = r"D:\3D_workshop\indoor_demo\tg_ortho_20\products"
report_path = os.path.join(output_folder, f"{project_name}_report.html")

# 读取HTML文件
html_file = report_path  # 替换为您的HTML文件路径
with open(html_file, 'r', encoding='utf-8') as file:
    soup = BeautifulSoup(file, 'html.parser')

# 定义需要提取的信息
fields = [
    "Aligned images",
    "Quality",
    "Flying altitude",
    "Ground resolution",
    "Coverage area",
    "Tie points",
    "Scale Bars"
]

# 存储提取的信息
data = {}

# 提取指定字段的信息
for field in fields:
    element = soup.find(text=field)  # 查找字段
    if element:
        next_sibling = element.find_next()  # 获取字段后的信息
        data[field] = next_sibling.get_text(strip=True) if next_sibling else "N/A"
    else:
        data[field] = "N/A"

# 处理Scale Bars中的total error
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

# 转换为DataFrame
df = pd.DataFrame([data])

# 输出表格并保存为CSV
csv_file = "output.csv"  # 替换为您的输出路径
df.to_csv(csv_file, index=False)
print(f"提取的信息已保存至 {csv_file}")

# 打印表格供参考
print(df)

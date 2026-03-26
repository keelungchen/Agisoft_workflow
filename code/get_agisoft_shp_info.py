from osgeo import ogr
import pandas as pd

shp_path = r"C:\Users\keelu\k2b_2023_export_markers.shp"

# 1. 打開圖層
ds = ogr.Open(shp_path, 0)  # 0 = read-only
if ds is None:
    raise FileNotFoundError(f"Cannot open {shp_path}")
layer = ds.GetLayer()

# 2. 印出座標系（CRS）
srs       = layer.GetSpatialRef()
auth      = srs.GetAuthorityName(None)   # 比如 "EPSG"
code      = srs.GetAuthorityCode(None)   # 比如 "32604"
name      = srs.GetName()
print(f"Spatial reference: {auth}:{code} – {name}\n")

# 3. 逐要素印出 NAME + X/Y(/Z)
records = []
for feat in layer:
    # 屬性欄位 NAME
    name = feat.GetField("NAME")
    # 幾何點
    geom = feat.GetGeometryRef()
    x    = geom.GetX()
    y    = geom.GetY()
    # 有些 shapefile 是 2D，GetZ() 會出錯；所以放到 try 裡
    try:
        z = geom.GetZ()
    except Exception:
        z = None

    # 用六位小數格式化輸出
    if z is not None:
        print(f"{name}: lon={x:.6f}, lat={y:.6f}, alt={z:.6f}")
    else:
        print(f"{name}: lon={x:.6f}, lat={y:.6f}")
    
    records.append({
        "Label": name,
        "X":     x,
        "Y":     y,
        "Z":     z
    })

ds = None
df = pd.DataFrame(records)
df
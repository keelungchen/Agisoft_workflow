# -*- coding: utf-8 -*-
"""
純 Python (GDAL/OGR + NumPy) 仿射變換範例：
1. 從控制點 shapefile 計算仿射參數，
2. 再將同參數套用至目標 shapefile (不使用 GeoPandas)。
"""

import os
import numpy as np
from osgeo import ogr

# 1. 控制點與目標檔案路徑
ctrl_shp   = r"\\jmadinlab\hawaii\reef_records\2023\k4b\products\site_4b_gcps.shp"
target_shp = r"C:\Users\keelu\GeoRef_test_Export.shp"
output_shp = r"C:\Users\keelu\GeoRef_test_Export_trans.shp"

# 2. 檢查檔案存在
for p in (ctrl_shp, target_shp):
    if not os.path.exists(p):
        raise FileNotFoundError(f"找不到檔案: {p}")

# 3. 讀取控制點並配對
driver  = ogr.GetDriverByName("ESRI Shapefile")
ds_ctrl = driver.Open(ctrl_shp, 0)
lyr_ctrl = ds_ctrl.GetLayer()

old_pts = {}
new_pts = {}
for feat in lyr_ctrl:
    name = feat.GetField("NAME")
    x, y = feat.GetGeometryRef().GetX(), feat.GetGeometryRef().GetY()
    if name.endswith("old"):
        old_pts[name] = (x, y)
    else:
        new_pts[name] = (x, y)

# 4. 配對至少三對
pairs = []
for oname, (ox, oy) in old_pts.items():
    base = oname[:-3]
    if base in new_pts:
        nx, ny = new_pts[base]
        pairs.append(((ox, oy), (nx, ny)))
if len(pairs) < 3:
    raise RuntimeError("至少需要 3 對控制點才能計算仿射參數。")

# 5. 計算仿射參數 a,b,c,d,e,f
A = []; B = []
for (ox, oy), (nx, ny) in pairs:
    A.append([ox, oy, 1, 0, 0, 0]); B.append(nx)
    A.append([0, 0, 0, ox, oy, 1]); B.append(ny)
A = np.array(A); B = np.array(B)
a, b, c, d, e, f = np.linalg.solve(A, B)

# 6. 仿射轉換函式
def transform_geom(g):
    geom_type = g.GetGeometryType()
    # Point
    if geom_type == ogr.wkbPoint:
        x0, y0 = g.GetX(), g.GetY()
        g.SetPoint(0,
                   a*x0 + b*y0 + c,
                   d*x0 + e*y0 + f)
        return g
    # LineString
    if geom_type == ogr.wkbLineString:
        new_line = ogr.Geometry(ogr.wkbLineString)
        for i in range(g.GetPointCount()):
            x0, y0, *_ = g.GetPoint(i)
            new_line.AddPoint(a*x0+b*y0+c,
                              d*x0+e*y0+f)
        return new_line
    # Polygon (僅外環)
    if geom_type == ogr.wkbPolygon:
        new_poly = ogr.Geometry(ogr.wkbPolygon)
        ring     = g.GetGeometryRef(0)
        new_ring = ogr.Geometry(ogr.wkbLinearRing)
        for i in range(ring.GetPointCount()):
            x0, y0, *_ = ring.GetPoint(i)
            new_ring.AddPoint(a*x0+b*y0+c,
                              d*x0+e*y0+f)
        new_poly.AddGeometry(new_ring)
        return new_poly
    # 其他類型則直接複製
    return g.Clone()

print(a,b,c,d,e,f)

# 7. 開啟目標圖層並建輸出
ds_tgt_in  = driver.Open(target_shp, 0)
lyr_tgt_in = ds_tgt_in.GetLayer()
if os.path.exists(output_shp):
    driver.DeleteDataSource(output_shp)
ds_tgt_out = driver.CreateDataSource(output_shp)
srs        = lyr_tgt_in.GetSpatialRef()
lyr_tgt_out= ds_tgt_out.CreateLayer(lyr_tgt_in.GetName(), srs,
                                    geom_type=lyr_tgt_in.GetGeomType())

# 複製欄位
in_defn = lyr_tgt_in.GetLayerDefn()
for i in range(in_defn.GetFieldCount()):
    lyr_tgt_out.CreateField(in_defn.GetFieldDefn(i))

out_defn = lyr_tgt_out.GetLayerDefn()
lyr_tgt_in.ResetReading()

# 8. 逐要素執行仿射，寫入輸出
for feat in lyr_tgt_in:
    geom_in = feat.GetGeometryRef()
    geom     = geom_in.Clone()
    new_geom = transform_geom(geom)

    feat_out = ogr.Feature(out_defn)
    for i in range(in_defn.GetFieldCount()):
        name = in_defn.GetFieldDefn(i).GetNameRef()
        feat_out.SetField(name, feat.GetField(i))
    feat_out.SetGeometry(new_geom)
    lyr_tgt_out.CreateFeature(feat_out)
    feat_out = None

# 9. Cleanup
ds_ctrl     = None
ds_tgt_in   = None
ds_tgt_out  = None

print("Affine 轉換完成，結果儲存於：", output_shp)

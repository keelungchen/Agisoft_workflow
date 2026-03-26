import xml.etree.ElementTree as ET
import Metashape
import tempfile
import re
import pandas as pd
from pyproj import Transformer

'''
### 啟用pt做為GCP
def enable_pt_as_control(psx_path):
    # 打開 Metashape 專案
    doc = Metashape.Document()
    doc.open(psx_path)
    chunk = doc.chunk

    # 用正則過濾所有 pt#
    pattern = re.compile(r"^pt\d+$", re.IGNORECASE)
    count = 0
    for m in chunk.markers:
        if pattern.match(m.label):
            if not m.reference.enabled:
                m.reference.enabled = True
                count += 1
                print(f"✅ 啟用 control point：{m.label}")
            else:
                print(f"ℹ️ 已是 control point：{m.label}")

    if count == 0:
        print("⚠️ 沒有新的 pt# 被設為 control point。")
    else:
        # 更新模型定位並存檔
        chunk.updateTransform()
        doc.save()
        print(f"共啟用 {count} 個 pt# 作為 control point，並已更新 Transform 及存檔。")

if __name__ == "__main__":
    psx = r"\\jmadinlab\hawaii\reef_records\2023\k4b\metashape_files\site_4b.psx"  # 改成你的路徑
    enable_pt_as_control(psx)
'''

def markers_to_table(psx_path, target_epsg=None, precision=12):
    """
    讀取 Metashape PSX 標記點，若指定 target_epsg，則同時計算投影座標。
    返回 DataFrame，包含原始 X,Y,Z 及選擇性的 X_proj, Y_proj。
    """
    # 1. 開專案
    doc = Metashape.Document()
    doc.open(psx_path)
    chunk = doc.chunk

    # 2. 如需投影，初始化 Transformer
    transformer = None
    if target_epsg is not None:
        # 假設原座標系為 EPSG:4326; 若非，需根據 chunk.crs 調整
        transformer = Transformer.from_crs("EPSG:4326",
                                           f"EPSG:{target_epsg}",
                                           always_xy=True)

    # 3. 擷取 marker 與計算(投影)座標
    records = []
    for m in chunk.markers:
        lbl     = m.label
        ref     = "Y" if m.reference.enabled else "N"
        loc     = m.reference.location
        if loc:
            x0, y0, z0 = loc.x, loc.y, loc.z
            if transformer:
                x1, y1 = transformer.transform(x0, y0)
            else:
                x1, y1 = None, None
        else:
            x0 = y0 = z0 = x1 = y1 = None

        rec = {"Label": lbl,
               "Reference": ref,
               "X": x0, "Y": y0, "Z": z0}
        if transformer:
            rec["X_proj"] = x1
            rec["Y_proj"] = y1
        records.append(rec)

    df = pd.DataFrame(records)

    # 4. 設置 pandas 顯示精度（底層值不變，僅影響 display）
    fmt = f"%.{precision}f"
    pd.set_option('display.precision', precision)
    pd.set_option('display.float_format', lambda x: fmt % x)

    return df

# 使用範例
psx = r"\\jmadinlab\hawaii\reef_records\2023\k2b\metashape_files\rr-k2b-2023_08.psx"
df_proj = markers_to_table(psx, target_epsg=32604)
print(df_proj)


# 只保留 pt 開頭的 old & 對應 new 點 / Keep only 'pt' control points
df_ctrl = df_proj[df_proj['Label'].str.startswith('pt')].copy()

print(df_ctrl)

# 1. 先提取 ID
df_ctrl['ID'] = df_ctrl['Label'].str.extract(r'(\d+)', expand=False).astype(int)

# 2. 分隔 new vs old
df_new = df_ctrl[~df_ctrl['Label'].str.contains('_old')].copy()
df_old = df_ctrl[df_ctrl['Label'].str.contains('_old')].copy()

# 3. 重命名投影欄位
df_new = df_new.rename(columns={'X_proj':'new_X','Y_proj':'new_Y'})
df_old = df_old.rename(columns={'X_proj':'old_X','Y_proj':'old_Y'})

# 4. 合併 new (前) 與 old (後)
df_pair = pd.merge(
    df_new[['ID','new_X','new_Y']],
    df_old[['ID','old_X','old_Y']],
    on='ID'
)

# 5. 只保留順序欄位，並設定顯示六位小數
df_out = df_pair[['new_X','new_Y','old_X','old_Y']]
pd.set_option('display.float_format', lambda x: f"{x:.6f}")

# 6. 列印結果
print(df_out)

# 7. 匯出成 tab 分隔、無索引無標頭的 txt
df_out.to_csv(
    'pt_transforms.txt',
    sep='\t',
    header=False,
    index=False,
    float_format='%.6f'
)



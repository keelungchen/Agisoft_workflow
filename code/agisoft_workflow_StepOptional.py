"""
Metashape 批次處理腳本 v4  (Metashape 2.x API)

可在開頭指定：
  - 執行模式：整個根資料夾批次處理，或只跑單一資料集 / 單一 .psx
  - 起始與結束步驟（共 10 步）
  - 是否使用比例尺、是否在報告加 logo
  - 是否建立 DEM 與 orthomosaic，以及是否匯出成 GeoTIFF

步驟簡述：
   1. 匯入照片        讀取 photos 資料夾中的影像（已在專案中的不重複加入）
   2. 對齊照片        matchPhotos + alignCameras，產生稀疏點雲並優化相機
   3. 稀疏點雲清理    依 Reconstruction Uncertainty、Projection Accuracy 刪點後再優化
   4. 偵測標記        偵測 Circular 12bit 標記
   5. 建立比例尺      依 Excel 定義加入比例尺並更新 Transform（賦予實際尺度）
   6. 重投影誤差清理  依 Reprojection Error 刪點 + 最終優化
   7. 深度圖 + 密集點雲  建立深度圖與密集點雲，並刪除低信度點
   8. 建立 DEM        （可選）以密集點雲建立 DEM，可匯出 GeoTIFF
   9. 建立 Orthomosaic（可選）以 DEM 為表面建立正射影像，可匯出 GeoTIFF
  10. 輸出報告        輸出 PDF / HTML 報告（放最後才會包含 DEM 與 ortho 頁面）

子資料夾名稱採寬鬆比對（photos / photo / images 等皆可，不分大小寫）。

執行方式：Metashape 內執行，或 metashape.exe -r this_script.py
"""

import os
import pandas as pd
import Metashape

print("Metashape 版本:", Metashape.app.version)

# 版本判斷：本腳本使用 2.x API（tie_points / point_cloud / exportRaster）
MS_VERSION = tuple(int(x) for x in Metashape.app.version.split(".")[:2])
if MS_VERSION < (2, 0):
    raise RuntimeError(
        f"本腳本使用 Metashape 2.x API，偵測到 {Metashape.app.version}。"
        "1.x 需改用 dense_cloud / exportDem / exportOrthomosaic 等舊名稱。"
    )

# =============================================================================
# 使用者設定
# =============================================================================

INTERACTIVE = False          # True = 執行時在主控台詢問下列設定

# --- 執行對象 ---------------------------------------------------------------
RUN_MODE = "batch"           # "batch" = 跑整個 BASE_FOLDER；"single" = 只跑 SINGLE_TARGET

BASE_FOLDER = r"F:\Kauai_imus"
SINGLE_TARGET = r"F:\Kauai_imus\site_01"
# SINGLE_TARGET 可以是：
#   (a) 資料集資料夾  ->  F:\Kauai_imus\site_01
#   (b) 專案檔本身    ->  F:\Kauai_imus\site_01\agisoft\site_01.psx

EXCLUDED_FOLDERS = {"folder_to_exclude", "another_folder_to_exclude"}

# 子資料夾名稱的可接受寫法（全部轉小寫後比對，順序即優先順序）
SUBFOLDER_ALIASES = {
    "photos":   ["photos", "photo", "images", "image", "img", "raw"],
    "agisoft":  ["agisoft", "metashape", "project", "projects", "psx"],
    "products": ["products", "product", "outputs", "output", "results", "result"],
}

# --- 步驟範圍 ---------------------------------------------------------------
START_STEP = 1               # 從第幾步開始
END_STEP = None              # 執行到第幾步為止（含）；None = 跑到最後一步

# --- 選用功能 ---------------------------------------------------------------
USE_SCALEBARS = True         # 是否建立比例尺（缺檔案時自動關閉）
USE_LOGO = True              # 報告是否加 logo（缺檔案時自動關閉）
OVERWRITE_PROJECT = False    # START_STEP == 1 時，若已有 .psx 是否重建

BUILD_DEM = True             # Step 8：以密集點雲建立 DEM
BUILD_ORTHOMOSAIC = True     # Step 9：以 DEM 為表面建立 orthomosaic
EXPORT_RASTERS = True        # 建立後是否匯出成 GeoTIFF 到 products 資料夾

LOGO_PATH = r"D:\3D_workshop\logo\report_logo.png"
SCALE_BAR_FILE = r"D:\Document_D\scale_bars_KBay.xlsx"

# --- 處理參數 ---------------------------------------------------------------
PARAMS = {
    "match_downscale": 1,          # 1 = High
    "depth_downscale": 4,          # 4 = Medium
    "keypoint_limit": 50000,
    "tiepoint_limit": 0,
    "recon_uncertainty": 15,
    "projection_accuracy": 5,
    "reprojection_error": 0.5,
    "marker_tolerance": 20,

    # DEM / orthomosaic
    "dem_resolution": 0,           # 公尺/像素，0 = 由 Metashape 自動決定
    "ortho_resolution": 0,         # 公尺/像素，0 = 自動（約為 DEM 的 1/4）
    "dem_interpolation": True,     # True = EnabledInterpolation，False = DisabledInterpolation
    "ortho_fill_holes": True,
    "ortho_ghosting_filter": False,
    "ortho_refine_seamlines": False,
}

# 投影方式：
#   "default" = 使用 chunk.crs（需要 chunk 有有效 transform，一般靠比例尺 + 標記建立）
#   "planar"  = 沿 chunk region 的 Z 軸做平面正射投影（局部座標、無地理參考時用）
PROJECTION_MODE = "default"


# =============================================================================
# 共用小工具
# =============================================================================

def optimize(chunk):
    chunk.optimizeCameras(
        fit_f=True, fit_cx=True, fit_cy=True,
        fit_b1=True, fit_b2=True,
        fit_k1=True, fit_k2=True, fit_k3=True, fit_k4=True,
        fit_p1=True, fit_p2=True, fit_p3=True, fit_p4=True,
        tiepoint_covariance=True,
    )


def filter_tie_points(chunk, criterion, threshold, label):
    if chunk.tie_points is None:
        print(f"  警告: 尚無 tie points，略過 {label} 篩選")
        return
    f = Metashape.TiePoints.Filter()
    f.init(chunk, criterion=criterion)
    f.selectPoints(threshold=threshold)
    n = len([p for p in chunk.tie_points.points if p.selected])
    chunk.tie_points.removeSelectedPoints()
    print(f"  {label} > {threshold}：刪除 {n} 點")


def has_valid_transform(chunk):
    """DEM / orthomosaic 需要 chunk 有已定義的 transform"""
    t = chunk.transform
    return bool(t and t.scale and t.rotation and t.translation)


def build_projection(chunk):
    """回傳要傳給 buildDem / buildOrthomosaic 的 projection，或 None（用預設）"""
    if PROJECTION_MODE != "planar":
        return None

    # 局部座標的平面正射投影：沿 chunk region 的 Z 軸俯視
    # 世界座標 -> 內部座標 -> region 對齊座標
    proj = Metashape.OrthoProjection()
    proj.type = Metashape.OrthoProjection.Type.Planar
    proj.crs = chunk.crs

    T = chunk.transform.matrix
    R = chunk.region.rot
    center = chunk.region.center
    proj.matrix = (Metashape.Matrix().Rotation(R.t())
                   * Metashape.Matrix().Translation(-center)
                   * T.inv())
    print("  使用 planar 投影（沿 region Z 軸俯視）— 建議產出後目視確認方向")
    return proj


def export_raster(chunk, path, source_data, resolution, save_alpha):
    """2.x 統一用 exportRaster；1.x 的 exportDem / exportOrthomosaic 已移除"""
    kwargs = {
        "path": path,
        "source_data": source_data,
        "image_format": Metashape.ImageFormatTIFF,
        "save_world": True,
    }
    if resolution:
        kwargs["resolution"] = resolution
    if save_alpha:
        kwargs["save_alpha"] = True
    try:
        chunk.exportRaster(**kwargs)
        print(f"  已匯出: {path}")
    except Exception as e:
        print(f"  錯誤: 匯出 {os.path.basename(path)} 失敗。原因: {e}")


# =============================================================================
# 十個步驟
# =============================================================================

def step_1_import(ctx):
    """匯入照片（已在專案中的照片不會重複加入）"""
    chunk = ctx["chunk"]
    photos_folder = ctx["photos_folder"]

    if not photos_folder or not os.path.isdir(photos_folder):
        raise RuntimeError("找不到照片資料夾（可接受名稱: "
                           + " / ".join(SUBFOLDER_ALIASES["photos"]) + "）")

    photos = [
        os.path.join(photos_folder, f)
        for f in sorted(os.listdir(photos_folder))
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff"))
    ]
    if not photos:
        raise RuntimeError(f"{photos_folder} 中沒有影像")

    existing = {c.photo.path for c in chunk.cameras if c.photo}
    new_photos = [p for p in photos if p not in existing]

    if not new_photos:
        print(f"  專案中已有全部 {len(photos)} 張照片，不重複匯入")
        return
    chunk.addPhotos(new_photos)
    print(f"  匯入 {len(new_photos)} 張照片（總計 {len(chunk.cameras)}）")


def step_2_align(ctx):
    """對齊照片（matchPhotos + alignCameras）並優化相機"""
    chunk = ctx["chunk"]

    chunk.matchPhotos(
        downscale=PARAMS["match_downscale"],
        generic_preselection=True,
        reference_preselection=False,
        filter_mask=False,
        filter_stationary_points=True,
        keypoint_limit=PARAMS["keypoint_limit"],
        tiepoint_limit=PARAMS["tiepoint_limit"],
        reset_matches=True,
        progress=lambda p: print(f"  matchPhotos: {p:.1f}%"),
    )
    chunk.alignCameras(
        adaptive_fitting=True,
        reset_alignment=True,
        progress=lambda p: print(f"  alignCameras: {p:.1f}%"),
    )
    aligned = len([c for c in chunk.cameras if c.transform])
    print(f"  對齊完成: {aligned}/{len(chunk.cameras)} 張相機已定位")
    optimize(chunk)
    ctx["doc"].save()


def step_3_clean_sparse(ctx):
    """稀疏點雲清理（Reconstruction Uncertainty、Projection Accuracy）後再優化"""
    chunk = ctx["chunk"]

    if chunk.tie_points is None:
        print("  警告: 尚無 tie points，請先執行 Step 2")
        return

    filter_tie_points(chunk, Metashape.TiePoints.Filter.ReconstructionUncertainty,
                      PARAMS["recon_uncertainty"], "Reconstruction Uncertainty")
    filter_tie_points(chunk, Metashape.TiePoints.Filter.ProjectionAccuracy,
                      PARAMS["projection_accuracy"], "Projection Accuracy")
    optimize(chunk)


def step_4_detect_markers(ctx):
    """偵測 Circular 12bit 標記"""
    chunk = ctx["chunk"]
    chunk.detectMarkers(
        target_type=Metashape.TargetType.CircularTarget12bit,
        tolerance=PARAMS["marker_tolerance"],
        progress=lambda p: print(f"  detectMarkers: {p:.1f}%"),
    )
    if chunk.markers:
        print(f"  偵測到 {len(chunk.markers)} 個標記: "
              + ", ".join(m.label for m in chunk.markers))
    else:
        print("  警告: 沒有偵測到任何標記")


def step_5_scalebars(ctx):
    """依 Excel 定義建立比例尺並更新 Transform"""
    chunk = ctx["chunk"]

    if not USE_SCALEBARS:
        print("  設定為不使用比例尺，略過（模型將維持無實際尺度）")
        return
    if not chunk.markers:
        print("  警告: chunk 中沒有標記，無法建立比例尺（請先執行 Step 4）")
        return

    existing = {sb.label for sb in chunk.scalebars}
    created = 0
    for _, row in ctx["scale_bar_data"].iterrows():
        l1, l2, length = row["scale_bar_1"], row["scale_bar_2"], row["length"]
        m1 = next((m for m in chunk.markers if m.label == l1), None)
        m2 = next((m for m in chunk.markers if m.label == l2), None)
        if not m1 or not m2:
            print(f"  警告: 找不到標記 {l1} 或 {l2}，跳過")
            continue
        if f"{l1}_{l2}" in existing or f"{l2}_{l1}" in existing:
            print(f"  比例尺 {l1} - {l2} 已存在，跳過")
            continue
        try:
            sb = chunk.addScalebar(m1, m2)
            sb.reference.distance = length
            created += 1
            print(f"  建立比例尺 {l1} - {l2} = {length} m")
        except Exception as e:
            print(f"  錯誤: 無法建立 {l1}-{l2} 的比例尺。原因: {e}")

    if created == 0 and not chunk.scalebars:
        print("  警告: 沒有任何比例尺可用")
        return

    chunk.updateTransform()
    report_scalebar_error(chunk)


def report_scalebar_error(chunk):
    total, count = 0.0, 0
    for sb in chunk.scalebars:
        src = sb.reference.distance
        if not src:
            continue
        if isinstance(sb.point0, Metashape.Camera):
            if not (sb.point0.center and sb.point1.center):
                continue
            est = (sb.point0.center - sb.point1.center).norm() * chunk.transform.scale
        else:
            if not (sb.point0.position and sb.point1.position):
                continue
            est = (sb.point0.position - sb.point1.position).norm() * chunk.transform.scale
        err = est - src
        total += err
        count += 1
        print(f"  比例尺 {sb.label}: 來源 {src} m, 預估 {est:.6f} m, 誤差 {err:.6f} m")
    if count:
        print(f"  總誤差 {total:.6f} m（平均 {total / count:.6f} m）")


def step_6_refine(ctx):
    """Reprojection Error 篩選 + 最終優化"""
    filter_tie_points(ctx["chunk"], Metashape.TiePoints.Filter.ReprojectionError,
                      PARAMS["reprojection_error"], "Reprojection Error")
    optimize(ctx["chunk"])


def step_7_dense(ctx):
    """深度圖 + 密集點雲 + 信度過濾"""
    chunk = ctx["chunk"]

    chunk.buildDepthMaps(
        downscale=PARAMS["depth_downscale"],
        progress=lambda p: print(f"  buildDepthMaps: {p:.1f}%"),
    )
    ctx["doc"].save()

    chunk.buildPointCloud(
        point_confidence=True,
        progress=lambda p: print(f"  buildPointCloud: {p:.1f}%"),
    )
    ctx["doc"].save()

    if chunk.point_cloud is None:
        print("  警告: 點雲建立失敗，略過信度過濾")
        return
    chunk.point_cloud.setConfidenceFilter(0, 1)
    chunk.point_cloud.removePoints(list(range(128)))
    chunk.point_cloud.resetFilters()
    print("  已刪除信度 0-1 的點")


def step_8_dem(ctx):
    """（可選）以密集點雲建立 DEM"""
    chunk = ctx["chunk"]

    if not BUILD_DEM:
        print("  設定為不建立 DEM，略過")
        return
    if chunk.point_cloud is None:
        print("  警告: 沒有密集點雲，無法建立 DEM（請先執行 Step 7）")
        return
    if not has_valid_transform(chunk):
        print("  警告: chunk 沒有有效的 transform，無法建立 DEM"
              "（通常表示缺少比例尺或參考點）")
        return

    kwargs = {
        "source_data": Metashape.PointCloudData,
        "interpolation": (Metashape.EnabledInterpolation if PARAMS["dem_interpolation"]
                          else Metashape.DisabledInterpolation),
        "resolution": PARAMS["dem_resolution"],
        "progress": lambda p: print(f"  buildDem: {p:.1f}%"),
    }
    projection = build_projection(chunk)
    if projection:
        kwargs["projection"] = projection
    if MS_VERSION >= (2, 1):
        kwargs["replace_asset"] = True   # 重跑時取代既有 DEM，不會累積多個資產

    chunk.buildDem(**kwargs)
    ctx["doc"].save()

    if chunk.elevation is None:
        print("  警告: DEM 建立後為空")
        return
    dem = chunk.elevation
    print(f"  DEM 完成: {dem.width} x {dem.height} px, "
          f"解析度 {dem.resolution:.5f} m/px")

    if EXPORT_RASTERS:
        os.makedirs(ctx["products_folder"], exist_ok=True)
        export_raster(
            chunk,
            os.path.join(ctx["products_folder"], f"{ctx['name']}_DEM.tif"),
            Metashape.ElevationData,
            PARAMS["dem_resolution"],
            save_alpha=False,
        )


def step_9_orthomosaic(ctx):
    """（可選）以 DEM 為表面建立 orthomosaic"""
    chunk = ctx["chunk"]

    if not BUILD_ORTHOMOSAIC:
        print("  設定為不建立 orthomosaic，略過")
        return
    if chunk.elevation is None:
        print("  警告: 沒有 DEM，無法以 ElevationData 建立 orthomosaic（請先執行 Step 8）")
        return

    kwargs = {
        "surface_data": Metashape.ElevationData,
        "blending_mode": Metashape.MosaicBlending,
        "fill_holes": PARAMS["ortho_fill_holes"],
        "ghosting_filter": PARAMS["ortho_ghosting_filter"],
        "refine_seamlines": PARAMS["ortho_refine_seamlines"],
        "resolution": PARAMS["ortho_resolution"],
        "progress": lambda p: print(f"  buildOrthomosaic: {p:.1f}%"),
    }
    projection = build_projection(chunk)
    if projection:
        kwargs["projection"] = projection
    if MS_VERSION >= (2, 1):
        kwargs["replace_asset"] = True

    chunk.buildOrthomosaic(**kwargs)
    ctx["doc"].save()

    if chunk.orthomosaic is None:
        print("  警告: orthomosaic 建立後為空")
        return
    ortho = chunk.orthomosaic
    print(f"  Orthomosaic 完成: {ortho.width} x {ortho.height} px, "
          f"解析度 {ortho.resolution:.5f} m/px")

    if EXPORT_RASTERS:
        os.makedirs(ctx["products_folder"], exist_ok=True)
        export_raster(
            chunk,
            os.path.join(ctx["products_folder"], f"{ctx['name']}_ortho.tif"),
            Metashape.OrthomosaicData,
            PARAMS["ortho_resolution"],
            save_alpha=True,
        )


def step_10_report(ctx):
    """輸出 PDF 與 HTML 報告（放最後，報告才會包含 DEM / orthomosaic 頁面）"""
    chunk, name = ctx["chunk"], ctx["name"]
    kwargs = {
        "title": f"{name} Report",
        "description": "Generated using Metashape Python API @Guan-Yan Chen",
    }
    if ctx["logo_path"]:
        kwargs["logo_path"] = ctx["logo_path"]

    os.makedirs(ctx["products_folder"], exist_ok=True)
    for ext in ("pdf", "html"):
        path = os.path.join(ctx["products_folder"], f"{name}_report.{ext}")
        try:
            chunk.exportReport(path=path, **kwargs)
            print(f"  已輸出: {path}")
        except Exception as e:
            print(f"  錯誤: 輸出 {ext.upper()} 報告失敗。原因: {e}")


# 調整處理順序只要改動這個清單的順序即可
STEPS = [
    (1, "匯入照片", step_1_import),
    (2, "對齊照片", step_2_align),
    (3, "稀疏點雲清理", step_3_clean_sparse),
    (4, "偵測標記", step_4_detect_markers),
    (5, "建立比例尺 + 更新 Transform", step_5_scalebars),
    (6, "重投影誤差清理 + 優化", step_6_refine),
    (7, "深度圖 + 密集點雲", step_7_dense),
    (8, "建立 DEM（可選）", step_8_dem),
    (9, "建立 Orthomosaic（可選）", step_9_orthomosaic),
    (10, "輸出報告", step_10_report),
]
LAST_STEP = STEPS[-1][0]


# =============================================================================
# 設定檢查與互動輸入
# =============================================================================

def print_steps():
    print("\n步驟一覽：")
    for num, label, _ in STEPS:
        print(f"  {num}. {label}")
    print()


def ask(prompt, default):
    raw = input(f"{prompt} [{default}]: ").strip()
    return raw if raw else str(default)


def ask_int(prompt, default, lo, hi):
    try:
        val = int(ask(prompt, default))
    except ValueError:
        print(f"  輸入無效，使用 {default}")
        return default
    if not lo <= val <= hi:
        print(f"  超出範圍 {lo}-{hi}，使用 {default}")
        return default
    return val


def ask_bool(prompt, default):
    raw = input(f"{prompt} ({'Y/n' if default else 'y/N'}): ").strip().lower()
    return default if not raw else raw in ("y", "yes", "1", "t")


def configure_interactively():
    global RUN_MODE, SINGLE_TARGET, START_STEP, END_STEP
    global USE_SCALEBARS, USE_LOGO, OVERWRITE_PROJECT
    global BUILD_DEM, BUILD_ORTHOMOSAIC, EXPORT_RASTERS

    print_steps()
    mode = ask("執行模式 (batch = 整個資料夾 / single = 單一專案)", RUN_MODE).lower()
    RUN_MODE = "single" if mode.startswith("s") else "batch"
    if RUN_MODE == "single":
        SINGLE_TARGET = ask("請輸入資料集資料夾或 .psx 路徑", SINGLE_TARGET).strip('"')

    START_STEP = ask_int("從第幾步開始", START_STEP, 1, LAST_STEP)
    END_STEP = ask_int("執行到第幾步為止", LAST_STEP, START_STEP, LAST_STEP)
    USE_SCALEBARS = ask_bool("是否使用比例尺", USE_SCALEBARS)
    USE_LOGO = ask_bool("報告是否加 logo", USE_LOGO)
    if START_STEP == 1:
        OVERWRITE_PROJECT = ask_bool("若已存在專案是否重建", OVERWRITE_PROJECT)

    if START_STEP <= 8 <= END_STEP:
        BUILD_DEM = ask_bool("是否建立 DEM", BUILD_DEM)
    if START_STEP <= 9 <= END_STEP:
        BUILD_ORTHOMOSAIC = ask_bool("是否建立 orthomosaic", BUILD_ORTHOMOSAIC)
    if BUILD_DEM or BUILD_ORTHOMOSAIC:
        EXPORT_RASTERS = ask_bool("是否匯出 GeoTIFF", EXPORT_RASTERS)


def preflight():
    """檢查步驟範圍與外部資源；缺資源時自動關閉對應功能。"""
    global START_STEP, END_STEP, USE_SCALEBARS, USE_LOGO, BUILD_ORTHOMOSAIC

    if END_STEP is None:
        END_STEP = LAST_STEP
    if not 1 <= START_STEP <= LAST_STEP:
        raise ValueError(f"START_STEP 必須介於 1 到 {LAST_STEP}")
    if not START_STEP <= END_STEP <= LAST_STEP:
        raise ValueError(f"END_STEP 必須介於 {START_STEP} 到 {LAST_STEP}")

    scale_bar_data = None
    if USE_SCALEBARS:
        if not os.path.isfile(SCALE_BAR_FILE):
            print(f"警告: 找不到比例尺檔案 {SCALE_BAR_FILE}，本次不建立比例尺")
            USE_SCALEBARS = False
        else:
            try:
                scale_bar_data = pd.read_excel(SCALE_BAR_FILE)
                missing = {"scale_bar_1", "scale_bar_2", "length"} - set(scale_bar_data.columns)
                if missing:
                    print(f"警告: 比例尺檔案缺少欄位 {missing}，本次不建立比例尺")
                    USE_SCALEBARS, scale_bar_data = False, None
                else:
                    print(f"已讀取比例尺定義 {len(scale_bar_data)} 筆")
            except Exception as e:
                print(f"警告: 讀取比例尺檔案失敗（{e}），本次不建立比例尺")
                USE_SCALEBARS = False

    logo_path = None
    if USE_LOGO:
        if os.path.isfile(LOGO_PATH):
            logo_path = LOGO_PATH
        else:
            print(f"警告: 找不到 logo {LOGO_PATH}，報告不使用 logo")
            USE_LOGO = False

    if BUILD_ORTHOMOSAIC and not BUILD_DEM and START_STEP <= 8:
        print("提醒: orthomosaic 以 DEM 為表面，若專案中沒有既有 DEM 會自動略過")

    return scale_bar_data, logo_path


# =============================================================================
# 子資料夾寬鬆比對 / 決定要處理哪些資料集
# =============================================================================

def find_subfolder(parent, key):
    """在 parent 底下找符合別名清單的子資料夾（不分大小寫），找不到回傳 None"""
    try:
        entries = [e for e in os.listdir(parent) if os.path.isdir(os.path.join(parent, e))]
    except OSError:
        return None
    lookup = {e.lower(): e for e in entries}
    for alias in SUBFOLDER_ALIASES[key]:
        if alias in lookup:
            return os.path.join(parent, lookup[alias])
    return None


def find_project_file(agisoft_folder, name):
    """在 agisoft 資料夾中找 .psx；優先同名，其次唯一的一個"""
    if not agisoft_folder or not os.path.isdir(agisoft_folder):
        return None
    psx = [f for f in os.listdir(agisoft_folder) if f.lower().endswith(".psx")]
    if not psx:
        return None
    preferred = f"{name}.psx"
    for f in psx:
        if f.lower() == preferred.lower():
            return os.path.join(agisoft_folder, f)
    if len(psx) > 1:
        print(f"  注意: {agisoft_folder} 中有多個 .psx，使用 {psx[0]}")
    return os.path.join(agisoft_folder, psx[0])


def make_job_from_dataset(dataset_folder):
    name = os.path.basename(os.path.normpath(dataset_folder))

    photos = find_subfolder(dataset_folder, "photos")
    agisoft = find_subfolder(dataset_folder, "agisoft") or os.path.join(dataset_folder, "agisoft")
    products = find_subfolder(dataset_folder, "products") or os.path.join(dataset_folder, "products")
    project_path = find_project_file(agisoft, name) or os.path.join(agisoft, f"{name}.psx")

    return {
        "name": name,
        "dataset_folder": dataset_folder,
        "photos_folder": photos,
        "agisoft_folder": agisoft,
        "products_folder": products,
        "project_path": project_path,
    }


def make_job_from_psx(psx_path):
    """直接指定 .psx；往上推一層找資料集，非標準結構就把產出放在 psx 所在資料夾"""
    name = os.path.splitext(os.path.basename(psx_path))[0]
    agisoft = os.path.dirname(psx_path)
    dataset = os.path.dirname(agisoft)

    return {
        "name": name,
        "dataset_folder": dataset,
        "photos_folder": find_subfolder(dataset, "photos"),
        "agisoft_folder": agisoft,
        "products_folder": find_subfolder(dataset, "products") or agisoft,
        "project_path": psx_path,
    }


def build_jobs():
    if RUN_MODE == "single":
        target = SINGLE_TARGET.strip('"')
        if target.lower().endswith(".psx"):
            if not os.path.isfile(target):
                raise FileNotFoundError(f"找不到專案檔: {target}")
            return [make_job_from_psx(target)]
        if not os.path.isdir(target):
            raise FileNotFoundError(f"找不到資料夾: {target}")
        return [make_job_from_dataset(target)]

    if not os.path.isdir(BASE_FOLDER):
        raise FileNotFoundError(f"找不到根資料夾: {BASE_FOLDER}")

    jobs = []
    for f in sorted(os.listdir(BASE_FOLDER)):
        path = os.path.join(BASE_FOLDER, f)
        if not os.path.isdir(path) or f in EXCLUDED_FOLDERS:
            continue
        job = make_job_from_dataset(path)
        if not job["photos_folder"] and not os.path.isfile(job["project_path"]):
            print(f"略過 {f}：找不到照片資料夾也沒有既有專案")
            continue
        jobs.append(job)
    return jobs


def describe_job(job):
    def short(p):
        return os.path.basename(os.path.normpath(p)) if p else "（無）"
    print(f"  照片: {short(job['photos_folder'])} | "
          f"專案: {short(job['agisoft_folder'])}/{os.path.basename(job['project_path'])} | "
          f"輸出: {short(job['products_folder'])}")


def open_or_create_project(job):
    """回傳 (doc, chunk)，要跳過則回傳 (None, None)"""
    project_path = job["project_path"]
    exists = os.path.isfile(project_path)

    if START_STEP == 1:
        if exists and not OVERWRITE_PROJECT:
            print(f"跳過 {job['name']}：已有專案（要重跑請設 OVERWRITE_PROJECT=True，"
                  f"或把 START_STEP 調到 2 以上接續處理）")
            return None, None
        os.makedirs(job["agisoft_folder"], exist_ok=True)
        doc = Metashape.Document()
        doc.save(path=project_path)
        chunk = doc.addChunk()
        doc.save()
        print(f"已建立新專案: {project_path}")
        return doc, chunk

    if not exists:
        print(f"跳過 {job['name']}：START_STEP={START_STEP} 需要既有專案，但找不到 {project_path}")
        return None, None

    doc = Metashape.Document()
    doc.open(project_path, read_only=False, ignore_lock=True)
    if not doc.chunks:
        print(f"跳過 {job['name']}：專案中沒有任何 chunk")
        return None, None
    chunk = doc.chunk or doc.chunks[0]
    print(f"已開啟既有專案: {project_path}（chunk: {chunk.label}）")
    return doc, chunk


# =============================================================================
# 主流程
# =============================================================================

def main():
    if INTERACTIVE:
        configure_interactively()

    scale_bar_data, logo_path = preflight()
    jobs = build_jobs()

    print("\n===== 本次執行設定 =====")
    print(f"模式     : {RUN_MODE}" + (f"  ({SINGLE_TARGET})" if RUN_MODE == "single" else ""))
    print(f"步驟範圍 : {START_STEP} → {END_STEP}（共 {LAST_STEP} 步）")
    print(f"比例尺   : {'使用' if USE_SCALEBARS else '不使用'}")
    print(f"Logo     : {'使用' if USE_LOGO else '不使用'}")
    print(f"DEM      : {'建立' if BUILD_DEM else '不建立'}")
    print(f"Ortho    : {'建立' if BUILD_ORTHOMOSAIC else '不建立'}")
    print(f"匯出 TIFF: {'是' if EXPORT_RASTERS else '否'}")
    print(f"待處理   : {len(jobs)} 個資料集")
    print("========================")

    succeeded, failed, skipped = [], [], []

    for job in jobs:
        print(f"\n########## {job['name']} ##########")
        describe_job(job)

        doc, chunk = open_or_create_project(job)
        if doc is None:
            skipped.append(job["name"])
            continue

        ctx = dict(job, doc=doc, chunk=chunk,
                   scale_bar_data=scale_bar_data, logo_path=logo_path)

        ok = True
        for num, label, func in STEPS:
            if not START_STEP <= num <= END_STEP:
                continue
            print(f"\n--- Step {num}: {label} ---")
            try:
                func(ctx)
                doc.save()
            except Exception as e:
                print(f"錯誤: Step {num}（{label}）失敗，中止此資料集。原因: {e}")
                failed.append(f"{job['name']} @ step {num}")
                ok = False
                break
        if ok:
            print(f"\n{job['name']} 完成，專案已儲存。")
            succeeded.append(job["name"])

    print("\n===== 處理總結 =====")
    print(f"成功 {len(succeeded)}：{', '.join(succeeded) if succeeded else '-'}")
    print(f"跳過 {len(skipped)}：{', '.join(skipped) if skipped else '-'}")
    print(f"失敗 {len(failed)}：{', '.join(failed) if failed else '-'}")


if __name__ == "__main__":
    main()
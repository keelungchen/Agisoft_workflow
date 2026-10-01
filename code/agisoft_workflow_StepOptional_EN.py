"""
Metashape batch processing script v4  (Metashape 2.x API)

Settings at the top of the file let you choose:
  - Run mode: process every dataset in a root folder, or only one dataset / one .psx
  - Start and end step (10 steps in total)
  - Whether to use scale bars and whether to add a logo to the report
  - Whether to build DEM and orthomosaic, and whether to export them as GeoTIFF

Steps:
   1. Import photos         Load images from the photos folder (skip photos already in the project)
   2. Align photos          matchPhotos + alignCameras, build tie points and optimize cameras
   3. Clean tie points      Remove points by Reconstruction Uncertainty and Projection Accuracy, then optimize
   4. Detect markers        Detect Circular 12bit targets
   5. Scale bars            Add scale bars from the CSV and update the transform (gives real-world scale)
   6. Reprojection cleanup  Remove points by Reprojection Error + final optimization
   7. Depth maps + dense cloud  Build depth maps and the dense point cloud, remove low-confidence points
   8. Build DEM             (optional) Build DEM from the dense cloud, can export GeoTIFF
   9. Build orthomosaic     (optional) Build orthomosaic on the DEM surface, can export GeoTIFF
      For steps 8 and 9 the projection is "auto" by default: when there are no geographic
      coordinates (scale bars only), the chunk is switched to Local Coordinates (m) and a
      planar projection along the region Z axis is used. See PROJECTION_MODE.
  10. Export report         Export PDF / HTML report (last, so it includes DEM and ortho pages)

Subfolder names are matched loosely (photos / photo / images, etc., case-insensitive).

How to run: inside Metashape, or metashape.exe -r this_script.py
"""

import os
import csv
import Metashape

print("Metashape version:", Metashape.app.version)

# Version check: this script uses the 2.x API (tie_points / point_cloud / exportRaster)
MS_VERSION = tuple(int(x) for x in Metashape.app.version.split(".")[:2])
if MS_VERSION < (2, 0):
    raise RuntimeError(
        f"This script uses the Metashape 2.x API, but found {Metashape.app.version}. "
        "For 1.x use the old names: dense_cloud / exportDem / exportOrthomosaic."
    )

# =============================================================================
# User settings
# =============================================================================

INTERACTIVE = False          # True = ask for the settings below in the console

# --- What to run -------------------------------------------------------------
RUN_MODE = "batch"           # "batch" = whole BASE_FOLDER; "single" = only SINGLE_TARGET

BASE_FOLDER = r"F:\Kauai_imus"
SINGLE_TARGET = r"F:\Kauai_imus\site_01"
# SINGLE_TARGET can be:
#   (a) a dataset folder  ->  F:\Kauai_imus\site_01
#   (b) a project file    ->  F:\Kauai_imus\site_01\agisoft\site_01.psx

EXCLUDED_FOLDERS = {"folder_to_exclude", "another_folder_to_exclude"}

# Accepted subfolder names (compared in lowercase; list order = priority)
SUBFOLDER_ALIASES = {
    "photos":   ["photos", "photo", "images", "image", "img", "raw"],
    "agisoft":  ["agisoft", "metashape", "project", "projects", "psx"],
    "products": ["products", "product", "outputs", "output", "results", "result"],
}

# --- Step range --------------------------------------------------------------
START_STEP = 1               # first step to run
END_STEP = None              # last step to run (inclusive); None = run to the end

# --- Optional features -------------------------------------------------------
USE_SCALEBARS = True         # build scale bars (turned off automatically if the file is missing)
USE_LOGO = True              # add a logo to the report (turned off automatically if missing)
OVERWRITE_PROJECT = False    # when START_STEP == 1, rebuild the .psx if it already exists

BUILD_DEM = True             # Step 8: build DEM from the dense cloud
BUILD_ORTHOMOSAIC = True     # Step 9: build orthomosaic on the DEM surface
EXPORT_RASTERS = True        # export DEM / ortho as GeoTIFF to the products folder

LOGO_PATH = r"D:\3D_workshop\logo\report_logo.png"

# Scale bar CSV. Needs columns scale_bar_1 / scale_bar_2 / length (length in meters)
#   scale_bar_1,scale_bar_2,length
#   target 52,target 53,0.297
SCALE_BAR_FILE = r"D:\Document_D\scale_bars_KBay.csv"

# --- Processing parameters ---------------------------------------------------
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
    "dem_resolution": 0,           # meters/pixel, 0 = let Metashape decide
    "ortho_resolution": 0,         # meters/pixel, 0 = auto (about 1/4 of the DEM)
    "dem_interpolation": True,     # True = EnabledInterpolation, False = DisabledInterpolation
    "ortho_fill_holes": True,
    "ortho_ghosting_filter": False,
    "ortho_refine_seamlines": False,
}

# Projection for DEM / orthomosaic:
#   "auto"    = decide automatically (recommended). If the chunk is georeferenced (cameras or
#               markers have coordinates) use chunk.crs; otherwise switch the chunk to
#               Local Coordinates (m) and use a planar projection along the region Z axis
#   "default" = always use chunk.crs (a new chunk defaults to WGS84, usually wrong without georeference)
#   "planar"  = always use the local-coordinate planar projection
PROJECTION_MODE = "auto"


# =============================================================================
# Helpers
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
        print(f"  Warning: no tie points yet, skipping {label} filter")
        return
    f = Metashape.TiePoints.Filter()
    f.init(chunk, criterion=criterion)
    f.selectPoints(threshold=threshold)
    n = len([p for p in chunk.tie_points.points if p.selected])
    chunk.tie_points.removeSelectedPoints()
    print(f"  {label} > {threshold}: removed {n} points")


def read_scale_bar_csv(path):
    """Read the scale bar CSV and return [{'scale_bar_1':.., 'scale_bar_2':.., 'length':float}, ...]

    Column names are case-insensitive and trimmed. Missing columns raise an error;
    bad rows (empty marker name, non-numeric length) print a warning and are skipped.
    """
    required = ("scale_bar_1", "scale_bar_2", "length")

    with open(path, newline="", encoding="utf-8-sig") as fp:
        reader = csv.DictReader(fp)
        if not reader.fieldnames:
            raise ValueError("CSV has no header row")

        # header name -> real column name (ignore case and extra spaces)
        header = {(h or "").strip().lower(): h for h in reader.fieldnames}
        missing = [c for c in required if c not in header]
        if missing:
            raise ValueError(f"missing columns {missing} (found: {reader.fieldnames})")

        rows = []
        for raw in reader:
            line = reader.line_num          # real line number in the file (line 1 = header)
            values = [(raw.get(header[c]) or "").strip() for c in required]
            if not any(values):
                continue
            l1, l2, length = values
            if not l1 or not l2:
                print(f"  Warning: scale bar CSV line {line} is missing a marker name, skipped")
                continue
            try:
                length = float(length)
            except ValueError:
                print(f"  Warning: scale bar CSV line {line} length '{length}' is not a number, skipped")
                continue
            rows.append({"scale_bar_1": l1, "scale_bar_2": l2, "length": length})
    return rows


def has_valid_transform(chunk):
    """DEM / orthomosaic need the chunk to have a defined transform"""
    t = chunk.transform
    return bool(t and t.scale and t.rotation and t.translation)


LOCAL_CRS_WKT = ('LOCAL_CS["Local Coordinates (m)",'
                 'LOCAL_DATUM["Local Datum",0],'
                 'UNIT["metre",1,AUTHORITY["EPSG","9001"]]]')


def is_local_crs(chunk):
    crs = chunk.crs
    if crs is None:
        return True
    return (crs.wkt or "").strip().upper().startswith("LOCAL_CS")


def is_georeferenced(chunk):
    """Does the chunk have real geographic coordinates?

    Only enabled camera or marker reference.location counts. A transform made only
    from scale bars has scale and orientation but no geographic position.
    """
    if is_local_crs(chunk):
        return False
    if any(c.reference.enabled and c.reference.location for c in chunk.cameras):
        return True
    if any(m.reference.enabled and m.reference.location for m in chunk.markers):
        return True
    return False


def ensure_local_crs(chunk):
    """If there is no coordinate system, set the chunk to Local Coordinates (m)

    Do not call updateTransform(): keep the transform built from scale bars in Step 5.
    """
    if is_local_crs(chunk):
        return
    try:
        chunk.crs = Metashape.CoordinateSystem(LOCAL_CRS_WKT)
    except Exception as e:
        print(f"  Warning: failed to set LOCAL_CS ({e}), using chunk.crs = None instead")
        chunk.crs = None
    print("  No georeference found -> chunk CRS set to Local Coordinates (m)")


def use_local_projection(chunk):
    """Should this run use the local-coordinate planar projection?"""
    if PROJECTION_MODE == "planar":
        return True
    if PROJECTION_MODE == "default":
        return False
    return not is_georeferenced(chunk)          # "auto"


def build_projection(chunk):
    """Return the projection for buildDem / buildOrthomosaic, or None (use chunk.crs)"""
    if not use_local_projection(chunk):
        return None

    ensure_local_crs(chunk)

    # Planar projection in local coordinates: look down the chunk region Z axis, origin at
    # the region center. region.rot / region.center are internal coordinates, so convert
    # them to world with chunk.transform first, then build "rotation + translation".
    # This keeps the meter scale from the scale bars (T.inv() would remove the scale).
    T = chunk.transform.matrix
    R_world = T.rotation() * chunk.region.rot
    center_world = T.mulp(chunk.region.center)

    proj = Metashape.OrthoProjection()
    proj.type = Metashape.OrthoProjection.Type.Planar
    proj.crs = chunk.crs
    proj.matrix = (Metashape.Matrix().Rotation(R_world.t())
                   * Metashape.Matrix().Translation(-center_world))
    print("  Using local-coordinate planar projection (looking down region Z axis) "
          "- please check the orientation visually")
    return proj


def export_raster(chunk, path, source_data, resolution, save_alpha):
    """2.x uses exportRaster for everything; 1.x exportDem / exportOrthomosaic are removed"""
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
        print(f"  Exported: {path}")
    except Exception as e:
        print(f"  Error: failed to export {os.path.basename(path)}. Reason: {e}")


# =============================================================================
# The ten steps
# =============================================================================

def step_1_import(ctx):
    """Import photos (photos already in the project are not added again)"""
    chunk = ctx["chunk"]
    photos_folder = ctx["photos_folder"]

    if not photos_folder or not os.path.isdir(photos_folder):
        raise RuntimeError("Photos folder not found (accepted names: "
                           + " / ".join(SUBFOLDER_ALIASES["photos"]) + ")")

    photos = [
        os.path.join(photos_folder, f)
        for f in sorted(os.listdir(photos_folder))
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff"))
    ]
    if not photos:
        raise RuntimeError(f"No images in {photos_folder}")

    existing = {c.photo.path for c in chunk.cameras if c.photo}
    new_photos = [p for p in photos if p not in existing]

    if not new_photos:
        print(f"  All {len(photos)} photos are already in the project, nothing to import")
        return
    chunk.addPhotos(new_photos)
    print(f"  Imported {len(new_photos)} photos (total {len(chunk.cameras)})")


def step_2_align(ctx):
    """Align photos (matchPhotos + alignCameras) and optimize cameras"""
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
    print(f"  Alignment done: {aligned}/{len(chunk.cameras)} cameras aligned")
    optimize(chunk)
    ctx["doc"].save()


def step_3_clean_sparse(ctx):
    """Clean tie points (Reconstruction Uncertainty, Projection Accuracy), then optimize"""
    chunk = ctx["chunk"]

    if chunk.tie_points is None:
        print("  Warning: no tie points yet, please run Step 2 first")
        return

    filter_tie_points(chunk, Metashape.TiePoints.Filter.ReconstructionUncertainty,
                      PARAMS["recon_uncertainty"], "Reconstruction Uncertainty")
    filter_tie_points(chunk, Metashape.TiePoints.Filter.ProjectionAccuracy,
                      PARAMS["projection_accuracy"], "Projection Accuracy")
    optimize(chunk)


def step_4_detect_markers(ctx):
    """Detect Circular 12bit markers"""
    chunk = ctx["chunk"]
    chunk.detectMarkers(
        target_type=Metashape.TargetType.CircularTarget12bit,
        tolerance=PARAMS["marker_tolerance"],
        progress=lambda p: print(f"  detectMarkers: {p:.1f}%"),
    )
    if chunk.markers:
        print(f"  Detected {len(chunk.markers)} markers: "
              + ", ".join(m.label for m in chunk.markers))
    else:
        print("  Warning: no markers detected")


def step_5_scalebars(ctx):
    """Create scale bars from the CSV and update the transform"""
    chunk = ctx["chunk"]

    if not USE_SCALEBARS:
        print("  Scale bars disabled, skipping (model will have no real-world scale)")
        return
    if not chunk.markers:
        print("  Warning: no markers in the chunk, cannot create scale bars (run Step 4 first)")
        return

    existing = {sb.label for sb in chunk.scalebars}
    created = 0
    for row in ctx["scale_bar_data"] or []:
        l1, l2, length = row["scale_bar_1"], row["scale_bar_2"], row["length"]
        m1 = next((m for m in chunk.markers if m.label == l1), None)
        m2 = next((m for m in chunk.markers if m.label == l2), None)
        if not m1 or not m2:
            print(f"  Warning: marker {l1} or {l2} not found, skipped")
            continue
        if f"{l1}_{l2}" in existing or f"{l2}_{l1}" in existing:
            print(f"  Scale bar {l1} - {l2} already exists, skipped")
            continue
        try:
            sb = chunk.addScalebar(m1, m2)
            sb.reference.distance = length
            created += 1
            print(f"  Created scale bar {l1} - {l2} = {length} m")
        except Exception as e:
            print(f"  Error: cannot create scale bar {l1}-{l2}. Reason: {e}")

    if created == 0 and not chunk.scalebars:
        print("  Warning: no scale bars available")
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
        print(f"  Scale bar {sb.label}: source {src} m, estimated {est:.6f} m, error {err:.6f} m")
    if count:
        print(f"  Total error {total:.6f} m (mean {total / count:.6f} m)")


def step_6_refine(ctx):
    """Reprojection Error filter + final optimization"""
    filter_tie_points(ctx["chunk"], Metashape.TiePoints.Filter.ReprojectionError,
                      PARAMS["reprojection_error"], "Reprojection Error")
    optimize(ctx["chunk"])


def step_7_dense(ctx):
    """Depth maps + dense point cloud + confidence filter"""
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
        print("  Warning: point cloud build failed, skipping confidence filter")
        return
    chunk.point_cloud.setConfidenceFilter(0, 1)
    chunk.point_cloud.removePoints(list(range(128)))
    chunk.point_cloud.resetFilters()
    print("  Removed points with confidence 0-1")


def step_8_dem(ctx):
    """(Optional) Build DEM from the dense point cloud"""
    chunk = ctx["chunk"]

    if not BUILD_DEM:
        print("  DEM disabled, skipping")
        return
    if chunk.point_cloud is None:
        print("  Warning: no dense point cloud, cannot build DEM (run Step 7 first)")
        return
    if not has_valid_transform(chunk):
        if not use_local_projection(chunk):
            print("  Warning: chunk has no valid transform, cannot build DEM "
                  "(usually missing scale bars or reference points)")
            return
        # local coordinates work without a transform, but the units are arbitrary
        print("  Note: chunk has no valid transform, DEM will use local coordinates with arbitrary units")

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
        kwargs["replace_asset"] = True   # replace the old DEM on re-run instead of adding another

    chunk.buildDem(**kwargs)
    ctx["doc"].save()

    if chunk.elevation is None:
        print("  Warning: DEM is empty after build")
        return
    dem = chunk.elevation
    print(f"  DEM done: {dem.width} x {dem.height} px, "
          f"resolution {dem.resolution:.5f} m/px")

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
    """(Optional) Build orthomosaic using the DEM as surface"""
    chunk = ctx["chunk"]

    if not BUILD_ORTHOMOSAIC:
        print("  Orthomosaic disabled, skipping")
        return
    if chunk.elevation is None:
        print("  Warning: no DEM, cannot build orthomosaic on ElevationData (run Step 8 first)")
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
        print("  Warning: orthomosaic is empty after build")
        return
    ortho = chunk.orthomosaic
    print(f"  Orthomosaic done: {ortho.width} x {ortho.height} px, "
          f"resolution {ortho.resolution:.5f} m/px")

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
    """Export PDF and HTML reports (last, so the report includes DEM / orthomosaic pages)"""
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
            print(f"  Exported: {path}")
        except Exception as e:
            print(f"  Error: failed to export {ext.upper()} report. Reason: {e}")


# To change the processing order, just reorder this list
STEPS = [
    (1, "Import photos", step_1_import),
    (2, "Align photos", step_2_align),
    (3, "Clean tie points", step_3_clean_sparse),
    (4, "Detect markers", step_4_detect_markers),
    (5, "Scale bars + update transform", step_5_scalebars),
    (6, "Reprojection error cleanup + optimize", step_6_refine),
    (7, "Depth maps + dense point cloud", step_7_dense),
    (8, "Build DEM (optional)", step_8_dem),
    (9, "Build orthomosaic (optional)", step_9_orthomosaic),
    (10, "Export report", step_10_report),
]
LAST_STEP = STEPS[-1][0]


# =============================================================================
# Settings check and interactive input
# =============================================================================

def print_steps():
    print("\nSteps:")
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
        print(f"  Invalid input, using {default}")
        return default
    if not lo <= val <= hi:
        print(f"  Out of range {lo}-{hi}, using {default}")
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
    mode = ask("Run mode (batch = whole folder / single = one project)", RUN_MODE).lower()
    RUN_MODE = "single" if mode.startswith("s") else "batch"
    if RUN_MODE == "single":
        SINGLE_TARGET = ask("Dataset folder or .psx path", SINGLE_TARGET).strip('"')

    START_STEP = ask_int("Start step", START_STEP, 1, LAST_STEP)
    END_STEP = ask_int("End step", LAST_STEP, START_STEP, LAST_STEP)
    USE_SCALEBARS = ask_bool("Use scale bars?", USE_SCALEBARS)
    USE_LOGO = ask_bool("Add logo to report?", USE_LOGO)
    if START_STEP == 1:
        OVERWRITE_PROJECT = ask_bool("Rebuild project if it already exists?", OVERWRITE_PROJECT)

    if START_STEP <= 8 <= END_STEP:
        BUILD_DEM = ask_bool("Build DEM?", BUILD_DEM)
    if START_STEP <= 9 <= END_STEP:
        BUILD_ORTHOMOSAIC = ask_bool("Build orthomosaic?", BUILD_ORTHOMOSAIC)
    if BUILD_DEM or BUILD_ORTHOMOSAIC:
        EXPORT_RASTERS = ask_bool("Export GeoTIFF?", EXPORT_RASTERS)


def preflight():
    """Check the step range and external files; turn off features whose files are missing."""
    global START_STEP, END_STEP, USE_SCALEBARS, USE_LOGO, BUILD_ORTHOMOSAIC

    if END_STEP is None:
        END_STEP = LAST_STEP
    if not 1 <= START_STEP <= LAST_STEP:
        raise ValueError(f"START_STEP must be between 1 and {LAST_STEP}")
    if not START_STEP <= END_STEP <= LAST_STEP:
        raise ValueError(f"END_STEP must be between {START_STEP} and {LAST_STEP}")

    scale_bar_data = None
    if USE_SCALEBARS:
        if not os.path.isfile(SCALE_BAR_FILE):
            print(f"Warning: scale bar file {SCALE_BAR_FILE} not found, no scale bars this run")
            USE_SCALEBARS = False
        else:
            try:
                scale_bar_data = read_scale_bar_csv(SCALE_BAR_FILE)
                if not scale_bar_data:
                    print("Warning: no usable rows in the scale bar file, no scale bars this run")
                    USE_SCALEBARS, scale_bar_data = False, None
                else:
                    print(f"Loaded {len(scale_bar_data)} scale bar definitions")
            except Exception as e:
                print(f"Warning: failed to read scale bar file ({e}), no scale bars this run")
                USE_SCALEBARS, scale_bar_data = False, None

    logo_path = None
    if USE_LOGO:
        if os.path.isfile(LOGO_PATH):
            logo_path = LOGO_PATH
        else:
            print(f"Warning: logo {LOGO_PATH} not found, report will have no logo")
            USE_LOGO = False

    if BUILD_ORTHOMOSAIC and not BUILD_DEM and START_STEP <= 8:
        print("Note: orthomosaic uses the DEM as surface; it will be skipped if the project has no DEM")

    return scale_bar_data, logo_path


# =============================================================================
# Loose subfolder matching / choose datasets to process
# =============================================================================

def find_subfolder(parent, key):
    """Find a subfolder of parent that matches the alias list (case-insensitive); None if not found"""
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
    """Find a .psx in the agisoft folder; prefer the same name, otherwise the first one"""
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
        print(f"  Note: multiple .psx files in {agisoft_folder}, using {psx[0]}")
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
    """Use a .psx directly; the dataset is one level up. If the layout is non-standard,
    outputs go into the folder of the .psx"""
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
                raise FileNotFoundError(f"Project file not found: {target}")
            return [make_job_from_psx(target)]
        if not os.path.isdir(target):
            raise FileNotFoundError(f"Folder not found: {target}")
        return [make_job_from_dataset(target)]

    if not os.path.isdir(BASE_FOLDER):
        raise FileNotFoundError(f"Root folder not found: {BASE_FOLDER}")

    jobs = []
    for f in sorted(os.listdir(BASE_FOLDER)):
        path = os.path.join(BASE_FOLDER, f)
        if not os.path.isdir(path) or f in EXCLUDED_FOLDERS:
            continue
        job = make_job_from_dataset(path)
        if not job["photos_folder"] and not os.path.isfile(job["project_path"]):
            print(f"Skipping {f}: no photos folder and no existing project")
            continue
        jobs.append(job)
    return jobs


def describe_job(job):
    def short(p):
        return os.path.basename(os.path.normpath(p)) if p else "(none)"
    print(f"  Photos: {short(job['photos_folder'])} | "
          f"Project: {short(job['agisoft_folder'])}/{os.path.basename(job['project_path'])} | "
          f"Output: {short(job['products_folder'])}")


def open_or_create_project(job):
    """Return (doc, chunk), or (None, None) to skip this dataset"""
    project_path = job["project_path"]
    exists = os.path.isfile(project_path)

    if START_STEP == 1:
        if exists and not OVERWRITE_PROJECT:
            print(f"Skipping {job['name']}: project already exists (set OVERWRITE_PROJECT=True "
                  f"to rebuild, or set START_STEP to 2 or higher to continue)")
            return None, None
        os.makedirs(job["agisoft_folder"], exist_ok=True)
        doc = Metashape.Document()
        doc.save(path=project_path)
        chunk = doc.addChunk()
        doc.save()
        print(f"Created new project: {project_path}")
        return doc, chunk

    if not exists:
        print(f"Skipping {job['name']}: START_STEP={START_STEP} needs an existing project, "
              f"but {project_path} was not found")
        return None, None

    doc = Metashape.Document()
    doc.open(project_path, read_only=False, ignore_lock=True)
    if not doc.chunks:
        print(f"Skipping {job['name']}: project has no chunks")
        return None, None
    chunk = doc.chunk or doc.chunks[0]
    print(f"Opened existing project: {project_path} (chunk: {chunk.label})")
    return doc, chunk


# =============================================================================
# Main
# =============================================================================

def main():
    if INTERACTIVE:
        configure_interactively()

    scale_bar_data, logo_path = preflight()
    jobs = build_jobs()

    print("\n===== Run settings =====")
    print(f"Mode       : {RUN_MODE}" + (f"  ({SINGLE_TARGET})" if RUN_MODE == "single" else ""))
    print(f"Steps      : {START_STEP} -> {END_STEP} (of {LAST_STEP})")
    print(f"Scale bars : {'yes' if USE_SCALEBARS else 'no'}")
    print(f"Logo       : {'yes' if USE_LOGO else 'no'}")
    print(f"DEM        : {'build' if BUILD_DEM else 'skip'}")
    print(f"Ortho      : {'build' if BUILD_ORTHOMOSAIC else 'skip'}")
    print(f"Projection : {PROJECTION_MODE}")
    print(f"Export TIFF: {'yes' if EXPORT_RASTERS else 'no'}")
    print(f"Datasets   : {len(jobs)}")
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
                print(f"Error: Step {num} ({label}) failed, stopping this dataset. Reason: {e}")
                failed.append(f"{job['name']} @ step {num}")
                ok = False
                break
        if ok:
            print(f"\n{job['name']} done, project saved.")
            succeeded.append(job["name"])

    print("\n===== Summary =====")
    print(f"Succeeded {len(succeeded)}: {', '.join(succeeded) if succeeded else '-'}")
    print(f"Skipped   {len(skipped)}: {', '.join(skipped) if skipped else '-'}")
    print(f"Failed    {len(failed)}: {', '.join(failed) if failed else '-'}")


if __name__ == "__main__":
    main()

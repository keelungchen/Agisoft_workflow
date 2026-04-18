import Metashape
import os

print(Metashape.app.version)

# Define root folder path
base_folder = r"F:\Kauai_imus"

# List all subfolders, excluding specified ones
excluded_folders = {"folder_to_exclude", "another_folder_to_exclude"}
all_folders = [folder for folder in os.listdir(base_folder) if os.path.isdir(os.path.join(base_folder, folder)) and folder not in excluded_folders]
print("Folders to process:\n" + "\n".join(all_folders))

for folder in all_folders:
    folder_path = os.path.join(base_folder, folder)

    # Define subfolder paths
    photos_folder = os.path.join(folder_path, "photos")
    agisoft_folder = os.path.join(folder_path, "agisoft")
    products_folder = os.path.join(folder_path, "products")

    # Check that all required subfolders exist
    if not all(os.path.exists(subfolder) for subfolder in [photos_folder, agisoft_folder, products_folder]):
        print(f"Warning: {folder} has incomplete folder structure, skipping.")
        continue

    # Skip if a .psx project file already exists
    psx_files = [file for file in os.listdir(agisoft_folder) if file.endswith(".psx")]
    if psx_files:
        print(f"Skipping {folder}, Metashape project already exists: {', '.join(psx_files)}")
        continue

    # Step 1: Create a new Metashape project
    project_name = os.path.basename(folder_path)
    project_path = os.path.join(agisoft_folder, f"{project_name}.psx")

    # Step 2: Initialize Metashape Document
    doc = Metashape.Document()
    doc.save(path=project_path)

    # Step 3: Add a new Chunk
    chunk = doc.addChunk()
    doc.save()

    # Step 4: Import photos
    photos = [os.path.join(photos_folder, f) for f in os.listdir(photos_folder) if f.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff'))]
    chunk.addPhotos(photos)
    doc.save()

    # Step 5: Align Photos
    chunk.matchPhotos(
        downscale=1,
        generic_preselection=True,
        reference_preselection=False,
        filter_mask=False,
        filter_stationary_points=True,
        keypoint_limit=50000,
        tiepoint_limit=0,
        reset_matches=True,
        progress=lambda p: print(f'Processing {folder} matchPhotos: {p :.2f}% complete')
    )
    chunk.alignCameras(adaptive_fitting=True, reset_alignment=True, progress=lambda p: print(f'Processing {folder} alignCameras: {p :.2f}% complete'))
    doc.save()
    print("Photo alignment: accuracy=high, generic_preselection=True, filter_stationary_points=True, adaptive_fitting=True, keypoints=50000, tiepoints=0")

    # Optimize camera alignment
    chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, \
        fit_b1=True, fit_b2=True, fit_k1=True, fit_k2=True, fit_k3=True, \
        fit_k4=True, fit_p1=True, fit_p2=True, fit_p3=True, fit_p4=True, tiepoint_covariance=True)
    doc.save()

    # Step 6: Gradual Selection - Reconstruction Uncertainty
    f = Metashape.TiePoints.Filter()
    f.init(chunk, criterion=Metashape.TiePoints.Filter.ReconstructionUncertainty)
    f.selectPoints(threshold=15)
    chunk.tie_points.removeSelectedPoints()
    doc.save()

    # Step 6.1: Gradual Selection - Projection Accuracy
    f.init(chunk, criterion=Metashape.TiePoints.Filter.ProjectionAccuracy)
    f.selectPoints(threshold=5)
    chunk.tie_points.removeSelectedPoints()
    chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, \
        fit_b1=True, fit_b2=True, fit_k1=True, fit_k2=True, fit_k3=True, \
        fit_k4=True, fit_p1=True, fit_p2=True, fit_p3=True, fit_p4=True, tiepoint_covariance=True)
    doc.save()

    # Step 8: Detect Markers (Circular 12-bit targets, tolerance=20)
    chunk.detectMarkers(
        target_type=Metashape.TargetType.CircularTarget12bit,
        tolerance=20,
        progress=lambda p: print(f'Processing {folder}: {p :.2f}% complete')
    )
    doc.save()

    # Step 9.1: Gradual Selection - Reprojection Error
    f.init(chunk, criterion=Metashape.TiePoints.Filter.ReprojectionError)
    f.selectPoints(threshold=0.5)
    chunk.tie_points.removeSelectedPoints()
    chunk.optimizeCameras(fit_f=True, fit_cx=True, fit_cy=True, \
        fit_b1=True, fit_b2=True, fit_k1=True, fit_k2=True, fit_k3=True, \
        fit_k4=True, fit_p1=True, fit_p2=True, fit_p3=True, fit_p4=True, tiepoint_covariance=True)
    doc.save()

    # Step 10: Build Depth Maps and Dense Point Cloud
    chunk.buildDepthMaps(
        downscale=4,
        progress=lambda p: print(f'Processing {folder} buildDepthMaps: {p :.2f}% complete')
    )
    doc.save()
    chunk.buildPointCloud(
        point_confidence=True,
        progress=lambda p: print(f'Processing {folder} buildPointCloud: {p :.2f}% complete')
    )
    doc.save()

    # Step 10.1: Filter Dense Cloud by Confidence (remove points with confidence 0-1)
    chunk.point_cloud.setConfidenceFilter(0, 1)
    chunk.point_cloud.removePoints(list(range(128)))
    chunk.point_cloud.resetFilters()
    doc.save()

    # Step 13: Generate Report (PDF and HTML)
    report_path = os.path.join(products_folder, f"{project_name}_report.pdf")
    chunk.exportReport(
        path=report_path,
        title=f"{project_name} Report",
        description="Generated using Metashape Python API @Guan-Yan Chen"
    )
    report_path = os.path.join(products_folder, f"{project_name}_report.html")
    chunk.exportReport(
        path=report_path,
        title=f"{project_name} Report",
        description="Generated using Metashape Python API @Guan-Yan Chen"
    )
    print("PDF and HTML reports generated: ", report_path)

    doc.save()
    print("Project saved to:", project_path)

print("All folders processed!")

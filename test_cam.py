import pyrealsense2 as rs
import numpy as np
import cv2
import open3d as o3d
import time  # Pour ajouter un délai

# Initialisation RealSense
pipeline = rs.pipeline()
config = rs.config()
config.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
config.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
pipeline.start(config)

# Paramètres de la caméra pour Open3D
profile = pipeline.get_active_profile()
depth_profile = profile.get_stream(rs.stream.depth)
intr = depth_profile.as_video_stream_profile().get_intrinsics()
camera_intrinsics = o3d.camera.PinholeCameraIntrinsic(
    intr.width, intr.height, intr.fx, intr.fy, intr.ppx, intr.ppy
)

# Visualiseur Open3D
vis = o3d.visualization.Visualizer()
vis.create_window("Nuage de points Live")
pcd = o3d.geometry.PointCloud()  # Un seul nuage de points
vis.add_geometry(pcd)

def is_valid_depth_value(depth_value):
    """ Fonction pour vérifier si une valeur de profondeur est valide. """
    return depth_value > 0 and depth_value < 10000  # Ignore les valeurs de profondeur nulles ou trop grandes

try:
    while True:
        # Capturer une frame
        frames = pipeline.wait_for_frames()
        depth_frame = frames.get_depth_frame()
        color_frame = frames.get_color_frame()
        if not depth_frame or not color_frame:
            continue

        # Convertir en images NumPy
        depth_image = np.asanyarray(depth_frame.get_data())
        color_image = np.asanyarray(color_frame.get_data())

        # Affichage RGB
        cv2.imshow("RGB", color_image)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

        # Attendre quelques millisecondes pour permettre à la caméra de se stabiliser
        time.sleep(0.1)  # 100 ms de délai, ajuste si nécessaire

        # Filtrer les valeurs de profondeur invalides (par exemple, 0)
        valid_depth_image = np.where(depth_image > 0, depth_image, np.nan)

        # Vérification des valeurs de profondeur
        depth_min = np.nanmin(valid_depth_image)
        depth_max = np.nanmax(valid_depth_image)
        print(f"Profondeur min: {depth_min} | max: {depth_max}")

        # Convertir en format Open3D
        depth_o3d = o3d.geometry.Image(valid_depth_image.astype(np.float32))  # Utiliser np.float32
        color_o3d = o3d.geometry.Image(color_image)
        
        rgbd = o3d.geometry.RGBDImage.create_from_color_and_depth(
            color_o3d, depth_o3d, depth_scale=1000.0, depth_trunc=0.8, convert_rgb_to_intensity=False
        )

        # Générer le nuage de points
        pcd_new = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd, camera_intrinsics)
        
        # Appliquer la transformation pour inverser l'axe Y et Z si nécessaire
        pcd_new.transform([[1, 0, 0, 0],
                           [0, -1, 0, 0],
                           [0, 0, -1, 0],
                           [0, 0, 0, 1]])

        # Vérification du nombre de points
        if len(pcd_new.points) == 0:
            print("Aucun point valide détecté.")
        else:
            # Mettre à jour le nuage de points existant
            pcd.points = pcd_new.points
            pcd.colors = pcd_new.colors

            # Mettre à jour la scène dans le visualiseur
            vis.update_geometry(pcd)
            vis.poll_events()
            vis.update_renderer()

finally:
    pipeline.stop()
    vis.destroy_window()
    cv2.destroyAllWindows()

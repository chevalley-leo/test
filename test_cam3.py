import open3d as o3d
import pyrealsense2 as rs
import numpy as np
import cv2
from scipy.spatial.transform import Rotation as R
from sklearn.cluster import DBSCAN
from scipy.spatial import cKDTree

# constantes
piece_path = "piece.stl"                    # path to the STL file
number_of_points = 5000                     # number of points to sample from the mesh
max_depth = 700                             # maximum depth for filtering
min_depth = 150                             # minimum depth for filtering
color_to_filter = np.array([128, 96, 49])   # color to filter in RGB format
positive_tolerance = np.array([20, 20, 20]) # tolerance for positive filtering
negative_tolerance = np.array([30, 30, 30]) # tolerance for negative filtering
voxel_size = 0.001                          # voxel size for downsampling
camera_position_world = np.array([0.42104, 0, 0.78244]) # camera position in world coordinates
camera_quaternion = [0.0, 0.707107, -0.707107, 0] # camera orientation in quaternion format

# load the STL file and sample points
mesh = o3d.io.read_triangle_mesh(piece_path)
mesh.scale(0.001, center=mesh.get_center())
pcd_model = mesh.sample_points_uniformly(number_of_points)
pcd_model.estimate_normals()


model_points = np.asarray(pcd_model.points)
z_min = np.min(model_points[:, 2])
tolerance_z = 0.0001
filtered_model_points = model_points[np.abs(model_points[:, 2] - z_min) <= tolerance_z]

pcd_model = o3d.geometry.PointCloud()
pcd_model.points = o3d.utility.Vector3dVector(filtered_model_points)
pcd_model.estimate_normals()

rotation_matrix = o3d.geometry.get_rotation_matrix_from_axis_angle([0, 0, np.pi])
pcd_model.rotate(rotation_matrix, center=pcd_model.get_center())

# Initialize the RealSense camera
pipeline = rs.pipeline()
config = rs.config()
config.enable_stream(rs.stream.depth, 1280, 720, rs.format.z16, 30)
config.enable_stream(rs.stream.color, 1280, 720, rs.format.bgr8, 30)
pipeline.start(config)
align = rs.align(rs.stream.color)
spatial = rs.spatial_filter()
temporal = rs.temporal_filter()

initial_model_points = np.asarray(pcd_model.points).copy()

# Method to find the best rotation angle
def find_best_rotation(pcd_model, pcd_piece, axis, angle_range, angle_step=3, fit_tolerance=0.01):
    def calculate_average_distance(source_points, target_points):
        tree = cKDTree(target_points)
        distances, _ = tree.query(source_points, k=1)
        return np.mean(distances), distances

    initial_model_points = np.asarray(pcd_model.points).copy()
    center_of_model = np.mean(initial_model_points, axis=0)
    best_angle = None
    min_distance = float('inf')
    best_distances = None
    angles = np.arange(*angle_range, angle_step)

    for angle in angles:
        pcd_model.points = o3d.utility.Vector3dVector(initial_model_points)
        angle_rad = np.radians(angle)
        rotation_vector = [angle_rad if axis == 'x' else 0, angle_rad if axis == 'y' else 0, angle_rad if axis == 'z' else 0]
        rotation_matrix = o3d.geometry.get_rotation_matrix_from_axis_angle(rotation_vector)
        pcd_model.rotate(rotation_matrix, center=center_of_model)
        avg_distance, distances = calculate_average_distance(np.asarray(pcd_model.points), np.asarray(pcd_piece.points))
        if avg_distance < min_distance:
            min_distance = avg_distance
            best_angle = angle
            best_distances = distances

    pcd_model.points = o3d.utility.Vector3dVector(initial_model_points)
    angle_rad = np.radians(best_angle)
    best_rotation_vector = [angle_rad if axis == 'x' else 0, angle_rad if axis == 'y' else 0, angle_rad if axis == 'z' else 0]
    best_rotation_matrix = o3d.geometry.get_rotation_matrix_from_axis_angle(best_rotation_vector)
    pcd_model.rotate(best_rotation_matrix, center=center_of_model)

    # Calcul du pourcentage de fit
    fit_percent = 0.0
    if best_distances is not None and len(best_distances) > 0:
        fit_percent = np.sum(best_distances < fit_tolerance) / len(best_distances) * 100
    print(f"[find_best_rotation] axis={axis}, best_angle={best_angle}, fit={fit_percent:.1f}% (tol={fit_tolerance})")
    return best_rotation_matrix, fit_percent

# Main loop
try:
    while True:
        pcd_model.points = o3d.utility.Vector3dVector(initial_model_points)
        pcd_model.paint_uniform_color([0, 1, 0])

        frames = pipeline.wait_for_frames()
        aligned_frames = align.process(frames)
        depth_frame = aligned_frames.get_depth_frame()
        color_frame = aligned_frames.get_color_frame()

        if not depth_frame or not color_frame:
            continue

        depth_frame = spatial.process(depth_frame)
        depth_frame = temporal.process(depth_frame)

        color_image = np.asanyarray(color_frame.get_data())
        depth_image = np.asanyarray(depth_frame.get_data())
        depth_image = np.where((depth_image > min_depth) & (depth_image < max_depth), depth_image, 0)
        color_image = cv2.cvtColor(color_image, cv2.COLOR_BGR2RGB)

        intr = depth_frame.profile.as_video_stream_profile().intrinsics
        intrinsic_o3d = o3d.camera.PinholeCameraIntrinsic(
            intr.width, intr.height, intr.fx, intr.fy, intr.ppx, intr.ppy
        )

        depth_o3d = o3d.geometry.Image(depth_image)
        color_o3d = o3d.geometry.Image(color_image)
        rgbd_image = o3d.geometry.RGBDImage.create_from_color_and_depth(
            color_o3d, depth_o3d, depth_scale=1000.0, depth_trunc=3.0, convert_rgb_to_intensity=False
        )
        pcd = o3d.geometry.PointCloud.create_from_rgbd_image(rgbd_image, intrinsic_o3d)

        target_color = color_to_filter / 255.0
        tolerance_positive = positive_tolerance / 255.0
        tolerance_negative = negative_tolerance / 255.0
        colors = np.asarray(pcd.colors)
        mask = np.all(
            (colors >= (target_color - tolerance_negative)) &
            (colors <= (target_color + tolerance_positive)),
            axis=1
        )
        pcd_filtered = pcd.select_by_index(np.where(mask)[0])

        points = np.asarray(pcd_filtered.points)
        eps = 0.01
        min_points = 10
        clustering = DBSCAN(eps=eps, min_samples=min_points).fit(points)
        labels = clustering.labels_
        unique_labels, counts = np.unique(labels, return_counts=True)
        target_label = unique_labels[np.argmax(counts)]
        mask = labels == target_label
        piece_points = points[mask]
        pcd_piece = o3d.geometry.PointCloud()
        pcd_piece.points = o3d.utility.Vector3dVector(piece_points)

        average_position_piece = np.mean(piece_points, axis=0)
        model_points = np.asarray(pcd_model.points)
        average_position_model = np.mean(model_points, axis=0)
        translation = average_position_piece - average_position_model

        initial_transformation = np.eye(4)
        initial_transformation[:3, 3] = translation
        pcd_model.transform(initial_transformation)



        
        pcd_model = pcd_model.voxel_down_sample(voxel_size)
        pcd_piece = pcd_piece.voxel_down_sample(voxel_size)

        rot_Y, fit_Y = find_best_rotation(pcd_model, pcd_piece, axis='y', angle_range=(-30, 35))
        rot_X, fit_X = find_best_rotation(pcd_model, pcd_piece, axis='x', angle_range=(-30, 35))
        rot_Z, fit_Z = find_best_rotation(pcd_model, pcd_piece, axis='z', angle_range=(0, 360))
        best_rotation_matrix = rot_X @ rot_Y @ rot_Z
        print(f"Fit Y: {fit_Y:.1f}%, Fit X: {fit_X:.1f}%, Fit Z: {fit_Z:.1f}%")

        global_transformation = np.eye(4)
        translation_matrix = np.eye(4)
        translation_matrix[:3, 3] = average_position_piece
        global_transformation = global_transformation @ translation_matrix
        rotation_matrix_4x4 = np.eye(4)
        rotation_matrix_4x4[:3, :3] = best_rotation_matrix
        global_transformation = global_transformation @ rotation_matrix_4x4

        camera_orientation_world = R.from_quat([camera_quaternion[1], camera_quaternion[2], camera_quaternion[3], camera_quaternion[0]])
        camera_orientation_matrix = camera_orientation_world.as_matrix()
        camera_transformation_world = np.eye(4)
        camera_transformation_world[:3, :3] = camera_orientation_matrix
        camera_transformation_world[:3, 3] = camera_position_world

        piece_transformation_world = camera_transformation_world @ global_transformation
        rotation_90_x = np.eye(4)
        rotation_90_x[:3, :3] = R.from_euler('x', 90, degrees=True).as_matrix()
        piece_transformation_world = piece_transformation_world @ rotation_90_x

        piece_position_world = piece_transformation_world[:3, 3]
        piece_orientation_world = piece_transformation_world[:3, :3]
        piece_quaternion = R.from_matrix(piece_orientation_world).as_quat()
        piece_quaternion = [piece_quaternion[3], piece_quaternion[0], piece_quaternion[1], piece_quaternion[2]]

        # print(f"Position: {piece_position_world}")
       # print(f"Orientation (quaternion): {piece_quaternion}")



        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

except KeyboardInterrupt:
    pass

finally:
    pipeline.stop()
    cv2.destroyAllWindows()



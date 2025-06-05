from scipy.spatial.transform import Rotation as R
import numpy as np

# Orientation actuelle (quaternion)
current_quaternion = [-0.01801, 0.72512, -0.68811, 0.01898]  # (w, x, y, z)

# Orientation souhaitée (quaternion)
target_quaternion = [0.513621, -0.512108, 0.484796, -0.488786]  # (w, x, y, z)

# Convertir les quaternions en objets de rotation
current_rotation = R.from_quat([current_quaternion[1],  # x
                                 current_quaternion[2],  # y
                                 current_quaternion[3],  # z
                                 current_quaternion[0]])  # w

target_rotation = R.from_quat([target_quaternion[1],  # x
                                target_quaternion[2],  # y
                                target_quaternion[3],  # z
                                target_quaternion[0]])  # w

# Calculer la rotation relative (rotation nécessaire pour passer de l'actuel au souhaité)
relative_rotation = target_rotation * current_rotation.inv()

# Extraire l'axe et l'angle de rotation
rotation_vector = relative_rotation.as_rotvec()  # Rotation vector (axis * angle in radians)
rotation_axis = rotation_vector / np.linalg.norm(rotation_vector)  # Normalized axis
rotation_angle = np.linalg.norm(rotation_vector)  # Angle in radians

# Convertir l'angle en degrés
rotation_angle_degrees = np.degrees(rotation_angle)

# Afficher les résultats
print(f"Rotation nécessaire :")
print(f"   - Axe de rotation : {rotation_axis}")
print(f"   - Angle de rotation : {rotation_angle_degrees:.2f}°")


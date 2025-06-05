import ezdxf
import serial
import time
import math

# ======== CONFIGURATION ========
DXF_FILE = "test_complexe.dxf"  # Ton fichier DXF
SERIAL_PORT = "/dev/ttyACM0"  # ← Port correct pour Linux
BAUDRATE = 115200
LASER_POWER = 1000      # 0 à 1000 (puissance du laser)
FEED_RATE = 600         # Vitesse de gravure en mm/min
SCALE_FACTOR = 1.0
OFFSET_X = 0
OFFSET_Y = 0

# ======== FONCTIONS UTILITAIRES ========
def apply_offset(x, y):
    return x * SCALE_FACTOR + OFFSET_X, y * SCALE_FACTOR + OFFSET_Y

def laser_on(power=LASER_POWER):
    return f"M3 S{power}"

def laser_off():
    return "M5"

def rapid_move(x, y):
    return f"G0 X{x:.3f} Y{y:.3f}"  # Déplacement rapide sans laser

def engrave_move(x, y):
    return f"G1 X{x:.3f} Y{y:.3f} F{FEED_RATE}"  # Déplacement avec gravure

def process_lwpolyline(entity):
    commands = []
    points = entity.get_points('xy')
    if not points:
        return commands

    # Laser off + aller au premier point
    x_start, y_start = apply_offset(*points[0])
    commands.append(laser_off())
    commands.append(rapid_move(x_start, y_start))
    commands.append(laser_on())

    for x, y in points[1:]:  # Commence à partir du 2ème point
        x, y = apply_offset(x, y)
        commands.append(engrave_move(x, y))

    if entity.closed:  # Si la polyligne est fermée
        x, y = apply_offset(points[0][0], points[0][1])  # Revenir au début
        commands.append(engrave_move(x, y))

    commands.append(laser_off())
    return commands


def process_spline(entity):
    # Approximations de la spline par des segments
    spline_points = list(entity.flattening(distance_tolerance=0.1, angle_tolerance=5, num_points=60))
    if not spline_points:
        return []

    commands = []
    x_start, y_start, _ = spline_points[0]
    x_start, y_start = apply_offset(x_start, y_start)
    commands.append(laser_off())
    commands.append(rapid_move(x_start, y_start))
    commands.append(laser_on())

    for x, y, _ in spline_points[1:]:
        x, y = apply_offset(x, y)
        commands.append(engrave_move(x, y))

    commands.append(laser_off())
    return commands

def initialize_machine(ser, do_homing=True):
    print("Initialisation de la machine...")

    if do_homing:
        print("Lancement du Homing...")
        ser.write(b"$H\n")  # <=== AJOUT homing
        time.sleep(5)  # Temps pour faire son homing (ajuster selon ta machine)

    ser.write(b"$X\n")  # Unlock après homing si besoin
    time.sleep(0.5)
    ser.write(b"G21\n")  # Units en mm
    time.sleep(0.1)
    ser.write(b"G90\n")  # Mode absolu
    time.sleep(0.1)
    ser.write(b"M5\n")   # Laser OFF
    time.sleep(0.1)
    ser.write(b"G92 X0 Y0\n")  # Set la position actuelle à (0,0)
    time.sleep(0.1)
    
    print("Machine initialisée et prête.")

# ======== CONVERTIR DXF EN G-CODE ========
def dxf_to_gcode(filename):
    try:
        doc = ezdxf.readfile(filename)
    except IOError:
        print(f"Erreur lors de l'ouverture du fichier {filename}.")
        return []
    except ezdxf.DXFStructureError:
        print(f"Le fichier {filename} n'est pas un fichier DXF valide.")
        return []

    msp = doc.modelspace()
    gcode = []
    gcode.append("G21")  # Unités en mm
    gcode.append("G90")  # Mode absolu
    gcode.append(laser_off())  # Toujours démarrer laser éteint

    for entity in msp:
        if entity.dxftype() == "LINE":
            print("Dessin d'une ligne...")
            x1, y1 = apply_offset(entity.dxf.start.x, entity.dxf.start.y)
            x2, y2 = apply_offset(entity.dxf.end.x, entity.dxf.end.y)
            gcode.append(laser_off())
            gcode.append(rapid_move(x1, y1))
            gcode.append(laser_on())
            gcode.append(engrave_move(x2, y2))
            gcode.append(laser_off())

        elif entity.dxftype() == "ARC":
            print("Dessin d'un arc...")
            cx, cy = apply_offset(entity.dxf.center.x, entity.dxf.center.y)
            radius = entity.dxf.radius * SCALE_FACTOR
            start_angle = math.radians(entity.dxf.start_angle)
            end_angle = math.radians(entity.dxf.end_angle)

            num_points = 50
            points = []
            for i in range(num_points + 1):
                angle = start_angle + (end_angle - start_angle) * (i / num_points)
                x = cx + radius * math.cos(angle)
                y = cy + radius * math.sin(angle)
                points.append((x, y))

            if points:
                gcode.append(laser_off())
                gcode.append(rapid_move(points[0][0], points[0][1]))
                gcode.append(laser_on())
                for x, y in points[1:]:
                    gcode.append(engrave_move(x, y))
                gcode.append(laser_off())

        elif entity.dxftype() == "CIRCLE":
            print("Dessin d'un cercle...")
            cx, cy = apply_offset(entity.dxf.center.x, entity.dxf.center.y)
            radius = entity.dxf.radius * SCALE_FACTOR

            num_points = 50
            points = [(cx + radius * math.cos(2 * math.pi * i / num_points),
                       cy + radius * math.sin(2 * math.pi * i / num_points)) for i in range(num_points + 1)]

            if points:
                gcode.append(laser_off())
                gcode.append(rapid_move(points[0][0], points[0][1]))
                gcode.append(laser_on())
                for x, y in points[1:]:
                    gcode.append(engrave_move(x, y))
                gcode.append(laser_off())

        elif entity.dxftype() == "POINT":
            print("Déplacement vers un point...")
            x, y = apply_offset(entity.dxf.location.x, entity.dxf.location.y)
            gcode.append(laser_off())
            gcode.append(rapid_move(x, y))

        elif entity.dxftype() == "LWPOLYLINE":
            print("Dessin d'une polyligne...")
            gcode += process_lwpolyline(entity)

        elif entity.dxftype() == "SPLINE":
            print("Dessin d'une spline...")
            gcode += process_spline(entity)

        else:
            print(f"Entité inconnue: {entity.dxftype()}")

    gcode.append(laser_off())
    gcode.append("G0 X0 Y0")  # Retourner à l'origine
    return gcode

# ======== ENVOYER G-CODE À LA MACHINE ========
def send_gcode_to_machine(gcode_lines, port, baudrate):
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            time.sleep(2)
            ser.write(b"\r\n\r\n")  # "Réveiller" le contrôleur
            time.sleep(2)
            ser.flushInput()

            initialize_machine(ser, do_homing=True)  # Active le homing automatiquement


            for line in gcode_lines:
                command = line.strip() + '\n'
                print(f"Envoyé: {command.strip()}")
                ser.write(command.encode('utf-8'))
                response = ser.readline()
                if response:
                    print(f"Réponse: {response.strip().decode()}")
    except serial.SerialException as e:
        print(f"Erreur de communication série: {e}")

# ======== MAIN ========

if __name__ == "__main__":
    gcode = dxf_to_gcode(DXF_FILE)
    if gcode:
        send_gcode_to_machine(gcode, SERIAL_PORT, BAUDRATE)
"""
laser_test.py

Description:
    Author: Léo Chevalley
    This script reads a DXF file, converts its geometric entities to G-code, and sends the G-code to a GRBL-compatible laser engraving machine via serial communication. It supports lines, arcs, circles, polylines, splines, and points. The script is intended for use with laser engravers for precise 2D path following.

License:
    MIT License
    Copyright (c) 2025 Léo Chevalley
    Permission is hereby granted, free of charge, to any person obtaining a copy
    of this software and associated documentation files (the "Software"), to deal
    in the Software without restriction, including without limitation the rights
    to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
    copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions:

    The above copyright notice and this permission notice shall be included in all
    copies or substantial portions of the Software.

    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
    IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
    FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
    AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
    LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
    OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
    SOFTWARE.
"""

import ezdxf
import serial
import time
import math

# ======== CONFIGURATION ========
DXF_FILE = "test_complexe.dxf"  # Path to the DXF file
SERIAL_PORT = "/dev/ttyACM0"    # Serial port for the laser engraver
BAUDRATE = 115200                # Serial communication speed
LASER_POWER = 1000               # Laser power (0 to 1000)
FEED_RATE = 600                  # Engraving speed in mm/min
SCALE_FACTOR = 1.0               # Scale for the drawing
OFFSET_X = 0                     # X offset for the drawing
OFFSET_Y = 0                     # Y offset for the drawing

# ======== UTILITY FUNCTIONS ========
def apply_offset(x, y):
    """Apply scaling and offset to coordinates."""
    return x * SCALE_FACTOR + OFFSET_X, y * SCALE_FACTOR + OFFSET_Y

def laser_on(power=LASER_POWER):
    """Return G-code to turn the laser on with specified power."""
    return f"M3 S{power}"

def laser_off():
    """Return G-code to turn the laser off."""
    return "M5"

def rapid_move(x, y):
    """Return G-code for rapid move (laser off)."""
    return f"G0 X{x:.3f} Y{y:.3f}"

def engrave_move(x, y):
    """Return G-code for engraving move (laser on)."""
    return f"G1 X{x:.3f} Y{y:.3f} F{FEED_RATE}"

def process_lwpolyline(entity):
    """Convert a lightweight polyline entity to G-code commands."""
    commands = []
    points = entity.get_points('xy')
    if not points:
        return commands
    # Move to start point with laser off
    x_start, y_start = apply_offset(*points[0])
    commands.append(laser_off())
    commands.append(rapid_move(x_start, y_start))
    commands.append(laser_on())
    # Engrave each segment
    for x, y in points[1:]:
        x, y = apply_offset(x, y)
        commands.append(engrave_move(x, y))
    # Close polyline if needed
    if entity.closed:
        x, y = apply_offset(points[0][0], points[0][1])
        commands.append(engrave_move(x, y))
    commands.append(laser_off())
    return commands

def process_spline(entity):
    """Convert a spline entity to G-code commands by flattening to line segments."""
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
    """Send initialization and homing commands to the laser engraver."""
    print("Initializing machine...")
    if do_homing:
        print("Performing homing...")
        ser.write(b"$H\n")
        time.sleep(5)
    ser.write(b"$X\n")  # Unlock
    time.sleep(0.5)
    ser.write(b"G21\n")  # Set units to mm
    time.sleep(0.1)
    ser.write(b"G90\n")  # Absolute positioning
    time.sleep(0.1)
    ser.write(b"M5\n")   # Laser OFF
    time.sleep(0.1)
    ser.write(b"G92 X0 Y0\n")  # Set current position as (0,0)
    time.sleep(0.1)
    print("Machine initialized and ready.")

# ======== DXF TO G-CODE CONVERSION ========
def dxf_to_gcode(filename):
    """Convert DXF entities to a list of G-code commands."""
    try:
        doc = ezdxf.readfile(filename)
    except IOError:
        print(f"Error opening file {filename}.")
        return []
    except ezdxf.DXFStructureError:
        print(f"File {filename} is not a valid DXF file.")
        return []
    msp = doc.modelspace()
    gcode = ["G21", "G90", laser_off()]
    for entity in msp:
        if entity.dxftype() == "LINE":
            print("Drawing line...")
            x1, y1 = apply_offset(entity.dxf.start.x, entity.dxf.start.y)
            x2, y2 = apply_offset(entity.dxf.end.x, entity.dxf.end.y)
            gcode.append(laser_off())
            gcode.append(rapid_move(x1, y1))
            gcode.append(laser_on())
            gcode.append(engrave_move(x2, y2))
            gcode.append(laser_off())
        elif entity.dxftype() == "ARC":
            print("Drawing arc...")
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
            print("Drawing circle...")
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
            print("Moving to point...")
            x, y = apply_offset(entity.dxf.location.x, entity.dxf.location.y)
            gcode.append(laser_off())
            gcode.append(rapid_move(x, y))
        elif entity.dxftype() == "LWPOLYLINE":
            print("Drawing polyline...")
            gcode += process_lwpolyline(entity)
        elif entity.dxftype() == "SPLINE":
            print("Drawing spline...")
            gcode += process_spline(entity)
        else:
            print(f"Unknown entity: {entity.dxftype()}")
    gcode.append(laser_off())
    gcode.append("G0 X0 Y0")  # Return to origin
    return gcode

# ======== SEND G-CODE TO MACHINE ========
def send_gcode_to_machine(gcode_lines, port, baudrate):
    """Send G-code commands to the laser engraver via serial port."""
    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            time.sleep(2)
            ser.write(b"\r\n\r\n")  # Wake up controller
            time.sleep(2)
            ser.flushInput()
            initialize_machine(ser, do_homing=True)
            for line in gcode_lines:
                command = line.strip() + '\n'
                print(f"Sent: {command.strip()}")
                ser.write(command.encode('utf-8'))
                response = ser.readline()
                if response:
                    print(f"Response: {response.strip().decode()}")
    except serial.SerialException as e:
        print(f"Serial communication error: {e}")

# ======== MAIN ENTRY POINT ========
if __name__ == "__main__":
    gcode = dxf_to_gcode(DXF_FILE)
    if gcode:
        send_gcode_to_machine(gcode, SERIAL_PORT, BAUDRATE)
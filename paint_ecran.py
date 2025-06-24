"""
paint_ecran.py

Description:
    Author: Léo Chevalley
    This script provides a touchscreen-friendly drawing interface using Tkinter, allowing users to draw, edit, and export shapes (lines, rectangles, circles, freehand, text) to DXF format. It supports object manipulation, logo overlay, and network file transfer to a remote PC. Designed for use in educational or prototyping environments with laser or CNC workflows.

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

# ======== IMPORTS ========
import tkinter as tk
from tkinter import messagebox
import ezdxf
import math
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
import numpy as np
import socket
import os

# ======== CONFIGURATION ========
MM_TO_UNITS = 1
DRAWING_WIDTH = 98
DRAWING_HEIGHT = 38
PC_PRINCIPAL_IP = "192.168.1.216"
PC_PRINCIPAL_PORT = 5001

# ======== DATA STRUCTURES ========
class Drawable:
    def __init__(self, type_, coords, canvas_id, text=None):
        self.type = type_  # shape type
        self.coords = coords
        self.canvas_id = canvas_id
        self.text = text
        self.angle = 0

# ======== MAIN APPLICATION CLASS ========
class PaintEcran:
    def __init__(self, root):
        # Main application class for drawing and exporting shapes
        self.root = root
        self.root.title("paint_ecran.py")
        self.root.attributes('-fullscreen', True)
        self.root.bind("<Escape>", lambda e: self.root.attributes("-fullscreen", False))
        self.zone_mode = tk.StringVar(value="rectangle")
        self.tool_mode = tk.StringVar(value="freehand")
        self.objects = []
        self.current = None
        self.start_pos = None
        self.selected_obj = None
        self.logo_dxf_path = os.path.join(os.path.dirname(__file__), "heig_vd.dxf")
        self.logo_polylines = self.load_logo_dxf(self.logo_dxf_path)
        self.setup_ui()
        self.set_canvas_zone()
        self.canvas.bind("<Configure>", lambda e: self.set_canvas_zone())

    def load_logo_dxf(self, dxf_path):
        """Load logo polylines from DXF file."""
        polylines = []
        try:
            doc = ezdxf.readfile(dxf_path)
            msp = doc.modelspace()
            for e in msp:
                if e.dxftype() == "LWPOLYLINE":
                    pts = [(v[0], v[1]) for v in e]
                    polylines.append(pts)
                elif e.dxftype() == "POLYLINE":
                    pts = [(v.dxf.location.x, v.dxf.location.y) for v in e.vertices]
                    polylines.append(pts)
                elif e.dxftype() == "LINE":
                    start = e.dxf.start
                    end = e.dxf.end
                    polylines.append([start[:2], end[:2]])
        except Exception as e:
            print(f"DXF logo load error: {e}")
        return polylines

    def setup_ui(self):
        # Set up the main UI components and toolbars
        self.root.configure(bg="#e3e6f3")
        title = tk.Label(self.root, text="Draw", font=("Arial", 20, "bold"), bg="#e3e6f3", fg="#22223b")
        title.pack(pady=(10, 2))
        close_btn = tk.Button(self.root, text="✖", font=("Arial", 18, "bold"), fg="white", bg="#e63946", activebackground="#b5171e", activeforeground="white", bd=0, relief=tk.FLAT, command=self.root.destroy)
        close_btn.place(relx=1.0, y=10, anchor="ne")
        fullscreen_btn = tk.Button(self.root, text="⛶", font=("Arial", 18, "bold"), fg="white", bg="#457b9d", activebackground="#1d3557", activeforeground="white", bd=0, relief=tk.FLAT, command=self.toggle_fullscreen)
        fullscreen_btn.place(relx=0.96, y=10, anchor="ne")
        canvas_frame = tk.Frame(self.root, bg="#e3e6f3")
        canvas_frame.pack(expand=True, fill=tk.BOTH)
        self.canvas = tk.Canvas(canvas_frame, bg="#fff", highlightthickness=0, bd=0, relief=tk.FLAT)
        self.canvas.pack(expand=True, fill=tk.BOTH, padx=60, pady=40)
        self.canvas.create_rectangle(10, 10, self.canvas.winfo_reqwidth()-10, self.canvas.winfo_reqheight()-10, outline="#bfc0c0", width=3)
        toolbar = tk.Frame(self.root, bg="#f5f6fa")
        toolbar.pack(side=tk.BOTTOM, fill=tk.X, pady=(0, 10))
        tools_frame = tk.Frame(toolbar, bg="#f5f6fa")
        tools_frame.pack(side=tk.TOP, pady=5)
        button_style = {"font": ("Arial", 21), "bg": "#a3cef1", "fg": "#22223b", "activebackground": "#5390d9", "activeforeground": "white", "bd": 0, "relief": tk.FLAT, "width": 16, "height": 2}
        radio_style = {"font": ("Arial", 20), "bg": "#bde0fe", "selectcolor": "#48bfe3", "indicatoron": 0, "width": 12, "height": 2, "bd": 0, "relief": tk.FLAT}
        tool_labels = [
            ("freehand", "Dessin libre"),
            ("line", "Ligne"),
            ("rectangle", "Rectangle"),
            ("circle", "Cercle"),
            ("text", "Texte")
        ]
        for tool, label in tool_labels:
            tk.Radiobutton(tools_frame, text=label, variable=self.tool_mode, value=tool, **radio_style).pack(side=tk.LEFT, padx=10, pady=5)
        actions_frame = tk.Frame(toolbar, bg="#f5f6fa")
        actions_frame.pack(side=tk.TOP, pady=10, fill=tk.X)
        actions_inner = tk.Frame(actions_frame, bg="#f5f6fa")
        actions_inner.pack(expand=True)
        tk.Button(actions_inner, text="Sélection", command=lambda: self.tool_mode.set("select"), font=("Arial", 21), bg="#bde0fe", fg="#22223b", activebackground="#48bfe3", activeforeground="white", bd=0, relief=tk.FLAT, width=16, height=2).pack(side=tk.LEFT, padx=15)
        tk.Button(actions_inner, text="Supprimer la sélection", command=self.delete_selected, **button_style).pack(side=tk.LEFT, padx=15)
        tk.Button(actions_inner, text="✔ Valider", command=self.export_dxf, font=("Arial", 21), bg="#4CAF50", fg="white", activebackground="#388E3C", activeforeground="white", bd=0, relief=tk.FLAT, width=16, height=2).pack(side=tk.LEFT, padx=15)
        tk.Button(actions_inner, text="Tout effacer", command=self.reset_canvas, font=("Arial", 21), bg="#e63946", fg="white", activebackground="#b5171e", activeforeground="white", bd=0, relief=tk.FLAT, width=16, height=2).pack(side=tk.LEFT, padx=15)
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-1>", self.on_double_click)
        self.root.bind("<Delete>", lambda e: self.delete_selected())

    def reset_canvas(self):
        # Clear all drawings and reset the canvas
        self.canvas.delete("all")
        self.objects.clear()
        self.selected_obj = None
        self.hide_control_points()
        self.set_canvas_zone()

    # --- Drawing and coordinate conversion ---
    def get_zone_coords(self):
        # Compute drawing zone coordinates in pixels
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        margin = 40
        zone_width_mm = DRAWING_WIDTH
        zone_height_mm = DRAWING_HEIGHT
        scale_x = (canvas_width - 2 * margin) / zone_width_mm
        scale_y = (canvas_height - 2 * margin) / zone_height_mm
        scale = min(scale_x, scale_y)
        zone_width_px = zone_width_mm * scale
        zone_height_px = zone_height_mm * scale
        x0 = (canvas_width - zone_width_px) / 2
        y0 = (canvas_height - zone_height_px) / 2
        x1 = x0 + zone_width_px
        y1 = y0 + zone_height_px
        self._current_scale = scale
        return x0, y0, x1, y1

    def set_canvas_zone(self):
        # Draw the main drawing zone and logo
        self.canvas.delete("all")
        self.objects.clear()
        x0, y0, x1, y1 = self.get_zone_coords()
        self.canvas.create_rectangle(x0, y0, x1, y1, outline="black", width=2)
        self.draw_logo_on_canvas(x0, y0, x1, y1)

    def draw_logo_on_canvas(self, x0, y0, x1, y1):
        # Draw the logo in the drawing zone if available
        if not self.logo_polylines:
            return
        logo_width_mm = 187
        logo_height_mm = 140
        display_width_mm = (30 / 5) * 2
        display_height_mm = (20 / 5) * 2
        margin_mm = 2
        scale = min(display_width_mm / logo_width_mm, display_height_mm / logo_height_mm)
        zone_width_mm = DRAWING_WIDTH
        zone_height_mm = DRAWING_HEIGHT
        logo_x0_mm = zone_width_mm - display_width_mm - margin_mm
        logo_y0_mm = margin_mm
        for poly in self.logo_polylines:
            if len(poly) < 2:
                continue
            points = []
            for px, py in poly:
                x_mm = logo_x0_mm + (px * scale)
                y_mm = logo_y0_mm + (py * scale)
                x_canvas, y_canvas = self.real_to_canvas(x_mm, y_mm)
                points.append((x_canvas, y_canvas))
            if points[0] != points[-1]:
                points.append(points[0])
            self.canvas.create_line(points, fill="#888", width=2, tags="logo", smooth=False)

    def canvas_to_real(self, x, y):
        # Convert canvas coordinates (pixels) to real-world millimeters
        x0, y0, x1, y1 = self.get_zone_coords()
        scale = self._current_scale
        real_x = (x - x0) / scale
        real_y = (y1 - y) / scale
        return real_x, real_y

    def real_to_canvas(self, rx, ry):
        # Convert real-world millimeters to canvas coordinates (pixels)
        x0, y0, x1, y1 = self.get_zone_coords()
        scale = self._current_scale
        x = x0 + rx * scale
        y = y1 - ry * scale
        return x, y

    # --- Event handlers for drawing and editing ---
    def on_click(self, event):
        # Handle mouse click for drawing or selecting objects
        tool = self.tool_mode.get()
        self.start_pos = (event.x, event.y)
        if tool == "freehand":
            self.current = [(event.x, event.y)]
            self.hide_control_points()
        elif tool == "text":
            self.hide_control_points()
            dialog = tk.Toplevel(self.root)
            dialog.title("Texte")
            dialog.transient(self.root)
            dialog.geometry("+20+20")
            dialog.wait_visibility()
            dialog.grab_set()
            tk.Label(dialog, text="Texte :", font=("Arial", 22)).pack(pady=(20,5))
            text_var = tk.StringVar()
            text_entry = tk.Entry(dialog, textvariable=text_var, font=("Arial", 28), width=18)
            text_entry.pack(ipadx=30, ipady=10, pady=10)
            text_entry.focus_set()
            tk.Label(dialog, text="Taille (mm) :", font=("Arial", 18)).pack(pady=(10,0))
            size_var = tk.StringVar(value="5")
            size_entry = tk.Entry(dialog, textvariable=size_var, font=("Arial", 22), width=8)
            size_entry.pack(ipadx=10, ipady=5, pady=10)
            is_upper = [False]
            current_field = [text_entry]
            def insert_char(c):
                current_field[0].insert(tk.END, c)
                current_field[0].focus_set()
            def backspace():
                entry = current_field[0]
                val = entry.get()
                entry.delete(0, tk.END)
                entry.insert(0, val[:-1])
                entry.focus_set()
            def space():
                current_field[0].insert(tk.END, ' ')
                current_field[0].focus_set()
            def toggle_case():
                is_upper[0] = not is_upper[0]
                update_keyboard()
            def switch_field():
                if current_field[0] == text_entry:
                    current_field[0] = size_entry
                else:
                    current_field[0] = text_entry
                current_field[0].focus_set()
            keyboard_frame = tk.Frame(dialog)
            keyboard_frame.pack(pady=10)
            letter_keys = ['a','z','e','r','t','y','u','i','o','p',
                           'q','s','d','f','g','h','j','k','l','m',
                           'w','x','c','v','b','n']
            number_keys = ['1','2','3','4','5','6','7','8','9','0']
            key_buttons = []
            def update_keyboard():
                for btn, key in key_buttons:
                    if key.isalpha():
                        btn.config(text=key.upper() if is_upper[0] else key.lower(),
                                   command=lambda c=(key.upper() if is_upper[0] else key.lower()): insert_char(c))
            row_frame = tk.Frame(keyboard_frame)
            row_frame.pack()
            for key in number_keys:
                btn = tk.Button(row_frame, text=key, width=4, height=2, font=("Arial", 18), command=lambda c=key: insert_char(c))
                btn.pack(side=tk.LEFT, padx=2, pady=2)
                key_buttons.append((btn, key))
            row_frame = tk.Frame(keyboard_frame)
            row_frame.pack()
            for key in letter_keys[:10]:
                btn = tk.Button(row_frame, text=key, width=4, height=2, font=("Arial", 18), command=lambda c=key: insert_char(c))
                btn.pack(side=tk.LEFT, padx=2, pady=2)
                key_buttons.append((btn, key))
            row_frame = tk.Frame(keyboard_frame)
            row_frame.pack()
            for key in letter_keys[10:20]:
                btn = tk.Button(row_frame, text=key, width=4, height=2, font=("Arial", 18), command=lambda c=key: insert_char(c))
                btn.pack(side=tk.LEFT, padx=2, pady=2)
                key_buttons.append((btn, key))
            row_frame = tk.Frame(keyboard_frame)
            row_frame.pack()
            maj_btn = tk.Button(row_frame, text='Maj', width=5, height=2, font=("Arial", 18), command=toggle_case)
            maj_btn.pack(side=tk.LEFT, padx=2, pady=2)
            for key in letter_keys[20:]:
                btn = tk.Button(row_frame, text=key, width=4, height=2, font=("Arial", 18), command=lambda c=key: insert_char(c))
                btn.pack(side=tk.LEFT, padx=2, pady=2)
                key_buttons.append((btn, key))
            tk.Button(row_frame, text='⌫', width=4, height=2, font=("Arial", 18), command=backspace).pack(side=tk.LEFT, padx=2, pady=2)
            tk.Button(row_frame, text='Champ suivant', width=12, height=2, font=("Arial", 18), command=switch_field).pack(side=tk.LEFT, padx=2, pady=2)
            row_frame = tk.Frame(keyboard_frame)
            row_frame.pack()
            tk.Button(row_frame, text='Espace', width=20, height=2, font=("Arial", 18), command=space).pack(side=tk.LEFT, padx=2, pady=2)
            update_keyboard()
            btn_frame = tk.Frame(dialog)
            btn_frame.pack(pady=20)
            def confirm():
                text = text_var.get()
                try:
                    size_mm = float(size_var.get())
                    if size_mm <= 0:
                        raise ValueError
                except ValueError:
                    size_entry.config(bg="#ffcccc")
                    return
                size_px = self.mm_to_tk_font_size(size_mm)
                font_name = "DejaVu Sans"
                if text:
                    canvas_id = self.canvas.create_text(
                        event.x, event.y,
                        text=text,
                        font=(font_name, size_px),
                        anchor="nw"
                    )
                    drawable = Drawable("text", [(event.x, event.y)], canvas_id, text)
                    drawable.size_mm = size_mm
                    drawable.font = font_name
                    self.objects.append(drawable)
                dialog.destroy()
            def cancel():
                dialog.destroy()
            tk.Button(btn_frame, text="OK", command=confirm, font=("Arial", 20), width=8, bg="#a3cef1").pack(side=tk.LEFT, padx=10)
            tk.Button(btn_frame, text="Annuler", command=cancel, font=("Arial", 20), width=8, bg="#bde0fe").pack(side=tk.LEFT, padx=10)
            dialog.wait_window(dialog)
        elif tool == "select":
            self.select_object(event.x, event.y)

    def on_drag(self, event):
        # Handle mouse drag for drawing or moving objects
        tool = self.tool_mode.get()
        if tool == "freehand" and self.current:
            x1, y1 = self.current[-1]
            x2, y2 = event.x, event.y
            line = self.canvas.create_line(x1, y1, x2, y2, fill="blue")
            self.current.append((x2, y2))
        elif tool in ("line", "rectangle", "circle") and self.start_pos:
            self.canvas.delete("preview")
            x0, y0 = self.start_pos
            if tool == "line":
                self.canvas.create_line(x0, y0, event.x, event.y, fill="blue", tags="preview")
            elif tool == "rectangle":
                self.canvas.create_rectangle(x0, y0, event.x, event.y, outline="blue", tags="preview")
            elif tool == "circle":
                self.canvas.create_oval(x0, y0, event.x, event.y, outline="blue", tags="preview")
        elif tool == "select" and self.selected_obj and hasattr(self, '_drag_data') and self._drag_data:
            dx = event.x - self._drag_data['x']
            dy = event.y - self._drag_data['y']
            self.canvas.move(self.selected_obj.canvas_id, dx, dy)
            self.selected_obj.coords = [(x+dx, y+dy) for (x, y) in self.selected_obj.coords]
            self._drag_data = {'x': event.x, 'y': event.y}

    def on_release(self, event):
        # Handle mouse release to finalize drawing
        tool = self.tool_mode.get()
        if self.start_pos:
            x0, y0 = self.start_pos
        else:
            x0, y0 = event.x, event.y
        x1, y1 = event.x, event.y

        if tool == "freehand" and self.current:
            canvas_id = None
            for i in range(1, len(self.current)):
                x1_, y1_ = self.current[i - 1]
                x2_, y2_ = self.current[i]
                canvas_id = self.canvas.create_line(x1_, y1_, x2_, y2_, fill="blue")
            self.objects.append(Drawable("freehand", self.current[:], canvas_id))
            self.current = None

        elif tool in ("line", "rectangle", "circle"):
            self.canvas.delete("preview")
            canvas_id = None
            coords = []
            if tool == "line":
                canvas_id = self.canvas.create_line(x0, y0, x1, y1, fill="blue")
                coords = [(x0, y0), (x1, y1)]
            elif tool == "rectangle":
                canvas_id = self.canvas.create_rectangle(x0, y0, x1, y1, outline="blue")
                coords = [(x0, y0), (x1, y1)]
            elif tool == "circle":
                canvas_id = self.canvas.create_oval(x0, y0, x1, y1, outline="blue")
                coords = [(x0, y0), (x1, y1)]
            self.objects.append(Drawable(tool, coords, canvas_id))

        self.start_pos = None

    def select_object(self, x, y):
        # Select an object under the cursor
        # Deselect all objects
        for obj in self.objects:
            if obj.type in ("line", "rectangle", "circle", "triangle", "freehand"):
                self.canvas.itemconfig(obj.canvas_id, width=1, tags="")
            else:
                self.canvas.itemconfig(obj.canvas_id, tags="")
        # Tolerance zone for touch screen (20x20 px around the point)
        tolerance = 20
        overlapping = self.canvas.find_overlapping(x - tolerance, y - tolerance, x + tolerance, y + tolerance)
        for obj in reversed(self.objects):
            if obj.canvas_id in overlapping:
                self.selected_obj = obj
                self._drag_data = {'x': x, 'y': y}
                if obj.type in ("line", "rectangle", "circle", "triangle", "freehand"):
                    self.canvas.itemconfig(obj.canvas_id, width=3, tags="selected")
                else:
                    self.canvas.itemconfig(obj.canvas_id, tags="selected")
                self.show_control_points(obj)
                return
        self.selected_obj = None
        self._drag_data = None
        self.hide_control_points()

    def on_double_click(self, event):
        # Edit object on double click
        # Find the object under the cursor
        for obj in self.objects:
            if self.canvas.find_withtag("current") and self.canvas.find_withtag("current")[0] == obj.canvas_id:
                self.edit_object(obj)
                break

    # --- Object editing dialogs ---
    def edit_object(self, obj):
        # Open the appropriate edit dialog for the object type
        if obj.type == "text":
            self.edit_text_object(obj)
        elif obj.type in ("rectangle", "circle"):
            self.edit_rect_or_ellipse(obj)
        elif obj.type == "line":
            self.edit_line_object(obj)
        elif obj.type == "triangle":
            self.edit_triangle_object(obj)
        elif obj.type == "freehand":
            self.edit_freehand_object(obj)

    def edit_text_object(self, obj):
        # Edit a text object (content, size, position)
        x, y = obj.coords[0]
        dialog = tk.Toplevel(self.root)
        dialog.title("Modifier le texte")
        dialog.transient(self.root)
        dialog.geometry(f"+{self.root.winfo_rootx() + 200}+{self.root.winfo_rooty() + 200}")
        dialog.wait_visibility()
        dialog.grab_set()

        tk.Label(dialog, text="Texte :").pack()
        text_var = tk.StringVar(value=obj.text)
        text_entry = tk.Entry(dialog, textvariable=text_var)
        text_entry.pack()

        tk.Label(dialog, text="Taille (mm) :").pack()
        size_var = tk.StringVar(value=str(getattr(obj, "size_mm", 10)))
        size_entry = tk.Entry(dialog, textvariable=size_var)
        size_entry.pack()

        tk.Label(dialog, text="Position X :").pack()
        x_var = tk.StringVar(value=str(int(x)))
        x_entry = tk.Entry(dialog, textvariable=x_var)
        x_entry.pack()
        tk.Label(dialog, text="Position Y :").pack()
        y_var = tk.StringVar(value=str(int(y)))
        y_entry = tk.Entry(dialog, textvariable=y_var)
        y_entry.pack()

        def confirm():
            try:
                size_mm = float(size_var.get())
                if size_mm <= 0:
                    raise ValueError
                new_x = int(x_var.get())
                new_y = int(y_var.get())
            except ValueError:
                messagebox.showerror("Erreur", "Valeur(s) invalide(s).")
                return
            self.canvas.delete(obj.canvas_id)
            size_px = int(size_mm * self._current_scale)  # Correction ici
            canvas_id = self.canvas.create_text(
                new_x, new_y,
                text=text_var.get(),
                font=("DejaVu Sans", size_px),
                anchor="nw"
            )
            obj.text = text_var.get()
            obj.size_mm = size_mm
            obj.font = "DejaVu Sans"
            obj.coords = [(new_x, new_y)]
            obj.canvas_id = canvas_id
            dialog.destroy()

        tk.Button(dialog, text="OK", command=confirm).pack(pady=5)
        text_entry.focus_set()
        dialog.wait_window(dialog)

    def edit_rect_or_ellipse(self, obj):
        # Edit a rectangle or ellipse object
        (x0, y0), (x1, y1) = obj.coords
        dialog = tk.Toplevel(self.root)
        dialog.title("Modifier " + ("rectangle" if obj.type == "rectangle" else "ellipse"))
        dialog.transient(self.root)
        dialog.geometry(f"+{self.root.winfo_rootx() + 200}+{self.root.winfo_rooty() + 200}")
        dialog.wait_visibility()
        dialog.grab_set()

        tk.Label(dialog, text="Coin 1 X :").pack()
        x0_var = tk.StringVar(value=str(int(x0)))
        tk.Entry(dialog, textvariable=x0_var).pack()
        tk.Label(dialog, text="Coin 1 Y :").pack()
        y0_var = tk.StringVar(value=str(int(y0)))
        tk.Entry(dialog, textvariable=y0_var).pack()
        tk.Label(dialog, text="Coin 2 X :").pack()
        x1_var = tk.StringVar(value=str(int(x1)))
        tk.Entry(dialog, textvariable=x1_var).pack()
        tk.Label(dialog, text="Coin 2 Y :").pack()
        y1_var = tk.StringVar(value=str(int(y1)))
        tk.Entry(dialog, textvariable=y1_var).pack()

        def confirm():
            try:
                nx0 = int(x0_var.get())
                ny0 = int(y0_var.get())
                nx1 = int(x1_var.get())
                ny1 = int(y1_var.get())
            except ValueError:
                messagebox.showerror("Erreur", "Valeur(s) invalide(s).")
                return
            self.canvas.delete(obj.canvas_id)
            if obj.type == "rectangle":
                canvas_id = self.canvas.create_rectangle(nx0, ny0, nx1, ny1, outline="blue")
            else:
                canvas_id = self.canvas.create_oval(nx0, ny0, nx1, ny1, outline="blue")
            obj.coords = [(nx0, ny0), (nx1, ny1)]
            obj.canvas_id = canvas_id
            dialog.destroy()

        tk.Button(dialog, text="OK", command=confirm).pack(pady=5)
        dialog.wait_window(dialog)

    def edit_line_object(self, obj):
        # Edit a line object
        (x0, y0), (x1, y1) = obj.coords
        dialog = tk.Toplevel(self.root)
        dialog.title("Modifier ligne")
        dialog.transient(self.root)
        dialog.geometry(f"+{self.root.winfo_rootx() + 200}+{self.root.winfo_rooty() + 200}")
        dialog.wait_visibility()
        dialog.grab_set()

        tk.Label(dialog, text="Début X :").pack()
        x0_var = tk.StringVar(value=str(int(x0)))
        tk.Entry(dialog, textvariable=x0_var).pack()
        tk.Label(dialog, text="Début Y :").pack()
        y0_var = tk.StringVar(value=str(int(y0)))
        tk.Entry(dialog, textvariable=y0_var).pack()
        tk.Label(dialog, text="Fin X :").pack()
        x1_var = tk.StringVar(value=str(int(x1)))
        tk.Entry(dialog, textvariable=x1_var).pack()
        tk.Label(dialog, text="Fin Y :").pack()
        y1_var = tk.StringVar(value=str(int(y1)))
        tk.Entry(dialog, textvariable=y1_var).pack()

        def confirm():
            try:
                nx0 = int(x0_var.get())
                ny0 = int(y0_var.get())
                nx1 = int(x1_var.get())
                ny1 = int(y1_var.get())
            except ValueError:
                messagebox.showerror("Erreur", "Valeur(s) invalide(s).")
                return
            self.canvas.delete(obj.canvas_id)
            canvas_id = self.canvas.create_line(nx0, ny0, nx1, ny1, fill="blue")
            obj.coords = [(nx0, ny0), (nx1, ny1)]
            obj.canvas_id = canvas_id
            dialog.destroy()

        tk.Button(dialog, text="OK", command=confirm).pack(pady=5)
        dialog.wait_window(dialog)

    def edit_triangle_object(self, obj):
        # Edit a triangle object
        (x1, y1), (x2, y2), (x3, y3) = obj.coords
        dialog = tk.Toplevel(self.root)
        dialog.title("Modifier triangle")
        dialog.transient(self.root)
        dialog.geometry(f"+{self.root.winfo_rootx() + 200}+{self.root.winfo_rooty() + 200}")
        dialog.wait_visibility()
        dialog.grab_set()

        tk.Label(dialog, text="Sommet 1 X :").pack()
        x1_var = tk.StringVar(value=str(int(x1)))
        tk.Entry(dialog, textvariable=x1_var).pack()
        tk.Label(dialog, text="Sommet 1 Y :").pack()
        y1_var = tk.StringVar(value=str(int(y1)))
        tk.Entry(dialog, textvariable=y1_var).pack()
        tk.Label(dialog, text="Sommet 2 X :").pack()
        x2_var = tk.StringVar(value=str(int(x2)))
        tk.Entry(dialog, textvariable=x2_var).pack()
        tk.Label(dialog, text="Sommet 2 Y :").pack()
        y2_var = tk.StringVar(value=str(int(y2)))
        tk.Entry(dialog, textvariable=y2_var).pack()
        tk.Label(dialog, text="Sommet 3 X :").pack()
        x3_var = tk.StringVar(value=str(int(x3)))
        tk.Entry(dialog, textvariable=x3_var).pack()
        tk.Label(dialog, text="Sommet 3 Y :").pack()
        y3_var = tk.StringVar(value=str(int(y3)))
        tk.Entry(dialog, textvariable=y3_var).pack()

        def confirm():
            try:
                nx1 = int(x1_var.get())
                ny1 = int(y1_var.get())
                nx2 = int(x2_var.get())
                ny2 = int(y2_var.get())
                nx3 = int(x3_var.get())
                ny3 = int(y3_var.get())
            except ValueError:
                messagebox.showerror("Erreur", "Valeur(s) invalide(s).")
                return
            self.canvas.delete(obj.canvas_id)
            canvas_id = self.canvas.create_polygon(nx1, ny1, nx2, ny2, nx3, ny3, outline="blue", fill="")
            obj.coords = [(nx1, ny1), (nx2, ny2), (nx3, ny3)]
            obj.canvas_id = canvas_id
            dialog.destroy()

        tk.Button(dialog, text="OK", command=confirm).pack(pady=5)
        dialog.wait_window(dialog)

    def edit_freehand_object(self, obj):
        # Move a freehand drawing
        # Allows moving the entire freehand drawing at once
        dialog = tk.Toplevel(self.root)
        dialog.title("Déplacer tracé libre")
        dialog.transient(self.root)
        dialog.geometry(f"+{self.root.winfo_rootx() + 200}+{self.root.winfo_rooty() + 200}")
        dialog.wait_visibility()
        dialog.grab_set()

        tk.Label(dialog, text="Décalage X :").pack()
        dx_var = tk.StringVar(value="0")
        tk.Entry(dialog, textvariable=dx_var).pack()
        tk.Label(dialog, text="Décalage Y :").pack()
        dy_var = tk.StringVar(value="0")
        tk.Entry(dialog, textvariable=dy_var).pack()

        def confirm():
            try:
                dx = int(dx_var.get())
                dy = int(dy_var.get())
            except ValueError:
                messagebox.showerror("Erreur", "Valeur(s) invalide(s).")
                return
            self.canvas.delete(obj.canvas_id)
            new_coords = [(x+dx, y+dy) for (x, y) in obj.coords]
            canvas_id = None
            for i in range(1, len(new_coords)):
                x1, y1 = new_coords[i-1]
                x2, y2 = new_coords[i]
                canvas_id = self.canvas.create_line(x1, y1, x2, y2, fill="blue")
            obj.coords = new_coords
            obj.canvas_id = canvas_id
            dialog.destroy()

        tk.Button(dialog, text="OK", command=confirm).pack(pady=5)
        dialog.wait_window(dialog)

    # --- Object management ---
    def delete_selected(self):
        # Delete the currently selected object
        if self.selected_obj:
            self.canvas.delete(self.selected_obj.canvas_id)
            self.objects.remove(self.selected_obj)
            self.selected_obj = None
            self.hide_control_points()

    def export_dxf(self):
        # Export all objects to a DXF file and send to the main PC
        doc = ezdxf.new(dxfversion="R2010")
        msp = doc.modelspace()

        offset_x = 100
        offset_y = 21


        for obj in self.objects:
            if obj.type == "freehand":
                pts = [(x + offset_x, y + offset_y) for x, y in [self.canvas_to_real(px, py) for px, py in obj.coords]]
                msp.add_lwpolyline(pts)
            elif obj.type == "line":
                x0, y0 = self.canvas_to_real(*obj.coords[0])
                x1, y1 = self.canvas_to_real(*obj.coords[1])
                msp.add_line((x0 + offset_x, y0 + offset_y), (x1 + offset_x, y1 + offset_y))
            elif obj.type == "rectangle":
                x0, y0 = self.canvas_to_real(*obj.coords[0])
                x1, y1 = self.canvas_to_real(*obj.coords[1])
                cx = (x0 + x1) / 2
                cy = (y0 + y1) / 2
                angle = getattr(obj, 'angle', 0)
                angle_rad = math.radians(-angle) 
                pts = [
                    (x0, y0), (x1, y0), (x1, y1), (x0, y1)
                ]
                rot_pts = [
                    (
                        cx + math.cos(angle_rad) * (px - cx) - math.sin(angle_rad) * (py - cy) + offset_x,
                        cy + math.sin(angle_rad) * (px - cx) + math.cos(angle_rad) * (py - cy) + offset_y
                    ) for (px, py) in pts
                ]
                msp.add_lwpolyline(rot_pts + [rot_pts[0]], close=True)
            elif obj.type == "circle":
                x0, y0 = obj.coords[0]
                x1, y1 = obj.coords[1]
                cx = (x0 + x1) / 2
                cy = (y0 + y1) / 2
                cx_real, cy_real = self.canvas_to_real(cx, cy)
                rx_canvas = abs(x1 - x0) / 2
                ry_canvas = abs(y1 - y0) / 2
                scale = self._current_scale
                rx = rx_canvas / scale  
                ry = ry_canvas / scale 
                angle = getattr(obj, 'angle', 0)
                if abs(rx - ry) < 1e-3:
                    msp.add_circle((cx_real + offset_x, cy_real + offset_y), rx)
                else:
                    angle_rad = math.radians(-angle)
                    if ry > rx:
                        major_axis = (ry * math.cos(angle_rad + math.pi/2), ry * math.sin(angle_rad + math.pi/2))
                        ratio = rx / ry if ry != 0 else 1
                    else:
                        major_axis = (rx * math.cos(angle_rad), rx * math.sin(angle_rad))
                        ratio = ry / rx if rx != 0 else 1
                    msp.add_ellipse(
                        center=(cx_real + offset_x, cy_real + offset_y),
                        major_axis=major_axis,
                        ratio=ratio
                    )
            elif obj.type == "text":
                x, y = self.canvas_to_real(*obj.coords[0])
                height = getattr(obj, "size_mm", 5)
                fontname = getattr(obj, "font", "DejaVu Sans")
                size_pt = height / 0.41
                try:
                    fp = FontProperties(family=fontname, size=size_pt)
                    tp = TextPath((0, 0), obj.text, prop=fp, size=size_pt)
                    all_pts = np.concatenate([np.array(poly) for poly in tp.to_polygons()])
                    min_x = np.min(all_pts[:, 0])
                    max_y = np.max(all_pts[:, 1])
                    min_y = np.min(all_pts[:, 1])
                    bbox_height = max_y - min_y
                    for poly in tp.to_polygons():
                        poly = np.array(poly)
                        poly[:, 0] -= min_x
                        poly[:, 1] -= max_y
                        poly[:, 1] -= bbox_height * 0.24
                        poly[:, 0] = poly[:, 0] * 0.3528 + x + offset_x
                        poly[:, 1] = poly[:, 1] * 0.3528 + y + offset_y
                        msp.add_lwpolyline([tuple(pt) for pt in poly], close=True)
                except Exception as e:
                    msp.add_text(obj.text, dxfattribs={"height": height, "insert": (x + offset_x, y + offset_y)})

        # Add logo to exported DXF
        try:
            logo_doc = ezdxf.readfile(self.logo_dxf_path)
            logo_msp = logo_doc.modelspace()
            logo_width_mm = 187
            logo_height_mm = 140
            display_width_mm = (30 / 5) * 2
            display_height_mm = (20 / 5) * 2
            margin_mm = 2
            scale = min(display_width_mm / logo_width_mm, display_height_mm / logo_height_mm)
            zone_width_mm = DRAWING_WIDTH
            zone_height_mm = DRAWING_HEIGHT
            logo_x0_mm = zone_width_mm - display_width_mm - margin_mm + offset_x
            logo_y0_mm = margin_mm + offset_y
            for e in logo_msp:
                if e.dxftype() == "LWPOLYLINE":
                    pts = [(logo_x0_mm + v[0]*scale, logo_y0_mm + v[1]*scale) for v in e]
                    msp.add_lwpolyline(pts, close=e.closed)
                elif e.dxftype() == "POLYLINE":
                    pts = [(logo_x0_mm + v.dxf.location.x*scale, logo_y0_mm + v.dxf.location.y*scale) for v in e.vertices]
                    closed = bool(e.dxf.flags & 1)
                    msp.add_lwpolyline(pts, close=closed)
                elif e.dxftype() == "LINE":
                    start = e.dxf.start
                    end = e.dxf.end
                    start_pt = (logo_x0_mm + start[0]*scale, logo_y0_mm + start[1]*scale)
                    end_pt = (logo_x0_mm + end[0]*scale, logo_y0_mm + end[1]*scale)
                    msp.add_line(start_pt, end_pt)
        except Exception as e:
            print(f"Erreur ajout logo DXF export: {e}")

        try:
            doc.saveas("dxf3.dxf")
            if self.send_dxf_to_pc("dxf3.dxf", PC_PRINCIPAL_IP, PC_PRINCIPAL_PORT):
                notif = tk.Toplevel(self.root)
                notif.title("Envoi")
                notif.geometry(f"+{self.root.winfo_rootx() + 400}+{self.root.winfo_rooty() + 400}")
                tk.Label(notif, text="Fichier envoyé à la graveuse !", font=("Arial", 20)).pack(padx=30, pady=30)
                notif.after(1200, notif.destroy) 
        except Exception as e:
            notif = tk.Toplevel(self.root)
            notif.title("Erreur export")
            notif.geometry(f"+{self.root.winfo_rootx() + 400}+{self.root.winfo_rooty() + 400}")
            tk.Label(notif, text=f"Erreur export : {e}", font=("Arial", 16), fg="red").pack(padx=30, pady=30)
            notif.after(2000, notif.destroy)

    @staticmethod
    def send_dxf_to_pc(filepath, pc_ip, port=5001):
        # Send the DXF file to the main PC via TCP
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((pc_ip, port))
                with open(filepath, 'rb') as f:
                    while True:
                        data = f.read(4096)
                        if not data:
                            break
                        s.sendall(data)
            return True
        except Exception as e:
            print(f"Erreur d'envoi TCP : {e}")
            return False

    # --- Control points and rotation ---
    def show_control_points(self, obj):
        # Show control points for resizing/rotating the selected object
        self.hide_control_points()
        self.control_points = []
        import math
        # Rectangle, circle, line, triangle get rotation handle
        if obj.type in ("rectangle", "circle", "line", "triangle"):
            cx, cy = self.get_object_center(obj)
            angle_rad = math.radians(getattr(obj, 'angle', 0))
            if obj.type == "rectangle" or obj.type == "circle":
                (x0, y0), (x1, y1) = obj.coords
                pts = [
                    (x0, y0), (x1, y0), (x1, y1), (x0, y1)
                ]
                rot_pts = [
                    (
                        cx + math.cos(angle_rad) * (px - cx) - math.sin(angle_rad) * (py - cy),
                        cy + math.sin(angle_rad) * (px - cx) + math.cos(angle_rad) * (py - cy)
                    ) for (px, py) in pts
                ]
                top_mid = (
                    (rot_pts[0][0] + rot_pts[1][0]) / 2,
                    (rot_pts[0][1] + rot_pts[1][1]) / 2
                )
                dx = top_mid[0] - cx
                dy = top_mid[1] - cy
                norm = math.hypot(dx, dy)
                if norm == 0:
                    norm = 1
                dx /= norm
                dy /= norm
                rot_x = top_mid[0] + (-dy) * 30
                rot_y = top_mid[1] + (dx) * 30
            elif obj.type == "line":
                (x0, y0), (x1, y1) = obj.coords
                top_mid = ((x0 + x1) / 2, (y0 + y1) / 2)
                dx = x1 - x0
                dy = y1 - y0
                norm = math.hypot(dx, dy)
                if norm == 0:
                    norm = 1
                dx /= norm
                dy /= norm
                perp_x = -dy
                perp_y = dx
                rot_x = top_mid[0] + perp_x * 30
                rot_y = top_mid[1] + perp_y * 30
            elif obj.type == "triangle":
                pts = obj.coords
                top_mid = ((pts[0][0] + pts[1][0]) / 2, (pts[0][1] + pts[1][1]) / 2)
                dx = top_mid[0] - cx
                dy = top_mid[1] - cy
                norm = math.hypot(dx, dy)
                if norm == 0:
                    norm = 1
                dx /= norm
                dy /= norm
                rot_x = top_mid[0] + (-dy) * 30
                rot_y = top_mid[1] + (dx) * 30
            elif obj.type == "text":
                (x, y) = obj.coords[0]
                rot_x = x
                rot_y = y - 30
            rot_cp = self.canvas.create_oval(rot_x-8, rot_y-8, rot_x+8, rot_y+8, fill="orange", outline="black", tags="rotation_point")
            self.canvas.tag_bind(rot_cp, '<Button-1>', lambda e: self.start_rotate_control_point(e, obj))
            self.control_points.append(rot_cp)

    def start_rotate_control_point(self, event, obj):
        # Start rotating the selected object
        self._rotating_obj = obj
        self._rotate_origin = self.get_object_center(obj)
        self._rotate_start_angle = obj.angle
        self._rotate_start_mouse = (event.x, event.y)
        self.canvas.bind('<B1-Motion>', self.rotate_control_point)
        self.canvas.bind('<ButtonRelease-1>', self.stop_rotate_control_point)

    def rotate_control_point(self, event):
        # Rotate the selected object based on mouse movement
        obj = self._rotating_obj
        ox, oy = self._rotate_origin
        x0, y0 = self._rotate_start_mouse
        a0 = math.atan2(y0 - oy, x0 - ox)
        a1 = math.atan2(event.y - oy, event.x - ox)
        delta_deg = math.degrees(a1 - a0)
        obj.angle = (self._rotate_start_angle + delta_deg) % 360
        self.redraw_object_with_rotation(obj)
        self.show_control_points(obj)

    def stop_rotate_control_point(self, event):
        # Stop rotating and restore normal bindings
        self.canvas.unbind('<B1-Motion>')
        self.canvas.unbind('<ButtonRelease-1>')
        self._rotating_obj = None
        self._rotate_origin = None
        self._rotate_start_angle = None
        self._rotate_start_mouse = None
        # Restore all event bindings after rotation
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-1>", self.on_double_click)
        self.canvas.focus_set()

    def get_object_center(self, obj):
        # Get the center point of an object
        if obj.type in ("rectangle", "circle"):
            (x0, y0), (x1, y1) = obj.coords
            return ((x0 + x1) / 2, (y0 + y1) / 2)
        elif obj.type == "line":
            (x0, y0), (x1, y1) = obj.coords
            return ((x0 + x1) / 2, (y0 + y1) / 2)
        elif obj.type == "triangle":
            pts = obj.coords
            cx = sum(p[0] for p in pts) / 3
            cy = sum(p[1] for p in pts) / 3
            return (cx, cy)
        elif obj.type == "text":
            return obj.coords[0]
        return (0, 0)

    def redraw_object_with_rotation(self, obj):
        # Redraw an object with its current rotation
        self.canvas.delete(obj.canvas_id)
        import math
        if obj.type == "rectangle":
            (x0, y0), (x1, y1) = obj.coords
            cx, cy = self.get_object_center(obj)
            pts = [
                (x0, y0), (x1, y0), (x1, y1), (x0, y1)
            ]
            angle_rad = math.radians(obj.angle)
            rot_pts = [
                (
                    cx + math.cos(angle_rad) * (px - cx) - math.sin(angle_rad) * (py - cy),
                    cy + math.sin(angle_rad) * (px - cx) + math.cos(angle_rad) * (py - cy)
                ) for (px, py) in pts
            ]
            obj.canvas_id = self.canvas.create_polygon(*sum(rot_pts, ()), outline="blue", fill="")
        elif obj.type == "circle":
            (x0, y0), (x1, y1) = obj.coords
            cx, cy = self.get_object_center(obj)
            rx = abs(x1 - x0) / 2
            ry = abs(y1 - y0) / 2
            angle = getattr(obj, 'angle', 0)
            if abs(rx - ry) < 1e-2:
                # Perfect circle: no visible rotation
                obj.canvas_id = self.canvas.create_oval(x0, y0, x1, y1, outline="blue")
            else:
                # Ellipse: draw as polygon with rotation
                points = []
                steps = 60
                for i in range(steps):
                    t = 2 * math.pi * i / steps
                    ex = cx + rx * math.cos(t)
                    ey = cy + ry * math.sin(t)
                    # Appliquer la rotation
                    angle_rad = math.radians(angle)
                    rot_x = cx + math.cos(angle_rad) * (ex - cx) - math.sin(angle_rad) * (ey - cy)
                    rot_y = cy + math.sin(angle_rad) * (ex - cx) + math.cos(angle_rad) * (ey - cy)
                    points.extend([rot_x, rot_y])
                obj.canvas_id = self.canvas.create_polygon(points, outline="blue", fill="")
        elif obj.type == "line":
            (x0, y0), (x1, y1) = obj.coords
            cx, cy = self.get_object_center(obj)
            angle = getattr(obj, 'angle', 0)
            angle_rad = math.radians(angle)
            def rotate_point(px, py):
                return (
                    cx + math.cos(angle_rad) * (px - cx) - math.sin(angle_rad) * (py - cy),
                    cy + math.sin(angle_rad) * (px - cx) + math.cos(angle_rad) * (py - cy)
                )
            rx0, ry0 = rotate_point(x0, y0)
            rx1, ry1 = rotate_point(x1, y1)
            x0_real, y0_real = self.canvas_to_real(rx0, ry0)
            x1_real, y1_real = self.canvas_to_real(rx1, ry1)
            obj.canvas_id = self.canvas.create_line(x0_real, y0_real, x1_real, y1_real, fill="blue", width=3 if hasattr(obj, 'selected') and obj.selected else 1)
        elif obj.type == "triangle":
            pts = obj.coords
            cx, cy = self.get_object_center(obj)
            angle_rad = math.radians(obj.angle)
            def rotate_point(px, py):
                return (
                    cx + math.cos(angle_rad) * (px - cx) - math.sin(angle_rad) * (py - cy),
                    cy + math.sin(angle_rad) * (px - cx) + math.cos(angle_rad) * (py - cy)
                )
            rot_pts = [rotate_point(px, py) for (px, py) in pts]
            obj.canvas_id = self.canvas.create_polygon(*sum(rot_pts, ()), outline="blue", fill="")
        elif obj.type == "text":
            (x, y) = obj.coords[0]
            size_mm = getattr(obj, 'size_mm', 5)
            font = getattr(obj, 'font', 'DejaVu Sans')
            obj.canvas_id = self.canvas.create_text(x, y, text=obj.text, font=(font, int(size_mm * 10)), anchor="nw")

    def hide_control_points(self):
        # Remove all control points from the canvas
        if hasattr(self, 'control_points'):
            for cp in self.control_points:
                self.canvas.delete(cp)
            self.control_points = []

    # --- Font size utility ---
    def mm_to_tk_font_size(self, size_mm):
        # Convert font size in mm to a suitable Tkinter font size (pixels)
        test_id = self.canvas.create_text(0, 0, text="Hg", font=("DejaVu Sans", int(size_mm * self._current_scale)), anchor="nw")
        bbox = self.canvas.bbox(test_id)
        height_px = bbox[3] - bbox[1]
        self.canvas.delete(test_id)
        # Calculate correction factor for font size
        target_height_px = size_mm * self._current_scale
        correction = target_height_px / height_px if height_px else 1
        return int(size_mm * self._current_scale * correction)

    # --- Fullscreen toggle ---
    def toggle_fullscreen(self):
        # Toggle fullscreen mode for the application
        is_fullscreen = self.root.attributes('-fullscreen')
        self.root.attributes('-fullscreen', not is_fullscreen)


if __name__ == "__main__":
    root = tk.Tk()
    app = PaintEcran(root)
    root.mainloop()


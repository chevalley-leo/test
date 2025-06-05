print("Script lancé")
import tkinter as tk
from tkinter import simpledialog, messagebox
import ezdxf

MM_TO_UNITS = 1

DRAWING_WIDTH = 100
DRAWING_HEIGHT = 40


class Drawable:
    def __init__(self, type_, coords, canvas_id, text=None):
        self.type = type_  # 'line', 'rect', 'circle', 'text', 'freehand'
        self.coords = coords
        self.canvas_id = canvas_id
        self.text = text
        self.angle = 0  # Ajout de l'angle de rotation (en degrés)


class PaintEcran:
    def __init__(self, root):
        print("Démarrage de PaintEcran.__init__")
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

        self.setup_ui()
        self.set_canvas_zone()

        self.canvas.bind("<Configure>", lambda e: self.set_canvas_zone())

    def setup_ui(self):
        sidebar = tk.Frame(self.root)
        sidebar.pack(side=tk.LEFT, fill=tk.Y)

        tk.Label(sidebar, text="Zone de dessin:").pack()
        tk.Radiobutton(sidebar, text="Rectangle", variable=self.zone_mode, value="rectangle",
                       command=self.set_canvas_zone).pack(anchor=tk.W)

        tk.Label(sidebar, text="\nOutils:").pack()
        for tool in ["freehand", "line", "rectangle", "circle", "text", "select"]:
            tk.Radiobutton(sidebar, text=tool.capitalize(), variable=self.tool_mode, value=tool).pack(anchor=tk.W)

        tk.Button(sidebar, text="Supprimer", command=self.delete_selected).pack(pady=5)
        tk.Button(sidebar, text="Exporter en DXF", command=self.export_dxf).pack(pady=20)
        tk.Button(sidebar, text="Reset (Clear)", command=self.reset_canvas).pack(pady=5)

        self.canvas = tk.Canvas(self.root, bg="white")
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-1>", self.on_double_click)
        self.root.bind("<Delete>", lambda e: self.delete_selected())

    def reset_canvas(self):
        self.canvas.delete("all")
        self.objects.clear()
        self.selected_obj = None
        self.hide_control_points()
        self.set_canvas_zone()

    def get_zone_coords(self):
        """Calcule les coordonnées (x0, y0, x1, y1) de la zone de dessin centrée et agrandie dynamiquement dans le canvas."""
        canvas_width = self.canvas.winfo_width()
        canvas_height = self.canvas.winfo_height()
        # Dimensions réelles en mm
        zone_width_mm = DRAWING_WIDTH
        zone_height_mm = DRAWING_HEIGHT
        # Calcul du facteur d'échelle maximal pour que la zone tienne dans le canvas
        scale_x = canvas_width / zone_width_mm
        scale_y = canvas_height / zone_height_mm
        scale = min(scale_x, scale_y)
        # Taille réelle en pixels
        zone_width_px = zone_width_mm * scale
        zone_height_px = zone_height_mm * scale
        x0 = (canvas_width - zone_width_px) / 2
        y0 = (canvas_height - zone_height_px) / 2
        x1 = x0 + zone_width_px
        y1 = y0 + zone_height_px
        self._current_scale = scale
        return x0, y0, x1, y1

    def set_canvas_zone(self):
        """Dessine la zone de dessin centrée dans le canvas."""
        self.canvas.delete("all")
        self.objects.clear()

        x0, y0, x1, y1 = self.get_zone_coords()

        # Toujours rectangle
        self.canvas.create_rectangle(x0, y0, x1, y1, outline="black", width=2)

    def canvas_to_real(self, x, y):
        """Convertit les coordonnées du canvas (pixels) en coordonnées réelles (millimètres)."""
        x0, y0, x1, y1 = self.get_zone_coords()
        scale = self._current_scale
        real_x = (x - x0) / scale
        real_y = (y1 - y) / scale  # Inverser l'axe Y
        return real_x, real_y

    def real_to_canvas(self, rx, ry):
        """Convertit les coordonnées réelles (mm) en coordonnées canvas (pixels)."""
        x0, y0, x1, y1 = self.get_zone_coords()
        scale = self._current_scale
        x = x0 + rx * scale
        y = y1 - ry * scale
        return x, y

    def on_click(self, event):
        tool = self.tool_mode.get()
        self.start_pos = (event.x, event.y)
        if tool == "freehand":
            self.current = [(event.x, event.y)]
            self.hide_control_points()
        elif tool == "text":
            self.hide_control_points()
            # Nouvelle boîte de dialogue modale pour le texte
            dialog = tk.Toplevel(self.root)
            dialog.title("Texte")
            dialog.transient(self.root)
            dialog.geometry(f"+{self.root.winfo_rootx() + 200}+{self.root.winfo_rooty() + 200}")

            dialog.wait_visibility()  # S'assurer que la fenêtre est visible avant grab_set
            dialog.grab_set()

            tk.Label(dialog, text="Texte :").pack()
            text_var = tk.StringVar()
            text_entry = tk.Entry(dialog, textvariable=text_var)
            text_entry.pack()

            tk.Label(dialog, text="Taille (mm) :").pack()
            size_var = tk.StringVar(value="5")
            size_entry = tk.Entry(dialog, textvariable=size_var)
            size_entry.pack()

            tk.Label(dialog, text="Police :").pack()
            font_var = tk.StringVar(value="Arial")
            font_menu = tk.OptionMenu(dialog, font_var, "Arial", "Courier", "Times")
            font_menu.pack()

            preview_id = None
            def update_preview(*_):
                nonlocal preview_id
                if preview_id:
                    self.canvas.delete(preview_id)
                try:
                    size_px = int(float(size_var.get()) * 10)
                except ValueError:
                    size_px = 50
                preview_id = self.canvas.create_text(
                    event.x, event.y, text=text_var.get(), font=(font_var.get(), size_px),
                    anchor="nw", tags="preview"
                )

            text_var.trace_add("write", update_preview)
            size_var.trace_add("write", update_preview)
            font_var.trace_add("write", update_preview)

            def confirm():
                text = text_var.get()
                try:
                    size_mm = float(size_var.get())
                    if size_mm <= 0:
                        raise ValueError
                except ValueError:
                    messagebox.showerror("Erreur", "Taille invalide.")
                    return
                size_px = int(size_mm * 10)
                font_name = font_var.get()
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
                if preview_id:
                    self.canvas.delete("preview")
                dialog.destroy()

            def cancel():
                if preview_id:
                    self.canvas.delete("preview")
                dialog.destroy()

            btn_frame = tk.Frame(dialog)
            btn_frame.pack(pady=5)
            tk.Button(btn_frame, text="OK", command=confirm).pack(side=tk.LEFT, padx=5)
            tk.Button(btn_frame, text="Annuler", command=cancel).pack(side=tk.LEFT, padx=5)

            text_entry.focus_set()
            dialog.wait_window(dialog)

        elif tool == "select":
            self.select_object(event.x, event.y)

    def on_drag(self, event):
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
            # Met à jour les coordonnées internes
            self.selected_obj.coords = [(x+dx, y+dy) for (x, y) in self.selected_obj.coords]
            self._drag_data = {'x': event.x, 'y': event.y}

    def on_release(self, event):
        tool = self.tool_mode.get()
        x0, y0 = self.start_pos if self.start_pos else (event.x, event.y)
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
        # Désélectionne tout
        for obj in self.objects:
            if obj.type in ("line", "rectangle", "circle", "triangle", "freehand"):
                self.canvas.itemconfig(obj.canvas_id, width=1, tags="")
            else:
                self.canvas.itemconfig(obj.canvas_id, tags="")
        # Zone de tolérance pour écran tactile (20x20 px autour du point)
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
        # Trouve l'objet sous le curseur
        for obj in self.objects:
            if self.canvas.find_withtag("current") and self.canvas.find_withtag("current")[0] == obj.canvas_id:
                self.edit_object(obj)
                break

    def edit_object(self, obj):
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
        size_var = tk.StringVar(value=str(getattr(obj, "size_mm", 5)))
        size_entry = tk.Entry(dialog, textvariable=size_var)
        size_entry.pack()

        tk.Label(dialog, text="Police :").pack()
        font_var = tk.StringVar(value=getattr(obj, "font", "Arial"))
        font_menu = tk.OptionMenu(dialog, font_var, "Arial", "Courier", "Times")
        font_menu.pack()

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
            canvas_id = self.canvas.create_text(
                new_x, new_y,
                text=text_var.get(),
                font=(font_var.get(), int(size_mm * 10)),
                anchor="nw"
            )
            obj.text = text_var.get()
            obj.size_mm = size_mm
            obj.font = font_var.get()
            obj.coords = [(new_x, new_y)]
            obj.canvas_id = canvas_id
            dialog.destroy()

        tk.Button(dialog, text="OK", command=confirm).pack(pady=5)
        text_entry.focus_set()
        dialog.wait_window(dialog)

    def edit_rect_or_ellipse(self, obj):
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
        # Permet de déplacer tout le tracé d'un coup
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

    def delete_selected(self):
        if self.selected_obj:
            self.canvas.delete(self.selected_obj.canvas_id)
            self.objects.remove(self.selected_obj)
            self.selected_obj = None
            self.hide_control_points()

    def export_dxf(self):
        doc = ezdxf.new(dxfversion="R2010")
        msp = doc.modelspace()

        # Offsets en millimètres
        offset_x = 100
        offset_y = 21

        import math
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
                angle_rad = math.radians(angle)
                # 4 coins avant rotation
                pts = [
                    (x0, y0), (x1, y0), (x1, y1), (x0, y1)
                ]
                # Appliquer la rotation
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
                # Conversion canvas -> réel (mm), inversion axe Y
                cx_real, cy_real = self.canvas_to_real(cx, cy)
                rx_canvas = abs(x1 - x0) / 2
                ry_canvas = abs(y1 - y0) / 2
                scale = self._current_scale
                rx = rx_canvas / scale  # en mm
                ry = ry_canvas / scale  # en mm
                angle = getattr(obj, 'angle', 0)
                if abs(rx - ry) < 1e-3:
                    # Cercle
                    msp.add_circle((cx_real + offset_x, cy_real + offset_y), rx)
                else:
                    # Ellipse avec rotation (rotation via major_axis)
                    import math
                    angle_rad = math.radians(-angle)  # Inverser l'angle pour le repère DXF
                    major_axis = (rx * math.cos(angle_rad), rx * math.sin(angle_rad))
                    ratio = ry / rx if rx != 0 else 1
                    msp.add_ellipse(
                        center=(cx_real + offset_x, cy_real + offset_y),
                        major_axis=major_axis,
                        ratio=ratio
                    )
            elif obj.type == "triangle":
                pts = [(x + offset_x, y + offset_y) for x, y in [self.canvas_to_real(px, py) for px, py in obj.coords]]
                msp.add_lwpolyline(pts, close=True)
            elif obj.type == "text":
                x, y = self.canvas_to_real(*obj.coords[0])
                height = getattr(obj, "size_mm", 5)  # hauteur texte en mm, défaut 5
                msp.add_text(obj.text, dxfattribs={"height": height, "insert": (x + offset_x, y + offset_y)})

        try:
            doc.saveas("dxf3.dxf")
            messagebox.showinfo("Export", "Fichier 'dxf3.dxf' exporté avec succès.")
        except Exception as e:
            messagebox.showerror("Erreur export", str(e))

    # Ajout: gestion des points de contrôle pour modification tactile
    def show_control_points(self, obj):
        self.hide_control_points()
        self.control_points = []
        import math
        if obj.type in ("rectangle", "circle", "line", "triangle", "text"):
            cx, cy = self.get_object_center(obj)
            angle_rad = math.radians(getattr(obj, 'angle', 0))
            # Poignée de rotation (au-dessus du centre supérieur, après rotation)
            if obj.type == "rectangle" or obj.type == "circle":
                (x0, y0), (x1, y1) = obj.coords
                # Coins du rectangle avant rotation
                pts = [
                    (x0, y0), (x1, y0), (x1, y1), (x0, y1)
                ]
                # Appliquer la rotation aux coins
                rot_pts = [
                    (
                        cx + math.cos(angle_rad) * (px - cx) - math.sin(angle_rad) * (py - cy),
                        cy + math.sin(angle_rad) * (px - cx) + math.cos(angle_rad) * (py - cy)
                    ) for (px, py) in pts
                ]
                # Poignée de rotation (au-dessus du centre supérieur, après rotation)
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
                # Milieu de la ligne
                top_mid = ((x0 + x1) / 2, (y0 + y1) / 2)
                # Décalage vertical (30 px dans la direction perpendiculaire à la ligne)
                dx = x1 - x0
                dy = y1 - y0
                norm = math.hypot(dx, dy)
                if norm == 0:
                    norm = 1
                dx /= norm
                dy /= norm
                # Perpendiculaire
                perp_x = -dy
                perp_y = dx
                rot_x = top_mid[0] + perp_x * 30
                rot_y = top_mid[1] + perp_y * 30
            elif obj.type == "triangle":
                pts = obj.coords
                # Milieu du segment [0]-[1]
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
        self._rotating_obj = obj
        self._rotate_origin = self.get_object_center(obj)
        self._rotate_start_angle = obj.angle
        self._rotate_start_mouse = (event.x, event.y)
        self.canvas.bind('<B1-Motion>', self.rotate_control_point)
        self.canvas.bind('<ButtonRelease-1>', self.stop_rotate_control_point)

    def rotate_control_point(self, event):
        obj = self._rotating_obj
        ox, oy = self._rotate_origin
        x0, y0 = self._rotate_start_mouse
        # Angle initial
        import math
        a0 = math.atan2(y0 - oy, x0 - ox)
        a1 = math.atan2(event.y - oy, event.x - ox)
        delta_deg = math.degrees(a1 - a0)
        obj.angle = (self._rotate_start_angle + delta_deg) % 360
        self.redraw_object_with_rotation(obj)
        self.show_control_points(obj)

    def stop_rotate_control_point(self, event):
        self.canvas.unbind('<B1-Motion>')
        self.canvas.unbind('<ButtonRelease-1>')
        self._rotating_obj = None
        self._rotate_origin = None
        self._rotate_start_angle = None
        self._rotate_start_mouse = None
        # Correction : on réactive tous les bindings pour permettre de dessiner n'importe quel objet
        self.canvas.bind("<Button-1>", self.on_click)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-1>", self.on_double_click)
        self.canvas.focus_set()

    def get_object_center(self, obj):
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
                # Cercle parfait : pas de rotation visuelle
                obj.canvas_id = self.canvas.create_oval(x0, y0, x1, y1, outline="blue")
            else:
                # Ellipse : dessiner comme un polygone approché avec rotation
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
            angle = getattr(obj, 'angle', 0)
            size_mm = getattr(obj, 'size_mm', 5)
            font = getattr(obj, 'font', 'Arial')
            # Pour la rotation visuelle du texte, Tkinter ne supporte pas l'angle nativement sauf sur Windows (depuis 8.6)
            # On simule la rotation en créant le texte avec l'option angle si dispo, sinon on ignore visuellement
            try:
                obj.canvas_id = self.canvas.create_text(x, y, text=obj.text, font=(font, int(size_mm * 10)), anchor="nw", angle=angle)
            except:
                obj.canvas_id = self.canvas.create_text(x, y, text=obj.text, font=(font, int(size_mm * 10)), anchor="nw")

    def hide_control_points(self):
        if hasattr(self, 'control_points'):
            for cp in self.control_points:
                self.canvas.delete(cp)
            self.control_points = []

    def start_drag_control_point(self, event, obj, idx):
        pass  # Désactivé : plus de redimensionnement

    def drag_control_point(self, event):
        pass  # Désactivé : plus de redimensionnement

    def stop_drag_control_point(self, event):
        pass  # Désactivé : plus de redimensionnement


if __name__ == "__main__":
    root = tk.Tk()
    app = PaintEcran(root)
    root.mainloop()

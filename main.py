# -*- coding: utf-8 -*-
"""
Smart Renovation — Aesthetic teal + programmatic gradient background
Full main.py (drop-in replacement). Includes Worker Log feature:
 - Worker can add daily log: name, completed work, next day plan, attach photo
 - Work logs saved to SQLite (work_logs) and appended to data/work_logs.csv
 - History screen shows work logs along with visits and saved estimates
"""
import os
import json
import sqlite3
import csv
import shutil
import time
from datetime import datetime

# Optional ML loaders
try:
    import joblib
except Exception:
    joblib = None

# Pillow (optional but recommended)
try:
    from PIL import Image as PILImage, ImageDraw, ImageFont
except Exception:
    PILImage = None
    ImageDraw = None
    ImageFont = None

# Kivy imports
from kivy.core.window import Window
from kivy.lang import Builder
from kivy.app import App
from kivy.properties import StringProperty
from kivy.uix.popup import Popup
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.screenmanager import Screen
from kivy.animation import Animation
from kivy.uix.scatter import Scatter
from kivy.graphics import Color, RoundedRectangle, Rectangle

# Desktop preview
Window.size = (400, 800)

# Paths & files
DB_DIR = "db"
DB_FILE = os.path.join(DB_DIR, "app_data.db")
PROVIDERS_FILE = os.path.join("data", "providers.json")
ASSETS_DIR = "assets"
MODEL_PATH = os.path.join("models", "model.joblib")
MATERIAL_MODEL_PATH = os.path.join("models", "material_model.joblib")
RECORDS_CSV = os.path.join("data", "records.csv")
UPLOADS_DIR = os.path.join(ASSETS_DIR, "uploads")
PROV_AVATARS_DIR = os.path.join(ASSETS_DIR, "providers")
WORKLOGS_CSV = os.path.join("data", "work_logs.csv")

# Ensure directories
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs("data", exist_ok=True)
os.makedirs(DB_DIR, exist_ok=True)
os.makedirs("models", exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(PROV_AVATARS_DIR, exist_ok=True)

# Estimator fallbacks if estimator.py missing
try:
    from estimator import paint_estimate, tiles_estimate, plumbing_estimate, generic_labour
except Exception:
    def paint_estimate(area, coverage=10.0, coats=2, wastage=0.1, price_per_litre=250.0):
        if area <= 0:
            return 0.0, 0.0
        litres = (area / coverage) * coats * (1 + wastage)
        return round(litres, 2), round(litres * price_per_litre, 2)

    def tiles_estimate(area, wastage=0.05, rate_per_m2=600.0):
        if area <= 0:
            return 0.0, 0.0
        qty = area * (1 + wastage)
        return round(qty, 2), round(qty * rate_per_m2, 2)

    def plumbing_estimate(points=1, base=500.0, per_point=300.0):
        if points <= 0:
            return 0.0
        return round(base + points * per_point, 2)

    def generic_labour(area, labour_rate_per_m2=30.0):
        if area <= 0:
            return 0.0
        return round(area * labour_rate_per_m2, 2)

# ---------------- Gradient helper (create assets/bg_home.png) ----------------
def ensure_home_gradient(path=os.path.join(ASSETS_DIR, "bg_home.png"),
                         size=(720, 1280),
                         top_color=(30, 200, 190),   # light teal RGB
                         bottom_color=(12, 20, 40)): # dark navy RGB
    """
    Create vertical gradient PNG at path if it does not exist. Returns path.
    Uses Pillow if available; otherwise returns path (no crash).
    """
    try:
        if os.path.exists(path):
            return path
        if PILImage is None or ImageDraw is None:
            return path
        W, H = size
        img = PILImage.new("RGB", (W, H), bottom_color)
        draw = ImageDraw.Draw(img)
        top_r, top_g, top_b = top_color
        bot_r, bot_g, bot_b = bottom_color
        for y in range(H):
            t = y / float(H - 1)
            r = int(top_r * (1 - t) + bot_r * t)
            g = int(top_g * (1 - t) + bot_g * t)
            b = int(top_b * (1 - t) + bot_b * t)
            draw.line([(0, y), (W, y)], fill=(r, g, b))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img.save(path, format="PNG", optimize=True)
        return path
    except Exception as e:
        print("Gradient creation failed:", e)
        return path
# ------------------------------------------------------------------------------

# KV UI
KV = r'''
#:import dp kivy.metrics.dp

<HeaderBar@BoxLayout>:
    size_hint_y: None
    height: dp(60)
    padding: dp(10)
    spacing: dp(10)
    canvas.before:
        Color:
            rgba: (0.06, 0.06, 0.07, 1)
        Rectangle:
            pos: self.pos
            size: self.size
    Image:
        source: app.logo_path if app.logo_path else ''
        size_hint_x: None
        width: dp(36)
    Label:
        text: 'Smart Renovation'
        color: (1,1,1,1)
        bold: True
        font_size: '18sp'
        halign: 'left'
        valign: 'middle'
        text_size: self.size

<AccentButton@Button>:
    background_normal: ''
    background_color: app.aesthetic_teal
    color: (1,1,1,1)
    canvas.before:
        Color:
            rgba: app.aesthetic_teal
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [12]

<GhostBtn@Button>:
    background_normal: ''
    background_color: (0,0,0,0)
    color: (1,1,1,1)
    canvas.before:
        Color:
            rgba: (0.22, 0.08, 0.10, 0.6)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [12]

<GlassCard@BoxLayout>:
    size_hint_y: None
    height: dp(120)
    padding: dp(12)
    spacing: dp(10)
    canvas.before:
        Color:
            rgba: (0.12,0.12,0.14,0.8)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [16]

<DarkCard@BoxLayout>:
    size_hint_y: None
    height: dp(96)
    padding: dp(10)
    spacing: dp(8)
    canvas.before:
        Color:
            rgba: (0.12, 0.12, 0.14, 1)
        RoundedRectangle:
            pos: self.pos
            size: self.size
            radius: [14]

ScreenManager:
    SplashScreen:
    HomeScreen:
    ServiceScreen:
    QuoteScreen:
    ProvidersScreen:
    HistoryScreen:
    FileChooserPopup:

<SplashScreen@Screen>:
    name: 'splash'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: (0,0,0,1)
            Rectangle:
                pos: self.pos
                size: self.size
        Widget:
        BoxLayout:
            orientation: 'vertical'
            size_hint_y: None
            height: dp(260)
            spacing: dp(10)
            Image:
                id: splash_logo
                source: app.logo_path if app.logo_path else ''
                size_hint: None, None
                size: dp(140), dp(140)
                opacity: 0
            Label:
                id: splash_title
                text: 'Smart Renovation'
                color: (1,1,1,1)
                font_size: '22sp'
                opacity: 0
        Widget:

<HomeScreen@Screen>:
    name: 'home'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: 1,1,1,1
            Rectangle:
                pos: self.pos
                size: self.size
                source: app.home_bg if app.home_bg else ''
            Color:
                rgba: (0,0,0,0.45)
            Rectangle:
                pos: self.pos
                size: self.size
        HeaderBar:
        BoxLayout:
            size_hint_y: None
            height: dp(170)
            padding: dp(12)
            spacing: dp(12)
            Widget:
                size_hint_x: None
                width: dp(6)
            BoxLayout:
                id: hero_card
                orientation: 'vertical'
                padding: dp(14)
                spacing: dp(6)
                canvas.before:
                    Color:
                        rgba: (0.12,0.12,0.14,0.85)
                    RoundedRectangle:
                        pos: self.pos
                        size: self.size
                        radius: [18]
                BoxLayout:
                    orientation: 'horizontal'
                    spacing: dp(8)
                    Image:
                        source: app.logo_path if app.logo_path else ''
                        size_hint_x: None
                        width: dp(64)
                    BoxLayout:
                        orientation: 'vertical'
                        Label:
                            text: "[b]Smart Renovation[/b]"
                            markup: True
                            color: (1,1,1,1)
                            font_size: '20sp'
                            halign: 'left'
                            valign: 'middle'
                            text_size: self.size
                        Label:
                            text: "Transparent quotes · Verified providers · Site visits"
                            color: (0.9,0.9,0.95,1)
                            font_size: '12sp'
                            halign: 'left'
                            valign: 'top'
                            text_size: self.size
                BoxLayout:
                    size_hint_x: None
                    width: dp(6)
            Widget:
                size_hint_x: None
                width: dp(6)

        BoxLayout:
            padding: dp(12)
            spacing: dp(10)
            size_hint_y: None
            height: dp(64)
            canvas.before:
                Color:
                    rgba: (0.10,0.10,0.12,0.7)
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [14]
            AccentButton:
                id: btn_maint
                text: 'Maintenance'
                on_release: app.change_screen('service')
            GhostBtn:
                text: 'Renovation'
                on_release: app.change_screen('service')

        BoxLayout:
            padding: dp(12)
            spacing: dp(10)
            size_hint_y: None
            height: dp(64)
            canvas.before:
                Color:
                    rgba: (0.10,0.10,0.12,0.7)
                RoundedRectangle:
                    pos: self.pos
                    size: self.size
                    radius: [14]
            GhostBtn:
                text: 'Providers'
                on_release: app.change_screen('providers')
            GhostBtn:
                text: 'History'
                on_release: app.change_screen('history')

        BoxLayout:
            padding: dp(12)
            size_hint_y: None
            height: dp(48)
            Label:
                text: "Tip: attach a site photo & schedule a visit for accurate quotes."
                color: (0.9,0.9,0.95,1)
                font_size: '12sp'

        Widget:

<ServiceScreen@Screen>:
    name: 'service'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: (0.03,0.03,0.04,1)
            Rectangle:
                pos: self.pos
                size: self.size
        HeaderBar:
        BoxLayout:
            orientation: 'vertical'
            padding: dp(12)
            spacing: dp(8)
            Label:
                text: 'Request Service'
                color: (1,1,1,1)
                size_hint_y: None
                height: dp(30)
                font_size: '16sp'
            Spinner:
                id: svc_spinner
                text: 'Select Service'
                values: ['Painting','Plumbing','Tiles','Carpentry','AC Service','Renovation','Electrical']
                size_hint_y: None
                height: dp(44)
                background_color: (0.16,0.16,0.18,1)
                color: (1,1,1,1)
            TextInput:
                id: area_txt
                hint_text: 'Area (m²) — painting/tiles/renovation'
                input_filter: 'float'
                size_hint_y: None
                height: dp(44)
                background_color: (0.10,0.10,0.12,1)
                foreground_color: (1,1,1,1)
                hint_text_color: (0.7,0.7,0.75,1)
            TextInput:
                id: points_txt
                hint_text: 'Number of points (plumbing)'
                input_filter: 'int'
                size_hint_y: None
                height: dp(44)
                background_color: (0.10,0.10,0.12,1)
                foreground_color: (1,1,1,1)
                hint_text_color: (0.7,0.7,0.75,1)
            BoxLayout:
                size_hint_y: None
                height: dp(48)
                spacing: dp(8)
                GhostBtn:
                    text: 'Attach Photo'
                    on_release: app.open_filechooser()
                AccentButton:
                    text: 'Generate Estimate'
                    on_release: app.generate_estimate()
            BoxLayout:
                size_hint_y: None
                height: dp(48)
                spacing: dp(8)
                GhostBtn:
                    text: 'Schedule Site Visit'
                    on_release: app.open_site_visit_popup()
                GhostBtn:
                    text: 'Subscribe AMC'
                    on_release: app.open_amc_popup()
            BoxLayout:
                size_hint_y: None
                height: dp(48)
                spacing: dp(8)
                GhostBtn:
                    text: 'Worker Log'
                    on_release: app.open_work_log_popup()
                GhostBtn:
                    text: 'Clear'
                    on_release:
                        svc_spinner.text = 'Select Service'
                        area_txt.text = ''
                        points_txt.text = ''
                        app.current_image = ''

<QuoteScreen@Screen>:
    name: 'quote'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(12)
        canvas.before:
            Color:
                rgba: (0.03,0.03,0.04,1)
            Rectangle:
                pos: self.pos
                size: self.size
        HeaderBar:
        Label:
            id: est_label
            text: 'Quotation'
            color: (1,1,1,1)
            font_size: '18sp'
            size_hint_y: None
            height: dp(36)
        BoxLayout:
            spacing: dp(10)
            padding: dp(6)
            DarkCard:
                orientation: 'vertical'
                Label:
                    id: breakdown_label
                    text: ''
                    markup: True
                    color: (0.95,0.95,0.98,1)
                    text_size: (self.width, None)
                    halign: 'left'
                    valign: 'top'
            DarkCard:
                orientation: 'vertical'
                size_hint_x: .52
                Label:
                    text: 'Photo'
                    color: (0.8,0.8,0.85,1)
                    size_hint_y: None
                    height: dp(22)
                Image:
                    id: quote_image
                    source: ''
                    allow_stretch: True
                    keep_ratio: True
                GhostBtn:
                    text: 'View Full Image'
                    size_hint_y: None
                    height: dp(36)
                    on_release: app.open_full_image(app.current_image if app.current_image else self.source)
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(10)
            AccentButton:
                text: 'Save to History'
                on_release: app.save_estimate()
            GhostBtn:
                text: 'Back'
                on_release: app.change_screen('service')

<ProvidersScreen@Screen>:
    name: 'providers'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: (0.03,0.03,0.04,1)
            Rectangle:
                pos: self.pos
                size: self.size
        HeaderBar:
        BoxLayout:
            padding: dp(8)
            spacing: dp(8)
            size_hint_y: None
            height: dp(50)
            TextInput:
                id: prov_search
                hint_text: 'Search providers by name or service'
                multiline: False
                on_text: app.filter_providers(self.text)
            Spinner:
                id: prov_filter
                text: 'All'
                values: ['All','Painting','Plumbing','Tiles','Carpentry','AC Service','Renovation','Electrical']
                size_hint_x: None
                width: dp(120)
                on_text: app.filter_providers(prov_search.text, self.text)
        ScrollView:
            GridLayout:
                id: prov_grid
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(10)
                padding: dp(8)
        BoxLayout:
            size_hint_y: None
            height: dp(46)
            GhostBtn:
                text: 'Back'
                on_release: app.change_screen('home')

<HistoryScreen@Screen>:
    name: 'history'
    BoxLayout:
        orientation: 'vertical'
        canvas.before:
            Color:
                rgba: (0.03,0.03,0.04,1)
            Rectangle:
                pos: self.pos
                size: self.size
        HeaderBar:
        ScrollView:
            GridLayout:
                id: hist_grid
                cols: 1
                size_hint_y: None
                height: self.minimum_height
                spacing: dp(10)
                padding: dp(8)
        BoxLayout:
            size_hint_y: None
            height: dp(46)
            GhostBtn:
                text: 'Back'
                on_release: app.change_screen('home')

<FileChooserPopup@Screen>:
    name: 'filechooser_popup'
    BoxLayout:
        orientation: 'vertical'
        padding: dp(8)
        spacing: dp(8)
        Label:
            text: 'Select an image file (PNG, JPG)'
            size_hint_y: None
            height: dp(28)
            color: (1,1,1,1)
        BoxLayout:
            spacing: dp(8)
            FileChooserListView:
                id: filechooser
                filters: ['*.png', '*.jpg', '*.jpeg']
                path: '.'
                on_selection: app.preview_selected(self.selection)
            BoxLayout:
                orientation: 'vertical'
                size_hint_x: None
                width: dp(180)
                spacing: dp(6)
                Label:
                    text: 'Preview'
                    size_hint_y: None
                    height: dp(24)
                    color: (0.9,0.9,0.95,1)
                Image:
                    id: file_preview
                    source: ''
                    allow_stretch: True
                    keep_ratio: True
        BoxLayout:
            size_hint_y: None
            height: dp(48)
            spacing: dp(8)
            GhostBtn:
                text: 'Cancel'
                on_release: app.close_filechooser()
            AccentButton:
                text: 'Select'
                on_release: app.select_file()
'''

# Screen classes referenced by KV
class SplashScreen(Screen): pass
class HomeScreen(Screen): pass
class ServiceScreen(Screen): pass
class QuoteScreen(Screen): pass
class ProvidersScreen(Screen): pass
class HistoryScreen(Screen): pass
class FileChooserPopup(Screen): pass

class SmartApp(App):
    aesthetic_teal = (0.11, 0.63, 0.74, 1)
    current_image = StringProperty('')
    logo_path = StringProperty('')
    home_bg = StringProperty('')
    ml_model = None
    mat_model = None

    SERVICE_COLORS_KIVY = {
        'Painting':  (0.27, 0.52, 0.95, 1),
        'Plumbing':  (0.00, 0.67, 0.67, 1),
        'Tiles':     (0.60, 0.40, 0.80, 1),
        'Carpentry': (0.85, 0.55, 0.20, 1),
        'AC Service':(0.15, 0.65, 0.95, 1),
        'Renovation':(0.10, 0.70, 0.35, 1),
        'Electrical':(1.00, 0.70, 0.00, 1),
    }
    SERVICE_COLORS_PIL = {
        'Painting':  (69, 133, 242, 255),
        'Plumbing':  (0, 171, 171, 255),
        'Tiles':     (153, 102, 204, 255),
        'Carpentry': (217, 140, 51, 255),
        'AC Service':(38, 166, 242, 255),
        'Renovation':(26, 179, 89, 255),
        'Electrical':(255, 179, 0, 255),
    }

    def build(self):
        maybe_logo = os.path.join(ASSETS_DIR, "logo.png")
        if os.path.exists(maybe_logo):
            self.logo_path = maybe_logo
        # create gradient background (if possible) and set it
        try:
            self.home_bg = ensure_home_gradient()
        except Exception as e:
            print("Gradient helper error:", e)
            self.home_bg = ''
        # try to load models
        self.ml_model = self.load_model(MODEL_PATH, name="cost model")
        self.mat_model = self.load_model(MATERIAL_MODEL_PATH, name="material model (optional)")
        # seed providers if missing
        if not os.path.exists(PROVIDERS_FILE):
            sample = [
                {"id":1,"name":"Amit Electricals","service":"Electrical","rating":4.6,"phone":"9000000001","avg_charge":800},
                {"id":2,"name":"Ravi Painters","service":"Painting","rating":4.4,"phone":"9000000002","avg_charge":2500},
                {"id":3,"name":"Soni Plumbers","service":"Plumbing","rating":4.5,"phone":"9000000003","avg_charge":1200},
                {"id":4,"name":"Dream Carpentry","service":"Carpentry","rating":4.3,"phone":"9000000004","avg_charge":2000},
                {"id":5,"name":"Cool AC Services","service":"AC Service","rating":4.7,"phone":"9000000005","avg_charge":900},
                {"id":6,"name":"Modish Renovators","service":"Renovation","rating":4.2,"phone":"9000000006","avg_charge":15000}
            ]
            with open(PROVIDERS_FILE, 'w', encoding='utf-8') as f:
                json.dump(sample, f, indent=2)
        root = Builder.load_string(KV)
        self.animate_splash(root)
        # optional smoke tests
        if self.ml_model is not None:
            try:
                import pandas as _pd
                _row = _pd.DataFrame([{'service':'Painting','area':50,'points':0,'image':0}])
                _pred = float(self.ml_model.predict(_row)[0])
                print("Cost model ok → Painting(50 m²): ₹", round(_pred,2))
            except Exception as e:
                print("Cost model smoke failed:", e)
        if self.mat_model is not None:
            print("Material model loaded and ready.")
        return root

    def animate_splash(self, root):
        try:
            scr = root.get_screen('splash')
            logo = scr.ids.splash_logo
            title = scr.ids.splash_title
        except Exception:
            return
        Animation(opacity=1, d=0.35, t='out_quad').start(logo)
        Animation(size=(logo.width * 1.15, logo.height * 1.15), d=0.45, t='out_back').start(logo)
        Animation(opacity=1, d=0.45, t='out_quad').start(title)
        def go_home(*_):
            self.change_screen('home')
        anim = Animation(d=1.1)
        anim.bind(on_complete=lambda *_: go_home())
        anim.start(logo)

    def load_model(self, path, name="model"):
        if joblib is None:
            print(f"joblib not available — {name} disabled.")
            return None
        if not os.path.exists(path):
            print(f"No {name} found at {path}.")
            return None
        try:
            m = joblib.load(path)
            print(f"{name.capitalize()} loaded from {path}")
            return m
        except Exception as e:
            print(f"Failed to load {name}:", e)
            return None

    def change_screen(self, name):
        try:
            self.root.current = name
            if name == 'providers':
                self.load_providers()
            if name == 'history':
                self.load_history()
        except Exception as e:
            print("Change screen error:", e)

    def open_filechooser(self):
        try:
            fc = self.root.get_screen('filechooser_popup')
            from pathlib import Path
            pics = str(Path.home() / "Pictures")
            fc.ids.filechooser.path = pics if os.path.exists(pics) else os.getcwd()
            fc.ids.file_preview.source = ''
            self.change_screen('filechooser_popup')
        except Exception as e:
            print("Open filechooser error:", e)

    def close_filechooser(self):
        self.change_screen('service')

    def preview_selected(self, selection):
        try:
            fc = self.root.get_screen('filechooser_popup')
            if selection and len(selection) > 0 and os.path.exists(selection[0]):
                fc.ids.file_preview.source = selection[0]
            else:
                fc.ids.file_preview.source = ''
        except Exception as e:
            print("Preview error:", e)

    def select_file(self):
        fc = self.root.get_screen('filechooser_popup')
        sel = getattr(fc.ids.filechooser, 'selection', [])
        if not sel:
            self.show_popup("No file", "Please click a JPG/PNG, then press Select.")
            return
        chosen = sel[0]
        if not os.path.exists(chosen):
            self.show_popup("File missing", "That file path doesn’t exist. Try another image.")
            return
        basename = os.path.basename(chosen)
        dest = os.path.join(UPLOADS_DIR, f"{int(time.time())}_{basename}")
        try:
            shutil.copy(chosen, dest)
            self.current_image = dest
            print("Copied image to:", dest)
        except Exception as e:
            print("Copy failed, using original:", e)
            self.current_image = chosen
        try:
            self.root.get_screen('quote').ids.quote_image.source = self.current_image
        except Exception:
            pass
        self.change_screen('service')

    def generate_estimate(self):
        svc_widget = self.root.get_screen('service').ids.svc_spinner
        svc = svc_widget.text
        if not svc or svc == 'Select Service':
            svc = 'Painting'
            svc_widget.text = 'Painting'
        area_text = self.root.get_screen('service').ids.area_txt.text.strip()
        points_text = self.root.get_screen('service').ids.points_txt.text.strip()
        try:
            area = float(area_text) if area_text else 0.0
        except:
            area = 0.0
        try:
            points = int(points_text) if points_text else 0
        except:
            points = 0
        breakdown = []
        total = 0.0
        s = (svc or '').lower()
        material_qty = {}

        if 'paint' in s:
            litres, mat_cost = paint_estimate(area)
            labour = generic_labour(area)
            total = mat_cost + labour
            breakdown.append("[b]Painting[/b]")
            breakdown.append(f"• Material: {litres} L paint  → ₹{mat_cost:.2f}")
            breakdown.append(f"• Labour:  ₹{labour:.2f}")
            material_qty['paint_litres'] = litres
        elif 'tile' in s:
            qty_m2, mat_cost = tiles_estimate(area)
            labour = generic_labour(area, labour_rate_per_m2=50)
            total = mat_cost + labour
            breakdown.append("[b]Tiling[/b]")
            breakdown.append(f"• Material: {qty_m2} m² tiles (incl. wastage) → ₹{mat_cost:.2f}")
            breakdown.append(f"• Labour:  ₹{labour:.2f}")
            material_qty['tiles_m2'] = qty_m2
        elif 'plumb' in s:
            pl_cost = plumbing_estimate(points if points > 0 else 1)
            total = pl_cost
            breakdown.append("[b]Plumbing[/b]")
            breakdown.append(f"• Points: {max(points,1)}")
            breakdown.append(f"• Total:  ₹{pl_cost:.2f}")
            material_qty['plumbing_points'] = max(points,1)
        else:
            labour = generic_labour(area, labour_rate_per_m2=80)
            material = area * 150
            total = labour + material
            breakdown.append(f"[b]{svc}[/b]")
            breakdown.append(f"• Material est: ₹{material:.2f}")
            breakdown.append(f"• Labour:       ₹{labour:.2f}")
            material_qty['generic_area'] = area

        self.last_estimate = {
            'service': svc,
            'area': area,
            'points': points,
            'total': round(total,2),
            'breakdown': breakdown,
            'time': datetime.now().isoformat(),
            'image': self.current_image or ''
        }

        ml_text = ""
        if self.ml_model is not None:
            try:
                import pandas as _pd
                row = _pd.DataFrame([{
                    'service': svc,
                    'area': area,
                    'points': points,
                    'image': 1 if (self.current_image and len(self.current_image) > 0) else 0
                }])
                pred = float(self.ml_model.predict(row)[0])
                ml_text = f"\nML predicted total: ₹{pred:.2f}"
            except Exception as e:
                print("ML predict error:", e)

        mat_text = ""
        if self.mat_model is not None:
            try:
                import pandas as _pd
                row = _pd.DataFrame([{
                    'service': svc,
                    'area': area,
                    'points': points,
                    'image': 1 if (self.current_image and len(self.current_image) > 0) else 0
                }])
                mat_pred = self.mat_model.predict(row)
                mat_val = mat_pred[0] if hasattr(mat_pred, '__iter__') else mat_pred
                mat_text = f"\nML material suggestion: {mat_val}"
            except Exception as e:
                print("Material model predict failed:", e)
                mat_text = ""

        if not mat_text:
            if 'paint' in s:
                litres = material_qty.get('paint_litres', 0.0)
                if litres <= 0:
                    mat_text = "\nMaterial suggestion: No paint required for 0 area."
                else:
                    needed = litres
                    cans = {}
                    for size in (10.0, 4.0, 1.0):
                        cnt = int(needed // size)
                        if cnt > 0:
                            cans[f"{int(size)}L"] = cnt
                            needed = round(needed - cnt * size, 2)
                    if needed > 0:
                        cans["1L"] = cans.get("1L", 0) + 1
                    parts = ", ".join([f"{v}×{k}" for k,v in cans.items()]) if cans else f"{litres} L"
                    mat_text = f"\nPurchase suggestion (paint): {parts}  (approx. {litres} L required)"
            elif 'tile' in s:
                sqm = material_qty.get('tiles_m2', 0.0)
                if sqm <= 0:
                    mat_text = "\nMaterial suggestion: No tiles required for 0 area."
                else:
                    box_cover = 1.2
                    boxes = int(sqm // box_cover)
                    if sqm % box_cover > 0:
                        boxes += 1
                    mat_text = f"\nPurchase suggestion (tiles): {boxes} boxes (covering ~{round(boxes*box_cover,2)} m²) for required {sqm} m²"
            elif 'plumb' in s:
                pts = material_qty.get('plumbing_points', 1)
                mat_text = f"\nPurchase suggestion (plumbing): Basic parts for {pts} connection point(s)."
            else:
                area_generic = material_qty.get('generic_area', 0)
                mat_text = f"\nMaterial suggestion: Approx. material for {area_generic} m² (use local supplier rates)."

        try:
            q = self.root.get_screen('quote')
            q.ids.breakdown_label.text = '\n'.join(breakdown) + "\n" + mat_text
            q.ids.quote_image.source = self.current_image or ''
            q.ids.est_label.text = f"Estimated total: ₹{total:.2f}{ml_text}"
        except Exception as e:
            print("Quote update error:", e)

        self.change_screen('quote')

    def save_estimate(self):
        if not getattr(self, 'last_estimate', None):
            self.show_popup("No estimate", "Please generate an estimate first.")
            return
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS requests
                     (id INTEGER PRIMARY KEY AUTOINCREMENT,
                      service TEXT, details TEXT, cost REAL, created_at TEXT, image TEXT)''')
        det = '\n'.join(self.last_estimate['breakdown'])
        c.execute('INSERT INTO requests (service, details, cost, created_at, image) VALUES (?,?,?,?,?)',
                  (self.last_estimate['service'], det, self.last_estimate['total'],
                   self.last_estimate['time'], self.last_estimate.get('image', '')))
        conn.commit(); conn.close()
        try:
            write_header = not os.path.exists(RECORDS_CSV)
            with open(RECORDS_CSV, 'a', newline='', encoding='utf-8') as f:
                w = csv.writer(f)
                if write_header:
                    w.writerow(['time', 'service', 'area', 'points', 'image', 'total'])
                w.writerow([self.last_estimate['time'], self.last_estimate['service'],
                            self.last_estimate['area'], self.last_estimate['points'],
                            1 if self.last_estimate.get('image') else 0, self.last_estimate['total']])
        except Exception as e:
            print("CSV append failed:", e)
        self.show_popup("Saved", "Estimate saved to history.")
        self.current_image = ''
        self.change_screen('history')

    def get_provider_avatar(self, name, pid, service=''):
        svc_key = service if service in self.SERVICE_COLORS_PIL else 'Painting'
        out_path = os.path.join(PROV_AVATARS_DIR, f"{pid}_{svc_key}.png")
        if os.path.exists(out_path):
            return out_path
        if PILImage is None:
            default = os.path.join(ASSETS_DIR, "provider_icon.png")
            return default if os.path.exists(default) else ''
        W, H = 64, 64
        img = PILImage.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        color = self.SERVICE_COLORS_PIL.get(svc_key, (80,80,80,255))
        draw.ellipse((0, 0, W, H), fill=color)
        initial = (name.strip()[:1] or "P").upper()
        font = None
        try:
            for fp in ["C:\\Windows\\Fonts\\seguisb.ttf","C:\\Windows\\Fonts\\arialbd.ttf"]:
                if os.path.exists(fp):
                    font = ImageFont.truetype(fp, 34); break
        except Exception:
            font = None
        if font is None:
            font = ImageFont.load_default()
        try:
            bbox = draw.textbbox((0, 0), initial, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except Exception:
            tw, th = 22, 22
        tx, ty = (W - tw) // 2, (H - th) // 2 - 2
        draw.text((tx, ty), initial, font=font, fill=(255,255,255,255))
        img.save(out_path, "PNG")
        return out_path

    def open_provider_details(self, provider: dict):
        name = provider.get('name','Provider'); service = provider.get('service','Service')
        rating = provider.get('rating',4.0); phone = provider.get('phone','N/A')
        root = BoxLayout(orientation='vertical', padding=12, spacing=10)
        header = BoxLayout(orientation='horizontal', size_hint_y=None, height=90, padding=8, spacing=8)
        color = self.SERVICE_COLORS_KIVY.get(service, (0.2,0.2,0.2,1))
        with header.canvas.before:
            Color(*color); bg = RoundedRectangle(radius=[14], pos=header.pos, size=header.size)
        header.bind(pos=lambda *_: setattr(bg,'pos',header.pos), size=lambda *_: setattr(bg,'size',header.size))
        avatar_path = self.get_provider_avatar(name, provider.get('id',''), service)
        header.add_widget(Image(source=avatar_path, size_hint_x=None, width=64))
        info = Label(text=f"[b]{name}[/b]\n{service}  •  ⭐{rating}", markup=True, halign='left', valign='middle', color=(1,1,1,1))
        info.text_size = (240, None); header.add_widget(info)
        root.add_widget(header)
        bar = BoxLayout(size_hint_y=None, height=46, spacing=8)
        btn_call = Button(text='Call', background_normal='', background_color=self.aesthetic_teal, color=(1,1,1,1))
        btn_copy = Button(text='Copy Phone', background_normal='', background_color=(0.2,0.2,0.2,1), color=(1,1,1,1))
        bar.add_widget(btn_call); bar.add_widget(btn_copy); root.add_widget(bar)
        btn_close = Button(text='Close', size_hint_y=None, height=46); root.add_widget(btn_close)
        pop = Popup(title='Provider Details', content=root, size_hint=(0.92,0.7)); pop.open()
        btn_call.bind(on_release=lambda *_: self.show_popup('Calling', f'Dialing {phone}...'))
        def _copy(*_):
            try:
                from kivy.core.clipboard import Clipboard
                Clipboard.copy(str(phone)); self.show_popup('Copied', f'Phone copied: {phone}')
            except Exception:
                self.show_popup('Copy failed', str(phone))
        btn_copy.bind(on_release=_copy); btn_close.bind(on_release=lambda *_: pop.dismiss())

    def load_providers(self):
        grid = self.root.get_screen('providers').ids.prov_grid; grid.clear_widgets()
        try:
            with open(PROVIDERS_FILE, 'r', encoding='utf-8') as f:
                providers = json.load(f)
        except Exception:
            providers = []
        self._providers_cache = providers
        for p in providers:
            pid = p.get("id",""); pname = p.get("name","Provider"); pserv = p.get("service","Service")
            prat = p.get("rating",4.0); pphone = p.get("phone","")
            card = BoxLayout(orientation='horizontal', size_hint_y=None, height=110, padding=10, spacing=12)
            with card.canvas.before:
                Color(0.12,0.12,0.14,1); rr = RoundedRectangle(pos=card.pos, size=card.size, radius=[14])
            card.bind(pos=lambda *_: setattr(rr,'pos',card.pos), size=lambda *_: setattr(rr,'size',card.size))
            avatar_path = self.get_provider_avatar(pname, pid, pserv); card.add_widget(Image(source=avatar_path, size_hint_x=None, width=64))
            lbl = Label(text=f"[b]{pname}[/b]\n{pserv}  •  ⭐{prat}", markup=True, halign="left", valign="middle", color=(0.95,0.95,0.98,1))
            lbl.text_size = (200, None); card.add_widget(lbl)
            btn_details = Button(text="Details", size_hint_x=None, width=90, background_normal="", background_color=(0.25,0.25,0.25,1), color=(1,1,1,1))
            btn_call = Button(text="Call", size_hint_x=None, width=80, background_normal="", background_color=self.aesthetic_teal, color=(1,1,1,1))
            btn_details.bind(on_release=lambda inst, pr=p: self.open_provider_details(pr))
            btn_call.bind(on_release=lambda inst, ph=pphone: self.show_popup("Calling", f"Dialing {ph}..."))
            card.add_widget(btn_details); card.add_widget(btn_call); grid.add_widget(card)

    def filter_providers(self, search_text='', filter_service='All'):
        search_text = (search_text or '').strip().lower()
        if not hasattr(self, '_providers_cache'):
            try:
                with open(PROVIDERS_FILE,'r',encoding='utf-8') as f: self._providers_cache = json.load(f)
            except Exception:
                self._providers_cache = []
        filtered = []
        for p in self._providers_cache:
            name = p.get('name','').lower(); service = p.get('service','')
            if filter_service and filter_service != 'All' and service != filter_service: continue
            if search_text and search_text not in name and search_text not in service.lower(): continue
            filtered.append(p)
        grid = self.root.get_screen('providers').ids.prov_grid; grid.clear_widgets()
        for p in filtered:
            pid = p.get("id",""); pname = p.get("name","Provider"); pserv = p.get("service","Service")
            prat = p.get("rating",4.0); pphone = p.get("phone","")
            card = BoxLayout(orientation='horizontal', size_hint_y=None, height=110, padding=10, spacing=12)
            with card.canvas.before:
                Color(0.12,0.12,0.14,1); rr = RoundedRectangle(pos=card.pos, size=card.size, radius=[14])
            card.bind(pos=lambda *_: setattr(rr,'pos',card.pos), size=lambda *_: setattr(rr,'size',card.size))
            avatar_path = self.get_provider_avatar(pname, pid, pserv); card.add_widget(Image(source=avatar_path, size_hint_x=None, width=64))
            lbl = Label(text=f"[b]{pname}[/b]\n{pserv}  •  ⭐{prat}", markup=True, halign="left", valign="middle", color=(0.95,0.95,0.98,1))
            lbl.text_size = (200, None); card.add_widget(lbl)
            btn_details = Button(text="Details", size_hint_x=None, width=90, background_normal="", background_color=(0.25,0.25,0.25,1), color=(1,1,1,1))
            btn_call = Button(text="Call", size_hint_x=None, width=80, background_normal="", background_color=self.aesthetic_teal, color=(1,1,1,1))
            btn_details.bind(on_release=lambda inst, pr=p: self.open_provider_details(pr))
            btn_call.bind(on_release=lambda inst, ph=pphone: self.show_popup("Calling", f"Dialing {ph}..."))
            card.add_widget(btn_details); card.add_widget(btn_call); grid.add_widget(card)

    def load_history(self):
        grid = self.root.get_screen('history').ids.hist_grid; grid.clear_widgets()
        # show scheduled visits
        visits = self.get_site_visits()
        for v in visits:
            card = BoxLayout(orientation='horizontal', size_hint_y=None, height=110, padding=10, spacing=12)
            with card.canvas.before:
                Color(0.12,0.12,0.14,1); rr = RoundedRectangle(pos=card.pos, size=card.size, radius=[14])
            card.bind(pos=lambda *_: setattr(rr,'pos',card.pos), size=lambda *_: setattr(rr,'size',card.size))
            txt = f"[b]Site Visit[/b]\n{v.get('customer','')} • {v.get('when','')}\n{v.get('address','')}"
            lbl = Label(text=txt, markup=True, halign='left', valign='top', color=(0.95,0.95,0.98,1)); lbl.text_size = (self.root.width - 160, None)
            card.add_widget(lbl); grid.add_widget(card)
        # read saved estimates
        if not os.path.exists(DB_FILE): pass
        try:
            conn = sqlite3.connect(DB_FILE); c = conn.cursor()
            c.execute('SELECT service, details, cost, created_at, image FROM requests ORDER BY id DESC'); rows = c.fetchall(); conn.close()
        except Exception as e:
            print("DB read failed:", e); rows = []
        for (service, details, cost, created_at, image) in rows:
            card = BoxLayout(orientation='horizontal', size_hint_y=None, height=120, padding=10, spacing=12)
            with card.canvas.before:
                Color(0.12,0.12,0.14,1); rr = RoundedRectangle(pos=card.pos, size=card.size, radius=[14])
            card.bind(pos=lambda *_: setattr(rr,'pos',card.pos), size=lambda *_: setattr(rr,'size',card.size))
            if image and os.path.exists(image): card.add_widget(Image(source=image, size_hint_x=None, width=90))
            text = f"[b]{(created_at or '')[:19]}[/b]\n{service} → ₹{float(cost):.2f}\n{details}"
            lbl = Label(text=text, markup=True, halign='left', valign='top', color=(0.95,0.95,0.98,1)); lbl.text_size = (self.root.width - 160, None)
            card.add_widget(lbl); grid.add_widget(card)

        # read work logs and display them
        try:
            conn = sqlite3.connect(DB_FILE); c = conn.cursor()
            c.execute('''CREATE TABLE IF NOT EXISTS work_logs
                         (id INTEGER PRIMARY KEY AUTOINCREMENT,
                          worker TEXT, completed TEXT, next_day TEXT, photo TEXT, created_at TEXT)''')
            c.execute('SELECT worker, completed, next_day, photo, created_at FROM work_logs ORDER BY id DESC')
            wrows = c.fetchall(); conn.close()
        except Exception as e:
            print("Work logs read failed:", e); wrows = []
        for (worker, completed, next_day, photo, created_at) in wrows:
            card = BoxLayout(orientation='horizontal', size_hint_y=None, height=140, padding=10, spacing=12)
            with card.canvas.before:
                Color(0.12,0.12,0.14,1); rr = RoundedRectangle(pos=card.pos, size=card.size, radius=[14])
            card.bind(pos=lambda *_: setattr(rr,'pos',card.pos), size=lambda *_: setattr(rr,'size',card.size))
            if photo and os.path.exists(photo):
                card.add_widget(Image(source=photo, size_hint_x=None, width=110))
            text = f"[b]Work Log — {worker}[/b]\n{(created_at or '')[:19]}\n[b]Today:[/b] {completed}\n[b]Next:[/b] {next_day}"
            lbl = Label(text=text, markup=True, halign='left', valign='top', color=(0.95,0.95,0.98,1))
            lbl.text_size = (self.root.width - 160, None)
            card.add_widget(lbl); grid.add_widget(card)

    def open_full_image(self, path):
        if not path or not os.path.exists(path):
            self.show_popup("No image", "No image selected to preview."); return
        root = BoxLayout(orientation='vertical', padding=12, spacing=10)
        card = BoxLayout(orientation='vertical', padding=10, spacing=10)
        with card.canvas.before:
            Color(0,0,0,0.4); shadow = RoundedRectangle(radius=[18], pos=(0,0), size=(0,0))
            Color(0.10,0.10,0.12,1); bg = RoundedRectangle(radius=[16], pos=(0,0), size=(0,0))
        def _sync_bg(*_):
            shadow.pos = (card.x - 6, card.y - 6); shadow.size = (card.width + 12, card.height + 12)
            bg.pos = card.pos; bg.size = card.size
        card.bind(pos=_sync_bg, size=_sync_bg)
        sc = Scatter(do_rotation=False, do_translation=True, do_scale=True, scale=1.0, scale_min=0.9, scale_max=4)
        img = Image(source=path, allow_stretch=True, keep_ratio=True); sc.add_widget(img); card.add_widget(sc)
        btn_bar = BoxLayout(size_hint_y=None, height=44, spacing=8)
        btn_reset = Button(text='Reset Zoom', background_normal='', background_color=(0.25,0.25,0.25,1), color=(1,1,1,1))
        btn_close = Button(text='Close', background_normal='', background_color=self.aesthetic_teal, color=(1,1,1,1))
        btn_bar.add_widget(btn_reset); btn_bar.add_widget(btn_close)
        root.add_widget(card); root.add_widget(btn_bar)
        popup = Popup(title='Full Image Preview', content=root, size_hint=(0.96,0.96), opacity=0); popup.open()
        Animation(opacity=1, d=0.18).start(popup); Animation(scale=1.0, d=0.18, t='out_quad').start(sc)
        def _reset_zoom(*_): Animation(scale=1.0, d=0.12).start(sc)
        btn_reset.bind(on_release=_reset_zoom); btn_close.bind(on_release=lambda *_: popup.dismiss())

    def open_site_visit_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=8)
        from kivy.uix.textinput import TextInput
        name_input = TextInput(hint_text='Your name', size_hint_y=None, height=40, multiline=False)
        when_input = TextInput(hint_text='Date & time (e.g. 2025-11-10 14:00)', size_hint_y=None, height=40, multiline=False)
        addr_input = TextInput(hint_text='Site address', size_hint_y=None, height=80)
        save_btn = Button(text='Schedule Visit', size_hint_y=None, height=44, background_normal='', background_color=self.aesthetic_teal, color=(1,1,1,1))
        cancel_btn = Button(text='Cancel', size_hint_y=None, height=44)
        content.add_widget(Label(text='Schedule a Site Visit', size_hint_y=None, height=28, color=(1,1,1,1)))
        content.add_widget(name_input); content.add_widget(when_input); content.add_widget(addr_input)
        btn_row = BoxLayout(size_hint_y=None, height=44, spacing=8); btn_row.add_widget(save_btn); btn_row.add_widget(cancel_btn)
        content.add_widget(btn_row); pop = Popup(title='Site Visit', content=content, size_hint=(0.9,0.6)); pop.open()
        def _save(*_):
            name = (name_input.text or '').strip(); when = (when_input.text or '').strip(); addr = (addr_input.text or '').strip()
            if not name or not when or not addr:
                self.show_popup('Missing', 'Please fill all fields.'); return
            try:
                conn = sqlite3.connect(DB_FILE); c = conn.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS visits
                             (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, when_txt TEXT, address TEXT, created_at TEXT)''')
                c.execute('INSERT INTO visits (customer, when_txt, address, created_at) VALUES (?,?,?,?)',
                          (name, when, addr, datetime.now().isoformat()))
                conn.commit(); conn.close()
                self.show_popup('Scheduled', f'Visit scheduled: {when}'); pop.dismiss(); self.change_screen('history')
            except Exception as e:
                print("Save visit failed:", e); self.show_popup('Error', 'Failed to schedule visit.')
        save_btn.bind(on_release=_save); cancel_btn.bind(on_release=lambda *_: pop.dismiss())

    def get_site_visits(self):
        if not os.path.exists(DB_FILE): return []
        try:
            conn = sqlite3.connect(DB_FILE); c = conn.cursor()
            c.execute('SELECT customer, when_txt, address, created_at FROM visits ORDER BY id DESC'); rows = c.fetchall(); conn.close()
        except Exception as e:
            print("Get visits failed:", e); rows = []
        visits = [{'customer': r[0], 'when': r[1], 'address': r[2], 'created_at': r[3]} for r in rows]
        return visits

    def open_amc_popup(self):
        content = BoxLayout(orientation='vertical', padding=10, spacing=8)
        from kivy.uix.textinput import TextInput
        cust_input = TextInput(hint_text='Your name', size_hint_y=None, height=40, multiline=False)
        monthly_btn = Button(text='Monthly - ₹499', size_hint_y=None, height=40, background_normal='', background_color=(0.18,0.18,0.18,1), color=(1,1,1,1))
        yearly_btn = Button(text='Yearly - ₹4999', size_hint_y=None, height=40, background_normal='', background_color=self.aesthetic_teal, color=(1,1,1,1))
        content.add_widget(Label(text='AMC Subscription', size_hint_y=None, height=28, color=(1,1,1,1))); content.add_widget(cust_input)
        content.add_widget(monthly_btn); content.add_widget(yearly_btn)
        row = BoxLayout(size_hint_y=None, height=44, spacing=8); cancel_btn = Button(text='Cancel', size_hint_y=None, height=44); row.add_widget(cancel_btn)
        content.add_widget(row); pop = Popup(title='AMC', content=content, size_hint=(0.9,0.7)); pop.open()
        def _save(plan):
            name = (cust_input.text or '').strip()
            if not name: self.show_popup('Missing', 'Enter your name.'); return
            try:
                conn = sqlite3.connect(DB_FILE); c = conn.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS amc (id INTEGER PRIMARY KEY AUTOINCREMENT, customer TEXT, plan TEXT, created_at TEXT)''')
                c.execute('INSERT INTO amc (customer, plan, created_at) VALUES (?,?,?)', (name, plan, datetime.now().isoformat()))
                conn.commit(); conn.close(); self.show_popup('Subscribed', f'{plan.capitalize()} AMC activated.'); pop.dismiss()
            except Exception as e:
                print("AMC save failed:", e); self.show_popup('Error', 'Subscribe failed.')
        monthly_btn.bind(on_release=lambda *_: _save('monthly')); yearly_btn.bind(on_release=lambda *_: _save('yearly')); cancel_btn.bind(on_release=lambda *_: pop.dismiss())

    def show_popup(self, title, message):
        content = BoxLayout(orientation='vertical', padding=8, spacing=8)
        content.add_widget(Label(text=message, color=(1,1,1,1)))
        ok = Button(text='OK', size_hint=(1, None), height=40, background_normal='', background_color=self.aesthetic_teal, color=(1,1,1,1))
        content.add_widget(ok)
        popup = Popup(title=title, content=content, size_hint=(0.82, None), height=180)
        ok.bind(on_release=popup.dismiss); popup.open()

    # ----------------- NEW: Worker Log popup & save/load functionality -----------------
    def open_work_log_popup(self):
        """
        Popup for worker to enter: name, completed work, next day plan, and attach photo.
        The photo selection is handled inside the popup via FileChooser so the popup won't be dismissed.
        """
        try:
            from kivy.uix.textinput import TextInput
            from kivy.uix.filechooser import FileChooserListView
        except Exception as e:
            print("Work log popup imports failed:", e)
            self.show_popup("Error", "Unable to open worker log popup on this device.")
            return

        root = BoxLayout(orientation='vertical', padding=8, spacing=8)
        root.add_widget(Label(text='Worker Daily Log', size_hint_y=None, height=28, color=(1,1,1,1)))
        name_input = TextInput(hint_text='Worker name', size_hint_y=None, height=40, multiline=False)
        completed_input = TextInput(hint_text='Work completed today (short)', size_hint_y=None, height=100)
        next_input = TextInput(hint_text='Plan for next day', size_hint_y=None, height=100)
        root.add_widget(name_input)
        root.add_widget(Label(text='Completed (today):', size_hint_y=None, height=20, color=(1,1,1,1)))
        root.add_widget(completed_input)
        root.add_widget(Label(text='Next day plan:', size_hint_y=None, height=20, color=(1,1,1,1)))
        root.add_widget(next_input)

        # file chooser + preview inside popup
        chooser_row = BoxLayout(size_hint_y=None, height=160, spacing=8)
        filechooser = FileChooserListView(filters=['*.png', '*.jpg', '*.jpeg'])
        preview_box = BoxLayout(orientation='vertical', size_hint_x=None, width=160)
        preview_box.add_widget(Label(text='Photo Preview', size_hint_y=None, height=24, color=(1,1,1,1)))
        preview_img = Image(source='', allow_stretch=True, keep_ratio=True)
        preview_box.add_widget(preview_img)
        chooser_row.add_widget(filechooser); chooser_row.add_widget(preview_box)
        root.add_widget(chooser_row)

        # when selection changes update preview
        def _on_sel(*args):
            sel = getattr(filechooser, 'selection', [])
            if sel and os.path.exists(sel[0]):
                preview_img.source = sel[0]
            else:
                preview_img.source = ''
        filechooser.bind(selection=lambda inst, val: _on_sel())

        btn_row = BoxLayout(size_hint_y=None, height=44, spacing=8)
        save_btn = Button(text='Save Log', background_normal='', background_color=self.aesthetic_teal, color=(1,1,1,1))
        cancel_btn = Button(text='Cancel')
        btn_row.add_widget(save_btn); btn_row.add_widget(cancel_btn)
        root.add_widget(btn_row)

        pop = Popup(title='Worker Log', content=root, size_hint=(0.95, 0.9))
        pop.open()

        def _save(*_):
            worker = (name_input.text or '').strip()
            completed = (completed_input.text or '').strip()
            next_day = (next_input.text or '').strip()
            sel = getattr(filechooser, 'selection', [])
            photo_path = ''
            if sel and len(sel) > 0 and os.path.exists(sel[0]):
                chosen = sel[0]
                basename = os.path.basename(chosen)
                dest = os.path.join(UPLOADS_DIR, f"{int(time.time())}_{basename}")
                try:
                    shutil.copy(chosen, dest)
                    photo_path = dest
                except Exception as e:
                    print("Work log image copy failed:", e)
                    photo_path = chosen
            # basic validation
            if not worker:
                self.show_popup("Missing", "Enter worker name.")
                return
            if not completed and not next_day:
                self.show_popup("Missing", "Enter details about completed work or next day plan.")
                return
            # save to DB
            try:
                conn = sqlite3.connect(DB_FILE); c = conn.cursor()
                c.execute('''CREATE TABLE IF NOT EXISTS work_logs
                             (id INTEGER PRIMARY KEY AUTOINCREMENT,
                              worker TEXT, completed TEXT, next_day TEXT, photo TEXT, created_at TEXT)''')
                now = datetime.now().isoformat()
                c.execute('INSERT INTO work_logs (worker, completed, next_day, photo, created_at) VALUES (?,?,?,?,?)',
                          (worker, completed, next_day, photo_path, now))
                conn.commit(); conn.close()
            except Exception as e:
                print("Saving work log to DB failed:", e)
                self.show_popup("Error", "Failed to save work log to database.")
                return
            # append to CSV for ML / records
            try:
                write_header = not os.path.exists(WORKLOGS_CSV)
                with open(WORKLOGS_CSV, 'a', newline='', encoding='utf-8') as f:
                    w = csv.writer(f)
                    if write_header:
                        w.writerow(['created_at','worker','completed','next_day','photo'])
                    w.writerow([now, worker, completed, next_day, photo_path])
            except Exception as e:
                print("Append work log CSV failed:", e)
            self.show_popup("Saved", "Work log saved.")
            pop.dismiss()
            # reset current image to avoid accidental reuse
            self.current_image = ''
            self.change_screen('history')

        save_btn.bind(on_release=_save)
        cancel_btn.bind(on_release=lambda *_: pop.dismiss())

    # ---------------------------------------------------------------------------------

if __name__ == '__main__':
    SmartApp().run()



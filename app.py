import io
import os
import random
import sqlite3
import string
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib

import pandas as pd
from PIL import Image, ImageDraw
import streamlit as st
import streamlit.components.v1 as components

# ==========================================
# 1. SESSION STATE INITIALIZATION
# ==========================================
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'Home'
if 'admin_auth_step' not in st.session_state:
    st.session_state.admin_auth_step = 0  # 0: Credentials, 1: OTP, 2: Access Granted
if 'generated_otp' not in st.session_state:
    st.session_state.generated_otp = None
if 'admin_email' not in st.session_state:
    st.session_state.admin_email = None
if 'email_error_msg' not in st.session_state:
    st.session_state.email_error_msg = None

# ==========================================
# 2. PAGE CONFIGURATION & DYNAMIC STYLING
# ==========================================
st.set_page_config(
    page_title="SVCE Bengaluru - Exam Portal",
    page_icon="🎓",
    layout="wide"
)

def inject_custom_styles():
    if st.session_state.current_page in ['Home', 'Student']:
        css = """
<style>
html, body, [class*="css"], .stMarkdown, .stText, input, button, select, textarea {
    font-family: "Times New Roman", Times, serif !important;
}
[data-testid="stAppViewContainer"] {
    background-image: linear-gradient(rgba(0,0,0,0.5), rgba(0,0,0,0.5)), url("https://svcengg.edu.in/assets/bgimages/IMG_9641.webp") !important;
    background-size: cover !important;
    background-position: center !important;
    background-attachment: fixed !important;
}
.stMainBlockContainer {
    max-width: 980px !important;
    margin: 0 auto !important;
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
    background: rgba(255, 255, 255, 0.95) !important;
    backdrop-filter: blur(10px) !important;
    border-radius: 16px !important;
    box-shadow: 0 15px 35px rgba(0, 0, 0, 0.6) !important;
    border: 2px solid rgba(255, 255, 255, 0.8) !important;
}
.stMarkdown, .stText, label, h1, h2, h3, h4, h5, h6, li, p { color: #000000 !important; }
.stTextInput input {
    color: #000000 !important;
    background-color: #FFFFFF !important;
    border: 2px solid #000000 !important;
}
.stTextInput input:focus { border-color: #1E3A8A !important; }
.stButton>button {
    border: 2px solid #000000 !important;
    color: #000000 !important;
    background-color: #FFFFFF !important;
    font-weight: bold !important;
    font-size: 1.1rem !important;
}
.campus-marquee {
    width: 100%;
    overflow: hidden;
    white-space: nowrap;
    border-radius: 12px;
    margin-bottom: 20px;
    border: 1px solid rgba(0,0,0,0.1);
}
.campus-marquee-track {
    display: inline-block;
    white-space: nowrap;
    animation: marqueeSlide 18s linear infinite;
}
.campus-marquee-track img {
    width: 260px;
    height: 150px;
    object-fit: cover;
    border-radius: 8px;
    margin-right: 12px;
    display: inline-block;
}
@keyframes marqueeSlide {
    0% { transform: translateX(0%); }
    100% { transform: translateX(-50%); }
}
</style>
"""
    else:
        css = """
<style>
html, body, [class*="css"], .stMarkdown, .stText, input, button, select, textarea {
    font-family: "Times New Roman", Times, serif !important;
}
[data-testid="stAppViewContainer"] {
    background-color: #000000 !important;
    background-image: none !important;
}
.stMainBlockContainer {
    max-width: 980px !important;
    margin: 0 auto !important;
    padding-top: 2rem !important;
    padding-bottom: 2rem !important;
    background-color: transparent !important;
    box-shadow: none !important;
}
.stMarkdown, .stText, label, h1, h2, h3, h4, h5, h6, li, p { color: #FFFFFF !important; }
.stTextInput input {
    color: #FFFFFF !important;
    background-color: #1E1E1E !important;
    border: 2px solid #555555 !important;
}
.stButton>button {
    border: 2px solid #555555 !important;
    color: #FFFFFF !important;
    background-color: #333333 !important;
    font-weight: bold !important;
    font-size: 1.1rem !important;
}
</style>
"""
    st.markdown(css, unsafe_allow_html=True)

inject_custom_styles()

# ==========================================
# 3. DATABASE SETUP (SQLITE)
# ==========================================
DB_FILE = "allotments.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS allotments (
                    usn TEXT PRIMARY KEY, name TEXT, college TEXT, 
                    event TEXT, room TEXT, floor TEXT, bench INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS admin_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, 
                    password TEXT NOT NULL)''')
    c.execute('SELECT COUNT(*) FROM admin_config')
    if c.fetchone()[0] == 0:
        c.execute('INSERT INTO admin_config (password) VALUES (?)', ('Admin@123',))
    conn.commit()
    conn.close()

def get_admin_password():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT password FROM admin_config ORDER BY id DESC LIMIT 1')
    pwd = c.fetchone()[0]
    conn.close()
    return pwd

def update_admin_password(new_pwd):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE admin_config SET password = ? WHERE id = (SELECT MAX(id) FROM admin_config)', (new_pwd,))
    conn.commit()
    conn.close()

def save_allotments(df_allocated):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('DELETE FROM allotments')
    for _, row in df_allocated.iterrows():
        c.execute('''INSERT INTO allotments (usn, name, college, event, room, floor, bench)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                  (str(row['USN']).strip().upper(), str(row['Student Name']), 
                   str(row['College Name']), str(row['Event/Exam Name']), 
                   str(row['Room Number']), str(row['Floor']), int(row['Bench Number'])))
    conn.commit()
    conn.close()

def fetch_student_allotment(usn):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT * FROM allotments WHERE usn = ?', (usn.strip().upper(),))
    data = c.fetchone()
    conn.close()
    return data

def get_all_allotments():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM allotments", conn)
    conn.close()
    return df

init_db()

# ==========================================
# 4. GMAIL SMTP DISPATCH (SAFE CREDENTIAL LOADING)
# ==========================================
def get_credential(key_name, default_value=""):
    try:
        if key_name in st.secrets:
            return st.secrets[key_name]
    except Exception:
        pass
    return os.getenv(key_name, default_value)

SENDER_EMAIL = get_credential("SENDER_EMAIL", "funguru528@gmail.com")
SENDER_APP_PASSWORD = get_credential("SENDER_APP_PASSWORD", "your_16_char_app_password")

def send_email_otp(target_email, otp):
    """Sends OTP using standard smtplib on Port 587 (TLS) with robust error reporting."""
    if "your_16_char_app_password" in SENDER_APP_PASSWORD or not SENDER_APP_PASSWORD:
        return False, "SMTP Credentials Not Configured (Using On-Screen Display Fallback)"

    try:
        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = target_email
        msg['Subject'] = "SVCE Portal - Admin Login Verification Code"
        
        body = f"Security Alert: Your SVCE Admin verification OTP is {otp}. Do not share this with anyone."
        msg.attach(MIMEText(body, 'plain'))
        
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=10) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.send_message(msg)
        return True, "OTP email dispatched successfully!"
    except Exception as e:
        return False, f"Email delivery failed: {str(e)}"

# ==========================================
# 5. MULTI-TIER 3D BLUEPRINT & NAVIGATION ENGINE
# ==========================================
def render_3d_college_blueprint(target_room, target_floor, bench_no):
    room_clean = str(target_room).upper().strip().replace(" ", "")
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; overflow: hidden; background: #070d1f; font-family: 'Times New Roman', serif; }}
            #canvas-container {{ width: 100%; height: 580px; position: relative; }}
            .overlay-ui {{
                position: absolute;
                top: 12px;
                left: 12px;
                background: rgba(15, 23, 42, 0.9);
                backdrop-filter: blur(8px);
                border: 1px solid #38bdf8;
                border-radius: 8px;
                padding: 10px 16px;
                color: #ffffff;
                z-index: 10;
                pointer-events: none;
            }}
            .overlay-ui h4 {{ margin: 0 0 4px 0; color: #38bdf8; font-size: 15px; }}
            .overlay-ui p {{ margin: 0; font-size: 12px; color: #cbd5e1; }}
            .badge-assigned {{
                display: inline-block;
                background: #0284c7;
                color: #fff;
                padding: 2px 8px;
                border-radius: 4px;
                font-weight: bold;
            }}
            .badge-stair {{
                display: inline-block;
                background: #ef4444;
                color: #fff;
                padding: 2px 6px;
                border-radius: 4px;
                font-weight: bold;
            }}
            .nav-box {{
                position: absolute;
                bottom: 40px;
                left: 12px;
                background: rgba(15, 23, 42, 0.95);
                border: 1px solid #facc15;
                border-radius: 8px;
                padding: 8px 14px;
                color: #ffffff;
                font-size: 12px;
                z-index: 10;
                max-width: 380px;
            }}
            .nav-box h5 {{ margin: 0 0 4px 0; color: #facc15; font-size: 13px; }}
            .view-toolbar {{
                position: absolute;
                top: 12px;
                right: 12px;
                display: flex;
                gap: 6px;
                z-index: 10;
            }}
            .view-btn {{
                background: #1e293b;
                border: 1px solid #38bdf8;
                color: #ffffff;
                padding: 6px 12px;
                border-radius: 6px;
                cursor: pointer;
                font-size: 12px;
                font-weight: bold;
                transition: all 0.2s;
            }}
            .view-btn:hover {{
                background: #0284c7;
            }}
            .controls-hint {{
                position: absolute;
                bottom: 8px;
                left: 12px;
                right: 12px;
                display: flex;
                justify-content: space-between;
                background: rgba(0,0,0,0.75);
                border-radius: 6px;
                padding: 4px 12px;
                color: #94a3b8;
                font-size: 11px;
                z-index: 10;
            }}
        </style>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
        <script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>
    </head>
    <body>
        <div id="canvas-container">
            <div class="overlay-ui">
                <h4>🏛️ SVCE Campus Multi-Floor 3D Model</h4>
                <p>Target Class: <span class="badge-assigned">{target_room} ({target_floor}, Bench #{bench_no})</span></p>
                <p style="margin-top:4px;">Stairs: <span class="badge-stair">4 Red Vertical Connectors</span> linking Ground ⇄ 1st ⇄ 2nd</p>
            </div>

            <div class="nav-box" id="nav-instructions">
                <h5>🗺️ Active Navigation Path</h5>
                <p id="nav-text">Calculating route from Main Entrance to room...</p>
            </div>
            
            <div class="view-toolbar">
                <button class="view-btn" onclick="setExploded(false)">🏢 Stacked View</button>
                <button class="view-btn" onclick="setExploded(true)">📂 Explode Floors</button>
                <button class="view-btn" onclick="isolateFloor(0)">Gnd Floor</button>
                <button class="view-btn" onclick="isolateFloor(1)">1st Floor</button>
                <button class="view-btn" onclick="isolateFloor(2)">2nd Floor</button>
                <button class="view-btn" onclick="resetView()">🔄 Reset View</button>
            </div>

            <div class="controls-hint">
                <span>🖱️ <b>Left Click + Drag:</b> Rotate 360° | <b>Scroll:</b> Zoom | <b>Right Click:</b> Pan</span>
                <span>🟡 <b>Glowing Line:</b> Live Wayfinding Route to your Class</span>
            </div>
        </div>

        <script>
            const container = document.getElementById('canvas-container');
            const width = container.clientWidth || 900;
            const height = 580;

            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x070d1f);

            const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
            camera.position.set(65, 55, 75);

            const renderer = new THREE.WebGLRenderer({{ antialias: true }});
            renderer.setSize(width, height);
            renderer.setPixelRatio(window.devicePixelRatio);
            renderer.shadowMap.enabled = true;
            container.appendChild(renderer.domElement);

            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.maxPolarAngle = Math.PI / 2 - 0.02;
            controls.target.set(0, 15, 0);

            scene.add(new THREE.AmbientLight(0xffffff, 0.85));
            const sun = new THREE.DirectionalLight(0xffffff, 0.9);
            sun.position.set(50, 80, 40);
            sun.castShadow = true;
            scene.add(sun);

            const gridHelper = new THREE.GridHelper(120, 30, 0x1e3a5f, 0x0f172a);
            gridHelper.position.y = -0.5;
            scene.add(gridHelper);

            function makeTextSprite(message, color = "#ffffff", bgColor = "rgba(15, 23, 42, 0.85)", isSpecial = false) {{
                const canvas = document.createElement('canvas');
                canvas.width = 256;
                canvas.height = 128;
                const ctx = canvas.getContext('2d');
                ctx.fillStyle = bgColor;
                ctx.fillRect(0, 0, 256, 128);
                ctx.strokeStyle = color;
                ctx.lineWidth = isSpecial ? 6 : 3;
                ctx.strokeRect(4, 4, 248, 120);
                ctx.fillStyle = color;
                ctx.font = (isSpecial ? 'bold 28px' : 'bold 24px') + ' Times New Roman, serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(message, 128, 64);
                
                const texture = new THREE.CanvasTexture(canvas);
                const sprite = new THREE.Sprite(new THREE.SpriteMaterial({{ map: texture }}));
                sprite.scale.set(isSpecial ? 13 : 9, isSpecial ? 6.5 : 4.5, 1);
                return sprite;
            }}

            const assignedTarget = "{room_clean}";
            let targetPinMesh = null;
            let targetCoords = null;
            const floorGroups = [];
            const baseFloorHeights = [0, 11, 22];

            function createRoom(name, x, y, z, w, h, d, floorIdx) {{
                const group = new THREE.Group();
                const geo = new THREE.BoxGeometry(w, h, d);
                const isAssigned = (assignedTarget.length > 2 && name.replace(/\s+/g, '').includes(assignedTarget));
                
                let mat;
                if (isAssigned) {{
                    mat = new THREE.MeshStandardMaterial({{
                        color: 0x0284c7,
                        emissive: 0x0ea5e9,
                        emissiveIntensity: 0.8,
                        transparent: true,
                        opacity: 0.92,
                        roughness: 0.2
                    }});
                }} else {{
                    mat = new THREE.MeshStandardMaterial({{
                        color: 0x1e293b,
                        transparent: true,
                        opacity: 0.72,
                        roughness: 0.5
                    }});
                }}
                
                const mesh = new THREE.Mesh(geo, mat);
                mesh.position.set(0, h / 2, 0);
                mesh.castShadow = true;
                mesh.receiveShadow = true;
                group.add(mesh);

                const edges = new THREE.EdgesGeometry(geo);
                const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({{
                    color: isAssigned ? 0xfacc15 : 0x475569,
                    linewidth: isAssigned ? 3 : 1
                }}));
                line.position.set(0, h / 2, 0);
                group.add(line);

                const label = makeTextSprite(name, isAssigned ? "#facc15" : "#cbd5e1", isAssigned ? "rgba(2, 132, 199, 0.95)" : "rgba(30, 41, 59, 0.85)", isAssigned);
                label.position.set(0, h + 2.5, 0);
                group.add(label);

                if (isAssigned) {{
                    const pinGeo = new THREE.ConeGeometry(2, 5, 16);
                    const pinMat = new THREE.MeshStandardMaterial({{ color: 0xfacc15, emissive: 0xeab308, emissiveIntensity: 0.9 }});
                    const pin = new THREE.Mesh(pinGeo, pinMat);
                    pin.rotation.x = Math.PI;
                    pin.position.set(0, h + 9, 0);
                    group.add(pin);
                    targetPinMesh = pin;
                    
                    targetCoords = {{
                        x: x,
                        y: baseFloorHeights[floorIdx] + h / 2,
                        z: z,
                        floorIdx: floorIdx
                    }};
                }}

                group.position.set(x, y, z);
                return group;
            }}

            function createFloorSlab(floorName) {{
                const slabGroup = new THREE.Group();
                const rear = new THREE.Mesh(new THREE.BoxGeometry(76, 0.6, 26), new THREE.MeshStandardMaterial({{ color: 0x0f172a, roughness: 0.7 }}));
                rear.position.set(0, 0, -13);
                slabGroup.add(rear);

                const east = new THREE.Mesh(new THREE.BoxGeometry(16, 0.6, 38), new THREE.MeshStandardMaterial({{ color: 0x0f172a, roughness: 0.7 }}));
                east.position.set(-30, 0, 19);
                slabGroup.add(east);

                const west = new THREE.Mesh(new THREE.BoxGeometry(16, 0.6, 38), new THREE.MeshStandardMaterial({{ color: 0x0f172a, roughness: 0.7 }}));
                west.position.set(30, 0, 19);
                slabGroup.add(west);

                const banner = makeTextSprite(floorName, "#38bdf8", "rgba(15, 23, 42, 0.9)", true);
                banner.position.set(0, 1, 38);
                banner.scale.set(16, 8, 1);
                slabGroup.add(banner);

                return slabGroup;
            }}

            const floorConfigs = [
                {{
                    name: "GROUND FLOOR",
                    rooms: [
                        {{ name: "EB-101", x: -30, z: 32, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-102", x: -30, z: 23, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-103", x: -30, z: 14, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-104", x: -30, z: 5, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-106 Toilet", x: -30, z: -4, w: 12, h: 5.5, d: 7 }},
                        {{ name: "EB-107 Lab", x: -30, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-108 Lab", x: -30, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-111 Lab", x: -16, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-122 Comp Center", x: -16, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "CB-111 Main Office", x: 0, z: -16, w: 16, h: 5.5, d: 18 }},
                        {{ name: "WB-101 Studio", x: 30, z: 32, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-102 Studio", x: 30, z: 23, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-103 Studio", x: 30, z: 14, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-104 Faculty", x: 30, z: 5, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-106 Toilet", x: 30, z: -4, w: 12, h: 5.5, d: 7 }},
                        {{ name: "WB-110 Skill Lab", x: 16, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-109 Central Library", x: 22, z: -22, w: 26, h: 5.5, d: 8 }}
                    ]
                }},
                {{
                    name: "FIRST FLOOR",
                    rooms: [
                        {{ name: "EB-201 Lecture", x: -30, z: 32, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-202 Lecture", x: -30, z: 23, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-203 Lecture", x: -30, z: 14, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-204 Faculty", x: -30, z: 5, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-206 Toilet", x: -30, z: -4, w: 12, h: 5.5, d: 7 }},
                        {{ name: "EB-207 Lab", x: -30, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-208 Lab", x: -30, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-213 Lab", x: -16, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "CB-204 Dean Office", x: -7, z: -15, w: 10, h: 5.5, d: 8 }},
                        {{ name: "CB-201 Placement", x: 7, z: -15, w: 10, h: 5.5, d: 8 }},
                        {{ name: "CB-203 Seminar Hall", x: 0, z: -22, w: 20, h: 5.5, d: 8 }},
                        {{ name: "WB-201 Lecture", x: 30, z: 32, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-202 Lecture", x: 30, z: 23, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-203 Lecture", x: 30, z: 14, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-204 Lecture", x: 30, z: 5, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-206 Toilet", x: 30, z: -4, w: 12, h: 5.5, d: 7 }},
                        {{ name: "WB-207 Lecture", x: 30, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-209 Lecture", x: 16, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-210 Lecture", x: 4, z: -22, w: 11, h: 5.5, d: 8 }},
                        {{ name: "WB-211 Lecture", x: -8, z: -22, w: 11, h: 5.5, d: 8 }}
                    ]
                }},
                {{
                    name: "SECOND FLOOR",
                    rooms: [
                        {{ name: "EB-301 Lecture", x: -30, z: 32, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-302 Lecture", x: -30, z: 23, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-303 Lecture", x: -30, z: 14, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-304 Faculty", x: -30, z: 5, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-306 Toilet", x: -30, z: -4, w: 12, h: 5.5, d: 7 }},
                        {{ name: "EB-307 Lecture", x: -30, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-308 Studio", x: -30, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-314 Comp Center", x: -16, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "CB-301 Auditorium", x: 0, z: -18, w: 22, h: 7, d: 16 }},
                        {{ name: "WB-301 Lecture", x: 30, z: 32, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-302 Lecture", x: 30, z: 23, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-303 Lecture", x: 30, z: 14, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-304 Faculty", x: 30, z: 5, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-306 Toilet", x: 30, z: -4, w: 12, h: 5.5, d: 7 }},
                        {{ name: "WB-307 Lecture", x: 30, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-308 Lecture", x: 30, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-309 Lecture", x: 16, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "WB-311 Lecture", x: 2, z: -22, w: 12, h: 5.5, d: 8 }}
                    ]
                }}
            ];

            floorConfigs.forEach((cfg, idx) => {{
                const flGroup = new THREE.Group();
                flGroup.add(createFloorSlab(cfg.name));
                cfg.rooms.forEach(r => {{
                    flGroup.add(createRoom(r.name, r.x, 0.3, r.z, r.w, r.h, r.d, idx));
                }});
                flGroup.position.y = baseFloorHeights[idx];
                scene.add(flGroup);
                floorGroups.push(flGroup);
            }});

            const stairPositions = [
                {{ name: "East Stairs (EB)", x: -30, z: 0, w: 12, d: 8 }},
                {{ name: "Central Left Stairs", x: -9, z: 0, w: 9, d: 8 }},
                {{ name: "Central Right Stairs", x: 9, z: 0, w: 9, d: 8 }},
                {{ name: "West Stairs (WB)", x: 30, z: 0, w: 12, d: 8 }}
            ];

            const stairMeshes = [];

            stairPositions.forEach(pos => {{
                const totalH = 29;
                const shaftGeo = new THREE.BoxGeometry(pos.w, totalH, pos.d);
                const shaftMat = new THREE.MeshStandardMaterial({{
                    color: 0xef4444,
                    emissive: 0xb91c1c,
                    emissiveIntensity: 0.7,
                    transparent: true,
                    opacity: 0.88
                }});
                const shaft = new THREE.Mesh(shaftGeo, shaftMat);
                shaft.position.set(pos.x, totalH / 2, pos.z);
                shaft.castShadow = true;
                scene.add(shaft);
                stairMeshes.push(shaft);

                const edges = new THREE.EdgesGeometry(shaftGeo);
                const wire = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({{ color: 0xffffff, linewidth: 2 }}));
                wire.position.set(pos.x, totalH / 2, pos.z);
                scene.add(wire);

                for (let stepY = 1; stepY < totalH; stepY += 2) {{
                    const stepGeo = new THREE.BoxGeometry(pos.w - 1, 0.4, pos.d - 1);
                    const step = new THREE.Mesh(stepGeo, new THREE.MeshBasicMaterial({{ color: 0xffffff }}));
                    step.position.set(pos.x, stepY, pos.z);
                    scene.add(step);
                }}

                const label = makeTextSprite("🔴 " + pos.name, "#ffffff", "rgba(220, 38, 38, 0.9)", true);
                label.position.set(pos.x, totalH + 3, pos.z);
                scene.add(label);
            }});

            let animatedMarker = null;
            let pathCurve = null;

            if (targetCoords) {{
                let chosenStair = stairPositions[1];
                if (targetCoords.x <= -20) chosenStair = stairPositions[0];
                else if (targetCoords.x >= 20) chosenStair = stairPositions[3];

                const entrancePoint = new THREE.Vector3(0, 1, 35);
                const stairGnd = new THREE.Vector3(chosenStair.x, 1, chosenStair.z);
                const stairTargetFl = new THREE.Vector3(chosenStair.x, targetCoords.y, chosenStair.z);
                const destination = new THREE.Vector3(targetCoords.x, targetCoords.y, targetCoords.z);

                const pathPoints = [entrancePoint];

                if (targetCoords.floorIdx > 0) {{
                    pathPoints.push(stairGnd);
                    pathPoints.push(stairTargetFl);
                }} else {{
                    pathPoints.push(new THREE.Vector3(chosenStair.x, 1, chosenStair.z));
                }}
                pathPoints.push(destination);

                const lineGeometry = new THREE.BufferGeometry().setFromPoints(pathPoints);
                const lineMaterial = new THREE.LineDashedMaterial({{
                    color: 0x38bdf8,
                    linewidth: 4,
                    scale: 1,
                    dashSize: 2,
                    gapSize: 1,
                }});
                const pathLine = new THREE.Line(lineGeometry, lineMaterial);
                pathLine.computeLineDistances();
                scene.add(pathLine);

                const markerGeo = new THREE.SphereGeometry(1.2, 16, 16);
                const markerMat = new THREE.MeshStandardMaterial({{
                    color: 0xfacc15,
                    emissive: 0xeab308,
                    emissiveIntensity: 1.0
                }});
                animatedMarker = new THREE.Mesh(markerGeo, markerMat);
                scene.add(animatedMarker);

                pathCurve = new THREE.CatmullRomCurve3(pathPoints);

                const navText = document.getElementById('nav-text');
                if (targetCoords.floorIdx === 0) {{
                    navText.innerHTML = `Enter Main Gate ➔ Walk along Ground Floor Corridor ➔ Proceed directly to <b>${{assignedTarget}}</b>.`;
                }} else {{
                    const flName = targetCoords.floorIdx === 1 ? "1st Floor" : "2nd Floor";
                    navText.innerHTML = `Enter Main Gate ➔ Head to <b>${{chosenStair.name}}</b> ➔ Take Stairs up to <b>${{flName}}</b> ➔ Walk down corridor to <b>${{assignedTarget}}</b>.`;
                }}
            }} else {{
                document.getElementById('nav-text').innerText = "Target room not found in layout map.";
            }}

            window.setExploded = function(isExploded) {{
                floorGroups.forEach(fg => fg.visible = true);
                if (isExploded) {{
                    floorGroups[0].position.y = 0;
                    floorGroups[1].position.y = 20;
                    floorGroups[2].position.y = 40;
                }} else {{
                    floorGroups[0].position.y = baseFloorHeights[0];
                    floorGroups[1].position.y = baseFloorHeights[1];
                    floorGroups[2].position.y = baseFloorHeights[2];
                }}
            }};

            window.isolateFloor = function(flIdx) {{
                floorGroups.forEach((fg, idx) => {{
                    fg.visible = (idx === flIdx);
                    if (idx === flIdx) fg.position.y = 0;
                }});
            }};

            window.resetView = function() {{
                floorGroups.forEach((fg, idx) => {{
                    fg.visible = true;
                    fg.position.y = baseFloorHeights[idx];
                }});
                camera.position.set(65, 55, 75);
                controls.target.set(0, 15, 0);
            }};

            const clock = new THREE.Clock();
            function animate() {{
                requestAnimationFrame(animate);
                const t = clock.getElapsedTime();
                
                if (targetPinMesh) {{
                    targetPinMesh.position.y = 12 + Math.sin(t * 4) * 0.9;
                    targetPinMesh.rotation.y += 0.04;
                }}

                if (animatedMarker && pathCurve) {{
                    const progress = (t * 0.25) % 1;
                    const pos = pathCurve.getPointAt(progress);
                    animatedMarker.position.copy(pos);
                }}
                
                controls.update();
                renderer.render(scene, camera);
            }}

            animate();

            window.addEventListener('resize', () => {{
                const w = container.clientWidth || 900;
                camera.aspect = w / height;
                camera.updateProjectionMatrix();
                renderer.setSize(w, height);
            }});
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=600)

# ==========================================
# 6. APP NAVIGATION & PAGES
# ==========================================
def render_header():
    col1, col2 = st.columns([1, 5])
    with col1:
        st.write("🎓")
    with col2:
        st.title("SVCE Bengaluru")
        st.subheader("Sri Venkateshwara College of Engineering - Exam Portal")
    st.divider()

def render_marquee():
    marquee_html = """
    <div class="campus-marquee">
        <div class="campus-marquee-track">
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="Campus View 1">
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9643.webp" alt="Campus View 2">
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9645.webp" alt="Campus View 3">
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="Campus View 1">
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9643.webp" alt="Campus View 2">
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9645.webp" alt="Campus View 3">
        </div>
    </div>
    """
    st.markdown(marquee_html, unsafe_allow_html=True)

# Navigation Bar
nav_col1, nav_col2, nav_col3 = st.columns(3)
with nav_col1:
    if st.button("🏠 Home", use_container_width=True):
        st.session_state.current_page = 'Home'
        st.rerun()
with nav_col2:
    if st.button("👨‍🎓 Student Portal", use_container_width=True):
        st.session_state.current_page = 'Student'
        st.rerun()
with nav_col3:
    if st.button("🔒 Admin Portal", use_container_width=True):
        st.session_state.current_page = 'Admin'
        st.rerun()

st.write("---")

# ------------------------------------------
# PAGE 1: HOME
# ------------------------------------------
if st.session_state.current_page == 'Home':
    render_header()
    render_marquee()
    st.markdown("""
    ### Welcome to the SVCE Examination & Seating Management Portal
    
    This portal allows students to view their real-time seat allotments and navigate campus exam halls using our **3D Wayfinding Blueprint Engine**.
    
    * **Students:** Click on **Student Portal** above to enter your USN and locate your exam room and bench.
    * **Administrators:** Access the **Admin Portal** to upload master student lists, generate randomized seating allocations, and update credentials.
    """)

# ------------------------------------------
# PAGE 2: STUDENT PORTAL
# ------------------------------------------
elif st.session_state.current_page == 'Student':
    render_header()
    st.subheader("🔎 Student Seating Allotment Finder")
    
    usn_input = st.text_input("Enter your USN (e.g., 1VE21CS001):", placeholder="1VE...").strip().upper()
    
    if st.button("Search Allotment", type="primary"):
        if not usn_input:
            st.warning("Please enter a valid USN.")
        else:
            data = fetch_student_allotment(usn_input)
            if data:
                usn, name, college, event, room, floor, bench = data
                st.success(f"Allotment Found for {name} ({usn})")
                
                col1, col2, col3 = st.columns(3)
                col1.metric("Exam/Event", event)
                col2.metric("Room Number", room)
                col3.metric("Bench Number", f"Bench #{bench} ({floor})")
                
                st.markdown("### 🗺️ 3D Campus Navigation & Seat Blueprint")
                render_3d_college_blueprint(room, floor, bench)
            else:
                st.error("No allotment found for the entered USN. Please verify with the exam controller.")

# ------------------------------------------
# PAGE 3: ADMIN PORTAL
# ------------------------------------------
elif st.session_state.current_page == 'Admin':
    st.title("🔒 Admin Management Portal")
    
    # Step 0: Authentication
    if st.session_state.admin_auth_step == 0:
        st.subheader("Admin Login")
        admin_email = st.text_input("Admin Email Address", placeholder="admin@svce.edu.in")
        admin_pass = st.text_input("Admin Password", type="password")
        
        if st.button("Request Verification OTP"):
            if admin_pass == get_admin_password() and admin_email:
                otp = ''.join(random.choices(string.digits, k=6))
                st.session_state.generated_otp = otp
                st.session_state.admin_email = admin_email
                
                success, msg = send_email_otp(admin_email, otp)
                if success:
                    st.success(msg)
                else:
                    st.warning(f"{msg}\n\n👉 **Fallback OTP (for testing):** `{otp}`")
                
                st.session_state.admin_auth_step = 1
                st.rerun()
            else:
                st.error("Invalid password or missing email.")
                
    # Step 1: OTP Verification
    elif st.session_state.admin_auth_step == 1:
        st.subheader(f"Enter OTP sent to {st.session_state.admin_email}")
        user_otp = st.text_input("6-Digit OTP", max_chars=6)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Verify OTP", type="primary"):
                if user_otp == st.session_state.generated_otp:
                    st.session_state.admin_auth_step = 2
                    st.success("Access Granted!")
                    st.rerun()
                else:
                    st.error("Invalid OTP code.")
        with col2:
            if st.button("Back to Login"):
                st.session_state.admin_auth_step = 0
                st.rerun()

    # Step 2: Admin Dashboard
    elif st.session_state.admin_auth_step == 2:
        st.success("Authenticated as Administrator")
        
        tab1, tab2, tab3 = st.tabs(["📋 Upload & Allocate Seating", "📊 Current Allotments", "🔑 Security Settings"])
        
        with tab1:
            st.subheader("Generate Seating Allocations")
            uploaded_file = st.file_uploader("Upload Student List CSV/Excel", type=["csv", "xlsx"])
            
            if uploaded_file:
                if uploaded_file.name.endswith('.csv'):
                    df = pd.read_csv(uploaded_file)
                else:
                    df = pd.read_excel(uploaded_file)
                
                st.write("Preview Uploaded Data:", df.head())
                
                required_cols = ['USN', 'Student Name', 'College Name', 'Event/Exam Name']
                if all(col in df.columns for col in required_cols):
                    if st.button("Randomize & Save Allotments"):
                        rooms = ['EB-101', 'EB-102', 'EB-201', 'EB-202', 'WB-101', 'WB-201', 'CB-301']
                        floors = ['Ground Floor', 'Ground Floor', 'First Floor', 'First Floor', 'Ground Floor', 'First Floor', 'Second Floor']
                        
                        allocated_rows = []
                        for idx, row in df.iterrows():
                            r_idx = random.randint(0, len(rooms) - 1)
                            allocated_rows.append({
                                'USN': row['USN'],
                                'Student Name': row['Student Name'],
                                'College Name': row['College Name'],
                                'Event/Exam Name': row['Event/Exam Name'],
                                'Room Number': rooms[r_idx],
                                'Floor': floors[r_idx],
                                'Bench Number': random.randint(1, 30)
                            })
                        
                        df_allocated = pd.DataFrame(allocated_rows)
                        save_allotments(df_allocated)
                        st.success("Seating allocation generated and saved to database successfully!")
                else:
                    st.error(f"Missing required columns. File must contain: {', '.join(required_cols)}")

        with tab2:
            st.subheader("Database Master Allotment List")
            df_all = get_all_allotments()
            if not df_all.empty:
                st.dataframe(df_all, use_container_width=True)
                csv = df_all.to_csv(index=False).encode('utf-8')
                st.download_button("Download Allotment CSV", data=csv, file_name="SVCE_Exam_Allotments.csv", mime="text/csv")
            else:
                st.info("No allotments currently found in database.")

        with tab3:
            st.subheader("Change Admin Password")
            new_password = st.text_input("New Password", type="password")
            confirm_password = st.text_input("Confirm New Password", type="password")
            
            if st.button("Update Password"):
                if new_password and new_password == confirm_password:
                    update_admin_password(new_password)
                    st.success("Admin password updated successfully!")
                else:
                    st.error("Passwords do not match or are empty.")
                    
        st.divider()
        if st.button("Log Out"):
            st.session_state.admin_auth_step = 0
            st.rerun()

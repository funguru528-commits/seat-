import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sqlite3
import random
import string
import time
import smtplib
from email.mime.text import MIMEText
from PIL import Image, ImageDraw
import io

# ==========================================
# 1. SESSION STATE INITIALIZATION
# ==========================================
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'Home'
if 'admin_auth_step' not in st.session_state:
    st.session_state.admin_auth_step = 0 # 0: Password & Email, 1: OTP Verification, 2: Access Granted
if 'generated_otp' not in st.session_state:
    st.session_state.generated_otp = None
if 'admin_email' not in st.session_state:
    st.session_state.admin_email = None

# ==========================================
# 2. PAGE CONFIGURATION & DYNAMIC STYLING
# ==========================================
st.set_page_config(
    page_title="SVCE Bengaluru - Exam Portal",
    page_icon="🎓",
    layout="wide"
)

def inject_custom_styles():
    """
    Injects styles based on the active page.
    CSS strings are flush-left to prevent Streamlit from rendering them as code blocks.
    """
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
/* Moving Campus Banner Styling */
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

init_db()

# ==========================================
# 4. GMAIL OTP INTEGRATION
# ==========================================
def send_email_otp(target_email, otp):
    """
    Sends an email OTP using Gmail's SMTP server via funguru528@gmail.com
    """
    SENDER_EMAIL = "funguru528@gmail.com"
    SENDER_APP_PASSWORD = "yigscoygwoqdbmsd"

    try:
        msg = MIMEText(f"Security Alert: Your SVCE Admin login OTP is {otp}. Do not share this with anyone.")
        msg['Subject'] = 'SVCE Portal - Admin Login Verification'
        msg['From'] = SENDER_EMAIL
        msg['To'] = target_email

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.send_message(msg)
            
        return True, "Email Sent Successfully"
    except Exception as e:
        return False, str(e)

# ==========================================
# 5. MULTI-TIER 3D BLUEPRINT ENGINE (THREE.JS)
# ==========================================
def render_3d_college_blueprint(target_room, target_floor, bench_no):
    """
    Synthesizes Ground, 1st, and 2nd Floor blueprints with 4 Red Staircase connectors
    into a fully rotatable, explodable 3D WebGL architecture model.
    """
    room_clean = str(target_room).upper().strip().replace(" ", "")
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; overflow: hidden; background: #070d1f; font-family: 'Times New Roman', serif; }}
            #canvas-container {{ width: 100%; height: 550px; position: relative; }}
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
                bottom: 12px;
                left: 12px;
                right: 12px;
                display: flex;
                justify-content: space-between;
                background: rgba(0,0,0,0.65);
                border-radius: 6px;
                padding: 6px 12px;
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
            
            <div class="view-toolbar">
                <button class="view-btn" onclick="setExploded(false)">🏢 Stacked View</button>
                <button class="view-btn" onclick="setExploded(true)">📂 Explode Floors</button>
                <button class="view-btn" onclick="isolateFloor(0)">Gnd Floor</button>
                <button class="view-btn" onclick="isolateFloor(1)">1st Floor</button>
                <button class="view-btn" onclick="isolateFloor(2)">2nd Floor</button>
                <button class="view-btn" onclick="resetView()">🔄 Reset 360°</button>
            </div>

            <div class="controls-hint">
                <span>🖱️ <b>Left Click + Drag:</b> Rotate 360° | <b>Scroll:</b> Zoom | <b>Right Click:</b> Pan</span>
                <span>🔴 <b>Red Towers:</b> Staircases Linking Adjacent Floors</span>
            </div>
        </div>

        <script>
            const container = document.getElementById('canvas-container');
            const width = container.clientWidth || 900;
            const height = 550;

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

            // Lighting
            scene.add(new THREE.AmbientLight(0xffffff, 0.85));
            const sun = new THREE.DirectionalLight(0xffffff, 0.9);
            sun.position.set(50, 80, 40);
            sun.castShadow = true;
            scene.add(sun);

            const gridHelper = new THREE.GridHelper(120, 30, 0x1e3a5f, 0x0f172a);
            gridHelper.position.y = -0.5;
            scene.add(gridHelper);

            // Text Sprite Helper
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
            const floorGroups = [];

            // Helper to build room blocks
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
                }}

                group.position.set(x, y, z);
                return group;
            }}

            // Helper to build floor slab
            function createFloorSlab(floorName) {{
                const slabGroup = new THREE.Group();
                // Base slab layout following blueprints
                // Main Rear Block
                const rear = new THREE.Mesh(new THREE.BoxGeometry(76, 0.6, 26), new THREE.MeshStandardMaterial({{ color: 0x0f172a, roughness: 0.7 }}));
                rear.position.set(0, 0, -13);
                slabGroup.add(rear);

                // East Wing (Left)
                const east = new THREE.Mesh(new THREE.BoxGeometry(16, 0.6, 38), new THREE.MeshStandardMaterial({{ color: 0x0f172a, roughness: 0.7 }}));
                east.position.set(-30, 0, 19);
                slabGroup.add(east);

                // West Wing (Right)
                const west = new THREE.Mesh(new THREE.BoxGeometry(16, 0.6, 38), new THREE.MeshStandardMaterial({{ color: 0x0f172a, roughness: 0.7 }}));
                west.position.set(30, 0, 19);
                slabGroup.add(west);

                const banner = makeTextSprite(floorName, "#38bdf8", "rgba(15, 23, 42, 0.9)", true);
                banner.position.set(0, 1, 38);
                banner.scale.set(16, 8, 1);
                slabGroup.add(banner);

                return slabGroup;
            }}

            // -------------------------------------------------------------
            // BUILD 3 FLOORS FROM BLUEPRINTS
            // -------------------------------------------------------------
            const floorConfigs = [
                {{
                    name: "GROUND FLOOR",
                    rooms: [
                        // East Wing (Left)
                        {{ name: "EB-101", x: -30, z: 32, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-102", x: -30, z: 23, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-103", x: -30, z: 14, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-104", x: -30, z: 5, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-106 Toilet", x: -30, z: -4, w: 12, h: 5.5, d: 7 }},
                        {{ name: "EB-107 Lab", x: -30, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-108 Lab", x: -30, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-111 Lab", x: -16, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-122 Comp Center", x: -16, z: -13, w: 12, h: 5.5, d: 8 }},
                        // Central Block
                        {{ name: "CB-111 Main Office", x: 0, z: -16, w: 16, h: 5.5, d: 18 }},
                        // West Wing (Right)
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
                        // East Wing (Left)
                        {{ name: "EB-201 Lecture", x: -30, z: 32, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-202 Lecture", x: -30, z: 23, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-203 Lecture", x: -30, z: 14, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-204 Faculty", x: -30, z: 5, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-206 Toilet", x: -30, z: -4, w: 12, h: 5.5, d: 7 }},
                        {{ name: "EB-207 Lab", x: -30, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-208 Lab", x: -30, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-213 Lab", x: -16, z: -13, w: 12, h: 5.5, d: 8 }},
                        // Central Block
                        {{ name: "CB-204 Dean Office", x: -7, z: -15, w: 10, h: 5.5, d: 8 }},
                        {{ name: "CB-201 Placement", x: 7, z: -15, w: 10, h: 5.5, d: 8 }},
                        {{ name: "CB-203 Seminar Hall", x: 0, z: -22, w: 20, h: 5.5, d: 8 }},
                        // West Wing (Right)
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
                        // East Wing (Left)
                        {{ name: "EB-301 Lecture", x: -30, z: 32, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-302 Lecture", x: -30, z: 23, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-303 Lecture", x: -30, z: 14, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-304 Faculty", x: -30, z: 5, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-306 Toilet", x: -30, z: -4, w: 12, h: 5.5, d: 7 }},
                        {{ name: "EB-307 Lecture", x: -30, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-308 Studio", x: -30, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-314 Comp Center", x: -16, z: -13, w: 12, h: 5.5, d: 8 }},
                        // Central Block
                        {{ name: "CB-301 Auditorium", x: 0, z: -18, w: 22, h: 7, d: 16 }},
                        // West Wing (Right)
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

            const baseFloorHeights = [0, 11, 22];

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

            // -------------------------------------------------------------
            // 4 RED STAIRCASES CONNECTING ADJACENT FLOORS (FROM BLUEPRINTS)
            // -------------------------------------------------------------
            const stairPositions = [
                {{ name: "East Stairs (EB)", x: -30, z: 0, w: 12, d: 8 }},
                {{ name: "Central Left Stairs", x: -9, z: 0, w: 9, d: 8 }},
                {{ name: "Central Right Stairs", x: 9, z: 0, w: 9, d: 8 }},
                {{ name: "West Stairs (WB)", x: 30, z: 0, w: 12, d: 8 }}
            ];

            const stairMeshes = [];

            stairPositions.forEach(pos => {{
                // Continuous Red Vertical Column / Shaft through all floors
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

                // Wireframe edges on stairs
                const edges = new THREE.EdgesGeometry(shaftGeo);
                const wire = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({{ color: 0xffffff, linewidth: 2 }}));
                wire.position.set(pos.x, totalH / 2, pos.z);
                scene.add(wire);

                // Stair treads simulation
                for (let stepY = 1; stepY < totalH; stepY += 2) {{
                    const stepGeo = new THREE.BoxGeometry(pos.w - 1, 0.4, pos.d - 1);
                    const step = new THREE.Mesh(stepGeo, new THREE.MeshBasicMaterial({{ color: 0xffffff }}));
                    step.position.set(pos.x, stepY, pos.z);
                    scene.add(step);
                }}

                // Stair Top Label
                const label = makeTextSprite("🔴 " + pos.name, "#ffffff", "rgba(220, 38, 38, 0.9)", true);
                label.position.set(pos.x, totalH + 3, pos.z);
                scene.add(label);
            }});

            // -------------------------------------------------------------
            // INTERACTIVE TOOLBAR FUNCTIONS
            // -------------------------------------------------------------
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

            // -------------------------------------------------------------
            // ANIMATION LOOP
            // -------------------------------------------------------------
            const clock = new THREE.Clock();
            function animate() {{
                requestAnimationFrame(animate);
                const t = clock.getElapsedTime();
                
                // Floating pin animation
                if (targetPinMesh) {{
                    targetPinMesh.position.y = 12 + Math.sin(t * 4) * 0.9;
                    targetPinMesh.rotation.y += 0.04;
                }}
                
                // Subtle pulse on Red Staircases
                stairMeshes.forEach(mesh => {{
                    mesh.material.emissiveIntensity = 0.5 + Math.sin(t * 3) * 0.25;
                }});

                controls.update();
                renderer.render(scene, camera);
            }}
            animate();

            window.addEventListener('resize', () => {{
                const newW = container.clientWidth;
                camera.aspect = newW / height;
                camera.updateProjectionMatrix();
                renderer.setSize(newW, height);
            }});
        </script>
    </body>
    </html>
    """
    return html_code

# ==========================================
# 6. CAPTCHA & NAVIGATION
# ==========================================
def generate_captcha_image(text):
    img = Image.new('RGB', (160, 50), color=(240, 244, 248))
    draw = ImageDraw.Draw(img)
    for _ in range(6):
        draw.line([(random.randint(0, 160), random.randint(0, 50)), 
                   (random.randint(0, 160), random.randint(0, 50))], fill=(160, 170, 180), width=2)
    draw.text((25, 12), text, fill=(10, 20, 40))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

if "student_captcha" not in st.session_state:
    st.session_state.student_captcha = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

def refresh_student_captcha():
    st.session_state.student_captcha = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

def navigate_to(page):
    st.session_state.current_page = page
    if page == 'Home':
        st.session_state.admin_auth_step = 0
        st.session_state.generated_otp = None
        st.session_state.admin_email = None
    st.rerun()

# ==========================================
# 7. PAGE ROUTING
# ==========================================

# --- PAGE: HOME ---
if st.session_state.current_page == 'Home':
    st.title("🎓 Sri Venkateshwara College of Engineering")
    st.subheader("Welcome to the Seat Allotment Portal")
    
    marquee_html = """
    <div class="campus-marquee">
        <div class="campus-marquee-track">
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 1"/>
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 2"/>
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 3"/>
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 4"/>
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 5"/>
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 6"/>
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 7"/>
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 8"/>
        </div>
    </div>
    """
    st.markdown(marquee_html, unsafe_allow_html=True)
    st.markdown("Please select your role to continue:")
    
    st.write("") 
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🧑‍🎓 I am a Student", use_container_width=True):
            navigate_to('Student')
        st.write("")
        if st.button("🔐 I am an Admin", use_container_width=True):
            navigate_to('Admin')

# --- PAGE: STUDENT ---
elif st.session_state.current_page == 'Student':
    st.button("⬅️ Back to Home", on_click=navigate_to, args=('Home',))
    st.markdown("### Find Your Room & Seat Allotment")
    
    usn_input = st.text_input("Enter your USN / Registration Number:").strip().upper()
    
    col_cap1, col_cap2 = st.columns([1, 2])
    with col_cap1:
        captcha_bytes = generate_captcha_image(st.session_state.student_captcha)
        st.image(captcha_bytes, caption="Verification CAPTCHA Code")
    with col_cap2:
        captcha_input = st.text_input("Enter CAPTCHA Code:").strip().upper()
    
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("🔄 Refresh CAPTCHA"):
            refresh_student_captcha()
            st.rerun()

    with col_btn2:
        search_clicked = st.button("🔍 Search Allotment", type="primary")

    if search_clicked:
        if captcha_input != st.session_state.student_captcha:
            st.error("❌ Incorrect CAPTCHA. Please try again.")
            refresh_student_captcha()
        elif not usn_input:
            st.warning("⚠️ Please enter a valid USN.")
        else:
            student = fetch_student_allotment(usn_input)
            if student:
                usn, name, college, event, room, floor, bench = student
                st.success(f"✅ Allotment Found for **{name}**")
                
                # Allotment Details Card
                st.markdown(f"""
                ### 📋 Your Allotment Details:
                * **Student Name:** `{name}`
                * **USN:** `{usn}`
                * **College:** `{college}`
                * **Exam/Event:** `{event}`
                * **Assigned Room:** **{room}**
                * **Floor:** **{floor}**
                * **Bench Number:** **Bench #{bench}**
                """)
                
                st.markdown("---")
                st.markdown("### 🌐 3D Interactive Campus Blueprint (Ground + 1st + 2nd Floor)")
                st.caption("🖱️ **Drag to rotate 360° • Scroll to zoom • Use top buttons to separate floors.**")
                
                # Render 3D Model with Red Stairs and Highlighted Classroom
                blueprint_3d_html = render_3d_college_blueprint(room, floor, bench)
                components.html(blueprint_3d_html, height=570)
                
                # Dynamic Stairway Navigation Guidance
                room_upper = str(room).upper()
                if "EB" in room_upper:
                    nearest_stair = "🔴 **East Wing Staircase** (adjacent to EB-106 / EB-206 / EB-306)"
                elif "WB" in room_upper:
                    nearest_stair = "🔴 **West Wing Staircase** (adjacent to WB-106 / WB-206 / WB-306)"
                else:
                    nearest_stair = "🔴 **Central Stairs (Left or Right)** in the Main Courtyard Atrium"

                st.info(f"""
                **🚶 Turn-by-Turn Navigation Steps:**
                1. Enter through the **Main Front Courtyard / Atrium Gate**.
                2. {"Stay on the Ground Floor and walk straight to your room." if "GROUND" in str(floor).upper() or "0" in str(floor) else f"To reach the {floor}, take the {nearest_stair}."}
                3. Locate classroom **{room}** (indicated by the glowing beacon in the 3D map above) and sit at **Bench #{bench}**.
                """)
            else:
                st.error("❌ No allotment found for this USN. Please verify your details at the Security Desk.")

# --- PAGE: ADMIN ---
elif st.session_state.current_page == 'Admin':
    
    # ADMIN AUTHENTICATION FLOW
    if st.session_state.admin_auth_step < 2:
        st.button("⬅️ Cancel & Return Home", on_click=navigate_to, args=('Home',))
        st.markdown("### 🔒 System Administrator Access")
        
        # Step 1: Password & Email Verification
        if st.session_state.admin_auth_step == 0:
            current_stored_pass = get_admin_password()
            
            st.markdown("#### Step 1: Secure Login")
            admin_pass_input = st.text_input("Enter Master Password", type="password")
            admin_email_input = st.text_input("Enter Admin Email Address for OTP Delivery", value="funguru528@gmail.com")
            
            if st.button("Send Verification OTP", type="primary"):
                if admin_pass_input != current_stored_pass:
                    st.error("❌ Incorrect master password.")
                elif not admin_email_input or "@" not in admin_email_input:
                    st.warning("⚠️ Please enter a valid email address.")
                else:
                    st.session_state.generated_otp = "".join(random.choices(string.digits, k=6))
                    st.session_state.admin_email = admin_email_input
                    
                    with st.spinner("Dispatching secure email to inbox..."):
                        email_success, email_msg = send_email_otp(st.session_state.admin_email, st.session_state.generated_otp)
                        time.sleep(1)
                        
                    if email_success:
                        st.session_state.email_status = "sent"
                    else:
                        st.session_state.email_status = email_msg
                    
                    st.session_state.admin_auth_step = 1
                    st.rerun()
        
        # Step 2: OTP Verification
        elif st.session_state.admin_auth_step == 1:
            st.success("✅ Password Verified.")
            
            if st.session_state.email_status == "sent":
                st.info(f"📧 **Email OTP Sent from funguru528@gmail.com!** Check your inbox ({st.session_state.admin_email}) for the 6-digit code.")
            else:
                st.warning(f"⚠️ **Email Dispatch Status:** {st.session_state.email_status}. Operating in Fallback/Simulation Mode.")
                st.info(f"📧 **Simulation/Fallback Mode OTP:** ` {st.session_state.generated_otp} `")
            
            otp_input = st.text_input("Step 2: Enter 6-Digit OTP Code", max_chars=6).strip()
            
            col_otp1, col_otp2 = st.columns([1, 1])
            with col_otp1:
                if st.button("Verify & Login", type="primary"):
                    if otp_input == st.session_state.generated_otp:
                        st.session_state.admin_auth_step = 2
                        st.rerun()
                    else:
                        st.error("❌ Invalid or incorrect OTP code. Please try again.")
            with col_otp2:
                if st.button("Cancel / Restart Login"):
                    st.session_state.admin_auth_step = 0
                    st.rerun()

    # ADMIN DASHBOARD (Unlocked)
    if st.session_state.admin_auth_step == 2:
        col_head1, col_head2 = st.columns([3, 1])
        with col_head1:
            st.success("🔓 Administrator Session Active.")
        with col_head2:
            if st.button("🚪 Admin Logout", type="secondary"):
                st.session_state.admin_auth_step = 0
                st.session_state.generated_otp = None
                navigate_to('Home')

        st.markdown("### Admin Panel — Automated Room Allocation")
        
        st.markdown("#### Step 1: Upload Student List")
        st.caption("Required Excel/CSV columns: `USN`, `Student Name`, `College Name`, `Event/Exam Name`")
        uploaded_file = st.file_uploader("Upload Student Master Sheet", type=["xlsx", "csv"])
        
        st.markdown("#### Step 2: Set Room Capacity & Floors")
        
        # Updated Default Rooms matching the actual College Blueprint
        default_rooms = pd.DataFrame([
            {"Room Number": "WB-209", "Floor": "1st Floor", "Capacity": 30},
            {"Room Number": "EB-201", "Floor": "1st Floor", "Capacity": 30},
            {"Room Number": "WB-308", "Floor": "2nd Floor", "Capacity": 35},
            {"Room Number": "CB-301", "Floor": "2nd Floor", "Capacity": 35},
        ])
        edited_rooms = st.data_editor(default_rooms, num_rows="dynamic")
        
        if uploaded_file and st.button("⚙️ Generate & Save Allotments", type="primary"):
            try:
                if uploaded_file.name.endswith(".csv"):
                    df_students = pd.read_csv(uploaded_file)
                else:
                    df_students = pd.read_excel(uploaded_file)
                
                allocated_data = []
                student_idx = 0
                total_students = len(df_students)
                
                for _, room_row in edited_rooms.iterrows():
                    r_num = room_row["Room Number"]
                    r_floor = room_row["Floor"]
                    cap = int(room_row["Capacity"])
                    
                    bench = 1
                    for _ in range(cap):
                        if student_idx >= total_students:
                            break
                        student = df_students.iloc[student_idx]
                        allocated_data.append({
                            "USN": str(student["USN"]).strip().upper(),
                            "Student Name": student["Student Name"],
                            "College Name": student["College Name"],
                            "Event/Exam Name": student["Event/Exam Name"],
                            "Room Number": r_num,
                            "Floor": r_floor,
                            "Bench Number": bench
                        })
                        student_idx += 1
                        bench += 1
                        
                df_final = pd.DataFrame(allocated_data)
                save_allotments(df_final)
                
                st.success(f"🎉 Successfully allocated {len(df_final)} of {total_students} students!")
                st.dataframe(df_final)
                
                csv_buffer = df_final.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Master Allotment CSV",
                    data=csv_buffer, 
                    file_name="SVCE_Master_Allotment.csv",
                    mime="text/csv"
                )
                
            except Exception as e:
                st.error(f"❌ Error during processing: {str(e)}")import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sqlite3
import random
import string
import time
import smtplib
from email.mime.text import MIMEText
from PIL import Image, ImageDraw
import io

# ==========================================
# 1. SESSION STATE INITIALIZATION
# ==========================================
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'Home'
if 'admin_auth_step' not in st.session_state:
    st.session_state.admin_auth_step = 0 # 0: Password & Email, 1: OTP Verification, 2: Access Granted
if 'generated_otp' not in st.session_state:
    st.session_state.generated_otp = None
if 'admin_email' not in st.session_state:
    st.session_state.admin_email = None

# ==========================================
# 2. PAGE CONFIGURATION & DYNAMIC STYLING
# ==========================================
st.set_page_config(
    page_title="SVCE Bengaluru - Exam Portal",
    page_icon="🎓",
    layout="wide"
)

def inject_custom_styles():
    """
    Injects styles based on the active page.
    CSS strings are flush-left to prevent Streamlit from rendering them as code blocks.
    """
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
/* Moving Campus Banner Styling */
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

init_db()

# ==========================================
# 4. GMAIL OTP INTEGRATION
# ==========================================
def send_email_otp(target_email, otp):
    """
    Sends an email OTP using Gmail's SMTP server via funguru528@gmail.com
    """
    SENDER_EMAIL = "funguru528@gmail.com"
    SENDER_APP_PASSWORD = "yigscoygwoqdbmsd"

    try:
        msg = MIMEText(f"Security Alert: Your SVCE Admin login OTP is {otp}. Do not share this with anyone.")
        msg['Subject'] = 'SVCE Portal - Admin Login Verification'
        msg['From'] = SENDER_EMAIL
        msg['To'] = target_email

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.send_message(msg)
            
        return True, "Email Sent Successfully"
    except Exception as e:
        return False, str(e)

# ==========================================
# 5. MULTI-TIER 3D BLUEPRINT ENGINE (THREE.JS)
# ==========================================
def render_3d_college_blueprint(target_room, target_floor, bench_no):
    """
    Synthesizes Ground, 1st, and 2nd Floor blueprints with 4 Red Staircase connectors
    into a fully rotatable, explodable 3D WebGL architecture model.
    """
    room_clean = str(target_room).upper().strip().replace(" ", "")
    
    html_code = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            body {{ margin: 0; padding: 0; overflow: hidden; background: #070d1f; font-family: 'Times New Roman', serif; }}
            #canvas-container {{ width: 100%; height: 550px; position: relative; }}
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
                bottom: 12px;
                left: 12px;
                right: 12px;
                display: flex;
                justify-content: space-between;
                background: rgba(0,0,0,0.65);
                border-radius: 6px;
                padding: 6px 12px;
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
            
            <div class="view-toolbar">
                <button class="view-btn" onclick="setExploded(false)">🏢 Stacked View</button>
                <button class="view-btn" onclick="setExploded(true)">📂 Explode Floors</button>
                <button class="view-btn" onclick="isolateFloor(0)">Gnd Floor</button>
                <button class="view-btn" onclick="isolateFloor(1)">1st Floor</button>
                <button class="view-btn" onclick="isolateFloor(2)">2nd Floor</button>
                <button class="view-btn" onclick="resetView()">🔄 Reset 360°</button>
            </div>

            <div class="controls-hint">
                <span>🖱️ <b>Left Click + Drag:</b> Rotate 360° | <b>Scroll:</b> Zoom | <b>Right Click:</b> Pan</span>
                <span>🔴 <b>Red Towers:</b> Staircases Linking Adjacent Floors</span>
            </div>
        </div>

        <script>
            const container = document.getElementById('canvas-container');
            const width = container.clientWidth || 900;
            const height = 550;

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

            // Lighting
            scene.add(new THREE.AmbientLight(0xffffff, 0.85));
            const sun = new THREE.DirectionalLight(0xffffff, 0.9);
            sun.position.set(50, 80, 40);
            sun.castShadow = true;
            scene.add(sun);

            const gridHelper = new THREE.GridHelper(120, 30, 0x1e3a5f, 0x0f172a);
            gridHelper.position.y = -0.5;
            scene.add(gridHelper);

            // Text Sprite Helper
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
            const floorGroups = [];

            // Helper to build room blocks
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
                }}

                group.position.set(x, y, z);
                return group;
            }}

            // Helper to build floor slab
            function createFloorSlab(floorName) {{
                const slabGroup = new THREE.Group();
                // Base slab layout following blueprints
                // Main Rear Block
                const rear = new THREE.Mesh(new THREE.BoxGeometry(76, 0.6, 26), new THREE.MeshStandardMaterial({{ color: 0x0f172a, roughness: 0.7 }}));
                rear.position.set(0, 0, -13);
                slabGroup.add(rear);

                // East Wing (Left)
                const east = new THREE.Mesh(new THREE.BoxGeometry(16, 0.6, 38), new THREE.MeshStandardMaterial({{ color: 0x0f172a, roughness: 0.7 }}));
                east.position.set(-30, 0, 19);
                slabGroup.add(east);

                // West Wing (Right)
                const west = new THREE.Mesh(new THREE.BoxGeometry(16, 0.6, 38), new THREE.MeshStandardMaterial({{ color: 0x0f172a, roughness: 0.7 }}));
                west.position.set(30, 0, 19);
                slabGroup.add(west);

                const banner = makeTextSprite(floorName, "#38bdf8", "rgba(15, 23, 42, 0.9)", true);
                banner.position.set(0, 1, 38);
                banner.scale.set(16, 8, 1);
                slabGroup.add(banner);

                return slabGroup;
            }}

            // -------------------------------------------------------------
            // BUILD 3 FLOORS FROM BLUEPRINTS
            // -------------------------------------------------------------
            const floorConfigs = [
                {{
                    name: "GROUND FLOOR",
                    rooms: [
                        // East Wing (Left)
                        {{ name: "EB-101", x: -30, z: 32, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-102", x: -30, z: 23, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-103", x: -30, z: 14, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-104", x: -30, z: 5, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-106 Toilet", x: -30, z: -4, w: 12, h: 5.5, d: 7 }},
                        {{ name: "EB-107 Lab", x: -30, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-108 Lab", x: -30, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-111 Lab", x: -16, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-122 Comp Center", x: -16, z: -13, w: 12, h: 5.5, d: 8 }},
                        // Central Block
                        {{ name: "CB-111 Main Office", x: 0, z: -16, w: 16, h: 5.5, d: 18 }},
                        // West Wing (Right)
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
                        // East Wing (Left)
                        {{ name: "EB-201 Lecture", x: -30, z: 32, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-202 Lecture", x: -30, z: 23, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-203 Lecture", x: -30, z: 14, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-204 Faculty", x: -30, z: 5, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-206 Toilet", x: -30, z: -4, w: 12, h: 5.5, d: 7 }},
                        {{ name: "EB-207 Lab", x: -30, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-208 Lab", x: -30, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-213 Lab", x: -16, z: -13, w: 12, h: 5.5, d: 8 }},
                        // Central Block
                        {{ name: "CB-204 Dean Office", x: -7, z: -15, w: 10, h: 5.5, d: 8 }},
                        {{ name: "CB-201 Placement", x: 7, z: -15, w: 10, h: 5.5, d: 8 }},
                        {{ name: "CB-203 Seminar Hall", x: 0, z: -22, w: 20, h: 5.5, d: 8 }},
                        // West Wing (Right)
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
                        // East Wing (Left)
                        {{ name: "EB-301 Lecture", x: -30, z: 32, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-302 Lecture", x: -30, z: 23, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-303 Lecture", x: -30, z: 14, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-304 Faculty", x: -30, z: 5, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-306 Toilet", x: -30, z: -4, w: 12, h: 5.5, d: 7 }},
                        {{ name: "EB-307 Lecture", x: -30, z: -13, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-308 Studio", x: -30, z: -22, w: 12, h: 5.5, d: 8 }},
                        {{ name: "EB-314 Comp Center", x: -16, z: -13, w: 12, h: 5.5, d: 8 }},
                        // Central Block
                        {{ name: "CB-301 Auditorium", x: 0, z: -18, w: 22, h: 7, d: 16 }},
                        // West Wing (Right)
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

            const baseFloorHeights = [0, 11, 22];

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

            // -------------------------------------------------------------
            // 4 RED STAIRCASES CONNECTING ADJACENT FLOORS (FROM BLUEPRINTS)
            // -------------------------------------------------------------
            const stairPositions = [
                {{ name: "East Stairs (EB)", x: -30, z: 0, w: 12, d: 8 }},
                {{ name: "Central Left Stairs", x: -9, z: 0, w: 9, d: 8 }},
                {{ name: "Central Right Stairs", x: 9, z: 0, w: 9, d: 8 }},
                {{ name: "West Stairs (WB)", x: 30, z: 0, w: 12, d: 8 }}
            ];

            const stairMeshes = [];

            stairPositions.forEach(pos => {{
                // Continuous Red Vertical Column / Shaft through all floors
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

                // Wireframe edges on stairs
                const edges = new THREE.EdgesGeometry(shaftGeo);
                const wire = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({{ color: 0xffffff, linewidth: 2 }}));
                wire.position.set(pos.x, totalH / 2, pos.z);
                scene.add(wire);

                // Stair treads simulation
                for (let stepY = 1; stepY < totalH; stepY += 2) {{
                    const stepGeo = new THREE.BoxGeometry(pos.w - 1, 0.4, pos.d - 1);
                    const step = new THREE.Mesh(stepGeo, new THREE.MeshBasicMaterial({{ color: 0xffffff }}));
                    step.position.set(pos.x, stepY, pos.z);
                    scene.add(step);
                }}

                // Stair Top Label
                const label = makeTextSprite("🔴 " + pos.name, "#ffffff", "rgba(220, 38, 38, 0.9)", true);
                label.position.set(pos.x, totalH + 3, pos.z);
                scene.add(label);
            }});

            // -------------------------------------------------------------
            // INTERACTIVE TOOLBAR FUNCTIONS
            // -------------------------------------------------------------
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

            // -------------------------------------------------------------
            // ANIMATION LOOP
            // -------------------------------------------------------------
            const clock = new THREE.Clock();
            function animate() {{
                requestAnimationFrame(animate);
                const t = clock.getElapsedTime();
                
                // Floating pin animation
                if (targetPinMesh) {{
                    targetPinMesh.position.y = 12 + Math.sin(t * 4) * 0.9;
                    targetPinMesh.rotation.y += 0.04;
                }}
                
                // Subtle pulse on Red Staircases
                stairMeshes.forEach(mesh => {{
                    mesh.material.emissiveIntensity = 0.5 + Math.sin(t * 3) * 0.25;
                }});

                controls.update();
                renderer.render(scene, camera);
            }}
            animate();

            window.addEventListener('resize', () => {{
                const newW = container.clientWidth;
                camera.aspect = newW / height;
                camera.updateProjectionMatrix();
                renderer.setSize(newW, height);
            }});
        </script>
    </body>
    </html>
    """
    return html_code

# ==========================================
# 6. CAPTCHA & NAVIGATION
# ==========================================
def generate_captcha_image(text):
    img = Image.new('RGB', (160, 50), color=(240, 244, 248))
    draw = ImageDraw.Draw(img)
    for _ in range(6):
        draw.line([(random.randint(0, 160), random.randint(0, 50)), 
                   (random.randint(0, 160), random.randint(0, 50))], fill=(160, 170, 180), width=2)
    draw.text((25, 12), text, fill=(10, 20, 40))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

if "student_captcha" not in st.session_state:
    st.session_state.student_captcha = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

def refresh_student_captcha():
    st.session_state.student_captcha = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))

def navigate_to(page):
    st.session_state.current_page = page
    if page == 'Home':
        st.session_state.admin_auth_step = 0
        st.session_state.generated_otp = None
        st.session_state.admin_email = None
    st.rerun()

# ==========================================
# 7. PAGE ROUTING
# ==========================================

# --- PAGE: HOME ---
if st.session_state.current_page == 'Home':
    st.title("🎓 Sri Venkateshwara College of Engineering")
    st.subheader("Welcome to the Seat Allotment Portal")
    
    marquee_html = """
    <div class="campus-marquee">
        <div class="campus-marquee-track">
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 1"/>
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 2"/>
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 3"/>
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 4"/>
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 5"/>
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 6"/>
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 7"/>
            <img src="https://svcengg.edu.in/assets/bgimages/IMG_9641.webp" alt="SVCE Campus 8"/>
        </div>
    </div>
    """
    st.markdown(marquee_html, unsafe_allow_html=True)
    st.markdown("Please select your role to continue:")
    
    st.write("") 
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        if st.button("🧑‍🎓 I am a Student", use_container_width=True):
            navigate_to('Student')
        st.write("")
        if st.button("🔐 I am an Admin", use_container_width=True):
            navigate_to('Admin')

# --- PAGE: STUDENT ---
elif st.session_state.current_page == 'Student':
    st.button("⬅️ Back to Home", on_click=navigate_to, args=('Home',))
    st.markdown("### Find Your Room & Seat Allotment")
    
    usn_input = st.text_input("Enter your USN / Registration Number:").strip().upper()
    
    col_cap1, col_cap2 = st.columns([1, 2])
    with col_cap1:
        captcha_bytes = generate_captcha_image(st.session_state.student_captcha)
        st.image(captcha_bytes, caption="Verification CAPTCHA Code")
    with col_cap2:
        captcha_input = st.text_input("Enter CAPTCHA Code:").strip().upper()
    
    col_btn1, col_btn2 = st.columns([1, 1])
    with col_btn1:
        if st.button("🔄 Refresh CAPTCHA"):
            refresh_student_captcha()
            st.rerun()

    with col_btn2:
        search_clicked = st.button("🔍 Search Allotment", type="primary")

    if search_clicked:
        if captcha_input != st.session_state.student_captcha:
            st.error("❌ Incorrect CAPTCHA. Please try again.")
            refresh_student_captcha()
        elif not usn_input:
            st.warning("⚠️ Please enter a valid USN.")
        else:
            student = fetch_student_allotment(usn_input)
            if student:
                usn, name, college, event, room, floor, bench = student
                st.success(f"✅ Allotment Found for **{name}**")
                
                # Allotment Details Card
                st.markdown(f"""
                ### 📋 Your Allotment Details:
                * **Student Name:** `{name}`
                * **USN:** `{usn}`
                * **College:** `{college}`
                * **Exam/Event:** `{event}`
                * **Assigned Room:** **{room}**
                * **Floor:** **{floor}**
                * **Bench Number:** **Bench #{bench}**
                """)
                
                st.markdown("---")
                st.markdown("### 🌐 3D Interactive Campus Blueprint (Ground + 1st + 2nd Floor)")
                st.caption("🖱️ **Drag to rotate 360° • Scroll to zoom • Use top buttons to separate floors.**")
                
                # Render 3D Model with Red Stairs and Highlighted Classroom
                blueprint_3d_html = render_3d_college_blueprint(room, floor, bench)
                components.html(blueprint_3d_html, height=570)
                
                # Dynamic Stairway Navigation Guidance
                room_upper = str(room).upper()
                if "EB" in room_upper:
                    nearest_stair = "🔴 **East Wing Staircase** (adjacent to EB-106 / EB-206 / EB-306)"
                elif "WB" in room_upper:
                    nearest_stair = "🔴 **West Wing Staircase** (adjacent to WB-106 / WB-206 / WB-306)"
                else:
                    nearest_stair = "🔴 **Central Stairs (Left or Right)** in the Main Courtyard Atrium"

                st.info(f"""
                **🚶 Turn-by-Turn Navigation Steps:**
                1. Enter through the **Main Front Courtyard / Atrium Gate**.
                2. {"Stay on the Ground Floor and walk straight to your room." if "GROUND" in str(floor).upper() or "0" in str(floor) else f"To reach the {floor}, take the {nearest_stair}."}
                3. Locate classroom **{room}** (indicated by the glowing beacon in the 3D map above) and sit at **Bench #{bench}**.
                """)
            else:
                st.error("❌ No allotment found for this USN. Please verify your details at the Security Desk.")

# --- PAGE: ADMIN ---
elif st.session_state.current_page == 'Admin':
    
    # ADMIN AUTHENTICATION FLOW
    if st.session_state.admin_auth_step < 2:
        st.button("⬅️ Cancel & Return Home", on_click=navigate_to, args=('Home',))
        st.markdown("### 🔒 System Administrator Access")
        
        # Step 1: Password & Email Verification
        if st.session_state.admin_auth_step == 0:
            current_stored_pass = get_admin_password()
            
            st.markdown("#### Step 1: Secure Login")
            admin_pass_input = st.text_input("Enter Master Password", type="password")
            admin_email_input = st.text_input("Enter Admin Email Address for OTP Delivery", value="funguru528@gmail.com")
            
            if st.button("Send Verification OTP", type="primary"):
                if admin_pass_input != current_stored_pass:
                    st.error("❌ Incorrect master password.")
                elif not admin_email_input or "@" not in admin_email_input:
                    st.warning("⚠️ Please enter a valid email address.")
                else:
                    st.session_state.generated_otp = "".join(random.choices(string.digits, k=6))
                    st.session_state.admin_email = admin_email_input
                    
                    with st.spinner("Dispatching secure email to inbox..."):
                        email_success, email_msg = send_email_otp(st.session_state.admin_email, st.session_state.generated_otp)
                        time.sleep(1)
                        
                    if email_success:
                        st.session_state.email_status = "sent"
                    else:
                        st.session_state.email_status = email_msg
                    
                    st.session_state.admin_auth_step = 1
                    st.rerun()
        
        # Step 2: OTP Verification
        elif st.session_state.admin_auth_step == 1:
            st.success("✅ Password Verified.")
            
            if st.session_state.email_status == "sent":
                st.info(f"📧 **Email OTP Sent from funguru528@gmail.com!** Check your inbox ({st.session_state.admin_email}) for the 6-digit code.")
            else:
                st.warning(f"⚠️ **Email Dispatch Status:** {st.session_state.email_status}. Operating in Fallback/Simulation Mode.")
                st.info(f"📧 **Simulation/Fallback Mode OTP:** ` {st.session_state.generated_otp} `")
            
            otp_input = st.text_input("Step 2: Enter 6-Digit OTP Code", max_chars=6).strip()
            
            col_otp1, col_otp2 = st.columns([1, 1])
            with col_otp1:
                if st.button("Verify & Login", type="primary"):
                    if otp_input == st.session_state.generated_otp:
                        st.session_state.admin_auth_step = 2
                        st.rerun()
                    else:
                        st.error("❌ Invalid or incorrect OTP code. Please try again.")
            with col_otp2:
                if st.button("Cancel / Restart Login"):
                    st.session_state.admin_auth_step = 0
                    st.rerun()

    # ADMIN DASHBOARD (Unlocked)
    if st.session_state.admin_auth_step == 2:
        col_head1, col_head2 = st.columns([3, 1])
        with col_head1:
            st.success("🔓 Administrator Session Active.")
        with col_head2:
            if st.button("🚪 Admin Logout", type="secondary"):
                st.session_state.admin_auth_step = 0
                st.session_state.generated_otp = None
                navigate_to('Home')

        st.markdown("### Admin Panel — Automated Room Allocation")
        
        st.markdown("#### Step 1: Upload Student List")
        st.caption("Required Excel/CSV columns: `USN`, `Student Name`, `College Name`, `Event/Exam Name`")
        uploaded_file = st.file_uploader("Upload Student Master Sheet", type=["xlsx", "csv"])
        
        st.markdown("#### Step 2: Set Room Capacity & Floors")
        
        # Updated Default Rooms matching the actual College Blueprint
        default_rooms = pd.DataFrame([
            {"Room Number": "WB-209", "Floor": "1st Floor", "Capacity": 30},
            {"Room Number": "EB-201", "Floor": "1st Floor", "Capacity": 30},
            {"Room Number": "WB-308", "Floor": "2nd Floor", "Capacity": 35},
            {"Room Number": "CB-301", "Floor": "2nd Floor", "Capacity": 35},
        ])
        edited_rooms = st.data_editor(default_rooms, num_rows="dynamic")
        
        if uploaded_file and st.button("⚙️ Generate & Save Allotments", type="primary"):
            try:
                if uploaded_file.name.endswith(".csv"):
                    df_students = pd.read_csv(uploaded_file)
                else:
                    df_students = pd.read_excel(uploaded_file)
                
                allocated_data = []
                student_idx = 0
                total_students = len(df_students)
                
                for _, room_row in edited_rooms.iterrows():
                    r_num = room_row["Room Number"]
                    r_floor = room_row["Floor"]
                    cap = int(room_row["Capacity"])
                    
                    bench = 1
                    for _ in range(cap):
                        if student_idx >= total_students:
                            break
                        student = df_students.iloc[student_idx]
                        allocated_data.append({
                            "USN": str(student["USN"]).strip().upper(),
                            "Student Name": student["Student Name"],
                            "College Name": student["College Name"],
                            "Event/Exam Name": student["Event/Exam Name"],
                            "Room Number": r_num,
                            "Floor": r_floor,
                            "Bench Number": bench
                        })
                        student_idx += 1
                        bench += 1
                        
                df_final = pd.DataFrame(allocated_data)
                save_allotments(df_final)
                
                st.success(f"🎉 Successfully allocated {len(df_final)} of {total_students} students!")
                st.dataframe(df_final)
                
                csv_buffer = df_final.to_csv(index=False).encode('utf-8')
                st.download_button(
                    label="📥 Download Master Allotment CSV",
                    data=csv_buffer, 
                    file_name="SVCE_Master_Allotment.csv",
                    mime="text/csv"
                )
                
            except Exception as e:
                st.error(f"❌ Error during processing: {str(e)}")

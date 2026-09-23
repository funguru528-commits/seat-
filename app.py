import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sqlite3
import random
import string
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from PIL import Image, ImageDraw
import io

# ==========================================
# 1. SESSION STATE INITIALIZATION
# ==========================================
if 'current_page' not in st.session_state:
    st.session_state.current_page = 'Home'
if 'admin_auth_step' not in st.session_state:
    st.session_state.admin_auth_step = 0 # 0: Credentials, 1: OTP, 2: Access Granted
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
# 4. GMAIL SMTP DISPATCH (WITH FALLBACK)
# ==========================================
# Update these with your valid Gmail address and 16-character App Password if available
SENDER_EMAIL = "your_email@gmail.com"        
SENDER_APP_PASSWORD = "your_app_password"    

def send_email_otp(target_email, otp):
    """Sends OTP using standard smtplib on Port 587 (TLS) with robust error reporting."""
    if "your_email@gmail.com" in SENDER_EMAIL or "your_app_password" in SENDER_APP_PASSWORD:
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
        st.session_state.email_error_msg = None
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
    col1, col2 = st.columns(2)
    with col1:
        if st.button("👨‍🎓 Student Portal", use_container_width=True):
            navigate_to('Student')
    with col2:
        if st.button("🔐 Admin Portal", use_container_width=True):
            navigate_to('Admin')

# --- PAGE: STUDENT ---
elif st.session_state.current_page == 'Student':
    st.button("⬅️ Back to Home", on_click=navigate_to, args=('Home',))
    st.title("👨‍🎓 Student Seat Lookup")
    st.write("Enter your USN and verify the Captcha to view your seat allotment details and 3D floor model.")

    with st.form("student_search_form"):
        usn_input = st.text_input("Enter your USN (e.g., 1VE21CS001):").strip()
        
        c_col1, c_col2 = st.columns([1, 2])
        with c_col1:
            captcha_img = generate_captcha_image(st.session_state.student_captcha)
            st.image(captcha_img, caption="Security Code")
        with c_col2:
            captcha_input = st.text_input("Type the code shown above:")

        submit_search = st.form_submit_button("🔍 Search Allotment")

    if submit_search:
        if not usn_input:
            st.error("Please enter a valid USN.")
        elif captcha_input.strip().upper() != st.session_state.student_captcha.upper():
            st.error("Incorrect Captcha code. Please try again.")
            refresh_student_captcha()
        else:
            refresh_student_captcha()
            result = fetch_student_allotment(usn_input)
            if result:
                usn, name, college, event, room, floor, bench = result
                st.success(f"Allotment Found for **{name}** ({usn})")
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Exam / Event", event)
                m2.metric("Room / Hall", room)
                m3.metric("Floor / Bench", f"{floor} (Bench #{bench})")

                st.subheader("📍 Interactive 3D Campus Blueprint & Live Navigation")
                st.write("Rotate, zoom, or explode the 3D view below. Follow the glowing path to navigate directly to your allocated seat.")
                
                html_blueprint = render_3d_college_blueprint(room, floor, bench)
                components.html(html_blueprint, height=600)
            else:
                st.warning(f"No allotment record found for USN: **{usn_input.upper()}**")

# --- PAGE: ADMIN ---
elif st.session_state.current_page == 'Admin':
    st.button("⬅️ Back to Home", on_click=navigate_to, args=('Home',))
    st.title("🔐 Admin Management Portal")

    # Step 0: Authentication Form
    if st.session_state.admin_auth_step == 0:
        st.subheader("Admin Login")
        with st.form("admin_login_form"):
            email_input = st.text_input("Admin Email Address:")
            pwd_input = st.text_input("Admin Password:", type="password")
            btn_login = st.form_submit_button("Send Verification OTP")

        if btn_login:
            current_pwd = get_admin_password()
            if pwd_input != current_pwd:
                st.error("Invalid password.")
            elif "@" not in email_input or "." not in email_input:
                st.error("Please enter a valid email address.")
            else:
                generated_otp = str(random.randint(100000, 999999))
                st.session_state.generated_otp = generated_otp
                st.session_state.admin_email = email_input
                
                with st.spinner("Dispatching OTP email..."):
                    success, msg = send_email_otp(email_input, generated_otp)
                    if not success:
                        st.session_state.email_error_msg = msg
                    else:
                        st.session_state.email_error_msg = None
                
                st.session_state.admin_auth_step = 1
                st.rerun()

    # Step 1: OTP Verification
    elif st.session_state.admin_auth_step == 1:
        st.subheader("🔑 Enter Email OTP")
        st.info(f"Target Email: **{st.session_state.admin_email}**")

        if st.session_state.email_error_msg:
            st.warning(f"⚠️ Email Status Notice: {st.session_state.email_error_msg}")
            st.success(f"🔑 **Fallback Admin Verification OTP:** `{st.session_state.generated_otp}`")

        with st.form("otp_form"):
            otp_input = st.text_input("6-Digit Security OTP:")
            btn_verify = st.form_submit_button("Verify & Login")

        if btn_verify:
            if otp_input.strip() == st.session_state.generated_otp:
                st.session_state.admin_auth_step = 2
                st.success("Authentication Successful!")
                time.sleep(1)
                st.rerun()
            else:
                st.error("Invalid OTP code. Please try again.")

    # Step 2: Admin Dashboard
    elif st.session_state.admin_auth_step == 2:
        st.success(f"Logged in as Administrator ({st.session_state.admin_email})")
        
        tab1, tab2, tab3 = st.tabs(["📤 Upload Allotments", "📋 View Records", "⚙️ Settings"])

        with tab1:
            st.subheader("Upload Allotment Dataset")
            st.write("Upload an Excel (`.xlsx`) or CSV (`.csv`) file containing allotment details.")
            st.caption("Required Columns: `USN`, `Student Name`, `College Name`, `Event/Exam Name`, `Room Number`, `Floor`, `Bench Number`")

            uploaded_file = st.file_uploader("Choose a file", type=['csv', 'xlsx'])
            if uploaded_file is not None:
                try:
                    if uploaded_file.name.endswith('.csv'):
                        df = pd.read_csv(uploaded_file)
                    else:
                        df = pd.read_excel(uploaded_file)

                    required_cols = {'USN', 'Student Name', 'College Name', 'Event/Exam Name', 'Room Number', 'Floor', 'Bench Number'}
                    if not required_cols.issubset(df.columns):
                        st.error(f"Missing required columns! Ensure file contains: {', '.join(required_cols)}")
                    else:
                        st.dataframe(df.head(), use_container_width=True)
                        if st.button("💾 Save Allotments to Database"):
                            save_allotments(df)
                            st.success("Allotment database updated successfully!")
                except Exception as e:
                    st.error(f"❌ Error during processing: {str(e)}")

        with tab2:
            st.subheader("Current Database Records")
            df_records = get_all_allotments()
            if not df_records.empty:
                st.dataframe(df_records, use_container_width=True)
            else:
                st.info("No allotment records found in database.")

        with tab3:
            st.subheader("Change Password")
            with st.form("change_pwd_form"):
                new_p1 = st.text_input("New Password:", type="password")
                new_p2 = st.text_input("Confirm New Password:", type="password")
                btn_change_pwd = st.form_submit_button("Update Password")

            if btn_change_pwd:
                if not new_p1 or new_p1 != new_p2:
                    st.error("Passwords do not match or are empty.")
                else:
                    update_admin_password(new_p1)
                    st.success("Admin password updated successfully!")

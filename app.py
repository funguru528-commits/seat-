import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sqlite3
import random
import string
import time
import smtplib
import socket
from email.mime.text import MIMEText
from PIL import Image, ImageDraw
import io
import base64
import os

# ==========================================
# FORCE IPV4 FOR RENDER COMPATIBILITY
# ==========================================
# Render blocks outbound IPv6 connections on SMTP ports.
# This forces socket resolution to IPv4.
old_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(*args, **kwargs):
    responses = old_getaddrinfo(*args, **kwargs)
    return [response for response in responses if response[0] == socket.AF_INET]

socket.getaddrinfo = getaddrinfo_ipv4

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

AUTHORIZED_ADMIN_EMAIL = "funguru528@gmail.com"

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
# 4. GMAIL OTP INTEGRATION (FIXED FOR RENDER)
# ==========================================
def send_email_otp(target_email, otp):
    SENDER_EMAIL = AUTHORIZED_ADMIN_EMAIL
    SENDER_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "yigscoygwoqdbmsd")

    try:
        msg = MIMEText(f"Security Alert: Your SVCE Admin login OTP is {otp}. Do not share this with anyone.")
        msg['Subject'] = 'SVCE Portal - Admin Login Verification'
        msg['From'] = SENDER_EMAIL
        msg['To'] = target_email

        # Changed to Port 587 with STARTTLS (Port 465 is frequently blocked by cloud hosting providers like Render)
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.ehlo()
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.send_message(msg)
            
        return True, "Email Sent Successfully"
    except Exception as e:
        return False, str(e)

# ==========================================
# 5. REALISTIC 3D COLLEGE ARCHITECTURE ENGINE
# ==========================================
def get_campus_base64_image():
    local_candidates = [
        "campus_aerial.jpg",
        "campus_aerial.png",
        "campus_aerial.jpeg",
        "WhatsApp Image 2026-09-19 at 1.36.35 PM.jpeg"
    ]
    for filename in local_candidates:
        if os.path.exists(filename):
            with open(filename, "rb") as img_file:
                b64_str = base64.b64encode(img_file.read()).decode()
                return f"data:image/jpeg;base64,{b64_str}"
    return "https://svcengg.edu.in/assets/bgimages/IMG_9641.webp"

def render_3d_college_blueprint(target_room, target_floor, bench_no):
    room_clean = str(target_room).upper().strip().replace(" ", "")
    floor_clean = str(target_floor).upper().strip()
    aerial_data_uri = get_campus_base64_image()
    
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
                background: rgba(15, 23, 42, 0.92);
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
            .badge-path {{
                display: inline-block;
                background: #22c55e;
                color: #000;
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
            .view-btn:hover {{ background: #0284c7; }}
            .controls-hint {{
                position: absolute;
                bottom: 12px;
                left: 12px;
                right: 12px;
                display: flex;
                justify-content: space-between;
                background: rgba(0,0,0,0.78);
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
                <h4>🏛️ Realistic SVCE Campus Model & Active Wayfinder</h4>
                <p>Destination: <span class="badge-assigned">{target_room} ({target_floor}, Bench #{bench_no})</span></p>
                <p style="margin-top:4px;">Main Entrance: <span class="badge-path">🔴 East Wing Gate (Red Marked)</span></p>
            </div>
            
            <div class="view-toolbar">
                <button class="view-btn" onclick="focusDestination()">🎯 Focus Room</button>
                <button class="view-btn" onclick="setExploded(false)">🏢 Stacked View</button>
                <button class="view-btn" onclick="setExploded(true)">📂 Explode Floors</button>
                <button class="view-btn" onclick="resetView()">🔄 360° Overview</button>
            </div>

            <div class="controls-hint">
                <span>🖱️ <b>Rotate:</b> Left-Click Drag | <b>Zoom:</b> Scroll | <b>Pan:</b> Right-Click</span>
                <span>🏫 <b>Classroom Architecture:</b> Modeled from Drone & Architectural Blueprints</span>
            </div>
        </div>

        <script>
            const container = document.getElementById('canvas-container');
            const width = container.clientWidth || 900;
            const height = 580;

            const scene = new THREE.Scene();
            scene.background = new THREE.Color(0x070d1f);

            const camera = new THREE.PerspectiveCamera(45, width / height, 0.1, 1000);
            camera.position.set(-58, 62, 78);

            const renderer = new THREE.WebGLRenderer({{ antialias: true }});
            renderer.setSize(width, height);
            renderer.setPixelRatio(window.devicePixelRatio);
            renderer.shadowMap.enabled = true;
            container.appendChild(renderer.domElement);

            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.maxPolarAngle = Math.PI / 2 - 0.02;
            controls.target.set(0, 10, 0);

            // Lighting Setup for architectural rendering
            scene.add(new THREE.AmbientLight(0xffffff, 0.9));
            const sun = new THREE.DirectionalLight(0xffffff, 1.1);
            sun.position.set(45, 90, 50);
            sun.castShadow = true;
            scene.add(sun);

            // 1. Campus Aerial Texture Map Base
            const textureLoader = new THREE.TextureLoader();
            const aerialImageURI = "{aerial_data_uri}";

            textureLoader.load(aerialImageURI, function(texture) {{
                texture.wrapS = THREE.ClampToEdgeWrapping;
                texture.wrapT = THREE.ClampToEdgeWrapping;

                const planeGeo = new THREE.PlaneGeometry(105, 78);
                const planeMat = new THREE.MeshStandardMaterial({{
                    map: texture,
                    roughness: 0.7,
                    metalness: 0.1
                }});
                const groundPhoto = new THREE.Mesh(planeGeo, planeMat);
                groundPhoto.rotation.x = -Math.PI / 2;
                groundPhoto.position.set(0, -0.1, 8);
                groundPhoto.receiveShadow = true;
                scene.add(groundPhoto);
            }});

            // 2. Procedural Architectural Texture Generator for Classroom Facades
            function createClassroomFacadeTexture(roomName, isAssigned) {{
                const canvas = document.createElement('canvas');
                canvas.width = 512;
                canvas.height = 256;
                const ctx = canvas.getContext('2d');

                // Wall Base Concrete Coat
                ctx.fillStyle = isAssigned ? "#0369a1" : "#e2e8f0";
                ctx.fillRect(0, 0, 512, 256);

                // Architectural Plinth / Foundation
                ctx.fillStyle = isAssigned ? "#0284c7" : "#94a3b8";
                ctx.fillRect(0, 220, 512, 36);

                // Continuous Multi-Pane Ribbon Windows
                const windowCols = 4;
                const winWidth = 96;
                const winHeight = 100;
                const startY = 60;

                for (let i = 0; i < windowCols; i++) {{
                    const startX = 25 + i * 122;
                    ctx.fillStyle = "#1e293b";
                    ctx.fillRect(startX, startY, winWidth, winHeight);
                    ctx.fillStyle = isAssigned ? "#38bdf8" : "#93c5fd";
                    ctx.fillRect(startX + 4, startY + 4, winWidth - 8, winHeight - 8);
                    ctx.fillStyle = "#334155";
                    ctx.fillRect(startX + winWidth / 2 - 2, startY + 4, 4, winHeight - 8);
                    ctx.fillRect(startX + 4, startY + winHeight / 2 - 2, winWidth - 8, 4);
                }}

                // Room Identification Plaque
                ctx.fillStyle = isAssigned ? "#facc15" : "#0f172a";
                ctx.fillRect(156, 12, 200, 36);
                ctx.fillStyle = isAssigned ? "#000000" : "#ffffff";
                ctx.font = 'bold 20px "Times New Roman", serif';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText(roomName, 256, 30);

                return new THREE.CanvasTexture(canvas);
            }}

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
            const assignedFloorStr = "{floor_clean}";
            let targetPinMesh = null;
            let targetRoomCoords = {{ x: -30, y: 0.5, z: 32 }};
            const floorGroups = [];

            function createClassroomUnit(name, x, y, z, w, h, d, floorIdx) {{
                const group = new THREE.Group();
                const geo = new THREE.BoxGeometry(w, h, d);
                const isAssigned = (assignedTarget.length > 2 && name.replace(/\\s+/g, '').includes(assignedTarget));
                
                const facadeTexture = createClassroomFacadeTexture(name, isAssigned);
                const wallMat = new THREE.MeshStandardMaterial({{ color: isAssigned ? 0x0284c7 : 0xe2e8f0, roughness: 0.5 }});
                const frontFacadeMat = new THREE.MeshStandardMaterial({{
                    map: facadeTexture,
                    roughness: 0.4,
                    emissive: isAssigned ? 0x0369a1 : 0x000000,
                    emissiveIntensity: isAssigned ? 0.7 : 0.0
                }});

                const mats = [wallMat, wallMat, wallMat, wallMat, frontFacadeMat, frontFacadeMat];
                const mesh = new THREE.Mesh(geo, mats);
                mesh.position.set(0, h / 2, 0);
                mesh.castShadow = true;
                mesh.receiveShadow = true;
                group.add(mesh);

                if (isAssigned) {{
                    targetRoomCoords = {{ x: x, y: (floorIdx * 11) + 2.5, z: z }};
                    const edges = new THREE.EdgesGeometry(geo);
                    const line = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({{ color: 0xfacc15, linewidth: 3 }}));
                    line.position.set(0, h / 2, 0);
                    group.add(line);

                    const pinGeo = new THREE.ConeGeometry(2, 5, 16);
                    const pinMat = new THREE.MeshStandardMaterial({{ color: 0xfacc15, emissive: 0xeab308, emissiveIntensity: 1.0 }});
                    const pin = new THREE.Mesh(pinGeo, pinMat);
                    pin.rotation.x = Math.PI;
                    pin.position.set(0, h + 9, 0);
                    group.add(pin);
                    targetPinMesh = pin;
                }}

                group.position.set(x, y, z);
                return group;
            }}

            function createFloorSlab(floorName) {{
                const slabGroup = new THREE.Group();
                const rear = new THREE.Mesh(new THREE.BoxGeometry(76, 0.8, 26), new THREE.MeshStandardMaterial({{ color: 0xcfd8dc, roughness: 0.6 }}));
                rear.position.set(0, 0, -13);
                slabGroup.add(rear);

                const east = new THREE.Mesh(new THREE.BoxGeometry(16, 0.8, 38), new THREE.MeshStandardMaterial({{ color: 0xcfd8dc, roughness: 0.6 }}));
                east.position.set(-30, 0, 19);
                slabGroup.add(east);

                const west = new THREE.Mesh(new THREE.BoxGeometry(16, 0.8, 38), new THREE.MeshStandardMaterial({{ color: 0xcfd8dc, roughness: 0.6 }}));
                west.position.set(30, 0, 19);
                slabGroup.add(west);

                const banner = makeTextSprite(floorName, "#0284c7", "rgba(255, 255, 255, 0.95)", true);
                banner.position.set(0, 1.2, 38);
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
                    flGroup.add(createClassroomUnit(r.name, r.x, 0.4, r.z, r.w, r.h, r.d, idx));
                }});
                flGroup.position.y = baseFloorHeights[idx];
                scene.add(flGroup);
                floorGroups.push(flGroup);
            }});

            // 3. Central Block Glass Pyramid
            const pyramidGeo = new THREE.ConeGeometry(12, 6, 4);
            const pyramidMat = new THREE.MeshStandardMaterial({{ color: 0x0284c7, roughness: 0.1, metalness: 0.8, transparent: true, opacity: 0.85 }});
            const pyramidMesh = new THREE.Mesh(pyramidGeo, pyramidMat);
            pyramidMesh.rotation.y = Math.PI / 4;
            pyramidMesh.position.set(0, 31, -16);
            scene.add(pyramidMesh);

            // 4. Red Staircases
            const stairPositions = [
                {{ name: "East Stairs (EB)", x: -30, z: 0, w: 12, d: 8 }},
                {{ name: "Central Left Stairs", x: -9, z: 0, w: 9, d: 8 }},
                {{ name: "Central Right Stairs", x: 9, z: 0, w: 9, d: 8 }},
                {{ name: "West Stairs (WB)", x: 30, z: 0, w: 12, d: 8 }}
            ];

            stairPositions.forEach(pos => {{
                const totalH = 29;
                const shaftGeo = new THREE.BoxGeometry(pos.w, totalH, pos.d);
                const shaftMat = new THREE.MeshStandardMaterial({{ color: 0xef4444, emissive: 0xb91c1c, emissiveIntensity: 0.7, transparent: true, opacity: 0.88 }});
                const shaft = new THREE.Mesh(shaftGeo, shaftMat);
                shaft.position.set(pos.x, totalH / 2, pos.z);
                scene.add(shaft);

                const label = makeTextSprite("🔴 " + pos.name, "#ffffff", "rgba(220, 38, 38, 0.9)", true);
                label.position.set(pos.x, totalH + 3, pos.z);
                scene.add(label);
            }});

            // 5. Wayfinding Pathway
            let targetFloorY = 0.5;
            if (assignedFloorStr.includes("1") || assignedFloorStr.includes("FIRST")) targetFloorY = 11.5;
            if (assignedFloorStr.includes("2") || assignedFloorStr.includes("SECOND")) targetFloorY = 22.5;

            const pathPoints = [
                new THREE.Vector3(-36, 0.5, 42),
                new THREE.Vector3(-30, 0.5, 38),
                new THREE.Vector3(-30, targetFloorY, targetRoomCoords.z),
                new THREE.Vector3(targetRoomCoords.x, targetFloorY, targetRoomCoords.z)
            ];

            const curve = new THREE.CatmullRomCurve3(pathPoints);
            const tubeGeo = new THREE.TubeGeometry(curve, 90, 0.55, 8, false);
            const tubeMat = new THREE.MeshStandardMaterial({{ color: 0x22c55e, emissive: 0x16a34a, emissiveIntensity: 0.95 }});
            const tubeMesh = new THREE.Mesh(tubeGeo, tubeMat);
            scene.add(tubeMesh);

            // Controls & Animations
            function setExploded(isExploded) {{
                const targetY = isExploded ? [0, 18, 36] : [0, 11, 22];
                floorGroups.forEach((group, i) => {{
                    group.position.y = targetY[i];
                }});
            }}

            function focusDestination() {{
                controls.target.set(targetRoomCoords.x, targetRoomCoords.y, targetRoomCoords.z);
                camera.position.set(targetRoomCoords.x - 15, targetRoomCoords.y + 15, targetRoomCoords.z + 25);
            }}

            function resetView() {{
                controls.target.set(0, 10, 0);
                camera.position.set(-58, 62, 78);
            }}

            function animate() {{
                requestAnimationFrame(animate);
                if (targetPinMesh) {{
                    targetPinMesh.rotation.y += 0.03;
                }}
                controls.update();
                renderer.render(scene, camera);
            }}
            animate();
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=600)

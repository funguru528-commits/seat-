import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import sqlite3
import random
import string
import time
import smtplib
from email.mime.text import MIMEText
from email.utils import formatdate, make_msgid
from PIL import Image, ImageDraw
import io
import base64
import os

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
# 4. GMAIL OTP INTEGRATION (DIAGNOSTIC TRANSPORT)
# ==========================================
def send_email_otp(target_email, otp):
    """
    Connects to Gmail's SMTP server on port 587 with STARTTLS.
    Appends mandatory RFC email headers and catches discrete socket issues.
    """
    SENDER_EMAIL = AUTHORIZED_ADMIN_EMAIL
    SENDER_APP_PASSWORD = "spfysddlctqrwhuq"

    try:
        msg = MIMEText(f"Security Alert: Your SVCE Admin login OTP is {otp}. Do not share this with anyone.")
        msg['Subject'] = f'SVCE Portal - Admin Verification Code [{otp}]'
        msg['From'] = SENDER_EMAIL
        msg['To'] = target_email
        msg['Date'] = formatdate(localtime=True)
        msg['Message-ID'] = make_msgid()
        msg['X-Priority'] = '1'
        msg['X-MSMail-Priority'] = 'High'
        msg['Importance'] = 'High'

        # Establish connection with a 10s socket timeout
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
            server.send_message(msg)
            
        return True, "Email Sent Successfully"

    except smtplib.SMTPAuthenticationError as e:
        return False, f"AUTH_ERROR (535): Google rejected credentials. Verify App Password."
    except (smtplib.SMTPConnectError, TimeoutError, OSError) as e:
        return False, f"CONNECTION_BLOCKED: Host blocked outbound SMTP port 587 ({type(e).__name__})."
    except Exception as e:
        return False, f"ERROR: {type(e).__name__} - {str(e)}"

# ==========================================
# 5. REALISTIC 3D COLLEGE BLUEPRINT ENGINE
# ==========================================
def get_image_as_base64(candidates, fallback_url):
    for filename in candidates:
        if os.path.exists(filename):
            with open(filename, "rb") as img_file:
                b64_str = base64.b64encode(img_file.read()).decode()
                ext = "png" if filename.lower().endswith(".png") else "jpeg"
                return f"data:image/{ext};base64,{b64_str}"
    return fallback_url

def render_3d_college_blueprint(target_room, target_floor, bench_no):
    room_clean = str(target_room).upper().strip().replace(" ", "")
    floor_clean = str(target_floor).upper().strip()
    
    # Aerial satellite image
    aerial_candidates = ["campus_aerial.jpg", "campus_aerial.png", "campus_aerial.jpeg", "WhatsApp Image 2026-09-19 at 1.36.35 PM.jpeg", "WhatsApp Image 2026-09-19 at 1.36.35 PM_2.jpeg"]
    aerial_data_uri = get_image_as_base64(aerial_candidates, "https://svcengg.edu.in/assets/bgimages/IMG_9641.webp")
    
    # Central block facade image
    cb_candidates = ["cb_front.jpg", "cb_front.png", "cb_front.jpeg", "cb image of the college.jpg"]
    cb_data_uri = get_image_as_base64(cb_candidates, "https://svcengg.edu.in/assets/bgimages/IMG_9641.webp")
    
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
                <span>🏫 <b>Central Block:</b> Textured with SVCE Front Facade Photo</span>
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

            scene.add(new THREE.AmbientLight(0xffffff, 0.9));
            const sun = new THREE.DirectionalLight(0xffffff, 1.1);
            sun.position.set(45, 90, 50);
            sun.castShadow = true;
            scene.add(sun);

            const textureLoader = new THREE.TextureLoader();

            // 1. Campus Aerial Texture Map Base
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

            // 2. Central Block (CB) Front Facade Texture
            const cbImageURI = "{cb_data_uri}";
            let cbFacadeMesh = null;
            textureLoader.load(cbImageURI, function(cbTex) {{
                cbTex.wrapS = THREE.ClampToEdgeWrapping;
                cbTex.wrapT = THREE.ClampToEdgeWrapping;

                const cbGeo = new THREE.PlaneGeometry(26, 26);
                const cbMat = new THREE.MeshStandardMaterial({{
                    map: cbTex,
                    roughness: 0.4,
                    metalness: 0.1,
                    side: THREE.DoubleSide
                }});
                cbFacadeMesh = new THREE.Mesh(cbGeo, cbMat);
                cbFacadeMesh.position.set(0, 13.5, -6.8);
                scene.add(cbFacadeMesh);
            }});

            function createClassroomFacadeTexture(roomName, isAssigned) {{
                const canvas = document.createElement('canvas');
                canvas.width = 512;
                canvas.height = 256;
                const ctx = canvas.getContext('2d');

                ctx.fillStyle = isAssigned ? "#0369a1" : "#e2e8f0";
                ctx.fillRect(0, 0, 512, 256);

                ctx.fillStyle = isAssigned ? "#0284c7" : "#94a3b8";
                ctx.fillRect(0, 220, 512, 36);

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
                const isAssigned = (assignedTarget.length > 2 && name.replace(/\s+/g, '').includes(assignedTarget));
                
                const facadeTexture = createClassroomFacadeTexture(name, isAssigned);
                
                const wallMat = new THREE.MeshStandardMaterial({{
                    color: isAssigned ? 0x0284c7 : 0xe2e8f0,
                    roughness: 0.5
                }});

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

            // Central Block Glass Pyramid Rooftop Feature
            const pyramidGeo = new THREE.ConeGeometry(12, 6, 4);
            const pyramidMat = new THREE.MeshStandardMaterial({{
                color: 0x0284c7,
                roughness: 0.1,
                metalness: 0.8,
                transparent: true,
                opacity: 0.85
            }});
            const pyramidMesh = new THREE.Mesh(pyramidGeo, pyramidMat);
            pyramidMesh.rotation.y = Math.PI / 4;
            pyramidMesh.position.set(0, 31, -16);
            scene.add(pyramidMesh);

            // 4 RED STAIRCASES
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

            // Wayfinding Pathway originating from East Wing Entrance Gate
            let targetFloorY = 0.5;
            if (assignedFloorStr.includes("1") || assignedFloorStr.includes("FIRST")) targetFloorY = 11.5;
            if (assignedFloorStr.includes("2") || assignedFloorStr.includes("SECOND")) targetFloorY = 22.5;

            const entranceOrigin = new THREE.Vector3(-36, 0.5, 42);

            const pathPoints = [];
            pathPoints.push(entranceOrigin.clone());
            pathPoints.push(new THREE.Vector3(-30, 0.5, 38));

            if (assignedTarget.includes("EB") || targetRoomCoords.x < -10) {{
                if (targetFloorY > 1) {{
                    pathPoints.push(new THREE.Vector3(-30, 0.5, 0));
                    pathPoints.push(new THREE.Vector3(-30, targetFloorY, 0));
                    pathPoints.push(new THREE.Vector3(-30, targetFloorY, targetRoomCoords.z));
                }} else {{
                    pathPoints.push(new THREE.Vector3(-30, 0.5, targetRoomCoords.z));
                }}
            }} else {{
                pathPoints.push(new THREE.Vector3(-30, 0.5, 12));
                if (assignedTarget.includes("WB") || targetRoomCoords.x > 10) {{
                    pathPoints.push(new THREE.Vector3(30, 0.5, 12));
                    if (targetFloorY > 1) {{
                        pathPoints.push(new THREE.Vector3(30, 0.5, 0));
                        pathPoints.push(new THREE.Vector3(30, targetFloorY, 0));
                        pathPoints.push(new THREE.Vector3(30, targetFloorY, targetRoomCoords.z));
                    }} else {{
                        pathPoints.push(new THREE.Vector3(30, 0.5, targetRoomCoords.z));
                    }}
                }} else {{
                    pathPoints.push(new THREE.Vector3(-9, 0.5, 12));
                    if (targetFloorY > 1) {{
                        pathPoints.push(new THREE.Vector3(-9, 0.5, 0));
                        pathPoints.push(new THREE.Vector3(-9, targetFloorY, 0));
                    }}
                    pathPoints.push(new THREE.Vector3(targetRoomCoords.x, targetFloorY, targetRoomCoords.z));
                }}
            }}
            pathPoints.push(new THREE.Vector3(targetRoomCoords.x, targetFloorY, targetRoomCoords.z));

            const curve = new THREE.CatmullRomCurve3(pathPoints);
            const tubeGeo = new THREE.TubeGeometry(curve, 90, 0.55, 8, false);
            const tubeMat = new THREE.MeshStandardMaterial({{
                color: 0x22c55e,
                emissive: 0x16a34a,
                emissiveIntensity: 0.95,
                roughness: 0.2
            }});
            const pathTube = new THREE.Mesh(tubeGeo, tubeMat);
            scene.add(pathTube);

            const startMarker = makeTextSprite("📍 YOU ENTER HERE (EAST GATE)", "#22c55e", "rgba(15, 23, 42, 0.92)", true);
            startMarker.position.set(entranceOrigin.x, 6, entranceOrigin.z);
            scene.add(startMarker);

            const ringGeo = new THREE.RingGeometry(2.5, 3.5, 32);
            const ringMat = new THREE.MeshBasicMaterial({{ color: 0xef4444, side: THREE.DoubleSide }});
            const ringMesh = new THREE.Mesh(ringGeo, ringMat);
            ringMesh.rotation.x = -Math.PI / 2;
            ringMesh.position.set(entranceOrigin.x, 0.2, entranceOrigin.z);
            scene.add(ringMesh);

            const particleGeo = new THREE.SphereGeometry(1.2, 16, 16);
            const particleMat = new THREE.MeshBasicMaterial({{ color: 0xffff00 }});
            const walkerParticle = new THREE.Mesh(particleGeo, particleMat);
            scene.add(walkerParticle);

            window.setExploded = function(isExploded) {{
                floorGroups.forEach(fg => fg.visible = true);
                if (isExploded) {{
                    floorGroups[0].position.y = 0;
                    floorGroups[1].position.y = 20;
                    floorGroups[2].position.y = 40;
                    pyramidMesh.position.y = 49;
                    if (cbFacadeMesh) cbFacadeMesh.position.y = 20;
                }} else {{
                    floorGroups[0].position.y = baseFloorHeights[0];
                    floorGroups[1].position.y = baseFloorHeights[1];
                    floorGroups[2].position.y = baseFloorHeights[2];
                    pyramidMesh.position.y = 31;
                    if (cbFacadeMesh) cbFacadeMesh.position.y = 13.5;
                }}
            }};

            window.focusDestination = function() {{
                controls.target.set(targetRoomCoords.x, targetFloorY + 3, targetRoomCoords.z);
                camera.position.set(targetRoomCoords.x + 25, targetFloorY + 20, targetRoomCoords.z + 25);
            }};

            window.resetView = function() {{
                floorGroups.forEach((fg, idx) => {{
                    fg.visible = true;
                    fg.position.y = baseFloorHeights[idx];
                }});
                pyramidMesh.position.y = 31;
                if (cbFacadeMesh) cbFacadeMesh.position.y = 13.5;
                camera.position.set(-58, 62, 78);
                controls.target.set(0, 10, 0);
            }};

            const clock = new THREE.Clock();
            function animate() {{
                requestAnimationFrame(animate);
                const t = clock.getElapsedTime();
                
                if (targetPinMesh) {{
                    targetPinMesh.position.y = 12 + Math.sin(t * 4) * 0.9;
                    targetPinMesh.rotation.y += 0.04;
                }}
                
                const progress = (t * 0.18) % 1;
                const pt = curve.getPoint(progress);
                walkerParticle.position.copy(pt);

                const s = 1.0 + Math.sin(t * 5) * 0.15;
                ringMesh.scale.set(s, s, 1);

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
                st.markdown("### 🌐 Realistic Campus 3D Model & Walking Path")
                st.caption("🟢 **Follow the green route from the East Wing Entrance Gate up to your room.** Click **'🎯 Focus Room'** to zoom straight into your classroom.")
                
                blueprint_3d_html = render_3d_college_blueprint(room, floor, bench)
                components.html(blueprint_3d_html, height=600)
                
                room_upper = str(room).upper()
                if "EB" in room_upper:
                    nav_details = f"""
                    1. **Start:** Enter through the **East Wing Main Gate** (marked with the red ring and green label).
                    2. **Corridor:** {"Walk along the East Wing ground hallway directly to your room." if "GROUND" in str(floor).upper() or "0" in str(floor) else f"Step inside the East hallway, proceed straight to the 🔴 **East Wing Staircase (EB)**, and climb up to the **{floor}**."}
                    3. **Destination:** Locate **{room}** (highlighted in blue with the yellow locator pin) and proceed to **Bench #{bench}**.
                    """
                else:
                    nav_details = f"""
                    1. **Start:** Enter through the **East Wing Main Gate** (marked with the red ring).
                    2. **Crossway:** Proceed through the connecting ground walkway toward the central block / west wing.
                    3. **Ascent:** Take the nearest designated red staircase to the **{floor}**.
                    4. **Destination:** Follow the green line to **{room}** and take your seat at **Bench #{bench}**.
                    """

                st.info(f"**🚶 Turn-by-Turn Wayfinding Guide:**\n{nav_details}")
            else:
                st.error("❌ No allotment found for this USN. Please verify your details at the Security Desk.")

# --- PAGE: ADMIN ---
elif st.session_state.current_page == 'Admin':
    if st.session_state.admin_auth_step < 2:
        st.button("⬅️ Cancel & Return Home", on_click=navigate_to, args=('Home',))
        st.markdown("### 🔒 System Administrator Access")
        
        if st.session_state.admin_auth_step == 0:
            current_stored_pass = get_admin_password()
            
            st.markdown("#### Step 1: Secure Login")
            admin_pass_input = st.text_input("Enter Master Password", type="password")
            admin_email_input = st.text_input("Enter Admin Email Address for OTP Delivery", value="")
            
            if st.button("Send Verification OTP", type="primary"):
                entered_email_clean = admin_email_input.strip().lower()
                
                if admin_pass_input != current_stored_pass:
                    st.error("❌ Incorrect master password.")
                elif not entered_email_clean:
                    st.warning("⚠️ Please enter your registered administrator email address.")
                elif entered_email_clean != AUTHORIZED_ADMIN_EMAIL.lower():
                    st.error(f"❌ Access Denied: '{admin_email_input}' is not recognized as an authorized administrator email.")
                else:
                    st.session_state.generated_otp = "".join(random.choices(string.digits, k=6))
                    st.session_state.admin_email = entered_email_clean
                    
                    with st.spinner("Dispatching secure email to inbox..."):
                        email_success, email_msg = send_email_otp(st.session_state.admin_email, st.session_state.generated_otp)
                        time.sleep(1)
                        
                    if email_success:
                        st.session_state.email_status = "sent"
                    else:
                        st.session_state.email_status = email_msg
                    
                    st.session_state.admin_auth_step = 1
                    st.rerun()
        
        elif st.session_state.admin_auth_step == 1:
            st.success("✅ Credentials & Email Verified.")
            
            if st.session_state.email_status == "sent":
                st.info(f"📧 **Email OTP Sent to {st.session_state.admin_email}!** Check your inbox for the 6-digit code.")
            else:
                st.error(f"⚠️ **Dispatch Diagnostic:** {st.session_state.email_status}")
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

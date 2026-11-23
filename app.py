import os, json, sqlite3, secrets
from datetime import datetime, timedelta, date
from functools import wraps
from flask import Flask, g, jsonify, request, render_template, session
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(BASE_DIR, "lablink.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-this-secret")
app.config["JSON_SORT_KEYS"] = False

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(_):
    conn = g.pop("db", None)
    if conn: conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL, role TEXT NOT NULL CHECK(role IN ('student','faculty')),
      department TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS equipment(
      id INTEGER PRIMARY KEY, name TEXT NOT NULL, department TEXT NOT NULL,
      category TEXT NOT NULL, location TEXT NOT NULL, specs TEXT NOT NULL,
      total_units INTEGER NOT NULL DEFAULT 1, image TEXT DEFAULT '🔬'
    );
    CREATE TABLE IF NOT EXISTS requests(
      id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES users(id),
      project_name TEXT NOT NULL, deadline TEXT NOT NULL, equipment_id INTEGER NOT NULL REFERENCES equipment(id),
      purpose TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Pending',
      faculty_note TEXT DEFAULT '', created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS bookings(
      id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL REFERENCES users(id),
      equipment_id INTEGER NOT NULL REFERENCES equipment(id), request_id INTEGER REFERENCES requests(id),
      start_at TEXT NOT NULL, end_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'Confirmed',
      created_at TEXT NOT NULL
    );
    """)
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    if count == 0:
        users = [
          ("Aarav Student","student@lablink.edu","student123","student","Computer Science"),
          ("Faculty Admin","faculty@lablink.edu","faculty123","faculty","Computer Science"),
          ("Diya Student","diya@lablink.edu","student123","student","Electronics")
        ]
        conn.executemany("INSERT INTO users(name,email,password_hash,role,department) VALUES(?,?,?,?,?)",
          [(n,e,generate_password_hash(p),r,d) for n,e,p,r,d in users])
        equipment = [
          ("NVIDIA Jetson Nano Kit","Computer Science","AI & Edge Computing","AI Lab · Block C, 3rd Floor","4GB RAM; 128-core GPU; camera interface",5,"🤖"),
          ("GPU Workstation","Computer Science","Computing","Research Lab · Block C, 2nd Floor","RTX-class GPU; 32GB RAM; Ubuntu 22.04",4,"🖥️"),
          ("Arduino Sensor Kit","Electronics","Embedded Systems","IoT Lab · Block B, 1st Floor","Arduino Mega; sensors; jumper wires",12,"🔌"),
          ("Raspberry Pi 5 Kit","Computer Science","IoT & Prototyping","Innovation Lab · Block C, 1st Floor","Raspberry Pi 5; 8GB RAM; power supply",8,"🍓"),
          ("Digital Oscilloscope","Electronics","Measurement","Circuits Lab · Block B, 2nd Floor","4-channel; 100 MHz bandwidth",3,"📈"),
          ("3D Printer","Mechanical","Fabrication","Makerspace · Block D, Ground Floor","FDM; 220 × 220 × 250 mm build volume",2,"🧩"),
          ("Robotics Workstation","Mechanical","Robotics","Robotics Lab · Block D, 1st Floor","ROS 2; robotic arm interface; Ubuntu",3,"🦾"),
          ("VR Development Headset","Computer Science","XR Development","Media Lab · Block C, 4th Floor","6DoF tracking; PC-connected",4,"🥽")
        ]
        conn.executemany("INSERT INTO equipment(name,department,category,location,specs,total_units,image) VALUES(?,?,?,?,?,?,?)", equipment)
        conn.commit()
    conn.close()

def current_user():
    uid = session.get("user_id")
    return db().execute("SELECT id,name,email,role,department FROM users WHERE id=?", (uid,)).fetchone() if uid else None

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not current_user(): return jsonify(error="Please sign in first."), 401
        return fn(*args, **kwargs)
    return wrapped

def role_required(role):
    def decorator(fn):
        @wraps(fn)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user()["role"] != role: return jsonify(error="You do not have permission for this action."), 403
            return fn(*args, **kwargs)
        return wrapped
    return decorator

def overlaps(equipment_id, start_at, end_at):
    return db().execute("""SELECT COUNT(*) FROM bookings
      WHERE equipment_id=? AND status='Confirmed' AND start_at < ? AND end_at > ?""",
      (equipment_id, end_at, start_at)).fetchone()[0]

def available_units(equipment, start_at=None, end_at=None):
    if start_at and end_at:
        used = db().execute("""SELECT COUNT(*) FROM bookings WHERE equipment_id=?
          AND status='Confirmed' AND start_at < ? AND end_at > ?""",
          (equipment["id"], end_at, start_at)).fetchone()[0]
    else:
        now = datetime.now().isoformat(timespec="minutes")
        used = db().execute("""SELECT COUNT(*) FROM bookings WHERE equipment_id=?
          AND status='Confirmed' AND end_at > ?""", (equipment["id"], now)).fetchone()[0]
    return max(0, equipment["total_units"] - used)

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/me")
def me():
    u = current_user()
    return jsonify(user=dict(u) if u else None)

@app.post("/api/login")
def login():
    data = request.get_json(silent=True) or {}
    email, password = str(data.get("email","")).strip().lower(), str(data.get("password",""))
    user = db().execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify(error="Email or password is incorrect."), 401
    session.clear(); session["user_id"] = user["id"]
    return jsonify(user=dict(current_user()))

@app.post("/api/logout")
def logout():
    session.clear()
    return jsonify(ok=True)

@app.get("/api/equipment")
def equipment_list():
    q = request.args.get("q","").strip()
    department = request.args.get("department","").strip()
    category = request.args.get("category","").strip()
    rows = db().execute("SELECT * FROM equipment WHERE name LIKE ? AND department LIKE ? AND category LIKE ? ORDER BY name",
      (f"%{q}%", f"%{department}%", f"%{category}%")).fetchall()
    items = []
    for row in rows:
        item = dict(row); item["available"] = available_units(row); items.append(item)
    return jsonify(items)

@app.get("/api/equipment/<int:eid>")
def equipment_detail(eid):
    item = db().execute("SELECT * FROM equipment WHERE id=?", (eid,)).fetchone()
    if not item: return jsonify(error="Equipment not found."), 404
    bookings = db().execute("""SELECT b.start_at,b.end_at,b.status,u.name FROM bookings b
      JOIN users u ON u.id=b.student_id WHERE b.equipment_id=? AND b.status='Confirmed'
      ORDER BY b.start_at LIMIT 10""", (eid,)).fetchall()
    result = dict(item); result["available"] = available_units(item)
    result["bookings"] = [dict(x) for x in bookings]
    return jsonify(result)

@app.get("/api/dashboard")
@login_required
def dashboard():
    u = current_user()
    total = db().execute("SELECT COUNT(*) FROM equipment").fetchone()[0]
    available = sum(1 for x in db().execute("SELECT * FROM equipment") if available_units(x)>0)
    if u["role"] == "faculty":
        pending = db().execute("""SELECT r.*,u.name student_name,e.name equipment_name FROM requests r
          JOIN users u ON u.id=r.student_id JOIN equipment e ON e.id=r.equipment_id
          WHERE r.status='Pending' ORDER BY r.created_at""").fetchall()
        upcoming = db().execute("""SELECT b.*,u.name student_name,e.name equipment_name FROM bookings b
          JOIN users u ON u.id=b.student_id JOIN equipment e ON e.id=b.equipment_id
          WHERE b.end_at>? AND b.status='Confirmed' ORDER BY b.start_at LIMIT 8""",
          (datetime.now().isoformat(timespec="minutes"),)).fetchall()
        return jsonify(role="faculty", total=total, available=available, pending=[dict(x) for x in pending], upcoming=[dict(x) for x in upcoming])
    upcoming = db().execute("""SELECT b.*,e.name equipment_name,e.location FROM bookings b
      JOIN equipment e ON e.id=b.equipment_id WHERE b.student_id=? AND b.end_at>? AND b.status='Confirmed'
      ORDER BY b.start_at LIMIT 8""", (u["id"],datetime.now().isoformat(timespec="minutes"))).fetchall()
    requests = db().execute("""SELECT r.*,e.name equipment_name FROM requests r JOIN equipment e ON e.id=r.equipment_id
      WHERE r.student_id=? ORDER BY r.created_at DESC LIMIT 8""", (u["id"],)).fetchall()
    return jsonify(role="student", total=total, available=available, upcoming=[dict(x) for x in upcoming], requests=[dict(x) for x in requests])

@app.post("/api/requests")
@login_required
def create_request():
    u=current_user()
    if u["role"]!="student": return jsonify(error="Only students can submit project requests."),403
    d=request.get_json(silent=True) or {}
    project=str(d.get("project_name","")).strip(); purpose=str(d.get("purpose","")).strip()
    deadline=str(d.get("deadline","")).strip()
    try: eid=int(d.get("equipment_id"))
    except (TypeError,ValueError): return jsonify(error="Choose valid equipment."),400
    if len(project)<3 or len(project)>100 or len(purpose)<10 or len(purpose)>700:
        return jsonify(error="Project name must be 3–100 characters and purpose 10–700 characters."),400
    try: due=date.fromisoformat(deadline)
    except ValueError: return jsonify(error="Enter a valid project deadline."),400
    if due < date.today(): return jsonify(error="Deadline cannot be in the past."),400
    if not db().execute("SELECT id FROM equipment WHERE id=?",(eid,)).fetchone(): return jsonify(error="Equipment not found."),404
    db().execute("""INSERT INTO requests(student_id,project_name,deadline,equipment_id,purpose,created_at)
      VALUES(?,?,?,?,?,?)""",(u["id"],project,deadline,eid,purpose,datetime.now().isoformat(timespec="minutes")))
    db().commit()
    return jsonify(message="Project access request sent to faculty."),201

@app.post("/api/bookings")
@login_required
def create_booking():
    u=current_user()
    if u["role"]!="student": return jsonify(error="Only students can book equipment."),403
    d=request.get_json(silent=True) or {}
    try:
        eid=int(d.get("equipment_id")); start=datetime.fromisoformat(d.get("start_at","")); end=datetime.fromisoformat(d.get("end_at",""))
    except (TypeError,ValueError): return jsonify(error="Enter valid equipment and date/time values."),400
    if start <= datetime.now() or end <= start: return jsonify(error="Choose a future start time and an end time after it."),400
    if (end-start)>timedelta(hours=4): return jsonify(error="Bookings are limited to four hours per session."),400
    item=db().execute("SELECT * FROM equipment WHERE id=?",(eid,)).fetchone()
    if not item: return jsonify(error="Equipment not found."),404
    if available_units(item,start.isoformat(timespec="minutes"),end.isoformat(timespec="minutes")) <= 0:
        alternatives=[]
        for shift in [1,2,3,4,24]:
            s=start+timedelta(hours=shift); e=end+timedelta(hours=shift)
            if available_units(item,s.isoformat(timespec="minutes"),e.isoformat(timespec="minutes"))>0:
                alternatives.append({"start_at":s.isoformat(timespec="minutes"),"end_at":e.isoformat(timespec="minutes")})
                break
        other=db().execute("SELECT * FROM equipment WHERE category=? AND id<>?",(item["category"],eid)).fetchall()
        alt_equipment=[{"id":x["id"],"name":x["name"]} for x in other if available_units(x,start.isoformat(timespec="minutes"),end.isoformat(timespec="minutes"))>0][:3]
        return jsonify(error="That slot is already full. Try one of the alternatives.", alternatives=alternatives, alternative_equipment=alt_equipment),409
    db().execute("""INSERT INTO bookings(student_id,equipment_id,start_at,end_at,created_at)
      VALUES(?,?,?,?,?)""",(u["id"],eid,start.isoformat(timespec="minutes"),end.isoformat(timespec="minutes"),datetime.now().isoformat(timespec="minutes")))
    db().commit()
    return jsonify(message="Equipment booked successfully."),201

@app.post("/api/requests/<int:rid>/decision")
@role_required("faculty")
def decide_request(rid):
    d=request.get_json(silent=True) or {}; decision=d.get("decision")
    if decision not in ("Approved","Rejected"): return jsonify(error="Choose approve or reject."),400
    r=db().execute("SELECT * FROM requests WHERE id=?",(rid,)).fetchone()
    if not r: return jsonify(error="Request not found."),404
    if r["status"]!="Pending": return jsonify(error="This request has already been reviewed."),409
    note=str(d.get("note","")).strip()[:300]
    db().execute("UPDATE requests SET status=?,faculty_note=? WHERE id=?",(decision,note,rid))
    db().commit()
    return jsonify(message=f"Request {decision.lower()}.")

def fallback_recommendations(project, purpose, deadline):
    text=(project+" "+purpose).lower()
    rows=db().execute("SELECT * FROM equipment").fetchall()
    terms={
      "ai":["jetson","gpu"],"machine learning":["gpu","jetson"],"vision":["jetson","gpu"],
      "iot":["raspberry","arduino"],"sensor":["arduino","oscilloscope"],"embedded":["arduino","raspberry"],
      "robot":["robotics","jetson"],"3d":["3d printer"],"print":["3d printer"],
      "vr":["vr","gpu"],"virtual reality":["vr","gpu"],"circuit":["oscilloscope","arduino"]
    }
    ranked=[]
    for x in rows:
        name=x["name"].lower(); category=x["category"].lower(); score=0
        for word, matches in terms.items():
            if word in text and any(m in name for m in matches): score+=3
        if any(w in text for w in category.split()): score+=1
        if available_units(x)>0: score+=2
        ranked.append((score,x))
    ranked.sort(key=lambda z:z[0],reverse=True)
    return [{"id":x["id"],"name":x["name"],"department":x["department"],"category":x["category"],
      "location":x["location"],"available":available_units(x),"reason":"Matched project keywords and current availability."}
      for score,x in ranked[:3] if score>0] or [
      {"id":x["id"],"name":x["name"],"department":x["department"],"category":x["category"],
       "location":x["location"],"available":available_units(x),"reason":"Available campus resource to explore."}
      for x in ranked[:3]]

@app.post("/api/recommend")
@login_required
def recommend():
    d=request.get_json(silent=True) or {}
    project=str(d.get("project_name","")).strip(); purpose=str(d.get("purpose","")).strip(); deadline=str(d.get("deadline","")).strip()
    if len(project)<2 or len(purpose)<5: return jsonify(error="Enter a project name and a little more detail about your requirements."),400
    recommendations=fallback_recommendations(project,purpose,deadline)
    api_key=os.environ.get("GEMINI_API_KEY")
    if api_key:
        try:
            import urllib.request
            prompt=("You are a campus lab resource assistant. Recommend only from this equipment list. "
              "Return concise JSON with keys summary and recommendations (array of objects with id and reason). "
              "Do not invent equipment or availability. Project: "+project+"; purpose: "+purpose+
              "; deadline: "+deadline+"; equipment: "+json.dumps(recommendations))
            payload=json.dumps({"contents":[{"parts":[{"text":prompt}]}]}).encode()
            req=urllib.request.Request("https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent",
              data=payload,headers={"Content-Type":"application/json","x-goog-api-key":api_key},method="POST")
            with urllib.request.urlopen(req,timeout=12) as response:
                result=json.loads(response.read().decode())
            generated=result["candidates"][0]["content"]["parts"][0]["text"]
            return jsonify(mode="Gemini",summary="Gemini considered your project requirements. Verify the live slot before booking.",recommendations=recommendations,ai_note=generated[:1500])
        except Exception:
            pass
    return jsonify(mode="Fallback",summary="Suggested using project keywords, equipment category and current availability. Gemini is optional; the platform remains fully usable without it.",recommendations=recommendations)

@app.errorhandler(500)
def server_error(_):
    return jsonify(error="Something went wrong on the server. Please try again."),500

if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)), debug=os.environ.get("FLASK_DEBUG")=="1")

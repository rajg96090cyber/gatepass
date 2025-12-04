from flask import Flask, request, send_file, url_for
import sqlite3, qrcode, io, datetime, smtplib, os
from email.message import EmailMessage

app = Flask(__name__)

# ====== CONFIG ======
CLASS_EMAIL = "rg824797@gmail.com"
HOD_EMAIL = "rajg96090@gmail.com"

# ⭐ Principal + Registrar dono yahan rakhe hain
PRINCIPAL_EMAIL = "rajg96090@gmail.com"
REGISTRAR_EMAIL = "bhur4882@gmail.com"

SENDER_EMAIL = "aids24.shivrajgupta@ggct.co.in"
SENDER_PASS = "buekqnqazapxctme"

DB_NAME = "gatepass.db"

UPLOAD_FOLDER = "static/photos"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ====== DB HELPERS ======
def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Main request table
    c.execute("DROP TABLE IF EXISTS requests")

    c.execute(
        """
        CREATE TABLE requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            branch TEXT,
            year TEXT,
            roll TEXT,
            email TEXT,
            reason TEXT,
            out_time TEXT,
            date TEXT,
            class_status TEXT,
            hod_status TEXT,
            principal_status TEXT,
            created_at TEXT,
            class_note TEXT,
            photo_path TEXT,
            qr_token TEXT,
            used_status TEXT DEFAULT 'No'
        )
        """
    )

    conn.commit()
    conn.close()


def add_request(name, branch, year, roll, email, reason, out_time, date, photo_path):
    conn = get_conn()
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO requests
        (name, branch, year, roll, email, reason, out_time, date,
         class_status, hod_status, principal_status, created_at,
         class_note, photo_path, qr_token, used_status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            name, branch, year, roll, email, reason, out_time, date,
            "Pending", "Pending", "Pending",
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "", photo_path, "", "No"
        )
    )

    conn.commit()
    rid = c.lastrowid
    conn.close()
    return rid


def update_status(req_id, field, status):
    conn = get_conn()
    c = conn.cursor()
    c.execute(f"UPDATE requests SET {field}=? WHERE id=?", (status, req_id))
    conn.commit()
    conn.close()


def mark_used(req_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE requests SET used_status='Yes' WHERE id=?", (req_id,))
    conn.commit()
    conn.close()


def get_request(req_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM requests WHERE id=?", (req_id,))
    row = c.fetchone()
    conn.close()
    return row


# ====== EMAIL ======
def send_email(to_email, subject, html):
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg.set_content("HTML supported email required")
        msg.add_alternative(html, subtype="html")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASS)
            smtp.send_message(msg)

        print("EMAIL sent to", to_email)
    except Exception as e:
        print("Email error:", e)


def get_base_url():
    return request.host_url.rstrip("/")


# ====== HOME PAGE (BLUE + WHITE UI) ======
@app.route("/")
def home():
    return """
    <h2 style='color:white;text-align:center;margin-top:20px;'>GGCT GatePass</h2>

    <div style='background:white;width:400px;margin:auto;padding:20px;border-radius:10px;'>

        <h3 style='text-align:center;color:#0d47a1;'>GatePass Request</h3>

        <form method="POST" action="/submit" enctype="multipart/form-data">

            <label>Student Name</label>
            <input name="name" required style="width:100%;padding:8px;margin-bottom:8px;">

            <label>Branch</label>
            <input name="branch" value="AIDS" required style="width:100%;padding:8px;margin-bottom:8px;">

            <label>Year</label>
            <input name="year" placeholder="1 / 2 / 3" required style="width:100%;padding:8px;margin-bottom:8px;">

            <label>Roll No</label>
            <input name="roll" required style="width:100%;padding:8px;margin-bottom:8px;">

            <label>Email</label>
            <input name="email" type="email" required style="width:100%;padding:8px;margin-bottom:8px;">

            <label>Photo</label>
            <input type="file" name="photo" required style="margin-bottom:10px;">

            <label>Reason</label>
            <input name="reason" required style="width:100%;padding:8px;margin-bottom:8px;">

            <label>Out Time</label>
            <input name="out_time" placeholder="3:30 PM" required style="width:100%;padding:8px;margin-bottom:8px;">

            <label>Date</label>
            <input type="date" name="date" required style="width:100%;padding:8px;margin-bottom:8px;">

            <button style='background:#0d47a1;color:white;width:100%;padding:10px;border:none;border-radius:6px;'>
                Submit GatePass
            </button>

        </form>

        <br>
        <a href="/scanner">Security Scanner</a> |
        <a href="/admin">Admin</a>

    </div>
    """
# ==============================================
#              SUBMIT REQUEST
# ==============================================
@app.route("/submit", methods=["POST"])
def submit():
    name = request.form["name"].strip()
    branch = request.form["branch"].strip()
    year = request.form["year"].strip()
    roll = request.form["roll"].strip()
    email = request.form["email"].strip()
    reason = request.form["reason"].strip()
    out_time = request.form["out_time"].strip()
    date = request.form["date"].strip()

    # Photo upload
    photo = request.files.get("photo")
    if not photo:
        return "<h3>❌ Photo required</h3>"

    ext = photo.filename.split(".")[-1]
    photo_name = f"{roll}.{ext}"
    photo_path = f"{UPLOAD_FOLDER}/{photo_name}"
    photo.save(photo_path)

    # Add request to DB
    req_id = add_request(name, branch, year, roll, email,
                         reason, out_time, date, photo_path)

    # Email to Class Incharge
    html = f"""
    <h3>New GatePass Request</h3>
    <b>Name:</b> {name}<br>
    <b>Roll:</b> {roll}<br>
    <b>Branch:</b> {branch}<br>
    <b>Year:</b> {year}<br>
    <b>Reason:</b> {reason}<br>
    <b>Date:</b> {date}<br>
    <b>Out Time:</b> {out_time}<br><br>

    <img src='cid:photo1' width='150'><br><br>

    <a href='{url_for('class_approve', req_id=req_id, _external=True)}'>
        APPROVE
    </a> |
    <a href='{url_for('class_reject', req_id=req_id, _external=True)}'>
        REJECT
    </a>
    """

    send_email(CLASS_EMAIL, "GatePass – Class Approval Required", html)

    return "<h3>✅ Submitted! Sent to Class Incharge.</h3>"


# ==============================================
#              CLASS INCHARGE
# ==============================================
@app.route("/class_approve/<int:req_id>", methods=["GET", "POST"])
def class_approve(req_id):
    data = get_request(req_id)
    if not data:
        return "<h3>Invalid ID</h3>"

    if request.method == "POST":
        note = request.form["note"]

        conn = get_conn()
        c = conn.cursor()
        c.execute("UPDATE requests SET class_note=?, class_status='Approved' WHERE id=?",
                  (note, req_id))
        conn.commit()
        conn.close()

        # Send to HOD
        hod_mail = f"""
        <h3>Class Incharge Approved</h3>

        <p><b>Name:</b> {data['name']}<br>
        <b>Roll:</b> {data['roll']}<br>
        <b>Branch:</b> {data['branch']}<br>
        <b>Year:</b> {data['year']}<br>
        <b>Reason:</b> {data['reason']}<br></p>

        <p><b>Note:</b> {note}</p>

        <img src='cid:photo1' width='150'><br><br>

        <a href='{url_for('hod_approve', req_id=req_id, _external=True)}'>
            APPROVE
        </a> |
        <a href='{url_for('hod_reject', req_id=req_id, _external=True)}'>
            REJECT
        </a>
        """

        send_email(HOD_EMAIL, "HOD Approval Needed – GatePass", hod_mail)

        return "<h3>Approved & Sent to HOD</h3>"

    # GET FORM
    return f"""
    <h2>Class Incharge Approval</h2>

    <b>Name:</b> {data['name']}<br>
    <b>Roll:</b> {data['roll']}<br>
    <b>Reason:</b> {data['reason']}<br><br>

    <img src='/{data['photo_path']}' width='150'><br><br>

    <form method="POST">
        <textarea name="note" placeholder="Add Note" rows="4" cols="50"></textarea><br><br>
        <button type="submit">Approve & Send to HOD</button>
    </form>
    """


@app.route("/class_reject/<int:req_id>")
def class_reject(req_id):
    update_status(req_id, "class_status", "Rejected")
    return "<h3>Rejected by Class Incharge</h3>"


# ==============================================
#                     HOD
# ==============================================
@app.route("/hod_approve/<int:req_id>")
def hod_approve(req_id):
    update_status(req_id, "hod_status", "Approved")

    data = get_request(req_id)
    if not data:
        return "Invalid"

    # ⭐ QR create here (HOD approval)
    qr_data = f"GPID:{data['id']}|ROLL:{data['roll']}|DATE:{data['date']}"
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)

    qr_token = f"qr_{data['id']}.png"
    qr_path = f"static/{qr_token}"

    with open(qr_path, "wb") as f:
        f.write(buf.getvalue())

    # Save QR token in DB
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE requests SET qr_token=? WHERE id=?", (qr_token, req_id))
    conn.commit()
    conn.close()

    # ⭐ Send QR to Principal AND Registrar
    html = f"""
    <h3>GatePass – Final Approval Required</h3>

    <b>Name:</b> {data['name']}<br>
    <b>Roll:</b> {data['roll']}<br>
    <b>Reason:</b> {data['reason']}<br><br>

    <img src='cid:photo1' width='150'><br><br>

    <h3>QR for Verification</h3>
    <img src='cid:qr1' width='200'><br><br>

    <a href='{url_for('principal_approve', req_id=req_id, _external=True)}'>
        APPROVE
    </a> |
    <a href='{url_for('principal_reject', req_id=req_id, _external=True)}'>
        REJECT
    </a>
    """

    send_email(PRINCIPAL_EMAIL, "Principal Approval Needed – GatePass", html)
    send_email(REGISTRAR_EMAIL, "Registrar Approval – GatePass", html)

    return "<h3>Sent to Principal & Registrar</h3>"


@app.route("/hod_reject/<int:req_id>")
def hod_reject(req_id):
    update_status(req_id, "hod_status", "Rejected")
    return "<h3>Rejected by HOD</h3>"


# ==============================================
#                PRINCIPAL FINAL APPROVAL
# ==============================================
@app.route("/principal_approve/<int:req_id>")
def principal_approve(req_id):
    update_status(req_id, "principal_status", "Approved")

    data = get_request(req_id)

    # Send final QR to student
    qr_link = url_for("get_qr", token=data["qr_token"], _external=True)

    html = f"""
    <h3>Your GatePass is Fully Approved</h3>

    <b>Name:</b> {data['name']}<br>
    <b>Roll:</b> {data['roll']}<br><br>

    <h3>Your QR Code</h3>
    <img src="{qr_link}" width="220"><br><br>
    """

    send_email(data["email"], "GatePass Approved", html)

    return "<h3>Final Approval Done — QR sent to Student</h3>"


@app.route("/principal_reject/<int:req_id>")
def principal_reject(req_id):
    update_status(req_id, "principal_status", "Rejected")
    return "<h3>Rejected by Principal</h3>"

from flask import Flask, request, send_file, url_for
import sqlite3, qrcode, io, datetime, smtplib, random, os
from email.message import EmailMessage

app = Flask(__name__)

# ===== CONFIG =====
CLASS_EMAIL = "rg824797@gmail.com"
HOD_EMAIL = "rajg96090@gmail.com"
PRINCIPAL_EMAIL = "bhur4882@gmail.com"
REGISTRAR_EMAIL = "registrar@example.com"
SECURITY_EMAIL = "shivrajggct73839@gmail.com"

# Yahi se OTP aur sab mails jayenge (App Password)
SENDER_EMAIL = "aids24.shivrajgupta@ggct.co.in"
SENDER_PASS = "buekqnqazapxctme"

DB_NAME = "gatepass.db"

UPLOAD_FOLDER = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


# ===== DB CONNECT =====
def get_conn():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ===== DB INIT =====
def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute("DROP TABLE IF EXISTS requests")

    c.execute("""
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
            parent_confirm TEXT,
            created_at TEXT,
            class_note TEXT,
            used_status TEXT DEFAULT 'No',
            photo_path TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll TEXT,
            email TEXT,
            code TEXT,
            expires TEXT,
            verified TEXT DEFAULT 'No',
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()


# ===== EMAIL SENDER =====
def send_email(to, subject, html):
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = to
        msg.set_content("HTML required")
        msg.add_alternative(html, subtype="html")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
            s.login(SENDER_EMAIL, SENDER_PASS)
            s.send_message(msg)

        print("Email sent to:", to)
    except Exception as e:
        print("Email error:", e)


def get_base_url():
    return request.host_url.rstrip("/")


# ===== OTP System =====
def save_otp(roll, email, code, expires):
    conn = get_conn()
    conn.execute(
        "INSERT INTO otp_codes (roll,email,code,expires,verified,created_at) VALUES (?,?,?,?,?,?)",
        (roll, email, code, expires, "No", datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    conn.commit()
    conn.close()


def send_otp_email(roll, email):
    otp = str(random.randint(100000, 999999))
    exp = (datetime.datetime.now() + datetime.timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M:%S")

    html = f"<h2>Your OTP</h2><h1>{otp}</h1><p>Valid for 10 minutes.</p>"

    send_email(email, "GatePass OTP", html)
    save_otp(roll, email, otp, exp)
    return True


def verify_otp(roll, email, otp):
    conn = get_conn()
    row = conn.execute(
        "SELECT id,expires FROM otp_codes WHERE roll=? AND email=? AND code=? ORDER BY id DESC LIMIT 1",
        (roll, email, otp)
    ).fetchone()
    if not row:
        return False

    exp = datetime.datetime.strptime(row["expires"], "%Y-%m-%d %H:%M:%S")
    if datetime.datetime.now() > exp:
        return False

    conn.execute("UPDATE otp_codes SET verified='Yes' WHERE id=?", (row["id"],))
    conn.commit()
    conn.close()
    return True


def otp_verified(roll, email):
    conn = get_conn()
    row = conn.execute(
        "SELECT verified,expires FROM otp_codes WHERE roll=? AND email=? ORDER BY id DESC LIMIT 1",
        (roll, email)
    ).fetchone()
    conn.close()

    if not row:
        return False
    if row["verified"] != "Yes":
        return False

    exp = datetime.datetime.strptime(row["expires"], "%Y-%m-%d %H:%M:%S")
    return datetime.datetime.now() <= exp
# ===== HOME PAGE (UI + OTP + PHOTO UPLOAD) =====
@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Gate Pass – GGCT</title>
        <style>
            body {
                background: linear-gradient(135deg,#0d47a1,#1976d2);
                font-family: Arial;
                padding: 0;
                margin: 0;
            }
            .main {
                width: 420px;
                margin: 120px auto;
                background: white;
                padding: 25px;
                border-radius: 15px;
                box-shadow: 0 10px 40px rgba(0,0,0,.3);
            }
            input {
                width: 100%;
                padding: 10px;
                margin-bottom: 10px;
                border-radius: 10px;
                border: 1px solid #aaa;
            }
            button {
                width: 100%;
                padding: 10px;
                border: none;
                border-radius: 20px;
                background: #1565c0;
                color: white;
                font-size: 16px;
            }
            .otp-btn {
                background: #0d47a1;
            }
        </style>
    </head>
    <body>

    <div class='main'>
        <h2 align=center>🪪 Gate Pass Request</h2>

        <form method="POST" action="/submit" enctype="multipart/form-data">

            <input name="name" placeholder="Name" required>
            <input name="branch" value="AIDS" required>
            <input name="year" placeholder="Year (1/2/3/4)" required>
            <input name="roll" id="roll" placeholder="Roll No" required>

            <input name="email" id="email" placeholder="Email" type="email" required>

            <button type="button" class="otp-btn" id="sendOtp">Send OTP</button>

            <div id="otpBox" style="display:none;">
                <input name="otp" id="otp" placeholder="Enter OTP">
                <button type="button" id="verifyOtp">Verify OTP</button>
                <p id="otpStatus"></p>
            </div>

            <input name="parent_mobile" placeholder="Parent Mobile">

            <label>Upload Photo</label>
            <input type="file" name="photo" accept="image/*">

            <input name="reason" placeholder="Reason" required>
            <input name="out_time" placeholder="Out Time" required>
            <input name="date" type="date" required>

            <button type="submit">Submit</button>
        </form>
    </div>

    <script>
    document.getElementById("sendOtp").onclick = function() {
        let email = document.getElementById("email").value;
        let roll = document.getElementById("roll").value;
        if (!email || !roll) { alert("Enter Email & Roll first"); return; }

        fetch("/send_otp", {
            method:"POST",
            headers:{"Content-Type":"application/x-www-form-urlencoded"},
            body:"email="+email+"&roll="+roll
        }).then(res=>res.text()).then(t=>{
            document.getElementById("otpBox").style.display="block";
            document.getElementById("otpStatus").innerHTML="OTP sent ✔️";
        });
    };

    document.getElementById("verifyOtp").onclick = function() {
        let email = document.getElementById("email").value;
        let roll = document.getElementById("roll").value;
        let otp = document.getElementById("otp").value;

        fetch("/verify_otp", {
            method:"POST",
            headers:{"Content-Type":"application/x-www-form-urlencoded"},
            body:"email="+email+"&roll="+roll+"&otp="+otp
        }).then(async res=>{
            let t = await res.text();
            document.getElementById("otpStatus").innerHTML = t;
            if(res.ok) document.getElementById("otpStatus").style.color="green";
            else document.getElementById("otpStatus").style.color="red";
        });
    };
    </script>

    </body>
    </html>
    """


# ====== SUBMIT ROUTE ======
@app.route("/send_otp", methods=["POST"])
def send_otp_route():
    email = request.form["email"].strip()
    roll = request.form["roll"].strip()
    send_otp_email(roll, email)
    return "OTP Sent"


@app.route("/verify_otp", methods=["POST"])
def verify_otp_route():
    email = request.form["email"]
    roll = request.form["roll"]
    otp = request.form["otp"]
    if verify_otp(roll, email, otp):
        return "OTP Verified ✔️"
    return "Invalid OTP ❌", 400


# ===== SUBMIT FORM =====
@app.route("/submit", methods=["POST"])
def submit():
    name = request.form["name"]
    branch = request.form["branch"].upper()
    year = request.form["year"]
    roll = request.form["roll"]
    email = request.form["email"]
    reason = request.form["reason"]
    out_time = request.form["out_time"]
    date = request.form["date"]

    if branch != "AIDS":
        return "<h3>Only AIDS branch allowed.</h3>"

    if not otp_verified(roll, email):
        return "<h3>OTP not verified.</h3>"

    photo = request.files.get("photo")
    photo_path = ""
    if photo:
        fname = f"{roll}_{datetime.datetime.now().timestamp()}.jpg"
        photo_path = f"static/uploads/{fname}"
        photo.save(photo_path)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO requests
        (name,branch,year,roll,email,reason,out_time,date,
         class_status,hod_status,principal_status,parent_confirm,
         created_at,class_note,used_status,photo_path)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        name, branch, year, roll, email, reason, out_time, date,
        "Pending", "Pending", "Pending", "No",
        datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "", "No", photo_path
    ))
    conn.commit()
    req_id = cur.lastrowid
    conn.close()

    approve = get_base_url() + "/class_approve/" + str(req_id)
    reject = get_base_url() + "/class_reject/" + str(req_id)

    html = f"""
    <h2>New GatePass Request</h2>
    <img src='/{photo_path}' width='150'><br>
    <b>Name:</b> {name}<br>
    <b>Roll:</b> {roll}<br>
    <b>Reason:</b> {reason}<br>
    <br>
    <a href="{approve}">Approve</a> |
    <a href="{reject}">Reject</a>
    """

    send_email(CLASS_EMAIL, "GatePass Request", html)
    send_email(email, "GatePass Submitted", "<h3>Your request is submitted.</h3>")

    return "<h2>Submitted ✔️</h2>"
# ===== CLASS INCHARGE APPROVAL =====
@app.route("/class_approve/<int:req_id>", methods=["GET", "POST"])
def class_approve(req_id):
    conn = get_conn()
    r = conn.execute("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone()

    if request.method == "POST":
        note = request.form.get("note", "")
        conn.execute("UPDATE requests SET class_note=?, class_status='Approved' WHERE id=?", (note, req_id))
        conn.commit()

        approve = get_base_url() + "/hod_approve/" + str(req_id)
        reject = get_base_url() + "/hod_reject/" + str(req_id)

        html = f"""
        <h2>Class Approved</h2>
        <img src='/{r['photo_path']}' width='150'><br>
        <b>Name:</b> {r['name']}<br>
        <b>Roll:</b> {r['roll']}<br>
        <b>Note:</b> {note}<br><br>

        <a href="{approve}">HOD Approve</a> |
        <a href="{reject}">HOD Reject</a>
        """

        send_email(HOD_EMAIL, "HOD Approval Needed", html)

        return "Sent to HOD ✔️"

    return f"""
    <h2>Class Approval</h2>
    <img src='/{r['photo_path']}' width='150'><br>
    <form method="POST">
        <textarea name="note" placeholder="Note"></textarea><br>
        <button>Approve & Send to HOD</button>
    </form>
    """


@app.route("/class_reject/<int:req_id>")
def class_reject(req_id):
    conn = get_conn()
    conn.execute("UPDATE requests SET class_status='Rejected' WHERE id=?", (req_id,))
    conn.commit()
    return "<h3>Rejected</h3>"


# ===== HOD =====
@app.route("/hod_approve/<int:req_id>")
def hod_approve(req_id):
    conn = get_conn()
    conn.execute("UPDATE requests SET hod_status='Approved' WHERE id=?", (req_id,))
    conn.commit()

    r = conn.execute("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone()

    approve = get_base_url() + "/principal_approve/" + str(req_id)
    reject = get_base_url() + "/principal_reject/" + str(req_id)
    qr_link = get_base_url() + f"/qrcode/{req_id}"

    html = f"""
    <h2>HOD Approved</h2>
    <img src='/{r['photo_path']}' width='150'><br>
    <b>Name:</b> {r['name']}<br>
    <b>Roll:</b> {r['roll']}<br>

    <p>QR For Principal & Registrar:</p>
    <a href="{qr_link}">View QR</a><br>
    <img src="{qr_link}" width="200"><br><br>

    <a href="{approve}">Principal Approve</a> |
    <a href="{reject}">Reject</a>
    """

    send_email(PRINCIPAL_EMAIL, "Principal Approval Needed", html)
    send_email(REGISTRAR_EMAIL, "Registrar Approval Needed", html)

    return "<h3>Sent to Principal + Registrar ✔️</h3>"


@app.route("/hod_reject/<int:req_id>")
def hod_reject(req_id):
    conn = get_conn()
    conn.execute("UPDATE requests SET hod_status='Rejected' WHERE id=?", (req_id,))
    conn.commit()
    return "<h3>Rejected</h3>"


# ===== PRINCIPAL FINAL =====
@app.route("/principal_approve/<int:req_id>")
def principal_approve(req_id):
    conn = get_conn()
    conn.execute("UPDATE requests SET principal_status='Approved' WHERE id=?", (req_id,))
    conn.commit()

    r = conn.execute("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone()
    qr_link = get_base_url() + f"/qrcode/{req_id}"

    html = f"""
    <h2>GatePass Approved ✔️</h2>
    <img src='/{r['photo_path']}' width='150'><br>
    <p>Your QR:</p>
    <a href="{qr_link}">Open QR</a><br>
    <img src="{qr_link}" width="200"><br>
    """

    send_email(r["email"], "Your GatePass QR", html)

    return "<h3>QR SENT TO STUDENT ✔️</h3>"


@app.route("/principal_reject/<int:req_id>")
def principal_reject(req_id):
    conn = get_conn()
    conn.execute("UPDATE requests SET principal_status='Rejected' WHERE id=?", (req_id,))
    conn.commit()
    return "<h3>Rejected</h3>"


# ===== QR CODE =====
@app.route("/qrcode/<int:req_id>")
def qrcode_route(req_id):
    r = get_request(req_id := req_id)
    qr_data = (
        f"GatePass ID:{r['id']} | "
        f"Name:{r['name']} | Roll:{r['roll']} | Branch:{r['branch']} | "
        f"Class:{r['class_status']} | HOD:{r['hod_status']} | Principal:{r['principal_status']}"
    )
    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)
    return send_file(buf, mimetype="image/png")


def get_request(req_id):
    conn = get_conn()
    return conn.execute("SELECT * FROM requests WHERE id=?", (req_id,)).fetchone()


# ===== SECURITY SCANNER =====
@app.route("/scanner")
def scanner():
    return """
    <h2>Security Scanner</h2>
    <div id="reader" style="width:300px;"></div>
    <script src="https://unpkg.com/html5-qrcode"></script>
    <script>
        function onScanSuccess(text) {
            window.location = "/verify?q=" + encodeURIComponent(text);
        }
        new Html5QrcodeScanner("reader",{fps:10,qrbox:250}).render(onScanSuccess);
    </script>
    """


# ===== VERIFY QR (One Time Use) =====
@app.route("/verify")
def verify():
    raw = request.args.get("q")
    try:
        gid = int(raw.split("GatePass ID:")[1].split("|")[0])
    except:
        return "<h3>Invalid QR</h3>"

    conn = get_conn()
    r = conn.execute("SELECT * FROM requests WHERE id=?", (gid,)).fetchone()

    if r["used_status"] == "Yes":
        return "<h2>Already Used ❌</h2>"

    if r["principal_status"] != "Approved":
        return "<h2>Not Fully Approved ❌</h2>"

    conn.execute("UPDATE requests SET used_status='Yes' WHERE id=?", (gid,))
    conn.commit()

    return f"""
    <h2>Valid ✔️</h2>
    <p>Name: {r['name']}</p>
    <p>Roll: {r['roll']}</p>
    """


# ===== ADMIN =====
@app.route("/admin")
def admin():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM requests").fetchall()

    html = "<h2>All Requests</h2><table border=1>"
    for r in rows:
        html += f"<tr><td>{r['id']}</td><td>{r['name']}</td><td>{r['roll']}</td><td>{r['class_status']}</td></tr>"
    html += "</table>"
    return html


# ===== RUN =====
if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5000)

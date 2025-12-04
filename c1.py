from flask import Flask, request, send_file, url_for, flash, redirect
import sqlite3, qrcode, io, datetime, smtplib, os, random
from email.message import EmailMessage

app = Flask(__name__)
app.secret_key = "dev-secret-please-change"

# ====== CONFIG ======
CLASS_EMAIL = "rg824797@gmail.com"
HOD_EMAIL = "rajg96090@gmail.com"
PRINCIPAL_EMAIL = "bhur4882@gmail.com"
SECURITY_EMAIL = "shivrajggct73839@gmail.com"

SENDER_EMAIL = "aids24.shivrajgupta@ggct.co.in"
SENDER_PASS = "buekqnqazapxctme"

DB_NAME = "gatepass.db"
UPLOAD_FOLDER = "static/uploads"

# ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ====== DB HELPERS ======
def get_conn():
    # enable row access by name
    conn = sqlite3.connect(DB_NAME, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Original requests table (drop/create ensures new columns are present during dev)
    c.execute("DROP TABLE IF EXISTS requests")
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS requests (
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
            used_status TEXT DEFAULT 'No'
        )
        """
    )

    # NEW: students table (registered students)
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll TEXT UNIQUE,
            name TEXT,
            branch TEXT,
            year TEXT,
            email TEXT,
            parent_mobile TEXT,
            photo_path TEXT,
            created_at TEXT
        )
        """
    )

    # NEW: otp_codes table
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            roll TEXT,
            email TEXT,
            code TEXT,
            expires TEXT,
            verified TEXT DEFAULT 'No',
            created_at TEXT
        )
        """
    )

    conn.commit()
    conn.close()

# call init on startup (creates DB if not exists)
init_db()

# ====== EMAIL ======
def send_email(to_email, subject, html):
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = SENDER_EMAIL
        msg["To"] = to_email
        msg.set_content("HTML email required")
        msg.add_alternative(html, subtype="html")

        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(SENDER_EMAIL, SENDER_PASS)
            smtp.send_message(msg)

        print("✅ Email sent to", to_email)
    except Exception as e:
        print("❌ Email failed:", e)

def get_base_url():
    return request.host_url.rstrip("/")

# ====== NEW HELPERS: student + otp ======
def register_student_in_db(roll, name, branch, year, email, parent_mobile, photo_path=""):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO students (roll,name,branch,year,email,parent_mobile,photo_path,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (roll, name, branch, year, email, parent_mobile, photo_path, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # already registered; just ignore
        pass
    finally:
        conn.close()

def get_student_by_roll(roll):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM students WHERE roll=?", (roll,))
    row = c.fetchone()
    conn.close()
    return row

def save_otp(roll, email, code, expires):
    conn = get_conn()
    c = conn.cursor()
    c.execute("INSERT INTO otp_codes (roll,email,code,expires,verified,created_at) VALUES (?,?,?,?,?,?)",
              (roll, email, code, expires.isoformat(), "No", datetime.datetime.now().strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    conn.close()

def verify_otp_code(roll, email, code):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT id,expires,verified FROM otp_codes WHERE roll=? AND email=? AND code=? ORDER BY id DESC LIMIT 1",
              (roll, email, code))
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "OTP गलत है"
    if row["verified"] == "Yes":
        conn.close()
        return False, "OTP पहले से verify हो चुका है"
    try:
        expires = datetime.datetime.fromisoformat(row["expires"])
    except Exception:
        conn.close()
        return False, "OTP data invalid"
    if datetime.datetime.now() > expires:
        conn.close()
        return False, "OTP expire हो गया"
    # mark verified
    c.execute("UPDATE otp_codes SET verified='Yes' WHERE id=?", (row["id"],))
    conn.commit()
    conn.close()
    return True, "OTP verified"

def is_email_verified_for_roll(roll, email):
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT verified FROM otp_codes WHERE roll=? AND email=? ORDER BY id DESC LIMIT 1", (roll, email))
    row = c.fetchone()
    conn.close()
    return bool(row and row["verified"] == "Yes")

def send_otp_email(roll, email):
    # generate 6 digit otp
    code = f"{random.randint(100000,999999)}"
    expires = datetime.datetime.now() + datetime.timedelta(minutes=10)  # 10 minutes expiry
    html = f"<h3>Your OTP for GatePass</h3><p>OTP: <b>{code}</b></p><p>Valid for 10 minutes.</p>"
    try:
        send_email(email, "GatePass OTP", html)
        save_otp(roll, email, code, expires)
        return True, "OTP भेज दिया गया"
    except Exception as e:
        print("OTP send failed:", e)
        return False, "OTP भेजने में समस्या"

# ====== HOME (STUDENT FORM – BLUE UI + GGCT HEADER) ======
@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Gyan Ganga College of Technology – Gate Pass</title>
        <style>/* same styles as before */ *{box-sizing:border-box; font-family: system-ui;} body{background:linear-gradient(135deg,#0d47a1,#1976d2);margin:0;display:flex;justify-content:center} .container{width:100%;max-width:460px;background:white;border-radius:12px;padding:24px;margin-top:100px;box-shadow:0 12px 36px rgba(0,0,0,0.25)}</style>
    </head>
    <body>
      <div class="container">
        <h2>🪪 Gate Pass Request</h2>
        <p>
          <a href="/register_student">Register (Student)</a> |
          <a href="/verify_otp_form">Verify OTP</a> |
          <a href="/scanner">Security Scanner</a> |
          <a href="/admin">Admin Panel</a>
        </p>
        <hr>
        <form method="POST" action="/submit">
            <label>Student Name</label><br><input name="name" required><br>
            <label>Branch</label><br><input name="branch" value="AIDS" required><br>
            <label>Year</label><br><input name="year" value="2" required><br>
            <label>Roll No.</label><br><input name="roll" required><br>
            <label>Email</label><br><input name="email" type="email" required><br>
            <label>Reason</label><br><input name="reason" required><br>
            <label>Out Time</label><br><input name="out_time" required><br>
            <label>Date</label><br><input type="date" name="date" required value=""><br><br>
            <button type="submit">Submit Gate Pass</button>
        </form>
      </div>
    </body>
    </html>
    """

# ====== REGISTER STUDENT (upload photo + send OTP) ======
@app.route("/register_student", methods=["GET","POST"])
def register_student():
    if request.method == "POST":
        roll = request.form.get("roll","").strip()
        name = request.form.get("name","").strip()
        branch = request.form.get("branch","").strip().upper()
        year = request.form.get("year","").strip()
        email = request.form.get("email","").strip()
        parent_mobile = request.form.get("parent_mobile","").strip()
        photo = request.files.get("photo")

        # Branch restriction
        if branch != "AIDS":
            return "<h3>Registration केवल AIDS branch के students के लिए है</h3>", 400

        # Basic roll-year validation: adjust this if your roll format differs
        try:
            y = int(year)
            curr_two = datetime.datetime.now().year % 100
            expected = (curr_two - (y-1)) % 100
            expected_s = str(expected).zfill(2)
            # example roll: 0208AD241001 -> take positions 6-8 (index 6:8) -> '24'
            if len(roll) >= 8:
                roll_year_code = roll[6:8]
                if roll_year_code != expected_s:
                    return f"<h3>Roll invalid for year. Expected code {expected_s} in roll (pos 7-8).</h3>", 400
        except Exception:
            return "<h3>Year invalid</h3>", 400

        photo_path = ""
        if photo:
            ext = os.path.splitext(photo.filename)[1].lower()
            fname = f"{roll}{ext}"
            fpath = os.path.join(UPLOAD_FOLDER, fname)
            photo.save(fpath)
            photo_path = fpath

        # save student
        register_student_in_db(roll, name, branch, year, email, parent_mobile, photo_path)

        # send OTP
        ok, msg = send_otp_email(roll, email)
        if ok:
            return f"<h3>Registered. {msg} Check your email for OTP.</h3><p><a href='/'>Back</a></p>"
        else:
            return f"<h3>Registered but OTP send failed: {msg}</h3><p><a href='/'>Back</a></p>", 500

    # GET -> form
    return """
    <h3>Student Register</h3>
    <form method="POST" enctype="multipart/form-data">
      Roll: <br><input name="roll"><br>
      Name: <br><input name="name"><br>
      Branch (AIDS): <br><input name="branch" value="AIDS"><br>
      Year: <br><input name="year" value="2"><br>
      Email: <br><input name="email"><br>
      Parent Mobile: <br><input name="parent_mobile"><br>
      Photo (ID): <br><input type="file" name="photo"><br><br>
      <button>Register & Send OTP</button>
    </form>
    <p><a href="/">Back</a></p>
    """

# ====== OTP VERIFY FORM & Endpoint ======
@app.route("/verify_otp_form")
def verify_otp_form():
    return """
    <h3>Verify OTP</h3>
    <form method="POST" action="/verify_otp">
      Roll: <br><input name="roll"><br>
      Email: <br><input name="email"><br>
      OTP: <br><input name="code"><br><br>
      <button>Verify</button>
    </form>
    <p><a href="/">Back</a></p>
    """

@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    roll = request.form.get("roll","").strip()
    email = request.form.get("email","").strip()
    code = request.form.get("code","").strip()
    ok, msg = verify_otp_code(roll, email, code)
    if ok:
        return f"<h3>OTP verified. अब आप GatePass भर सकते हैं.</h3><p><a href='/'>Back</a></p>"
    else:
        return f"<h3>OTP verification failed: {msg}</h3><p><a href='/'>Back</a></p>", 400

# ====== SUBMIT (STUDENT) ======
@app.route("/submit", methods=["POST"])
def submit():
    name = request.form["name"].strip()
    branch = request.form["branch"].strip().upper()
    year = request.form["year"].strip()
    roll = request.form["roll"].strip()
    email = request.form["email"].strip()
    reason = request.form["reason"].strip()
    out_time = request.form["out_time"].strip()
    date = request.form["date"].strip()

    # branch restriction
    if branch != "AIDS":
        return "<h3>Only AIDS branch allowed to submit</h3>", 400

    # ensure student is registered and OTP verified
    student = get_student_by_roll(roll)
    if not student:
        return "<h3>Student not registered. Please register first.</h3>", 400

    if student["email"].lower() != email.lower():
        return "<h3>Email does not match registered email for this roll.</h3>", 400

    if not is_email_verified_for_roll(roll, email):
        return "<h3>OTP not verified for this email. Verify OTP first.</h3>", 400

    # proceed to add request (use existing add_request)
    req_id = add_request(name, branch, year, roll, email, reason, out_time, date)

    base = get_base_url()
    approve_url = f"{base}{url_for('class_approve', req_id=req_id)}"
    reject_url = f"{base}{url_for('class_reject', req_id=req_id)}"
    qr_url = f"{base}{url_for('qrcode_route', req_id=req_id)}"

    html_class = f"""
    <h3>🪪 New Gate Pass Request</h3>
    <p>
    <b>Name:</b> {name}<br>
    <b>Branch:</b> {branch}<br>
    <b>Year:</b> {year}<br>
    <b>Roll:</b> {roll}<br>
    <b>Email:</b> {email}<br>
    <b>Reason:</b> {reason}<br>
    <b>Out Time:</b> {out_time}<br>
    <b>Date:</b> {date}<br>
    </p>

    <p>🔗 Live QR Status: <a href="{qr_url}">View QR</a></p>
    <img src="{qr_url}" alt="GatePass QR"><br><br>

    <a href="{approve_url}" style="background:green;color:white;padding:10px;text-decoration:none;">
      ✅ Approve (Add Note)
    </a>
    &nbsp;
    <a href="{reject_url}" style="background:red;color:white;padding:10px;text-decoration:none;">
      ❌ Reject
    </a>
    """

    send_email(CLASS_EMAIL, f"Gate Pass Request from {name}", html_class)

    # Student ko confirmation
    send_email(
        email,
        "Gate Pass Submitted",
        f"<h3>Your gate pass request is submitted.</h3><p>Status: Pending (Class Incharge)</p><p>QR: <a href='{qr_url}'>View QR</a></p>",
    )

    return "<h3>✅ Request submitted successfully! Sent to Class Incharge & Student.</h3>"

# ====== CLASS INCHARGE ======
@app.route("/class_approve/<int:req_id>", methods=["GET", "POST"])
def class_approve(req_id):
    data = get_request(req_id)
    if not data:
        return "<h3>❌ Invalid Request ID</h3>"

    if request.method == "POST":
        action = request.form.get("action")
        note = request.form.get("note", "").strip()

        if note:
            update_class_note(req_id, note)

        if action == "approve":
            update_status(req_id, "class_status", "Approved")

            data = get_request(req_id)
            base = get_base_url()
            hod_approve_url = f"{base}{url_for('hod_approve', req_id=req_id)}"
            hod_reject_url = f"{base}{url_for('hod_reject', req_id=req_id)}"
            qr_url = f"{base}{url_for('qrcode_route', req_id=req_id)}"

            note_html = f"""
            <div style='border:2px solid #0084ff; padding:10px; border-radius:8px; background:#e7f1ff;'>
              <b>📌 Note from Class Incharge:</b><br>{data[14] or 'No note given.'}
            </div><br>
            """

            html_hod = f"""
            <h3>📩 Gate Pass Request (Class Incharge Approved)</h3>

            {note_html}

            <p>
            <b>Name:</b> {data[1]}<br>
            <b>Branch:</b> {data[2]}<br>
            <b>Year:</b> {data[3]}<br>
            <b>Roll:</b> {data[4]}<br>
            <b>Email:</b> {data[5]}<br>
            <b>Reason:</b> {data[6]}<br>
            <b>Out Time:</b> {data[7]}<br>
            <b>Date:</b> {data[8]}<br>
            <b>Class Incharge Status:</b> {data[9]}<br>
            </p>

            <p>🔗 Live QR Status: <a href="{qr_url}">View QR</a></p>
            <img src="{qr_url}" alt="GatePass QR"><br><br>

            <a href="{hod_approve_url}" style="background:green;color:white;padding:10px;text-decoration:none;">
              ✅ Approve
            </a>
            &nbsp;
            <a href="{hod_reject_url}" style="background:red;color:white;padding:10px;text-decoration:none;">
              ❌ Reject
            </a>
            """

            send_email(HOD_EMAIL, "HOD Approval Needed – Gate Pass", html_hod)

            # Student notification
            send_email(
                data[5],
                "Gate Pass Update – Class Incharge Approved",
                f"<h3>Your gate pass is APPROVED by Class Incharge.</h3><p>Next: HOD Approval</p><p>QR: <a href='{qr_url}'>View QR</a></p>",
            )

            return "<h3>✅ Class Incharge Approved and sent to HOD.</h3>"

        elif action == "reject":
            update_status(req_id, "class_status", "Rejected")
            # Student rejection mail
            send_email(
                data[5],
                "Gate Pass Rejected by Class Incharge",
                "<h3>Your gate pass has been REJECTED by Class Incharge.</h3>",
            )
            return "<h3>❌ Class Incharge Rejected the Request.</h3>"

        else:
            return "<h3>❌ Invalid action.</h3>"

    # GET → Approval form
    return f"""
    <h2>Class Incharge Approval</h2>
    <p><b>Request ID:</b> {data[0]}<br>
    <b>Name:</b> {data[1]}<br>
    <b>Branch:</b> {data[2]}<br>
    <b>Year:</b> {data[3]}<br>
    <b>Roll:</b> {data[4]}<br>
    <b>Email:</b> {data[5]}<br>
    <b>Reason:</b> {data[6]}<br>
    <b>Out Time:</b> {data[7]}<br>
    <b>Date:</b> {data[8]}</p>

    <form method="POST">
      <label><b>Note for HOD / Principal / Security:</b></label><br>
      <textarea name="note" rows="4" cols="50" placeholder="Parents se call par baat ho gayi...">{data[14] or ""}</textarea>
      <br><br>
      <button type="submit" name="action" value="approve">✅ Approve & Send to HOD</button>
      &nbsp;
      <button type="submit" name="action" value="reject">❌ Reject</button>
    </form>
    """

@app.route("/class_reject/<int:req_id>")
def class_reject(req_id):
    update_status(req_id, "class_status", "Rejected")
    return "<h3>❌ Class Incharge Rejected the Request.</h3>"

# ====== HOD ======
@app.route("/hod_approve/<int:req_id>")
def hod_approve(req_id):
    update_status(req_id, "hod_status", "Approved")
    data = get_request(req_id)
    if not data:
        return "<h3>❌ Invalid Request ID</h3>"

    base = get_base_url()
    principal_approve_url = f"{base}{url_for('principal_approve', req_id=req_id)}"
    registrar_approve_url = f"{base}{url_for('registrar_approve', req_id=req_id)}"
    principal_reject_url = f"{base}{url_for('principal_reject', req_id=req_id)}"
    qr_url = f"{base}{url_for('qrcode_route', req_id=req_id)}"

    note_html = f"""
    <div style='border:2px solid #0084ff; padding:10px; border-radius:8px; background:#e7f1ff;'>
      <b>📌 Note from Class Incharge:</b><br>{data[14] or 'No note given.'}
    </div><br>
    """

    html_principal = f"""
    <h3>📩 Gate Pass Request (HOD Approved)</h3>

    {note_html}

    <p>
    <b>Name:</b> {data[1]}<br>
    <b>Roll:</b> {data[4]}<br>
    <b>Reason:</b> {data[6]}<br>
    </p>

    <a href="{principal_approve_url}" style="background:green;color:white;padding:10px;text-decoration:none;">Principal Approve</a>
    &nbsp;
    <a href="{registrar_approve_url}" style="background:orange;color:white;padding:10px;text-decoration:none;">Registrar Approve</a>
    &nbsp;
    <a href="{principal_reject_url}" style="background:red;color:white;padding:10px;text-decoration:none;">Reject</a>
    """

    # send to principal & registrar
    send_email(PRINCIPAL_EMAIL, "Principal Approval Needed – Gate Pass", html_principal)
    send_email("bhur4882@gmail.com", "Registrar Approval Needed – Gate Pass", html_principal)

    # Student notification
    send_email(data[5], "Gate Pass Update – HOD Approved", f"<h3>Your gate pass is APPROVED by HOD. Next: Principal/Registrar</h3><p>QR: <a href='{qr_url}'>View</a></p>")

    return "<h3>✅ HOD Approved and sent to Principal & Registrar.</h3>"

@app.route("/hod_reject/<int:req_id>")
def hod_reject(req_id):
    update_status(req_id, "hod_status", "Rejected")
    data = get_request(req_id)
    if data:
        send_email(data[5], "Gate Pass Rejected by HOD", "<h3>Your gate pass has been REJECTED by HOD.</h3>")
    return "<h3>❌ HOD Rejected the Request.</h3>"

# ====== PRINCIPAL ======
@app.route("/principal_approve/<int:req_id>")
def principal_approve(req_id):
    update_status(req_id, "principal_status", "Approved")
    data = get_request(req_id)
    if not data:
        return "<h3>❌ Invalid Request ID</h3>"

    base = get_base_url()
    qr_url = f"{base}{url_for('qrcode_route', req_id=req_id)}"

    # send QR to security & student (QR here is live image of request; it's generated via qrcode_route)
    send_email(SECURITY_EMAIL, "Final Gate Pass QR – Security Check", f"<p>Final QR: <a href='{qr_url}'>Open</a></p>")
    send_email(data[5], "Gate Pass Fully Approved – Principal", f"<h3>Your gate pass is FULLY APPROVED.</h3><p>Show this QR at Security: <a href='{qr_url}'>Open QR</a></p>")

    return "<h3>✅ Principal Approved. Final QR sent to Security & Student.</h3>"

@app.route("/registrar_approve/<int:req_id>")
def registrar_approve(req_id):
    # registrar can also approve; mark registrar approval by setting principal_status too (optional)
    update_status(req_id, "principal_status", "Approved")
    data = get_request(req_id)
    if data:
        base = get_base_url()
        qr_url = f"{base}{url_for('qrcode_route', req_id=req_id)}"
        send_email(SECURITY_EMAIL, "Final Gate Pass QR – Security Check", f"<p>Final QR: <a href='{qr_url}'>Open</a></p>")
        send_email(data[5], "Gate Pass Fully Approved – Registrar", f"<h3>Your gate pass is FULLY APPROVED by Registrar.</h3><p>QR: <a href='{qr_url}'>Open</a></p>")
    return "<h3>Registrar Approved & QR sent.</h3>"

@app.route("/principal_reject/<int:req_id>")
def principal_reject(req_id):
    update_status(req_id, "principal_status", "Rejected")
    data = get_request(req_id)
    if data:
        send_email(data[5], "Gate Pass Rejected by Principal", "<h3>Your gate pass has been REJECTED by Principal.</h3>")
    return "<h3>❌ Principal Rejected the Request.</h3>"

# ====== QR CODE (DYNAMIC) ======
@app.route("/qrcode/<int:req_id>")
def qrcode_route(req_id):
    data = get_request(req_id)
    if not data:
        return "No such record found."

    # show dynamic QR based on request id and statuses
    qr_data = (
        f"GatePass ID:{data[0]} | Name:{data[1]} | Year:{data[3]} | Branch:{data[2]} | "
        f"Roll:{data[4]} | Class:{data[9]} | HOD:{data[10]} | Principal:{data[11]}"
    )

    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)

    return send_file(buf, mimetype="image/png")

# ====== SECURITY SCANNER PAGE (Scanner 2.0) ======
@app.route("/scanner")
def scanner():
    return """
    <h2>🔍 Security QR Scanner</h2>
    <div id="reader" style="width: 320px; max-width: 100%;"></div>

    <script src="https://unpkg.com/html5-qrcode"></script>

    <script>
        function onScanSuccess(decodedText, decodedResult) {
            // redirect to verify page
            window.location.href = '/verify?q=' + encodeURIComponent(decodedText);
        }
        function onScanFailure(error) { console.log(error); }
        let html5QrcodeScanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 });
        html5QrcodeScanner.render(onScanSuccess, onScanFailure);
    </script>
    """

# ====== VERIFY (ONE-TIME USE) ======
@app.route("/verify")
def verify_qr():
    raw = request.args.get("q", "")

    # 1) extract GatePass ID
    try:
        gp_id_str = raw.split("GatePass ID:")[1].split("|")[0].strip()
        gp_id = int(gp_id_str)
    except Exception:
        return "<h3>❌ Invalid QR Code Format</h3>"

    # 2) fetch
    req = get_request(gp_id)
    if not req:
        return "<h3>❌ No record found for this GatePass ID.</h3>"

    # 3) Check used
    if req[15] == "Yes":
        return """
        <h2>❌ ALREADY USED</h2>
        <p>This gate pass has already been used at security. Student cannot reuse this QR.</p>
        """

    # 4) Check approvals
    if (req[9] == "Approved" and req[10] == "Approved" and req[11] == "Approved"):
        mark_used(gp_id)
        # notify class incharge by email
        try:
            # attempt to find student's branch/year and select class incharge email logic if you have mapping
            send_email(CLASS_EMAIL, "Student Exited - GatePass Used", f"<p>{req[1]} ({req[4]}) used QR at {datetime.datetime.now()}</p>")
        except:
            pass

        return f"""
        <h2>✅ VALID PASS (Now Marked as Used)</h2>
        <p><b>Name:</b> {req[1]}</p>
        <p><b>Year:</b> {req[3]}</p>
        <p><b>Roll:</b> {req[4]}</p>
        <p><b>Branch:</b> {req[2]}</p>
        <p><b>Reason:</b> {req[6]}</p>
        <p><b>Out Time:</b> {req[7]}</p>
        <p><b>Date:</b> {req[8]}</p>
        """
    else:
        return """
        <h2>❌ NOT FULLY APPROVED</h2>
        <p>All three approvals (Class Incharge, HOD, Principal/Registrar) are required
        before student can leave the campus.</p>
        """

# ====== ADMIN PANEL ======
@app.route("/admin")
def admin():
    conn = get_conn()
    c = conn.cursor()
    c.execute("SELECT * FROM requests")
    rows = c.fetchall()
    conn.close()

    html = "<h2>📋 All Gate Pass Requests</h2><table border=1>"
    html += "<tr><th>ID</th><th>Name</th><th>Year</th><th>Roll</th><th>Class</th><th>HOD</th><th>Principal</th><th>Used?</th></tr>"

    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[9]}</td><td>{r[10]}</td><td>{r[11]}</td><td>{r[15]}</td></tr>"

    html += "</table><br><a href='/'>Back</a>"
    return html

# ====== EXISTING DB FUNCTIONS (requests helpers) ======
def add_request(name, branch, year, roll, email, reason, out_time, date):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO requests
        (name, branch, year, roll, email, reason, out_time, date,
         class_status, hod_status, principal_status, parent_confirm,
         created_at, class_note, used_status)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            name,
            branch,
            year,
            roll,
            email,
            reason,
            out_time,
            date,
            "Pending",
            "Pending",
            "Pending",
            "No",
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "",
            "No",
        ),
    )
    conn.commit()
    rid = c.lastrowid
    conn.close()
    return rid

def update_status(req_id, field, new_status):
    conn = get_conn()
    c = conn.cursor()
    # protect against sql injection by allowing only expected column names
    allowed = {"class_status","hod_status","principal_status","parent_confirm","used_status","class_note"}
    if field not in allowed:
        conn.close()
        return
    c.execute(f"UPDATE requests SET {field}=? WHERE id=?", (new_status, req_id))
    conn.commit()
    conn.close()

def update_class_note(req_id, note):
    conn = get_conn()
    c = conn.cursor()
    c.execute("UPDATE requests SET class_note=? WHERE id=?", (note, req_id))
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

# ====== MAIN ======
if __name__ == "__main__":
    # if you want a fresh DB while developing, delete gatepass.db
    # os.remove(DB_NAME)  # uncomment to force recreate (be careful)
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)

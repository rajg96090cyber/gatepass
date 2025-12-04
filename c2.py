from flask import Flask, request, send_file, url_for, jsonify
import sqlite3, qrcode, io, datetime, smtplib, os, random
from email.message import EmailMessage

app = Flask(__name__)

# ====== CONFIG ======
CLASS_EMAIL = "rg824797@gmail.com"
HOD_EMAIL = "rajg96090@gmail.com"
PRINCIPAL_EMAIL = "bhur4882@gmail.com"
REGISTRAR_EMAIL = "rajuji9828087@gmail.com"  # chaaho to alag email rakh sakte ho

SENDER_EMAIL = "aids24.shivrajgupta@ggct.co.in"
SENDER_PASS = "buekqnqazapxctme"

DB_NAME = "gatepass.db"

# ====== DB HELPERS ======
def get_conn():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Purani requests table hata do (students/otp ko mat hataana)
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

    # Students table – registration ke liye (photo + parent number)
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

    # OTP table – email verification ke liye
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS otp_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
            "Pending",      # class_status
            "Pending",      # hod_status
            "Pending",      # principal_status
            "No",           # parent_confirm
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "",             # class_note
            "No",           # used_status
        ),
    )

    conn.commit()
    rid = c.lastrowid
    conn.close()
    return rid


def update_status(req_id, field, new_status):
    conn = get_conn()
    c = conn.cursor()
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


# ====== STUDENT + OTP HELPERS ======
def register_student(roll, name, branch, year, email, parent_mobile, photo_path=""):
    conn = get_conn()
    c = conn.cursor()
    try:
        c.execute(
            "INSERT INTO students (roll,name,branch,year,email,parent_mobile,photo_path,created_at) VALUES (?,?,?,?,?,?,?,?)",
            (
                roll,
                name,
                branch,
                year,
                email,
                parent_mobile,
                photo_path,
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            ),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        # already registered
        pass
    conn.close()


def get_student_by_roll(roll):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT roll,name,branch,year,email,parent_mobile,photo_path FROM students WHERE roll=?",
        (roll,),
    )
    row = c.fetchone()
    conn.close()
    return row


def save_otp(email, code, expires):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "INSERT INTO otp_codes (email,code,expires,verified,created_at) VALUES (?,?,?,?,?)",
        (
            email,
            code,
            expires.strftime("%Y-%m-%d %H:%M:%S"),
            "No",
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        ),
    )
    conn.commit()
    conn.close()


def verify_otp_code(email, code):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT id,code,expires,verified FROM otp_codes WHERE email=? ORDER BY id DESC LIMIT 1",
        (email,),
    )
    row = c.fetchone()
    if not row:
        conn.close()
        return False, "OTP नहीं मिला (पहले Send OTP करो)"
    otp_id, db_code, expires_str, verified = row
    if verified == "Yes":
        conn.close()
        return False, "ये OTP पहले ही verify हो चुका है"
    if db_code != code:
        conn.close()
        return False, "गलत OTP"
    try:
        expires = datetime.datetime.strptime(expires_str, "%Y-%m-%d %H:%M:%S")
    except Exception:
        conn.close()
        return False, "OTP की expiry data गलत है"
    if datetime.datetime.now() > expires:
        conn.close()
        return False, "OTP expire हो गया (10 मिनट से ज़्यादा हो गया)"
    # mark verified
    c.execute("UPDATE otp_codes SET verified='Yes' WHERE id=?", (otp_id,))
    conn.commit()
    conn.close()
    return True, "OTP verify हो गया ✅"


def is_email_verified(email):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "SELECT verified FROM otp_codes WHERE email=? ORDER BY id DESC LIMIT 1",
        (email,),
    )
    row = c.fetchone()
    conn.close()
    return bool(row and row[0] == "Yes")


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


def send_otp_email(email):
    code = f"{random.randint(100000, 999999)}"
    expires = datetime.datetime.now() + datetime.timedelta(minutes=10)
    html = f"""
    <h3>GatePass Email OTP</h3>
    <p>आपका OTP है: <b>{code}</b></p>
    <p>ये OTP <b>10 मिनट</b> तक valid रहेगा.</p>
    """
    send_email(email, "GatePass OTP Verification", html)
    save_otp(email, code, expires)


def get_base_url():
    return request.host_url.rstrip("/")


# ====== HOME (GATE PASS PAGE) ======
@app.route("/")
def home():
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Gyan Ganga College of Technology – Gate Pass</title>
        <style>
            * {
                box-sizing: border-box;
                font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
            }
            body {
                margin: 0;
                padding: 0;
                min-height: 100vh;
                background: linear-gradient(135deg, #0d47a1, #1976d2);
                display: flex;
                justify-content: center;
                align-items: flex-start;
            }
            .header {
                width: 100%;
                background: #0d47a1;
                color: white;
                text-align: center;
                padding: 18px 0;
                font-size: 1.4rem;
                font-weight: 700;
                letter-spacing: 0.8px;
                box-shadow: 0 4px 10px rgba(0,0,0,0.25);
                position: fixed;
                top: 0;
                left: 0;
                z-index: 99;
            }
            .corner-link {
                position: fixed;
                top: 10px;
                right: 16px;
                font-size: 0.8rem;
            }
            .corner-link a {
                color: #bbdefb;
                text-decoration: none;
                background: rgba(0,0,0,0.25);
                padding: 4px 8px;
                border-radius: 999px;
            }
            .container {
                width: 100%;
                max-width: 460px;
                background: #ffffff;
                border-radius: 16px;
                padding: 24px 28px 20px;
                box-shadow: 0 18px 45px rgba(0,0,0,0.25);
                margin-top: 120px;
            }
            .title {
                text-align: center;
                font-size: 1.6rem;
                font-weight: 700;
                color: #0d47a1;
                margin-bottom: 4px;
            }
            .subtitle {
                text-align: center;
                font-size: 0.9rem;
                color: #607d8b;
                margin-bottom: 20px;
            }
            label {
                display: block;
                font-size: 0.85rem;
                font-weight: 600;
                color: #1f2933;
                margin-bottom: 4px;
            }
            input {
                width: 100%;
                padding: 9px 11px;
                border-radius: 10px;
                border: 1px solid #cfd8dc;
                outline: none;
                font-size: 0.9rem;
                margin-bottom: 12px;
                transition: border 0.2s, box-shadow 0.2s;
            }
            input:focus {
                border-color: #1976d2;
                box-shadow: 0 0 0 2px rgba(25,118,210,0.15);
            }
            .row {
                display: flex;
                gap: 10px;
            }
            .row > div {
                flex: 1;
            }
            .btn-primary {
                width: 100%;
                border: none;
                cursor: pointer;
                background: linear-gradient(135deg, #1976d2, #1565c0);
                color: #fff;
                font-size: 1rem;
                font-weight: 600;
                padding: 10px 0;
                border-radius: 999px;
                margin-top: 4px;
                transition: transform 0.1s, box-shadow 0.1s, opacity 0.1s;
            }
            .btn-primary[disabled] {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .btn-secondary {
                border: none;
                cursor: pointer;
                background: #0d47a1;
                color: #fff;
                font-size: 0.8rem;
                padding: 6px 10px;
                border-radius: 999px;
                margin-left: 6px;
            }
            .btn-primary:hover:not([disabled]) {
                transform: translateY(-1px);
                box-shadow: 0 8px 18px rgba(25,118,210,0.4);
                opacity: 0.96;
            }
            .links {
                margin-top: 14px;
                display: flex;
                justify-content: space-between;
                font-size: 0.85rem;
            }
            .links a {
                color: #1565c0;
                text-decoration: none;
                font-weight: 600;
            }
            .links a:hover {
                text-decoration: underline;
            }
            #otp-msg {
                font-size: 0.8rem;
                min-height: 16px;
            }
        </style>
    </head>

    <body>
        <div class="header">
            GYAN GANGA COLLEGE OF TECHNOLOGY
        </div>

        <div class="corner-link">
            <a href="/register">New Student? Register</a>
        </div>

        <div class="container">
            <div class="title">🪪 Gate Pass Request</div>
            <div class="subtitle">Fill your details and submit for approval</div>

            <form method="POST" action="/submit" onsubmit="return checkSubmit(event)">
                <label for="name">Student Name</label>
                <input id="name" name="name" required>

                <div class="row">
                    <div>
                        <label for="branch">Branch</label>
                        <input id="branch" name="branch" required placeholder="AIDS">
                    </div>
                    <div>
                        <label for="year">Year</label>
                        <input id="year" name="year" required placeholder="1 / 2 / 3 / 4">
                    </div>
                </div>

                <div class="row">
                    <div>
                        <label for="roll">Roll No.</label>
                        <input id="roll" name="roll" required placeholder="0208AD241060">
                    </div>
                    <div>
                        <label for="email">Email</label>
                        <div style="display:flex; gap:4px; align-items:center;">
                            <input id="email" name="email" type="email" required placeholder="student@gmail.com" style="flex:1;">
                            <button type="button" class="btn-secondary" onclick="sendOtp()">Send OTP</button>
                        </div>
                    </div>
                </div>

                <label for="otp">Email OTP</label>
                <div style="display:flex; gap:4px; align-items:center;">
                    <input id="otp" name="otp" placeholder="6-digit OTP">
                    <button type="button" class="btn-secondary" onclick="verifyOtp()">Verify OTP</button>
                </div>
                <div id="otp-msg"></div>

                <label for="reason">Reason</label>
                <input id="reason" name="reason" required placeholder="e.g. Medical / Personal">

                <div class="row">
                    <div>
                        <label for="out_time">Out Time</label>
                        <input id="out_time" name="out_time" required placeholder="3:30 PM">
                    </div>
                    <div>
                        <label for="date">Date</label>
                        <input id="date" type="date" name="date" required>
                    </div>
                </div>

                <button id="submit-btn" class="btn-primary" type="submit" disabled>Submit Gate Pass</button>
            </form>

            <div class="links">
                <a href="/admin">📋 Admin Panel</a>
                <span></span>
            </div>
        </div>

        <script>
            let otpVerified = false;

            function setOtpMessage(msg, ok) {
                const el = document.getElementById('otp-msg');
                el.style.color = ok ? 'green' : 'red';
                el.textContent = msg || '';
            }

            function sendOtp() {
                const email = document.getElementById('email').value.trim();
                if (!email) {
                    alert('पहले email डालो');
                    return;
                }
                setOtpMessage('OTP भेजा जा रहा है...', true);

                fetch('/send_otp', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: 'email=' + encodeURIComponent(email)
                })
                .then(r => r.json())
                .then(data => {
                    setOtpMessage(data.message, data.ok);
                })
                .catch(err => {
                    console.error(err);
                    setOtpMessage('कुछ गड़बड़ हो गयी, दुबारा try करो', false);
                });
            }

            function verifyOtp() {
                const email = document.getElementById('email').value.trim();
                const otp = document.getElementById('otp').value.trim();
                if (!email || !otp) {
                    alert('Email और OTP दोनों डालो');
                    return;
                }
                setOtpMessage('OTP verify किया जा रहा है...', true);

                fetch('/verify_otp', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    body: 'email=' + encodeURIComponent(email) + '&code=' + encodeURIComponent(otp)
                })
                .then(r => r.json())
                .then(data => {
                    setOtpMessage(data.message, data.ok);
                    if (data.ok) {
                        otpVerified = true;
                        document.getElementById('submit-btn').disabled = false;
                    }
                })
                .catch(err => {
                    console.error(err);
                    setOtpMessage('कुछ गड़बड़ हो गयी, दुबारा try करो', false);
                });
            }

            function checkSubmit(e) {
                if (!otpVerified) {
                    alert('पहले email OTP verify करो फिर submit करो');
                    e.preventDefault();
                    return false;
                }
                return true;
            }
        </script>
    </body>
    </html>
    """


# ====== STUDENT REGISTRATION PAGE ======
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        roll = request.form.get("roll", "").strip()
        name = request.form.get("name", "").strip()
        branch = request.form.get("branch", "").strip().upper()
        year = request.form.get("year", "").strip()
        email = request.form.get("email", "").strip()
        parent_mobile = request.form.get("parent_mobile", "").strip()

        if not (roll and name and branch and year and email):
            return "<h3>सब required fields भरो</h3>"

        if branch != "AIDS":
            return "<h3>ये registration सिर्फ AIDS branch के लिए है</h3>"

        if len(roll) < 10:
            return "<h3>Roll number format गलत है</h3>"

        photo = request.files.get("photo")
        photo_path = ""
        if photo and photo.filename:
            os.makedirs("static/uploads", exist_ok=True)
            ext = os.path.splitext(photo.filename)[1].lower()
            fname = f"{roll}{ext}"
            fpath = os.path.join("static/uploads", fname)
            photo.save(fpath)
            photo_path = fpath

        register_student(roll, name, branch, year, email, parent_mobile, photo_path)

        return "<h3>Student registered हो गया 👍 अब main GatePass page से form भर सकते हो.</h3><p><a href='/'>Back to GatePass</a></p>"

    return """
    <h2>Student Registration</h2>
    <form method="POST" enctype="multipart/form-data">
      Roll: <input name="roll"><br>
      Name: <input name="name"><br>
      Branch: <input name="branch" value="AIDS"><br>
      Year: <input name="year" value="2"><br>
      Email: <input name="email"><br>
      Parent Mobile: <input name="parent_mobile"><br>
      Photo (optional): <input type="file" name="photo"><br><br>
      <button>Register</button>
    </form>
    <p><a href="/">Back</a></p>
    """


# ====== OTP ROUTES ======
@app.route("/send_otp", methods=["POST"])
def send_otp_route():
    email = request.form.get("email", "").strip()
    if not email:
        return jsonify({"ok": False, "message": "Email required"})
    try:
        send_otp_email(email)
        return jsonify({"ok": True, "message": "OTP भेज दिया गया है (10 मिनट तक valid)."})
    except Exception as e:
        print("OTP error:", e)
        return jsonify({"ok": False, "message": "OTP भेजने में दिक्कत, बाद में try करो."})


@app.route("/verify_otp", methods=["POST"])
def verify_otp_route():
    email = request.form.get("email", "").strip()
    code = request.form.get("code", "").strip()
    if not email or not code:
        return jsonify({"ok": False, "message": "Email और OTP दोनों ज़रूरी हैं."})
    ok, msg = verify_otp_code(email, code)
    return jsonify({"ok": ok, "message": msg})


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

    # sirf AIDS branch allowed
    if branch != "AIDS":
        return "<h3>Sirf AIDS branch ke students is form ke liye allowed hain.</h3>", 400

    # OTP verify check
    if not is_email_verified(email):
        return "<h3>Email OTP verify नहीं हुआ. पहले OTP verify करो.</h3>", 400

    req_id = add_request(name, branch, year, roll, email, reason, out_time, date)

    base = get_base_url()
    approve_url = f"{base}{url_for('class_approve', req_id=req_id)}"
    reject_url = f"{base}{url_for('class_reject', req_id=req_id)}"

    # Class Incharge mail (photo agar registered hai to dikhayenge)
    stu = get_student_by_roll(roll)
    photo_html = ""
    if stu and stu[6]:
        photo_html = f"<p><img src='/{stu[6]}' alt='Student Photo' style='max-width:150px;border:1px solid #ccc;'></p>"

    html_class = f"""
    <h3>🪪 New Gate Pass Request</h3>
    {photo_html}
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

    <a href="{approve_url}" style="background:green;color:white;padding:10px;text-decoration:none;">
      ✅ Approve (Add Note)
    </a>
    &nbsp;
    <a href="{reject_url}" style="background:red;color:white;padding:10px;text-decoration:none;">
      ❌ Reject
    </a>
    """

    send_email(CLASS_EMAIL, f"Gate Pass Request from {name}", html_class)

    # Student ko confirmation (QR nahi, sirf submitted)
    send_email(
        email,
        "Gate Pass Submitted",
        "<h3>Your gate pass request is submitted.</h3><p>Status: Pending (Class Incharge)</p>",
    )

    return "<h3>✅ Request submitted successfully! Sent to Class Incharge & Student.</h3>"


# ====== CLASS INCHARGE ======
@app.route("/class_approve/<int:req_id>", methods=["GET", "POST"])
def class_approve(req_id):
    data = get_request(req_id)
    if not data:
        return "<h3>❌ Invalid Request ID</h3>"

    # index:
    # 0:id,1:name,2:branch,3:year,4:roll,5:email,6:reason,7:out_time,8:date
    # 9:class_status,10:hod_status,11:principal_status,12:parent_confirm
    # 13:created_at,14:class_note,15:used_status

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

            <a href="{hod_approve_url}" style="background:green;color:white;padding:10px;text-decoration:none;">
              ✅ Approve
            </a>
            &nbsp;
            <a href="{hod_reject_url}" style="background:red;color:white;padding:10px;text-decoration:none;">
              ❌ Reject
            </a>
            """

            send_email(HOD_EMAIL, "HOD Approval Needed – Gate Pass", html_hod)

            # Student update (QR nahi)
            send_email(
                data[5],
                "Gate Pass Update – Class Incharge Approved",
                "<h3>Your gate pass is APPROVED by Class Incharge.</h3><p>Next: HOD Approval</p>",
            )

            return "<h3>✅ Class Incharge Approved and sent to HOD.</h3>"

        elif action == "reject":
            update_status(req_id, "class_status", "Rejected")
            send_email(
                data[5],
                "Gate Pass Rejected by Class Incharge",
                "<h3>Your gate pass has been REJECTED by Class Incharge.</h3>",
            )
            return "<h3>❌ Class Incharge Rejected the Request.</h3>"

        else:
            return "<h3>❌ Invalid action.</h3>"

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
      <label><b>Note for HOD / Principal / Registrar:</b></label><br>
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
    principal_reject_url = f"{base}{url_for('principal_reject', req_id=req_id)}"
    registrar_approve_url = f"{base}{url_for('registrar_approve', req_id=req_id)}"

    # QR link ab sirf yahan se principal + registrar ko jayega
    qr_url = f"{base}{url_for('qrcode_route', req_id=req_id)}"

    note_html = f"""
    <div style='border:2px solid #0084ff; padding:10px; border-radius:8px; background:#e7f1ff;'>
      <b>📌 Note from Class Incharge:</b><br>{data[14] or 'No note given.'}
    </div><br>
    """

    html_principal_registrar = f"""
    <h3>📩 Gate Pass Request (HOD Approved)</h3>

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
    <b>HOD Status:</b> {data[10]}<br>
    </p>

    <p>🔗 QR (Only for Principal / Registrar): <a href="{qr_url}">View QR</a></p>
    <img src="{qr_url}" alt="GatePass QR"><br><br>

    <a href="{principal_approve_url}" style="background:green;color:white;padding:10px;text-decoration:none;">
      ✅ Principal Approve
    </a>
    &nbsp;
    <a href="{registrar_approve_url}" style="background:orange;color:white;padding:10px;text-decoration:none;">
      ✅ Registrar Approve
    </a>
    &nbsp;
    <a href="{principal_reject_url}" style="background:red;color:white;padding:10px;text-decoration:none;">
      ❌ Reject
    </a>
    """

    send_email(
        PRINCIPAL_EMAIL, "Principal Approval Needed – Gate Pass", html_principal_registrar
    )
    send_email(
        REGISTRAR_EMAIL, "Registrar Approval Needed – Gate Pass", html_principal_registrar
    )

    # Student ko update (abhi bhi QR nahi)
    send_email(
        data[5],
        "Gate Pass Update – HOD Approved",
        "<h3>Your gate pass is APPROVED by HOD.</h3><p>Next: Principal / Registrar Approval</p>",
    )

    return "<h3>✅ HOD Approved and sent to Principal & Registrar.</h3>"


@app.route("/hod_reject/<int:req_id>")
def hod_reject(req_id):
    update_status(req_id, "hod_status", "Rejected")
    data = get_request(req_id)
    if data:
        send_email(
            data[5],
            "Gate Pass Rejected by HOD",
            "<h3>Your gate pass has been REJECTED by HOD.</h3>",
        )
    return "<h3>❌ HOD Rejected the Request.</h3>"


# ====== PRINCIPAL / REGISTRAR ======
@app.route("/principal_approve/<int:req_id>")
def principal_approve(req_id):
    update_status(req_id, "principal_status", "Approved")
    data = get_request(req_id)
    if not data:
        return "<h3>❌ Invalid Request ID</h3>"

    base = get_base_url()
    qr_url = f"{base}{url_for('qrcode_route', req_id=req_id)}"

    html_student = f"""
    <h3>✅ Gate Pass Fully Approved (Principal)</h3>

    <p>
    <b>Name:</b> {data[1]}<br>
    <b>Branch:</b> {data[2]}<br>
    <b>Year:</b> {data[3]}<br>
    <b>Roll:</b> {data[4]}<br>
    <b>Reason:</b> {data[6]}<br>
    <b>Out Time:</b> {data[7]}<br>
    <b>Date:</b> {data[8]}<br>
    <b>Class Incharge Status:</b> {data[9]}<br>
    <b>HOD Status:</b> {data[10]}<br>
    <b>Principal Status:</b> {data[11]}<br>
    </p>

    <p>🔗 Your QR: <a href="{qr_url}">View QR</a></p>
    <img src="{qr_url}" alt="GatePass QR"><br><br>
    """

    send_email(
        data[5],
        "Gate Pass Fully Approved – Principal",
        html_student,
    )

    return "<h3>✅ Principal Approved. QR sent to Student.</h3>"


@app.route("/registrar_approve/<int:req_id>")
def registrar_approve(req_id):
    # Registrar bhi principal_status ko update karega
    update_status(req_id, "principal_status", "Approved (Registrar)")
    data = get_request(req_id)
    if not data:
        return "<h3>❌ Invalid Request ID</h3>"

    base = get_base_url()
    qr_url = f"{base}{url_for('qrcode_route', req_id=req_id)}"

    html_student = f"""
    <h3>✅ Gate Pass Fully Approved (Registrar)</h3>

    <p>
    <b>Name:</b> {data[1]}<br>
    <b>Branch:</b> {data[2]}<br>
    <b>Year:</b> {data[3]}<br>
    <b>Roll:</b> {data[4]}<br>
    <b>Reason:</b> {data[6]}<br>
    <b>Out Time:</b> {data[7]}<br>
    <b>Date:</b> {data[8]}<br>
    <b>Class Incharge Status:</b> {data[9]}<br>
    <b>HOD Status:</b> {data[10]}<br>
    <b>Principal Status:</b> {data[11]}<br>
    </p>

    <p>🔗 Your QR: <a href="{qr_url}">View QR</a></p>
    <img src="{qr_url}" alt="GatePass QR"><br><br>
    """

    send_email(
        data[5],
        "Gate Pass Fully Approved – Registrar",
        html_student,
    )

    return "<h3>✅ Registrar Approved. QR sent to Student.</h3>"


@app.route("/principal_reject/<int:req_id>")
def principal_reject(req_id):
    update_status(req_id, "principal_status", "Rejected")
    data = get_request(req_id)
    if data:
        send_email(
            data[5],
            "Gate Pass Rejected by Principal/Registrar",
            "<h3>Your gate pass has been REJECTED by Principal/Registrar.</h3>",
        )
    return "<h3>❌ Principal/Registrar Rejected the Request.</h3>"


# ====== QR CODE (DYNAMIC) ======
@app.route("/qrcode/<int:req_id>")
def qrcode_route(req_id):
    data = get_request(req_id)
    if not data:
        return "No such record found."

    qr_data = (
        f"GatePass ID:{data[0]} | Name:{data[1]} | Year:{data[3]} | Branch:{data[2]} | "
        f"Roll:{data[4]} | Class:{data[9]} | HOD:{data[10]} | Principal:{data[11]}"
    )

    img = qrcode.make(qr_data)
    buf = io.BytesIO()
    img.save(buf)
    buf.seek(0)

    return send_file(buf, mimetype="image/png")


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


# ====== MAIN ======
if __name__ == "__main__":
    init_db()  # pehli baar run se pehle agar purana gatepass.db ho to delete kar dena
    app.run(host="0.0.0.0", port=5000, debug=True)

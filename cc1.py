from flask import Flask, request, send_file, url_for
import sqlite3, qrcode, io, datetime, smtplib, threading, time, random
from email.message import EmailMessage

app = Flask(__name__)

# ====== CONFIG ======
# NOTE: Inko apne real emails se replace kar lena
# Year-wise Class Incharge
CLASS_INCHARGE_MAP = {
    "1st Year": "rajuji9828087@gmail.com",
    "2nd Year": "rajuji9828087@gmail.com",
    "3rd Year": "rajuji9828087@gmail.com",
    "4th Year": "rajuji9828087@gmail.com",
}

HOD_EMAIL = "rg824797@gmail.com"          # Same HOD for all years
PRINCIPAL_EMAIL = "raj96090@gmail.com"   # Same Principal
REGISTRAR_EMAIL = "bhur4882@gmail.com"   # Same Registrar
SECURITY_EMAIL = "shivrajggct73839@gmail.com"  # From your old code

SENDER_EMAIL = "aids24.shivrajgupta@ggct.co.in"
SENDER_PASS = "buekqnqazapxctme"

DB_NAME = "gatepass.db"

# OTP store (in-memory)
OTP_STORE = {}  # {email: {"otp": "123456", "created_at": datetime, "verified": True/False}}


# ====== DB HELPERS ======
def get_conn():
    return sqlite3.connect(DB_NAME)


def init_db():
    conn = get_conn()
    c = conn.cursor()

    # Purani table hata do (so mismatch na aaye)
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
            parent_confirm TEXT,
            created_at TEXT,
            class_note TEXT,
            used_status TEXT DEFAULT 'No',
            sent_to_hod_at TEXT
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
            "Pending",      # principal_status (final authority)
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


def set_sent_to_hod(req_id):
    conn = get_conn()
    c = conn.cursor()
    c.execute(
        "UPDATE requests SET sent_to_hod_at=? WHERE id=?",
        (datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"), req_id),
    )
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


# ====== HOD TIMEOUT WATCHDOG (10 MIN) ======
def start_hod_timeout_watchdog(req_id, class_email, emergency_url):
    """
    10 minute baad check karega:
    Agar hod_status abhi bhi 'Pending' hai → Class Incharge ko emergency approval link bhej dega.
    """
    def worker():
        # 10 minute wait
        time.sleep(600)
        req = get_request(req_id)
        if not req:
            return

        # 10 = hod_status
        if req[10] == "Pending":
            html = f"""
            <h3>⏰ HOD Approval Delayed (10+ minutes)</h3>
            <p>Request ID: {req[0]}<br>
            Name: {req[1]}<br>
            Year: {req[3]}<br>
            Roll: {req[4]}<br>
            Branch: {req[2]}<br>
            Reason: {req[6]}<br>
            </p>
            <p>HOD ne 10 minute tak approval nahi diya.</p>
            <p>⚠ Emergency: Please approve on behalf of HOD:</p>
            <a href="{emergency_url}" style="background:#ff9800;color:white;padding:10px;text-decoration:none;border-radius:6px;">
              Emergency HOD Approval
            </a>
            """
            if class_email:
                send_email(class_email, "Emergency HOD Approval Needed", html)

    t = threading.Thread(target=worker, daemon=True)
    t.start()


# ====== OTP ROUTES ======
@app.route("/send_otp", methods=["POST"])
def send_otp_route():
    email = request.form.get("email", "").strip()
    if not email:
        return "noemail"

    otp = str(random.randint(100000, 999999))
    OTP_STORE[email] = {
        "otp": otp,
        "created_at": datetime.datetime.now(),
        "verified": False,
    }

    send_email(
        email,
        "Your GatePass OTP",
        f"<h2>Your OTP is: {otp}</h2><p>Valid for 10 minutes.</p>",
    )
    return "sent"


@app.route("/verify_otp", methods=["POST"])
def verify_otp():
    email = request.form.get("email", "").strip()
    user_otp = request.form.get("otp", "").strip()

    rec = OTP_STORE.get(email)
    if not rec:
        return "no_otp"

    if rec["otp"] == user_otp:
        rec["verified"] = True
        return "ok"
    else:
        return "wrong"


# ====== HOME (STUDENT FORM – BLUE UI + GGCT HEADER + OTP + AIDS ONLY) ======
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
            input, select {
                width: 100%;
                padding: 9px 11px;
                border-radius: 10px;
                border: 1px solid #cfd8dc;
                outline: none;
                font-size: 0.9rem;
                margin-bottom: 12px;
                transition: border 0.2s, box-shadow 0.2s;
            }
            input:focus, select:focus {
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
            .btn-primary:hover {
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
            #otp-status {
                margin-top: -8px;
                margin-bottom: 8px;
            }
        </style>
    </head>

    <body>
        <div class="header">
            GYAN GANGA COLLEGE OF TECHNOLOGY
        </div>

        <div class="container">
            <div class="title">🪪 Gate Pass Request</div>
            <div class="subtitle">AIDS branch students only • Email OTP verification required</div>

            <form method="POST" action="/submit">
                <label for="name">Student Name</label>
                <input id="name" name="name" required>

                <div class="row">
                    <div>
                        <label for="branch">Branch</label>
                        <select id="branch" name="branch" required>
                            <option value="">Select Branch</option>
                            <option value="AIDS">AIDS</option>
                        </select>
                    </div>
                    <div>
                        <label for="year">Year</label>
                        <select id="year" name="year" required>
                            <option value="">Select Year</option>
                            <option value="1st Year">1st Year</option>
                            <option value="2nd Year">2nd Year</option>
                            <option value="3rd Year">3rd Year</option>
                            <option value="4th Year">4th Year</option>
                        </select>
                    </div>
                </div>

                <div class="row">
                    <div>
                        <label for="roll">Roll No.</label>
                        <input id="roll" name="roll" required>
                    </div>
                    <div>
                        <label for="email">Email</label>
                        <input id="email" name="email" type="email" required placeholder="student@gmail.com" onblur="sendOTP()">
                    </div>
                </div>

                <div id="otp-box" style="display:none; margin-top:4px;">
                    <label for="otp">Email OTP</label>
                    <input id="otp" name="otp" placeholder="Enter OTP" onblur="verifyOTP()">
                    <p id="otp-status" style="font-size:14px;"></p>
                </div>
                <input type="hidden" id="otp-verified" value="no">

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

                <button class="btn-primary" type="submit">Submit Gate Pass</button>
            </form>

            <div class="links">
                <a href="/scanner">🔍 Security Scanner</a>
                <a href="/admin">📋 Admin Panel</a>
            </div>
        </div>

        <script>
        function sendOTP() {
            let email = document.getElementById("email").value;
            if (!email) return;

            fetch("/send_otp", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: "email=" + encodeURIComponent(email)
            })
            .then(res => res.text())
            .then(data => {
                if (data === "sent") {
                    document.getElementById("otp-box").style.display = "block";
                    document.getElementById("otp-status").innerHTML = "OTP sent to your email ✔";
                    document.getElementById("otp-status").style.color = "green";
                } else {
                    document.getElementById("otp-status").innerHTML = "Failed to send OTP ❌";
                    document.getElementById("otp-status").style.color = "red";
                }
            });
        }

        function verifyOTP() {
            let email = document.getElementById("email").value;
            let otp = document.getElementById("otp").value;

            if (!otp) return;

            fetch("/verify_otp", {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded" },
                body: "email=" + encodeURIComponent(email) + "&otp=" + encodeURIComponent(otp)
            })
            .then(res => res.text())
            .then(data => {
                if (data === "ok") {
                    document.getElementById("otp-status").innerHTML = "OTP Verified ✔";
                    document.getElementById("otp-status").style.color = "green";
                    document.getElementById("otp-verified").value = "yes";
                } else if (data === "wrong") {
                    document.getElementById("otp-status").innerHTML = "Incorrect OTP ❌";
                    document.getElementById("otp-status").style.color = "red";
                    document.getElementById("otp-verified").value = "no";
                } else {
                    document.getElementById("otp-status").innerHTML = "No OTP found for this email ❌";
                    document.getElementById("otp-status").style.color = "red";
                    document.getElementById("otp-verified").value = "no";
                }
            });
        }

        // Prevent form submission if OTP not verified
        document.addEventListener("DOMContentLoaded", function() {
            const form = document.querySelector("form");
            form.addEventListener("submit", function(e) {
                if (document.getElementById("otp-verified").value !== "yes") {
                    e.preventDefault();
                    alert("Please verify OTP sent to your email before submitting!");
                }
            });
        });
        </script>
    </body>
    </html>
    """


# ====== SUBMIT (STUDENT) ======
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

    # Branch restriction: Only AIDS
    if branch.upper() != "AIDS":
        return "<h3>❌ Only AIDS branch students can submit this form.</h3>"

    # Year must be one of the keys in CLASS_INCHARGE_MAP
    if year not in CLASS_INCHARGE_MAP:
        return "<h3>❌ Only 1st, 2nd, 3rd, 4th year AIDS students can submit this form.</h3>"

    # OTP server-side check
    rec = OTP_STORE.get(email)
    if not rec or not rec.get("verified"):
        return "<h3>❌ Please verify OTP sent to your email before submitting the form.</h3>"

    # YEAR wise Class Incharge select
    class_email = CLASS_INCHARGE_MAP.get(year)
    if not class_email:
        return "<h3>❌ No Class Incharge configured for this year.</h3>"

    req_id = add_request(name, branch, year, roll, email, reason, out_time, date)

    base = get_base_url()
    approve_url = f"{base}{url_for('class_approve', req_id=req_id)}"
    reject_url = f"{base}{url_for('class_reject', req_id=req_id)}"
    qr_url = f"{base}{url_for('qrcode_route', req_id=req_id)}"

    html_class = f"""
    <h3>🪪 New Gate Pass Request</h3>
    <p>
    <b>Request ID:</b> {req_id}<br>
    <b>Name:</b> {name}<br>
    <b>Branch:</b> {branch}<br>
    <b>Year:</b> {year}<br>
    <b>Roll:</b> {roll}<br>
    <b>Email:</b> {email}<br>
    <b>Reason:</b> {reason}<br>
    <b>Out Time:</b> {out_time}<br>
    <b>Date:</b> {date}<br>
    </p>

    <p>🔗 Live QR Status (will work after HOD approval): <a href="{qr_url}">View QR</a></p>
    <img src="{qr_url}" alt="GatePass QR"><br><br>

    <a href="{approve_url}" style="background:green;color:white;padding:10px;text-decoration:none;">
      ✅ Approve (Add Note)
    </a>
    &nbsp;
    <a href="{reject_url}" style="background:red;color:white;padding:10px;text-decoration:none;">
      ❌ Reject
    </a>
    """

    # Class Incharge (year-wise) ko mail
    send_email(class_email, f"Gate Pass Request from {name}", html_class)

    # Student ko confirmation
    send_email(
        email,
        "Gate Pass Submitted",
        f"<h3>Your gate pass request is submitted.</h3><p>Status: Pending (Class Incharge)</p><p>QR (will work after HOD approval): <a href='{qr_url}'>View QR</a></p>",
    )

    return "<h3>✅ Request submitted successfully! Sent to Year-wise Class Incharge & Student.</h3>"


# ====== CLASS INCHARGE ======
@app.route("/class_approve/<int:req_id>", methods=["GET", "POST"])
def class_approve(req_id):
    data = get_request(req_id)
    if not data:
        return "<h3>❌ Invalid Request ID</h3>"

    # data index:
    # 0:id 1:name 2:branch 3:year 4:roll 5:email 6:reason 7:out_time 8:date
    # 9:class_status 10:hod_status 11:principal_status
    # 12:parent_confirm 13:created_at 14:class_note 15:used_status 16:sent_to_hod_at

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
            <b>Request ID:</b> {data[0]}<br>
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

            <p>🔗 Live QR Status (will work after HOD approval): <a href="{qr_url}">View QR</a></p>
            <img src="{qr_url}" alt="GatePass QR"><br><br>

            <a href="{hod_approve_url}" style="background:green;color:white;padding:10px;text-decoration:none;">
              ✅ Approve
            </a>
            &nbsp;
            <a href="{hod_reject_url}" style="background:red;color:white;padding:10px;text-decoration:none;">
              ❌ Reject
            </a>
            """

            # HOD ko mail
            send_email(HOD_EMAIL, "HOD Approval Needed – Gate Pass", html_hod)

            # HOD sent time save
            set_sent_to_hod(req_id)

            # Emergency HOD approval link (Class Incharge ke liye)
            year = data[3]
            class_email = CLASS_INCHARGE_MAP.get(year)git status

            emergency_url = f"{base}{url_for('emergency_hod_approve', req_id=req_id)}"
            start_hod_timeout_watchdog(req_id, class_email, emergency_url)

            # Student notification
            send_email(
                data[5],
                "Gate Pass Update – Class Incharge Approved",
                f"<h3>Your gate pass is APPROVED by Class Incharge.</h3><p>Next: HOD Approval</p><p>QR (will work after HOD approval): <a href='{qr_url}'>View QR</a></p>",
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


# ====== EMERGENCY HOD APPROVAL BY CLASS INCHARGE ======
@app.route("/emergency_hod_approve/<int:req_id>")
def emergency_hod_approve(req_id):
    data = get_request(req_id)
    if not data:
        return "<h3>❌ Invalid Request ID</h3>"

    # Agar HOD already approve kar chuka hai
    if data[10] == "Approved":
        return "<h3>✅ Already approved by HOD. Emergency approval not required.</h3>"

    # Emergency HOD approval by Class Incharge
    update_status(req_id, "hod_status", "Approved")

    # Student ko info
    base = get_base_url()
    qr_url = f"{base}{url_for('qrcode_route', req_id=req_id)}"
    send_email(
        data[5],
        "Gate Pass Update – HOD Approved (Emergency by Class Incharge)",
        f"<h3>Your gate pass is APPROVED (Emergency by Class Incharge on behalf of HOD).</h3><p>Next: Final Approval (Principal / Registrar)</p><p>QR: <a href='{qr_url}'>View QR</a></p>",
    )

    # Principal + Registrar ko mail (same as normal HOD approve)
    return hod_approve(req_id)


# ====== HOD ======
@app.route("/hod_approve/<int:req_id>")
def hod_approve(req_id):
    update_status(req_id, "hod_status", "Approved")
    data = get_request(req_id)
    if not data:
        return "<h3>❌ Invalid Request ID</h3>"

    base = get_base_url()
    final_approve_url = f"{base}{url_for('final_approve', req_id=req_id)}"
    final_reject_url = f"{base}{url_for('final_reject', req_id=req_id)}"
    qr_url = f"{base}{url_for('qrcode_route', req_id=req_id)}"

    note_html = f"""
    <div style='border:2px solid #0084ff; padding:10px; border-radius:8px; background:#e7f1ff;'>
      <b>📌 Note from Class Incharge:</b><br>{data[14] or 'No note given.'}
    </div><br>
    """

    html_final = f"""
    <h3>📩 Gate Pass Request (HOD Approved)</h3>

    {note_html}

    <p>
    <b>Request ID:</b> {data[0]}<br>
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

    <p>🔗 Live QR Status (now visible, but not usable until final approval): <a href="{qr_url}">View QR</a></p>
    <img src="{qr_url}" alt="GatePass QR"><br><br>

    <a href="{final_approve_url}" style="background:green;color:white;padding:10px;text-decoration:none;">
      ✅ Final Approve (Principal / Registrar)
    </a>
    &nbsp;
    <a href="{final_reject_url}" style="background:red;color:white;padding:10px;text-decoration:none;">
      ❌ Final Reject
    </a>
    """

    # Principal + Registrar – same mail, same links
    send_email(PRINCIPAL_EMAIL, "Final Approval Needed – Gate Pass", html_final)
    send_email(REGISTRAR_EMAIL, "Final Approval Needed – Gate Pass", html_final)

    # Student notification
    send_email(
        data[5],
        "Gate Pass Update – HOD Approved",
        f"<h3>Your gate pass is APPROVED by HOD.</h3><p>Next: Final Approval (Principal / Registrar)</p><p>QR: <a href='{qr_url}'>View QR</a></p>",
    )

    return "<h3>✅ HOD Approved and sent to Principal & Registrar (parallel).</h3>"


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


# ====== FINAL APPROVAL (PRINCIPAL or REGISTRAR – whoever first) ======
@app.route("/final_approve/<int:req_id>")
def final_approve(req_id):
    data = get_request(req_id)
    if not data:
        return "<h3>❌ Invalid Request ID</h3>"

    # 11 = principal_status (final approval status)
    if data[11] == "Approved":
        return "<h3>✅ Gate Pass already finally approved by another authority.</h3>"

    if data[11] == "Rejected":
        return "<h3>❌ Gate Pass already rejected earlier.</h3>"

    # Mark as fully approved
    update_status(req_id, "principal_status", "Approved")

    base = get_base_url()
    qr_url = f"{base}{url_for('qrcode_route', req_id=req_id)}"

    # Security ko final QR
    html_security = f"""
    <h3>✅ Final Gate Pass Approved</h3>
    <p>
    <b>Request ID:</b> {data[0]}<br>
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
    <b>Final Approval Status:</b> Approved<br>
    </p>

    <p>🔗 Final QR: <a href="{qr_url}">View QR</a></p>
    <img src="{qr_url}" alt="GatePass QR"><br><br>
    """

    send_email(SECURITY_EMAIL, "Final Gate Pass QR – Security Check", html_security)

    # Student notification with final QR
    send_email(
        data[5],
        "Gate Pass Fully Approved",
        f"<h3>Your gate pass is FULLY APPROVED.</h3><p>Show this QR at Security.</p><p>QR: <a href='{qr_url}'>View QR</a></p>",
    )

    return "<h3>✅ Final Approved. QR sent to Student & Security.</h3>"


@app.route("/final_reject/<int:req_id>")
def final_reject(req_id):
    data = get_request(req_id)
    if not data:
        return "<h3>❌ Invalid Request ID</h3>"

    if data[11] == "Approved":
        return "<h3>✅ Already approved earlier. Cannot reject now.</h3>"

    update_status(req_id, "principal_status", "Rejected")

    send_email(
        data[5],
        "Gate Pass Rejected at Final Approval",
        "<h3>Your gate pass has been REJECTED at Final Approval (Principal / Registrar).</h3>",
    )

    return "<h3>❌ Final Authority Rejected the Request.</h3>"


# Backward compatibility: old principal routes → final routes
@app.route("/principal_approve/<int:req_id>")
def principal_approve(req_id):
    return final_approve(req_id)


@app.route("/principal_reject/<int:req_id>")
def principal_reject(req_id):
    return final_reject(req_id)


# ====== QR CODE (DYNAMIC, VISIBLE ONLY AFTER HOD APPROVAL) ======
@app.route("/qrcode/<int:req_id>")
def qrcode_route(req_id):
    data = get_request(req_id)
    if not data:
        return "No such record found."

    # HOD approval required to show QR
    if data[10] != "Approved":  # 10 = hod_status
        return """
        <h3>⛔ QR Not Available Yet</h3>
        <p>HOD approval is required before QR can be viewed.</p>
        """

    qr_data = (
        f"GatePass ID:{data[0]} | Name:{data[1]} | Year:{data[3]} | Branch:{data[2]} | "
        f"Roll:{data[4]} | Class:{data[9]} | HOD:{data[10]} | Final:{data[11]}"
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
            // QR milte hi verify page pe redirect
            window.location.href = '/verify?q=' + encodeURIComponent(decodedText);
        }

        function onScanFailure(error) {
            console.log(error);
        }

        let html5QrcodeScanner = new Html5QrcodeScanner(
            "reader",
            { fps: 10, qrbox: 250 }
        );
        html5QrcodeScanner.render(onScanSuccess, onScanFailure);
    </script>
    """


# ====== VERIFY (ONE-TIME USE) ======
@app.route("/verify")
def verify_qr():
    raw = request.args.get("q", "")

    # 1) QR se GatePass ID nikaalo
    try:
        gp_id_str = raw.split("GatePass ID:")[1].split("|")[0].strip()
        gp_id = int(gp_id_str)
    except Exception:
        return "<h3>❌ Invalid QR Code Format</h3>"

    # 2) DB se record nikaalo
    req = get_request(gp_id)
    if not req:
        return "<h3>❌ No record found for this GatePass ID.</h3>"

    # Index:
    # 0:id, 1:name, 2:branch, 3:year, 4:roll, 5:email, 6:reason,
    # 7:out_time, 8:date, 9:class_status, 10:hod_status,
    # 11:principal_status, 12:parent_confirm, 13:created_at,
    # 14:class_note, 15:used_status, 16:sent_to_hod_at

    # 3) Check: pehle use ho chuka hai kya?
    if req[15] == "Yes":
        return """
        <h2>❌ ALREADY USED</h2>
        <p>This gate pass has already been used at security. Student cannot reuse this QR.</p>
        """

    # 4) Check: sabne approve kiya hai kya? (Class + HOD + Final)
    if (
        req[9] == "Approved" and    # Class Incharge
        req[10] == "Approved" and   # HOD
        req[11] == "Approved"       # Final (Principal or Registrar)
    ):
        # 5) Abhi pehli baar use ho raha hai → mark as used
        mark_used(gp_id)

        return f"""
        <h2>✅ VALID PASS (Now Marked as Used)</h2>
        <p><b>Name:</b> {req[1]}</p>
        <p><b>Year:</b> {req[3]}</p>
        <p><b>Roll:</b> {req[4]}</p>
        <p><b>Branch:</b> {req[2]}</p>
        <p><b>Reason:</b> {req[6]}</p>
        <p><b>Out Time:</b> {req[7]}</p>
        <p><b>Date:</b> {req[8]}</p>
        <p><b>Class Incharge:</b> {req[9]}</p>
        <p><b>HOD:</b> {req[10]}</p>
        <p><b>Final Approval:</b> {req[11]}</p>
        """
    else:
        # Abhi tak full approve nahi hua
        return """
        <h2>❌ NOT FULLY APPROVED</h2>
        <p>All approvals (Class Incharge, HOD, Final Authority) are required
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
    html += "<tr><th>ID</th><th>Name</th><th>Year</th><th>Roll</th><th>Class</th><th>HOD</th><th>Final</th><th>Used?</th></tr>"

    for r in rows:
        html += f"<tr><td>{r[0]}</td><td>{r[1]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{r[9]}</td><td>{r[10]}</td><td>{r[11]}</td><td>{r[15]}</td></tr>"

    html += "</table><br><a href='/'>Back</a>"
    return html


# ====== MAIN ======
if __name__ == "__main__":
    init_db()  # har run pe sahi table banega (ye pura DB reset karega)
    app.run(host="0.0.0.0", port=5000, debug=True)

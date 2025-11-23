from flask import Flask, request, send_file, url_for
import sqlite3, qrcode, io, datetime, smtplib
from email.message import EmailMessage

app = Flask(__name__)

# ====== CONFIG ======
CLASS_EMAIL = "rg824797@gmail.com"
HOD_EMAIL = "rajg96090@gmail.com"
PRINCIPAL_EMAIL = "bhur4882@gmail.com"
SECURITY_EMAIL = "shivrajggct73839@gmail.com"

SENDER_EMAIL = "aids24.shivrajgupta@ggct.co.in"
SENDER_PASS = "buekqnqazapxctme"

DB_NAME = "gatepass.db"


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
            used_status TEXT DEFAULT 'No'
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


# ====== HOME (STUDENT FORM – BLUE UI + GGCT HEADER) ======
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
        </style>
    </head>

    <body>
        <div class="header">
            GYAN GANGA COLLEGE OF TECHNOLOGY
        </div>

        <div class="container">
            <div class="title">🪪 Gate Pass Request</div>
            <div class="subtitle">Fill your details and submit for approval</div>

            <form method="POST" action="/submit">
                <label for="name">Student Name</label>
                <input id="name" name="name" required>

                <div class="row">
                    <div>
                        <label for="branch">Branch</label>
                        <input id="branch" name="branch" required>
                    </div>
                    <div>
                        <label for="year">Year</label>
                        <input id="year" name="year" required placeholder="1st / 2nd / 3rd / 4th">
                    </div>
                </div>

                <div class="row">
                    <div>
                        <label for="roll">Roll No.</label>
                        <input id="roll" name="roll" required>
                    </div>
                    <div>
                        <label for="email">Email</label>
                        <input id="email" name="email" type="email" required placeholder="student@gmail.com">
                    </div>
                </div>

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
    </body>
    </html>
    """


# ====== SUBMIT (STUDENT) ======
@app.route("/submit", methods=["POST"])
def submit():
    name = request.form["name"]
    branch = request.form["branch"]
    year = request.form["year"]
    roll = request.form["roll"]
    email = request.form["email"]
    reason = request.form["reason"]
    out_time = request.form["out_time"]
    date = request.form["date"]

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

    # data index:
    # 0:id 1:name 2:branch 3:year 4:roll 5:email 6:reason 7:out_time 8:date
    # 9:class_status 10:hod_status 11:principal_status
    # 12:parent_confirm 13:created_at 14:class_note 15:used_status

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

    <p>🔗 Live QR Status: <a href="{qr_url}">View QR</a></p>
    <img src="{qr_url}" alt="GatePass QR"><br><br>

    <a href="{principal_approve_url}" style="background:green;color:white;padding:10px;text-decoration:none;">
      ✅ Approve
    </a>
    &nbsp;
    <a href="{principal_reject_url}" style="background:red;color:white;padding:10px;text-decoration:none;">
      ❌ Reject
    </a>
    """

    send_email(PRINCIPAL_EMAIL, "Principal Approval Needed – Gate Pass", html_principal)

    # Student notification
    send_email(
        data[5],
        "Gate Pass Update – HOD Approved",
        f"<h3>Your gate pass is APPROVED by HOD.</h3><p>Next: Principal Approval</p><p>QR: <a href='{qr_url}'>View QR</a></p>",
    )

    return "<h3>✅ HOD Approved and sent to Principal.</h3>"


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


# ====== PRINCIPAL ======
@app.route("/principal_approve/<int:req_id>")
def principal_approve(req_id):
    update_status(req_id, "principal_status", "Approved")
    data = get_request(req_id)
    if not data:
        return "<h3>❌ Invalid Request ID</h3>"

    base = get_base_url()
    qr_url = f"{base}{url_for('qrcode_route', req_id=req_id)}"

    note_html = f"""
    <div style='border:2px solid #0084ff; padding:10px; border-radius:8px; background:#e7f1ff;'>
      <b>📌 Note from Class Incharge:</b><br>{data[14] or 'No note given.'}
    </div><br>
    """

    html_security = f"""
    <h3>✅ Final Gate Pass Approved by Principal</h3>

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
    <b>Principal Status:</b> {data[11]}<br>
    </p>

    <p>🔗 Final QR: <a href="{qr_url}">View QR</a></p>
    <img src="{qr_url}" alt="GatePass QR"><br><br>
    """

    send_email(SECURITY_EMAIL, "Final Gate Pass QR – Security Check", html_security)

    # Student notification
    send_email(
        data[5],
        "Gate Pass Fully Approved – Principal",
        f"<h3>Your gate pass is FULLY APPROVED by Principal.</h3><p>Show this QR at Security.</p><p>QR: <a href='{qr_url}'>View QR</a></p>",
    )

    return "<h3>✅ Principal Approved. Final QR sent to Security & Student.</h3>"


@app.route("/principal_reject/<int:req_id>")
def principal_reject(req_id):
    update_status(req_id, "principal_status", "Rejected")
    data = get_request(req_id)
    if data:
        send_email(
            data[5],
            "Gate Pass Rejected by Principal",
            "<h3>Your gate pass has been REJECTED by Principal.</h3>",
        )
    return "<h3>❌ Principal Rejected the Request.</h3>"


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


# ====== SECURITY SCANNER PAGE ======
@app.route("/scanner")
def scanner():
    return """
    <h2>🔍 Security QR Scanner</h2>
    <video id='preview' width='300'></video>

    <script src='https://cdnjs.cloudflare.com/ajax/libs/instascan/1.0.0/instascan.min.js'></script>
    
    <script>
        let scanner = new Instascan.Scanner({ video: document.getElementById('preview') });

        scanner.addListener('scan', function (content) {
            window.location.href = '/verify?q=' + encodeURIComponent(content);
        });

        Instascan.Camera.getCameras().then(cameras => {
            if(cameras.length > 0) scanner.start(cameras[0]);
            else alert("No Camera Found");
        });
    </script>
    """


# ====== VERIFY (ONE-TIME USE) ======
@app.route("/verify")
def verify_qr():
    data = request.args.get("q", "")

    try:
        gp_id_str = data.split("GatePass ID:")[1].split("|")[0].strip()
        gp_id = int(gp_id_str)
    except Exception:
        return "<h3>❌ Invalid QR Code</h3>"

    req = get_request(gp_id)
    if not req:
        return "<h3>❌ No record found!</h3>"

    # already used?
    if req[15] == "Yes":
        return """
        <h2>❌ ALREADY USED</h2>
        <p>This gate pass has already been used at security.</p>
        """

    # approved?
    if req[9] == "Approved" and req[10] == "Approved" and req[11] == "Approved":
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
        <p><b>Principal:</b> {req[11]}</p>
        """
    else:
        return "<h2>❌ NOT APPROVED</h2><p>Student cannot leave the campus.</p>"


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
    init_db()  # har run pe sahi table banega
    app.run(host="0.0.0.0", port=5000, debug=True)

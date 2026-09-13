
from datetime import datetime
import os, secrets, io, csv, shutil, uuid, urllib.request, json
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, abort, send_file
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

BASE=os.path.dirname(os.path.abspath(__file__))
UPLOAD=os.path.join(BASE,"static","uploads"); os.makedirs(UPLOAD,exist_ok=True)
app=Flask(__name__)
app.secret_key=os.environ.get("SECRET_KEY","CHANGE_THIS_SECRET_KEY")
app.config.update(MAX_CONTENT_LENGTH=8*1024*1024,SESSION_COOKIE_HTTPONLY=True,SESSION_COOKIE_SAMESITE="Lax",SESSION_COOKIE_SECURE=os.environ.get("COOKIE_SECURE","true").lower()=="true")
ALLOWED={"jpg","jpeg","png","webp","gif"}
GAMES=["Athletics","Football","Cricket","Basketball","Volleyball","Badminton","Table Tennis","Tennis","Kho-Kho","Kabaddi","Chess","Carrom","Handball","Hockey","Throwball","Long Jump","High Jump","Shot Put","Discus Throw","Javelin Throw","100m","200m","400m","800m","1500m","Relay","Yoga","Skipping"]
DEFAULT_HOUSES=["Aryabhatta House","Ashoka House","Gautam House","Chanakya House"]; CATS=["Group A","Group B","Group C","Group D"]
class Row(dict):
    def __getitem__(self,k): return list(self.values())[k] if isinstance(k,int) else super().__getitem__(k)
class CursorWrap:
    def __init__(self,cur): self.cur=cur
    def execute(self,sql,args=None): self.cur.execute(sql.replace('?', '%s'),args or ()); return self
    def fetchone(self):
        r=self.cur.fetchone(); return Row(r) if r is not None else None
    def fetchall(self): return [Row(r) for r in self.cur.fetchall()]
class PGConn:
    def __init__(self):
        import psycopg
        from psycopg.rows import dict_row
        url=os.environ.get('DATABASE_URL') or os.environ.get('SUPABASE_DB_URL')
        if not url: raise RuntimeError('DATABASE_URL/SUPABASE_DB_URL is required')
        self.c=psycopg.connect(url,row_factory=dict_row)
    def execute(self,sql,args=None): return CursorWrap(self.c.cursor()).execute(sql,args)
    def commit(self): self.c.commit()
    def rollback(self): self.c.rollback()
    def close(self): self.c.close()
def db(): return PGConn()
def init_db():
    c=db()
    for q in [
    "CREATE TABLE IF NOT EXISTS users(id BIGSERIAL PRIMARY KEY,user_id TEXT UNIQUE NOT NULL,password_hash TEXT NOT NULL,role TEXT NOT NULL,active INTEGER DEFAULT 1,created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS teachers(id BIGSERIAL PRIMARY KEY,user_id BIGINT UNIQUE REFERENCES users(id) ON DELETE CASCADE,name TEXT,designation TEXT,house TEXT,photo TEXT)",
    "CREATE TABLE IF NOT EXISTS students(id BIGSERIAL PRIMARY KEY,user_id BIGINT UNIQUE REFERENCES users(id) ON DELETE SET NULL,admission_no TEXT UNIQUE,name TEXT,class_name TEXT,section TEXT,roll_no TEXT,house TEXT,blood_group TEXT,dob TEXT,photo TEXT,height DOUBLE PRECISION,weight DOUBLE PRECISION,bmi DOUBLE PRECISION,body_age TEXT,guardian TEXT,phone TEXT,address TEXT,remarks TEXT,active INTEGER DEFAULT 1)",
    "CREATE TABLE IF NOT EXISTS events(id BIGSERIAL PRIMARY KEY,name TEXT,category TEXT,game TEXT,event_date TEXT,house1 TEXT,house2 TEXT,venue TEXT,description TEXT)",
    "CREATE TABLE IF NOT EXISTS results(id BIGSERIAL PRIMARY KEY,event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,house TEXT,position TEXT,points DOUBLE PRECISION,remarks TEXT)",
    "CREATE TABLE IF NOT EXISTS participation(id BIGSERIAL PRIMARY KEY,event_id BIGINT REFERENCES events(id) ON DELETE CASCADE,student_id BIGINT REFERENCES students(id) ON DELETE CASCADE,performance TEXT,position TEXT,remarks TEXT)",
    "CREATE TABLE IF NOT EXISTS assessments(id BIGSERIAL PRIMARY KEY,student_id BIGINT REFERENCES students(id) ON DELETE CASCADE,assess_date TEXT,fitness TEXT,running TEXT,strength TEXT,flexibility TEXT,endurance TEXT,discipline TEXT,participation TEXT,remarks TEXT)",
    "CREATE TABLE IF NOT EXISTS annual(id BIGSERIAL PRIMARY KEY,name TEXT,category TEXT,event_date TEXT,house TEXT,position TEXT,points DOUBLE PRECISION,remarks TEXT)",
    "CREATE TABLE IF NOT EXISTS certificates(id BIGSERIAL PRIMARY KEY,student_id BIGINT REFERENCES students(id) ON DELETE CASCADE,event_name TEXT,game TEXT,position TEXT,certificate_date TEXT,remarks TEXT)",
    "CREATE TABLE IF NOT EXISTS gallery(id BIGSERIAL PRIMARY KEY,filename TEXT,caption TEXT,house TEXT,event_name TEXT,uploaded_by TEXT,created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS reset_requests(id BIGSERIAL PRIMARY KEY,user_id TEXT,requested_at TEXT,status TEXT DEFAULT 'pending')",
    "CREATE TABLE IF NOT EXISTS audit(id BIGSERIAL PRIMARY KEY,user_id TEXT,action TEXT,created_at TEXT)",
    "CREATE TABLE IF NOT EXISTS settings(k TEXT PRIMARY KEY,v TEXT)"] : c.execute(q)
    d={"school_name":"S.D. Public School","school_address":"Kumhrar, Patna-07","department":"SPORTS DEPARTMENT","principal_name":"","sports_teacher_name":"","school_logo":""}
    for i,h in enumerate(DEFAULT_HOUSES,1): d[f"house_{i}"]=h; d[f"house_logo_{i}"]=""
    for k,v in d.items(): c.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO NOTHING",(k,v))
    if not c.execute("SELECT 1 FROM users WHERE user_id='owner'").fetchone(): c.execute("INSERT INTO users(user_id,password_hash,role,created_at) VALUES(?,?,?,?)",("owner",generate_password_hash("ChangeMe123!"),"owner",datetime.now().isoformat()))
    c.commit(); c.close()
init_db()

# Fixed Sports Teacher / Co-Owner login requested by school.
# User ID: SDPSEPT | Password: sdpsept
def ensure_sports_teacher_account():
    c=db()
    if not c.execute("SELECT 1 FROM users WHERE user_id=?",("SDPSEPT",)).fetchone():
        c.execute("INSERT INTO users(user_id,password_hash,role,created_at) VALUES(?,?,?,?)",
                  ("SDPSEPT",generate_password_hash("sdpsept"),"sports_teacher",datetime.now().isoformat()))
        c.commit()
    c.close()
ensure_sports_teacher_account()

def settings():
    c=db(); d={r["k"]:r["v"] for r in c.execute("SELECT k,v FROM settings")}; c.close(); return d
def houses():
    s=settings(); return [s.get("house_"+str(i),DEFAULT_HOUSES[i-1]) for i in range(1,5)]
def log(a):
    c=db(); c.execute("INSERT INTO audit(user_id,action,created_at) VALUES(?,?,?)",(session.get("user_id","system"),a,datetime.now().isoformat())); c.commit(); c.close()
def role_required(*roles):
    def dec(f):
        @wraps(f)
        def w(*a,**kw):
            if "uid" not in session: return redirect(url_for("login"))
            if roles and session.get("role") not in roles: abort(403)
            return f(*a,**kw)
        return w
    return dec
def csrf_ok():
    return request.form.get("_csrf")==session.get("_csrf")
def asset_url(name):
    if not name: return ""
    name=str(name)
    if name.startswith(('http://','https://')): return name
    if '/' in name and name.split('/',1)[0] in ('student-photos','school-assets','gallery'):
        bucket,obj=name.split('/',1)
        return url_for('media',bucket=bucket,object_path=obj)
    return url_for('static',filename='uploads/'+name)

def upload(field):
    f=request.files.get(field)
    if not f or not f.filename: return ""
    ext=f.filename.rsplit('.',1)[-1].lower() if '.' in f.filename else ''
    if ext not in ALLOWED: raise ValueError("केवल JPG/PNG/WEBP/GIF image allowed है")
    data=f.read()
    if len(data) > 8*1024*1024: raise ValueError("Image 8 MB से छोटी होनी चाहिए")
    fn=secrets.token_hex(16)+'.'+ext
    if field == 'school_logo' or field.startswith('house_logo_'):
        bucket='school-assets'
    elif field == 'gallery_photo':
        bucket='gallery'
    else:
        bucket='student-photos'
    url=os.environ.get('SUPABASE_URL'); key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SECRET_KEY')
    if not url or not key: raise RuntimeError('SUPABASE_URL और SUPABASE_SERVICE_ROLE_KEY आवश्यक हैं')
    endpoint=f"{url.rstrip('/')}/storage/v1/object/{bucket}/{fn}"
    req=urllib.request.Request(endpoint,data=data,method='POST',headers={'Authorization':f'Bearer {key}','apikey':key,'Content-Type':f.mimetype or 'application/octet-stream','x-upsert':'true'})
    urllib.request.urlopen(req,timeout=30).read()
    return f"{bucket}/{fn}"

@app.route('/media/<bucket>/<path:object_path>')
@role_required('owner','sports_teacher','house_teacher','prefect','student')
def media(bucket, object_path):
    if bucket not in ('student-photos','school-assets','gallery'): abort(404)
    url=os.environ.get('SUPABASE_URL'); key=os.environ.get('SUPABASE_SERVICE_ROLE_KEY') or os.environ.get('SUPABASE_SECRET_KEY')
    if not url or not key: abort(503)
    endpoint=f"{url.rstrip('/')}/storage/v1/object/{bucket}/{object_path}"
    req=urllib.request.Request(endpoint,headers={'Authorization':f'Bearer {key}','apikey':key})
    try:
        resp=urllib.request.urlopen(req,timeout=30)
        data=resp.read(); ctype=resp.headers.get_content_type() or 'application/octet-stream'
        return send_file(io.BytesIO(data),mimetype=ctype,download_name=os.path.basename(object_path))
    except Exception:
        abort(404)

def calc_bmi(h,w):
    try:
        h=float(h)/100; w=float(w)
        return round(w/(h*h),2) if h>0 and w>0 else None
    except: return None

@app.context_processor
def common():
    if "_csrf" not in session: session["_csrf"]=secrets.token_hex(24)
    return {"S":settings(),"HOUSES":houses(),"GAMES":GAMES,"CATS":CATS,"MY_HOUSE":teacher_house() if session.get("role") in ("sports_teacher","house_teacher","prefect") else "","asset_url":asset_url}


@app.route('/students/<int:sid>/photo', methods=['POST'])
@role_required('owner','sports_teacher','house_teacher','prefect')
def student_photo(sid):
    c = db(); st = c.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
    if not st: c.close(); abort(404)
    if session.get('role') == 'house_teacher' and not house_allowed(c, st['house']): c.close(); abort(403)
    try:
        ph=upload('photo')
        if not ph: raise ValueError('Photo select करें')
        c.execute("UPDATE students SET photo=? WHERE id=?", (ph, sid)); c.commit(); c.close()
        log(f'Updated profile photo for student {sid}'); flash('Student profile photo updated.','ok')
    except Exception as e:
        c.rollback(); c.close(); flash('Photo upload failed: '+str(e),'error')
    return redirect(request.referrer or url_for('students'))

@app.route("/")
def home(): return render_template("home.html")

@app.route("/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        c=db(); u=c.execute("SELECT * FROM users WHERE user_id=? AND active=1",(request.form["user_id"].strip(),)).fetchone(); c.close()
        if u and check_password_hash(u["password_hash"],request.form["password"]):
            session.clear(); session["uid"]=u["id"]; session["user_id"]=u["user_id"]; session["role"]=u["role"]; session["_csrf"]=secrets.token_hex(24); log("Login"); return redirect(url_for("dashboard"))
        flash("User ID या password गलत है","error")
    return render_template("login.html")
@app.route("/logout")
def logout(): session.clear(); return redirect(url_for("login"))

def teacher_house():
    c=db(); t=c.execute("SELECT house FROM teachers WHERE user_id=?",(session.get("uid"),)).fetchone(); c.close(); return t["house"] if t else ""

@app.route("/house/<path:house>")
@role_required("owner","sports_teacher","house_teacher","prefect")
def house_section(house):
    if house not in houses(): abort(404)
    if session["role"] == "house_teacher" and teacher_house()!=house: abort(403)
    c=db(); rows=c.execute("SELECT * FROM students WHERE active=1 AND house=? ORDER BY name",(house,)).fetchall(); c.close()
    return render_template("house_section.html",house=house,rows=rows)

@app.route("/dashboard")
@role_required()
def dashboard():
    if session["role"]=="student": return redirect(url_for("my_report"))
    if session["role"] == "house_teacher": return redirect(url_for("house_section",house=teacher_house()))
    c=db(); counts=[("Students",c.execute("SELECT count(*) FROM students WHERE active=1").fetchone()[0]),("Teachers",c.execute("SELECT count(*) FROM teachers").fetchone()[0]),("Events",c.execute("SELECT count(*) FROM events").fetchone()[0]),("Results",c.execute("SELECT count(*) FROM results").fetchone()[0])]; c.close()
    return render_template("dashboard.html",counts=counts)

@app.route("/students")
@role_required("owner","sports_teacher","house_teacher","prefect")
def students():
    c=db(); q="SELECT * FROM students WHERE active=1"; args=[]
    if session["role"] == "house_teacher":
        t=c.execute("SELECT house FROM teachers WHERE user_id=?",(session["uid"],)).fetchone(); q+=" AND house=?"; args.append(t["house"] if t else "")
    search=request.args.get("q","").strip()
    if search: q+=" AND (name LIKE ? OR admission_no LIKE ? OR class_name LIKE ?)"; args += ["%"+search+"%"]*3
    rows=c.execute(q+" ORDER BY house,name",args).fetchall(); c.close(); return render_template("students.html",rows=rows,search=search)

def house_allowed(c,house):
    if session.get("role") != "house_teacher": return True
    t=c.execute("SELECT house FROM teachers WHERE user_id=?",(session["uid"],)).fetchone()
    return bool(t and t["house"]==house)

@app.route("/students/add",methods=["GET","POST"])
@role_required("owner","sports_teacher","house_teacher","prefect")
def student_add():
    if request.method=="POST":
        if not csrf_ok(): abort(400)
        c=db(); h=request.form["house"]
        if not house_allowed(c,h): abort(403)
        try:
            ph=upload("photo")
            c.execute("""INSERT INTO students(admission_no,name,class_name,section,roll_no,house,house_position,blood_group,dob,photo,height,weight,bmi,body_age,guardian,phone,address,remarks)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",(request.form["admission_no"],request.form["name"],request.form["class_name"],request.form["section"],request.form["roll_no"],h,request.form.get("house_position",""),request.form["blood_group"],request.form["dob"],ph,float(request.form.get("height") or 0),float(request.form.get("weight") or 0),calc_bmi(request.form.get("height"),request.form.get("weight")),request.form["body_age"],request.form["guardian"],request.form["phone"],request.form["address"],request.form["remarks"]))
            c.commit(); log("Added student"); flash("Student added","ok"); return redirect(url_for("students"))
        except Exception as e: c.rollback(); flash("Save failed: "+str(e),"error")
        finally: c.close()
    return render_template("student_form.html",row=None)

@app.route("/students/<int:sid>/edit",methods=["GET","POST"])
@role_required("owner","sports_teacher")
def student_edit(sid):
    c=db(); s=c.execute("SELECT * FROM students WHERE id=?",(sid,)).fetchone()
    if not s: abort(404)
    if not house_allowed(c,s["house"]): abort(403)
    if request.method=="POST":
        if not csrf_ok(): abort(400)
        if not house_allowed(c,request.form["house"]): abort(403)
        ph=s["photo"] or ""
        try: ph=upload("photo") or ph
        except Exception as e: flash(str(e),"error"); c.close(); return render_template("student_form.html",row=s)
        c.execute("""UPDATE students SET admission_no=?,name=?,class_name=?,section=?,roll_no=?,house=?,house_position=?,blood_group=?,dob=?,photo=?,height=?,weight=?,bmi=?,body_age=?,guardian=?,phone=?,address=?,remarks=? WHERE id=?""",
        (request.form["admission_no"],request.form["name"],request.form["class_name"],request.form["section"],request.form["roll_no"],request.form["house"],request.form.get("house_position",""),request.form["blood_group"],request.form["dob"],ph,float(request.form.get("height") or 0),float(request.form.get("weight") or 0),calc_bmi(request.form.get("height"),request.form.get("weight")),request.form["body_age"],request.form["guardian"],request.form["phone"],request.form["address"],request.form["remarks"],sid))
        c.commit(); c.close(); log("Edited student"); flash("Student updated","ok"); return redirect(url_for("students"))
    c.close(); return render_template("student_form.html",row=s)

@app.route("/students/<int:sid>/delete",methods=["POST"])
@role_required("owner","sports_teacher","house_teacher","prefect")
def student_delete(sid):
    if not csrf_ok(): abort(400)
    c=db(); s=c.execute("SELECT * FROM students WHERE id=?",(sid,)).fetchone()
    if not s or not house_allowed(c,s["house"]): abort(403)
    c.execute("UPDATE students SET active=0 WHERE id=?",(sid,)); c.commit(); c.close(); log("Removed student"); flash("Student removed","ok"); return redirect(url_for("students"))

@app.route("/teachers",methods=["GET","POST"])
@role_required("owner","sports_teacher")
def teachers():
    c=db()
    if request.method=="POST":
        if not csrf_ok(): abort(400)
        try:
            uid=request.form["user_id"].strip()
            c.execute("INSERT INTO users(user_id,password_hash,role,created_at) VALUES(?,?,?,?)",(uid,generate_password_hash(request.form["password"]),request.form["role"],datetime.now().isoformat()))
            u=c.execute("SELECT id FROM users WHERE user_id=?",(uid,)).fetchone()
            c.execute("INSERT INTO teachers(user_id,name,designation,house,photo) VALUES(?,?,?,?,?)",(u["id"],request.form["name"],request.form["designation"],request.form["house"],upload("photo")))
            c.commit(); log("Created teacher"); flash("Teacher created","ok")
        except Exception as e: c.rollback(); flash("Create failed: "+str(e),"error")
    rows=c.execute("SELECT t.*,u.user_id,u.role,u.active FROM teachers t JOIN users u ON u.id=t.user_id ORDER BY t.name").fetchall(); c.close(); return render_template("teachers.html",rows=rows)

@app.route("/teachers/<int:tid>/disable",methods=["POST"])
@role_required("owner","sports_teacher")
def teacher_disable(tid):
    if not csrf_ok(): abort(400)
    c=db(); t=c.execute("SELECT user_id FROM teachers WHERE id=?",(tid,)).fetchone()
    if t: c.execute("UPDATE users SET active=0 WHERE id=?",(t["user_id"],)); c.commit()
    c.close(); log("Disabled teacher"); return redirect(url_for("teachers"))

@app.route("/owner-reset",methods=["GET","POST"])
@role_required("owner","sports_teacher")
def owner_reset():
    c=db()
    if request.method=="POST":
        if not csrf_ok(): abort(400)
        c.execute("UPDATE users SET password_hash=? WHERE user_id=?",(generate_password_hash(request.form["password"]),request.form["user_id"])); c.commit(); log("Owner reset password"); flash("Password reset किया गया","ok")
    users=c.execute("SELECT user_id,role,active FROM users ORDER BY user_id").fetchall(); req=c.execute("SELECT * FROM reset_requests ORDER BY id DESC LIMIT 50").fetchall(); c.close()
    return render_template("owner_reset.html",users=users,requests=req)

@app.route("/change-password",methods=["GET","POST"])
@role_required()
def change_password():
    if request.method=="POST":
        if not csrf_ok(): abort(400)
        c=db(); u=c.execute("SELECT password_hash FROM users WHERE id=?",(session["uid"],)).fetchone()
        if not check_password_hash(u["password_hash"],request.form["old"]): flash("Old password गलत है","error")
        elif request.form["new"]!=request.form["confirm"]: flash("Passwords match नहीं","error")
        elif len(request.form["new"])<8: flash("कम से कम 8 characters","error")
        else: c.execute("UPDATE users SET password_hash=? WHERE id=?",(generate_password_hash(request.form["new"]),session["uid"])); c.commit(); c.close(); log("Changed password"); flash("Password changed","ok"); return redirect(url_for("dashboard"))
        c.close()
    return render_template("form.html",title="Change Password",fields=[("old","Old Password","password"),("new","New Password","password"),("confirm","Confirm Password","password")])

@app.route("/forgot",methods=["GET","POST"])
def forgot():
    if request.method=="POST":
        c=db(); c.execute("INSERT INTO reset_requests(user_id,requested_at) VALUES(?,?)",(request.form["user_id"].strip(),datetime.now().isoformat())); c.commit(); c.close()
        flash("Request Owner को भेज दी गई. SMS/OTP नहीं है; Owner नया password सेट कर सकता है.","ok"); return redirect(url_for("login"))
    return render_template("form.html",title="Forgot Password",fields=[("user_id","User ID","text")])

@app.route("/events",methods=["GET","POST"])
@role_required("owner","sports_teacher")
def events():
    c=db()
    if request.method=="POST":
        if not csrf_ok(): abort(400)
        c.execute("INSERT INTO events(name,category,game,event_date,house1,house2,venue,description) VALUES(?,?,?,?,?,?,?,?)",(request.form["name"],request.form["category"],request.form["game"],request.form["event_date"],request.form["house1"],request.form["house2"],request.form["venue"],request.form["description"])); c.commit(); log("Created event"); flash("Event created","ok")
    rows=c.execute("SELECT * FROM events ORDER BY event_date DESC,id DESC").fetchall(); c.close(); return render_template("events.html",rows=rows)

@app.route("/events/<int:eid>/delete",methods=["POST"])
@role_required("owner","sports_teacher")
def event_delete(eid):
    if not csrf_ok(): abort(400)
    c=db()
    for t in ["results","participation"]: c.execute(f"DELETE FROM {t} WHERE event_id=?",(eid,))
    c.execute("DELETE FROM events WHERE id=?",(eid,)); c.commit(); c.close(); log("Deleted event"); return redirect(url_for("events"))

@app.route("/results",methods=["GET","POST"])
@role_required("owner","sports_teacher")
def results():
    c=db()
    if request.method=="POST":
        if not csrf_ok(): abort(400)
        c.execute("INSERT INTO results(event_id,house,position,points,remarks) VALUES(?,?,?,?,?)",(request.form["event_id"],request.form["house"],request.form["position"],float(request.form["points"]),request.form["remarks"])); c.commit(); log("Added house result"); flash("House result saved","ok")
    ev=c.execute("SELECT * FROM events ORDER BY event_date DESC").fetchall(); rows=c.execute("SELECT r.*,e.name,e.game,e.event_date FROM results r JOIN events e ON e.id=r.event_id ORDER BY e.event_date DESC").fetchall(); c.close(); return render_template("results.html",events=ev,rows=rows)

@app.route("/participation",methods=["GET","POST"])
@role_required("owner","sports_teacher")
def participation():
    c=db()
    if request.method=="POST":
        if not csrf_ok(): abort(400)
        s=c.execute("SELECT house FROM students WHERE id=?",(request.form["student_id"],)).fetchone()
        if not s or not house_allowed(c,s["house"]): abort(403)
        c.execute("INSERT INTO participation(event_id,student_id,performance,position,remarks) VALUES(?,?,?,?,?)",(request.form["event_id"],request.form["student_id"],request.form["performance"],request.form["position"],request.form["remarks"])); c.commit(); log("Added participation"); flash("Participation saved","ok")
    ev=c.execute("SELECT * FROM events ORDER BY event_date DESC").fetchall()
    if session["role"]=="house_teacher":
        t=c.execute("SELECT house FROM teachers WHERE user_id=?",(session["uid"],)).fetchone(); st=c.execute("SELECT * FROM students WHERE active=1 AND house=? ORDER BY name",(t["house"],)).fetchall()
    else: st=c.execute("SELECT * FROM students WHERE active=1 ORDER BY name").fetchall()
    rows=c.execute("SELECT p.*,e.name,e.game,e.event_date,s.name student_name FROM participation p JOIN events e ON e.id=p.event_id JOIN students s ON s.id=p.student_id ORDER BY e.event_date DESC").fetchall(); c.close()
    return render_template("participation.html",events=ev,students=st,rows=rows)

@app.route("/assessments",methods=["GET","POST"])
@role_required("owner","sports_teacher")
def assessments():
    c=db()
    if request.method=="POST":
        if not csrf_ok(): abort(400)
        s=c.execute("SELECT house FROM students WHERE id=?",(request.form["student_id"],)).fetchone()
        if not s or not house_allowed(c,s["house"]): abort(403)
        keys=["assess_date","fitness","running","strength","flexibility","endurance","discipline","participation","remarks"]
        vals=[request.form.get(k,"") for k in keys]
        c.execute("INSERT INTO assessments(student_id,assess_date,fitness,running,strength,flexibility,endurance,discipline,participation,remarks) VALUES(?,?,?,?,?,?,?,?,?,?)",(request.form["student_id"],*vals)); c.commit(); log("Added assessment"); flash("Assessment saved","ok")
    if session["role"]=="house_teacher":
        t=c.execute("SELECT house FROM teachers WHERE user_id=?",(session["uid"],)).fetchone(); st=c.execute("SELECT * FROM students WHERE active=1 AND house=? ORDER BY name",(t["house"],)).fetchall()
    else: st=c.execute("SELECT * FROM students WHERE active=1 ORDER BY name").fetchall()
    rows=c.execute("SELECT a.*,s.name student_name FROM assessments a JOIN students s ON s.id=a.student_id ORDER BY a.assess_date DESC").fetchall(); c.close(); return render_template("assessments.html",students=st,rows=rows)

@app.route("/annual",methods=["GET","POST"])
@role_required("owner","sports_teacher")
def annual():
    c=db()
    if request.method=="POST":
        if not csrf_ok(): abort(400)
        c.execute("INSERT INTO annual(name,category,event_date,house,position,points,remarks) VALUES(?,?,?,?,?,?,?)",(request.form["name"],request.form["category"],request.form["event_date"],request.form["house"],request.form["position"],float(request.form["points"]),request.form["remarks"])); c.commit(); log("Added annual record"); flash("Annual record saved","ok")
    rows=c.execute("SELECT * FROM annual ORDER BY event_date DESC").fetchall(); c.close(); return render_template("annual.html",rows=rows)

@app.route("/scoreboard")
@role_required()
def scoreboard():
    c=db(); rows=[]
    for h in houses():
        a=c.execute("SELECT COALESCE(SUM(points),0) FROM results WHERE house=?",(h,)).fetchone()[0]
        b=c.execute("SELECT COALESCE(SUM(points),0) FROM annual WHERE house=?",(h,)).fetchone()[0]
        rows.append((h,float(a+b)))
    rows.sort(key=lambda x:x[1],reverse=True); c.close(); return render_template("scoreboard.html",rows=rows)

def report_for(sid):
    c=db(); s=c.execute("SELECT * FROM students WHERE id=?",(sid,)).fetchone()
    if not s: abort(404)
    if session["role"]=="house_teacher" and not house_allowed(c,s["house"]): abort(403)
    a=c.execute("SELECT * FROM assessments WHERE student_id=? ORDER BY assess_date DESC LIMIT 1",(sid,)).fetchone()
    p=c.execute("SELECT p.*,e.name,e.game,e.event_date FROM participation p JOIN events e ON e.id=p.event_id WHERE p.student_id=? ORDER BY e.event_date DESC",(sid,)).fetchall()
    cert=c.execute("SELECT * FROM certificates WHERE student_id=? ORDER BY certificate_date DESC",(sid,)).fetchall()
    c.close(); return render_template("report.html",student=s,assessment=a,participation=p,certificates=cert)

@app.route("/my-report")
@role_required("student")
def my_report():
    c=db(); s=c.execute("SELECT id FROM students WHERE user_id=?",(session["uid"],)).fetchone(); c.close()
    if not s: abort(404)
    return report_for(s["id"])

@app.route("/student-report/<int:sid>")
@role_required("owner","sports_teacher")
def student_report(sid): return report_for(sid)

@app.route("/certificates",methods=["GET","POST"])
@role_required("owner","sports_teacher")
def certificates():
    c=db()
    if request.method=="POST":
        if not csrf_ok(): abort(400)
        c.execute("INSERT INTO certificates(student_id,event_name,game,position,certificate_date,remarks) VALUES(?,?,?,?,?,?)",(request.form["student_id"],request.form["event_name"],request.form["game"],request.form["position"],request.form["certificate_date"],request.form["remarks"])); c.commit(); log("Created certificate record"); flash("Certificate record saved","ok")
    st=c.execute("SELECT * FROM students WHERE active=1 ORDER BY name").fetchall(); rows=c.execute("SELECT x.*,s.name student_name FROM certificates x JOIN students s ON s.id=x.student_id ORDER BY x.certificate_date DESC").fetchall(); c.close(); return render_template("certificates.html",students=st,rows=rows)

@app.route("/certificate/<int:cid>")
@role_required("owner","sports_teacher","house_teacher","student")
def certificate(cid):
    c=db(); x=c.execute("SELECT x.*,s.name, s.class_name,s.section,s.house FROM certificates x JOIN students s ON s.id=x.student_id WHERE x.id=?",(cid,)).fetchone(); c.close()
    if not x: abort(404)
    if session["role"]=="student":
        c=db(); ok=c.execute("SELECT 1 FROM students WHERE id=? AND user_id=?",(x["student_id"],session["uid"])).fetchone(); c.close()
        if not ok: abort(403)
    return render_template("certificate.html",x=x)

@app.route("/settings",methods=["GET","POST"])
@role_required("owner","sports_teacher")
def app_settings():
    c=db()
    if request.method=="POST":
        if not csrf_ok(): abort(400)
        for k in ["school_name","school_address","principal_name","sports_teacher_name","house_1","house_2","house_3","house_4"]:
            c.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=EXCLUDED.v",(k,request.form.get(k,"")))
        try: logo=upload("school_logo")
        except: logo=""
        if logo: c.execute("INSERT INTO settings(k,v) VALUES('school_logo',?) ON CONFLICT(k) DO UPDATE SET v=EXCLUDED.v",(logo,))
        for i in range(1,5):
            try: fn=upload(f"house_logo_{i}")
            except: fn=""
            if fn: c.execute("INSERT INTO settings(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=EXCLUDED.v",(f"house_logo_{i}",fn))
        c.commit(); c.close(); log("Updated settings"); flash("Settings saved","ok"); return redirect(url_for("app_settings"))
    s={r["k"]:r["v"] for r in c.execute("SELECT k,v FROM settings")}; c.close(); return render_template("settings.html",s=s)

@app.route("/audit")
@role_required("owner","sports_teacher")
def audit():
    c=db(); rows=c.execute("SELECT * FROM audit ORDER BY id DESC LIMIT 500").fetchall(); c.close(); return render_template("audit.html",rows=rows)

@app.route("/export/students.csv")
@role_required("owner","sports_teacher")
def export_students():
    c=db(); rows=c.execute("SELECT admission_no,name,class_name,section,roll_no,house,blood_group,height,weight,bmi,body_age,guardian,phone,address FROM students WHERE active=1 ORDER BY house,name").fetchall(); c.close()
    out=io.StringIO(); w=csv.writer(out); w.writerow(rows[0].keys() if rows else ["admission_no","name"]); [w.writerow(tuple(r)) for r in rows]
    return send_file(io.BytesIO(out.getvalue().encode("utf-8-sig")),as_attachment=True,download_name="students.csv",mimetype="text/csv")


@app.route("/gallery",methods=["GET","POST"])
@role_required("owner","sports_teacher","house_teacher","prefect")
def gallery():
    c=db()
    if request.method=="POST":
        if not csrf_ok(): abort(400)
        house=request.form["house"]
        if session["role"] == "house_teacher" and not house_allowed(c,house): abort(403)
        try:
            fn=upload("gallery_photo")
            if not fn: raise ValueError("Photo select करें")
            c.execute("INSERT INTO gallery(filename,caption,house,event_name,uploaded_by,created_at) VALUES(?,?,?,?,?,?)",
                      (fn,request.form["caption"],house,request.form["event_name"],session["user_id"],datetime.now().isoformat()))
            c.commit(); log("Uploaded gallery photo"); flash("Photo uploaded","ok")
        except Exception as e:
            c.rollback(); flash("Photo upload failed: "+str(e),"error")
    if session["role"] == "house_teacher":
        t=c.execute("SELECT house FROM teachers WHERE user_id=?",(session["uid"],)).fetchone()
        rows=c.execute("SELECT * FROM gallery WHERE house=? ORDER BY id DESC",(t["house"] if t else "",)).fetchall()
    else:
        rows=c.execute("SELECT * FROM gallery ORDER BY id DESC").fetchall()
    c.close()
    return render_template("gallery.html",rows=rows)

@app.route("/backup")
@role_required("owner","sports_teacher")
def backup():
    c=db()
    tables=['users','teachers','students','events','results','participation','assessments','annual','certificates','gallery','reset_requests','audit','settings','houses','house_positions','games']
    dump={}
    for table in tables:
        try: dump[table]=[dict(r) for r in c.execute(f'SELECT * FROM {table}').fetchall()]
        except Exception: dump[table]=[]
    c.close()
    data=json.dumps(dump,ensure_ascii=False,default=str,indent=2).encode('utf-8')
    return send_file(io.BytesIO(data),as_attachment=True,download_name='sports_department_backup.json',mimetype='application/json')

if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.environ.get("PORT",5000)),debug=False)

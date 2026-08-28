
from flask import Flask, request, render_template, redirect, url_for, session, send_from_directory, flash
from werkzeug.utils import secure_filename
from pathlib import Path
from datetime import datetime
import sqlite3, os, smtplib
from email.message import EmailMessage

BASE=Path(__file__).parent
UPLOAD=BASE/"uploads"; UPLOAD.mkdir(exist_ok=True)
DB=BASE/"data.db"
app=Flask(__name__); app.secret_key=os.getenv("SECRET_KEY","local-demo-secret-change-me")
app.config["MAX_CONTENT_LENGTH"]=25*1024*1024
ADMIN_PASSWORD=os.getenv("ADMIN_PASSWORD","1234")
EMAIL_TO=os.getenv("EMAIL_TO","Luka.kapanadze.95@gmail.com")
WHATSAPP="+995551551118"

def db():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c
def init():
    c=db()
    c.execute("""CREATE TABLE IF NOT EXISTS listings(
    id INTEGER PRIMARY KEY AUTOINCREMENT,name TEXT NOT NULL,phone TEXT NOT NULL,city TEXT NOT NULL,
    address TEXT NOT NULL,price TEXT NOT NULL,available TEXT,bedrooms TEXT,furnished TEXT,
    terms TEXT,notes TEXT,created TEXT NOT NULL)""")
    c.commit(); c.close()
init()

def send_email(listing, files):
    host=os.getenv("SMTP_HOST"); user=os.getenv("SMTP_USER"); password=os.getenv("SMTP_PASSWORD")
    if not (host and user and password): return False
    msg=EmailMessage()
    msg["Subject"]=f"ახალი ბინის განცხადება #{listing['id']} — {listing['city']}"
    msg["From"]=user; msg["To"]=EMAIL_TO
    msg.set_content("\n".join([
      f"განცხადება #{listing['id']}",f"სახელი: {listing['name']}",f"ტელეფონი: {listing['phone']}",
      f"ქალაქი: {listing['city']}",f"მისამართი: {listing['address']}",f"ქირა: {listing['price']}",
      f"თავისუფალია: {listing['available']}",f"საძინებლები: {listing['bedrooms']}",
      f"ავეჯი: {listing['furnished']}",f"პირობები: {listing['terms']}",f"დამატებითი: {listing['notes']}"
    ]))
    for p in files:
        data=p.read_bytes()
        msg.add_attachment(data,maintype="image",subtype=(p.suffix.lstrip(".") or "jpeg"),filename=p.name)
    with smtplib.SMTP_SSL(host,465) as s:
        s.login(user,password); s.send_message(msg)
    return True

@app.route("/",methods=["GET","POST"])
def home():
    if request.method=="POST":
        keys=["name","phone","city","address","price","available","bedrooms","furnished","terms","notes"]
        d={k:request.form.get(k,"").strip() for k in keys}
        if not all(d[k] for k in ["name","phone","city","address","price"]):
            flash("გთხოვთ შეავსოთ ყველა სავალდებულო ველი."); return redirect(url_for("home"))
        c=db(); cur=c.execute("""INSERT INTO listings(name,phone,city,address,price,available,bedrooms,furnished,terms,notes,created)
        VALUES(?,?,?,?,?,?,?,?,?,?,?)""",(*d.values(),datetime.now().strftime("%Y-%m-%d %H:%M"))); lid=cur.lastrowid
        c.commit(); row=c.execute("SELECT * FROM listings WHERE id=?",(lid,)).fetchone(); c.close()
        folder=UPLOAD/str(lid); folder.mkdir(exist_ok=True)
        files=[]
        for f in request.files.getlist("photos"):
            if f and f.filename and f.mimetype.startswith("image/"):
                p=folder/secure_filename(f.filename); f.save(p); files.append(p)
        try: send_email(row,files)
        except Exception: pass
        return render_template("success.html",id=lid,whatsapp=WHATSAPP)
    return render_template("home.html",whatsapp=WHATSAPP)

@app.route("/admin/login",methods=["GET","POST"])
def login():
    if request.method=="POST":
        if request.form.get("password")==ADMIN_PASSWORD: session["admin"]=True; return redirect(url_for("admin"))
        flash("პაროლი არასწორია.")
    return render_template("login.html")
@app.route("/admin")
def admin():
    if not session.get("admin"): return redirect(url_for("login"))
    c=db(); rows=c.execute("SELECT * FROM listings ORDER BY id DESC").fetchall(); c.close()
    photo_map={}
    for r in rows:
        folder=UPLOAD/str(r["id"])
        photo_map[r["id"]]=[p.name for p in folder.glob("*") if p.is_file()] if folder.exists() else []
    return render_template("admin.html",rows=rows,photo_map=photo_map)
@app.post("/admin/delete/<int:lid>")
def delete(lid):
    if not session.get("admin"): return redirect(url_for("login"))
    c=db(); c.execute("DELETE FROM listings WHERE id=?",(lid,)); c.commit(); c.close()
    shutil.rmtree(UPLOAD/str(lid),ignore_errors=True)
    return redirect(url_for("admin"))
@app.route("/uploads/<int:lid>/<path:name>")
def photo(lid,name):
    if not session.get("admin"): return ("Forbidden",403)
    return send_from_directory(UPLOAD/str(lid),name)
@app.route("/admin/logout")
def logout(): session.clear(); return redirect(url_for("home"))

if __name__=="__main__":
    app.run(host="127.0.0.1",port=int(os.getenv("PORT","5000")),debug=True)

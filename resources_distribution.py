from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector

app = Flask(__name__)

# إعداد الاتصال بقاعدة البيانات
db = mysql.connector.connect(
    host="localhost",
    user="root",
    password="password",
    database="aidlink"
)

# صفحة لوحة التحكم
@app.route("/dashboard")
def dashboard():
    if not session.get('user_id'):
        return redirect(url_for('login'))
    return render_template("dashboard.html")

# صفحة إضافة مستفيد
@app.route("/add_beneficiary", methods=["GET", "POST"])
def add_beneficiary():
    if request.method == "POST":
        name = request.form["beneficiary_name"]
        beneficiary_id = request.form["beneficiary_id"]
        contact_info = request.form["contact_info"]

        cursor = db.cursor()
        cursor.execute("INSERT INTO beneficiaries (name, beneficiary_id, contact_info) VALUES (%s, %s, %s)", (name, beneficiary_id, contact_info))
        db.commit()
        flash("تم إضافة المستفيد بنجاح")
        return redirect(url_for('add_beneficiary'))

    return render_template("add_beneficiary.html")

# صفحة توزيع الموارد
@app.route("/resources_distribution", methods=["GET", "POST"])
def resources_distribution():
    if request.method == "POST":
        resource_name = request.form["resource_name"]
        quantity = request.form["quantity"]

        cursor = db.cursor()
        cursor.execute("INSERT INTO resources (resource_name, quantity) VALUES (%s, %s)", (resource_name, quantity))
        db.commit()
        flash("تم توزيع المورد بنجاح")
        return redirect(url_for('resources_distribution'))

    return render_template("resources_distribution.html")

if __name__ == "__main__":
    app.run(debug=True)

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify,make_response,Response
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from functools import wraps
import pyodbc
from datetime import datetime
import bcrypt
import datetime
import locale
from flask_wtf.csrf import CSRFProtect
from wtforms import StringField, PasswordField
from wtforms.validators import InputRequired
from flask_wtf import FlaskForm
from flask_assets import Environment, Bundle
from waitress import serve
import secrets
from cryptography.fernet import Fernet
import hashlib
from flask import jsonify, request, session
import base64
import pandas as pd
from flask import make_response
from fpdf import FPDF
from io import BytesIO
import pdfkit
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.ttfonts import TTFont
from reportlab import pdfbase
from reportlab.pdfbase import pdfmetrics
import arabic_reshaper
from bidi.algorithm import get_display
from urllib.parse import quote
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from modules import employee as emp
from modules import checkup as che
from modules.db import get_connection
import pandas as pd
from flask import make_response
import io
from flask import send_file
from modules.equipment import equipment_bp
from modules.reports import get_column_mapping

# ----------------------------------------------------------------
#  تكوين التطبيق
# ----------------------------------------------------------------
app = Flask(__name__)
assets = Environment(app)

app.secret_key = 'your_secret_key_here'  # استخدم مفتاحًا سريًا حقيقيًا في الإنتاج
csrf = CSRFProtect(app)
# ----------------------------------------------------------------
#  دوال التعامل مع قاعدة البيانات
# ----------------------------------------------------------------

def get_db():
    """
    تعيد دالة الاتصال بقاعدة بيانات SQL Server باستخدام pyodbc.
    تأكد من إعداد السلسلة الصحيحة للاتصال بقاعدة البيانات.
    """
    conn = pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=localhost;"                # أو اسم السيرفر أو عنوان IP
        "DATABASE=pulldb;"                # اسم قاعدة البيانات
        "Trusted_Connection=yes;"          # استخدم 'UID=xxx;PWD=xxx;' للمصادقة بـ SQL
    )
    return conn


def is_logged_in():
    """
    تتحقق مما إذا كان المستخدم مسجلاً للدخول.
    """
    return session.get('id_no') is not None

def login_required(f):
    """
    Decorator للتحقق من تسجيل الدخول قبل الوصول إلى المسار المطلوب.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function
def create_token():
    """Generate a secure random 16-character token."""
    characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%^&*()"
    return ''.join(secrets.choice(characters) for _ in range(16))
# ----------------------------------------------------------------
#  المسارات (Routes)
# ----------------------------------------------------------------
@app.route('/report')
def report_page():
    return render_template('report.html')
app.register_blueprint(equipment_bp)

@app.route('/generate_token', methods=['GET', 'POST'])
def generate_token():
    token = None
    if request.method == 'POST':
        department = request.form.get('department', None)

        if not department:
            session["notification"] = {"type": "danger", "message": "يرجى إدخال اسم المنظمة!"}

        else:
            # Get today's date
            created_at = datetime.date.today().isoformat()

            # Check if a token already exists for the organization today
            conn = get_db()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT token FROM token WHERE department = ? AND created_at = ?",
                (department, created_at)
            )
            existing_token = cursor.fetchone()

            if existing_token:
                # Token already exists for today, use the existing token
                token = existing_token[0]
                session["notification"] = {"type": "warning", "message": "تم العثور على الرمز الحالي!"}

            else:
                # Generate new token
                token = create_token()

                # Save the new token to the database
                cursor.execute(
                    "INSERT INTO token (department, token, created_at) VALUES (?, ?, ?)", 
                    (department, token, created_at)
                )
                conn.commit()
                session["notification"] = {"type": "success", "message": "تم توليد الرمز بنجاح!"}


            conn.close()

    # Ensure the function always returns a response
    return render_template('generate_token.html', token=token)


@app.route('/export_pdf', methods=['GET'])
def export_pdf():
    # Retrieve query parameters
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')
    report_type = request.args.get('report_type')
    department = session.get("department")
    print(end_date)
    
    # Ensure decryption_value exists in the session
    decryption_value = session.get("decryption_value")
    if not decryption_value:
        return jsonify({"success": False, "message": "Decryption value is missing in the session"})

    # Derive a valid Fernet key from decryption_value
    key = base64.urlsafe_b64encode(hashlib.sha256(decryption_value.encode()).digest()[:32])
    fernet = Fernet(key)

    # Initialize report_data and database connection
    report_data = []
    conn = get_db()

    # Handle report generation based on report_type
    if report_type == 'beneficiaries_report':
        report_type_ar = 'تقرير المستفيدين'
        query = "SELECT name, national_id, contact_number, address, family_members, created_at FROM beneficiaries WHERE org = ?"
        if start_date and end_date:
            query += " AND created_at BETWEEN ? AND ? ORDER BY name ASC"
            results = conn.execute(query, (department, start_date, end_date)).fetchall()
        else:
            query += " ORDER BY name ASC"
            results = conn.execute(query, (department,)).fetchall()

        # Decrypt relevant fields
        for row in results:
            report_data.append({
                "name": fernet.decrypt(row[0].encode()).decode(),
                "national_id": row[1],  # Assuming this is already masked
                "contact_number": fernet.decrypt(row[2].encode()).decode(),
                "address": fernet.decrypt(row[3].encode()).decode(),
                "family_members": fernet.decrypt(row[4].encode()).decode(),
                "created_at": row[5],  # Assuming this is already masked
            })

    elif report_type == 'resource_distribution_report':
        report_type_ar = 'تقرير توزيع الموارد'
        query = '''SELECT b.id, b.name, rd.date, SUM(rd.quantity) as quantity, b.national_id, rd.resource_name
                   FROM beneficiaries b
                   Inner JOIN resources_DE rd ON b.id = rd.national_id WHERE b.org = ?'''
        if start_date and end_date:
            query += """ AND rd.date BETWEEN ? AND ? 
                         GROUP BY b.id, b.name, rd.date, b.national_id, rd.resource_name 
                         ORDER BY rd.resource_name, b.name ASC"""
            results = conn.execute(query, (department, start_date, end_date)).fetchall()
        else:
            query += """ GROUP BY b.id, b.name, rd.date, b.national_id, rd.resource_name 
                         ORDER BY rd.resource_name, b.name ASC"""
            results = conn.execute(query, (department,)).fetchall()

        # Decrypt relevant fields
        for row in results:
            report_data.append({
                "id": row[0],
                "name": fernet.decrypt(row[1].encode()).decode(),
                "national_id":  row[4],
                "resource_name": fernet.decrypt(row[5].encode()).decode(),
                "quantity":  row[3],
                "date":  row[2],

            })
    elif report_type == 'resource_inventory_report':
        report_type_ar = 'تقرير المخزون'
        query = "SELECT resource_name, quantity, created_at FROM resources WHERE org = ? AND quantity <> 0"
        if start_date and end_date:
            query += " AND created_at BETWEEN ? AND ? ORDER BY created_at, resource_name ASC"
            results = conn.execute(query, (department, start_date, end_date)).fetchall()
        else:
            query += " ORDER BY created_at, resource_name ASC"
            results = conn.execute(query, (department,)).fetchall()

        for row in results:
            report_data.append({
                "resource_name": fernet.decrypt(row[0].encode()).decode(),
                "quantity": row[1],
                "created_at":  row[2],
            })

    elif report_type == 'resource_donor_report':
        report_type_ar = 'تقرير المانحين'
        query = "SELECT doner, resource_name, quantity_rc, created_at FROM resources WHERE org = ?"
        if start_date and end_date:
            query += " AND created_at BETWEEN ? AND ? ORDER BY created_at, doner, resource_name ASC"
            results = conn.execute(query, (department, start_date, end_date)).fetchall()
        else:
            query += " ORDER BY created_at, doner, resource_name ASC"
            results = conn.execute(query, (department,)).fetchall()

        for row in results:
            report_data.append({
                "doner": fernet.decrypt(row[0].encode()).decode(),
                "resource_name": fernet.decrypt(row[1].encode()).decode(),
                "quantity": int(row[2]),
                "created_at":  row[3],
            })

    conn.close()
    if not report_data:
        return jsonify({"success": False, "message": "No data available for the selected report type and date range"})

    # Path to Arabic font (Amiri or any Arabic font)
    font_path = 'static/fonts/Amiri-Bold.ttf'

    # Register the custom Arabic font
    try:
        pdfmetrics.registerFont(TTFont('Amiri', font_path))
    except Exception as e:
        return jsonify({"success": False, "message": f"Font registration failed: {str(e)}"})

    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    reshaped_title = arabic_reshaper.reshape(report_type_ar)
    bidi_title = get_display(reshaped_title)
    styles = getSampleStyleSheet()
    arabic_style = ParagraphStyle(
        'ArabicStyle',
        parent=styles['Normal'],
        fontName='Amiri',
        fontSize=14,
        leading=16,
        alignment=1  # Center alignment
    )

    # Set the font to Arabic
    pdf.setFont("Amiri", 14)
    pdf.drawCentredString(300, 780, bidi_title)
    # Define table headers and x_positions for each report type
    if report_type == 'beneficiaries_report':
        headers = ["الاسم", "الرقم الوطني", "رقم الاتصال", "العنوان", "أفراد الأسرة","تاريخ الانتساب"]
    elif report_type == 'resource_distribution_report':
        headers = ["الرقم التعريفي", "اسم المستفيد", "الرقم الوطني", "الموزع", "الكمية", "التاريخ"]

    elif report_type == 'resource_inventory_report':
        headers = ["اسم المورد", "الكمية", "تاريخ الإنشاء"]
    elif report_type == 'resource_donor_report':
        headers = ["المانح", "اسم المورد", "الكمية", "تاريخ الإنشاء"]

    # Prepare table data (headers + rows)
    reshaped_headers = [get_display(arabic_reshaper.reshape(header)) for header in headers]

    # Prepare table data
    table_data = [reshaped_headers]  # Add reshaped headers
    for row in report_data:
        reshaped_row = []
        for key, value in row.items():
            if key == "الكمية" and isinstance(value, (int, float)):  # Check if it's the "الكمية" column
                formatted_value = locale.format_string("%d", value, grouping=True)  # Format with commas
                bidi_value = get_display(arabic_reshaper.reshape(formatted_value))
            elif isinstance(value, str):
                reshaped_value = arabic_reshaper.reshape(value)
                bidi_value = get_display(reshaped_value)
            else:
                bidi_value = str(value)
            reshaped_row.append(bidi_value)
        table_data.append(reshaped_row)
    if report_type == 'beneficiaries_report':
        headers = ["الاسم", "الرقم الوطني", "رقم الاتصال", "العنوان", "أفراد الأسرة","تاريخ الانتساب"]
        table = Table(table_data, colWidths=[140, 80, 80, 120, 60, 80][:len(reshaped_headers)])

    elif report_type == 'resource_distribution_report':
        headers = ["الرقم التعريفي", "اسم المستفيد", "الرقم الوطني", "الموزع", "الكمية", "التاريخ"]
        table = Table(table_data, colWidths=[60, 140, 80, 80, 60, 80][:len(reshaped_headers)])


    elif report_type == 'resource_inventory_report':
        headers = ["اسم المورد", "الكمية", "تاريخ الإنشاء"]
        table = Table(table_data, colWidths=[180, 180, 180][:len(reshaped_headers)])

    elif report_type == 'resource_donor_report':
        headers = ["المانح", "اسم المورد", "الكمية", "تاريخ الإنشاء"]
        table = Table(table_data, colWidths=[140, 120, 100, 140][:len(reshaped_headers)])

    # Add table styling
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), '#383F51'),  # Header background color
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),  # Header text color
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),  # Center align all cells
        ('FONTNAME', (0, 0), (-1, -1), 'Amiri'),  # Use the Arabic font
        ('FONTSIZE', (0, 0), (-1, -1), 10),  # Font size
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),  # Padding for header
        ('BACKGROUND', (0, 1), (-1, -1), colors.whitesmoke),  # Body background color
        ('GRID', (0, 0), (-1, -1), 1, colors.black),  # Table grid lines
    ]))

    buffer.seek(0)
    doc = SimpleDocTemplate(buffer, pagesize=letter, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)

    # Create elements for the document
    elements = []

    # Add title
    elements.append(Paragraph(bidi_title, arabic_style))
    elements.append(Spacer(1, 20))  # Add some space below the title

    #elements.append(Paragraph(bidi_title, pdfmetrics.registerFont(TTFont('Amiri', font_path))))

    # Add the table
    elements.append(table)

    # Build the document
    doc.build(elements)

    # Return the generated PDF as a response
    buffer.seek(0)
    encoded_filename = quote(report_type_ar + ".pdf")

    
    return Response(buffer, mimetype='application/pdf', headers={
        "Content-Disposition": f"attachment;filename={encoded_filename}"
    })



@app.route('/export_excel', methods=['GET'])
def export_excel():
    report_type = request.args.get('report_type')
    date_range = request.args.get('report_data')
    department = session.get("department")

    # Fetch data similar to `/generate_report`
    report_data = fetch_report_data(report_type, date_range, department)

    # Convert data to DataFrame
    df = pd.DataFrame(report_data)

    # Create Excel file
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Report')

    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=report_{report_type}.xlsx'
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return response


def fetch_report_data(report_type, date_range, department):
    # Logic to fetch data based on report_type, date_range, and department
    # Extracted from your `/generate_report` function
    # Returns a list of dictionaries representing the rows
    pass
@app.route('/generate_report', methods=['GET'])
def generate_report():
    report_type = request.args.get('report_type')
    date_range = request.args.get('date_range')
    department = session.get("department")

    # Ensure decryption_value exists in the session
    decryption_value = session.get("decryption_value")
    if not decryption_value:
        return jsonify({"success": False, "message": "Decryption value is missing in the session"})

    # Derive a valid Fernet key from decryption_value
    key = base64.urlsafe_b64encode(hashlib.sha256(decryption_value.encode()).digest()[:32])
    fernet = Fernet(key)

    start_date = None
    end_date = None
    if date_range:
        date_range_parts = date_range.split(" إلى ")
        if len(date_range_parts) == 2:
            start_date = datetime.strptime(date_range_parts[0], '%d-%m-%Y')
            end_date = datetime.strptime(date_range_parts[1], '%d-%m-%Y')

    report_data = []

    conn = get_db()

    if report_type == 'beneficiaries_report':
        report_type_ar = 'تقرير المستفيدين'
        query = "SELECT name, national_id, contact_number, address, family_members, created_at FROM beneficiaries WHERE org = ?"
        if start_date and end_date:
            query += " AND created_at BETWEEN ? AND ? ORDER BY name ASC"
            results = conn.execute(query, (department, start_date, end_date)).fetchall()
        else:
            query += " ORDER BY name ASC"
            results = conn.execute(query, (department,)).fetchall()

        # Decrypt relevant fields
        for row in results:
            report_data.append({
                "name": fernet.decrypt(row[0].encode()).decode(),
                "national_id": row[1],  # Assuming this is already masked
                "contact_number": fernet.decrypt(row[2].encode()).decode(),
                "address": fernet.decrypt(row[3].encode()).decode(),
                "family_members": fernet.decrypt(row[4].encode()).decode(),
                "created_at": row[5],  # Assuming this is already masked
            })

    elif report_type == 'resource_distribution_report':
        report_type_ar = 'تقرير توزيع الموارد'
        query = '''SELECT b.id, b.name, rd.date, SUM(rd.quantity) as quantity, b.national_id, rd.resource_name
                   FROM beneficiaries b
                   Inner JOIN resources_DE rd ON b.id = rd.national_id WHERE b.org = ? '''
        if start_date and end_date:
            query += """ AND rd.date BETWEEN ? AND ? 
                         GROUP BY b.id, b.name, rd.date, b.national_id, rd.resource_name 
                         ORDER BY rd.resource_name, b.name ASC"""
            results = conn.execute(query, (department, start_date, end_date)).fetchall()
        else:
            query += """ GROUP BY b.id, b.name, rd.date, b.national_id, rd.resource_name 
                         ORDER BY rd.resource_name, b.name ASC"""
            results = conn.execute(query, (department,)).fetchall()

        # Decrypt relevant fields
        for row in results:
            report_data.append({
                "id": row[0],
                "name": fernet.decrypt(row[1].encode()).decode(),
                "national_id":  row[4],
                "resource_name": fernet.decrypt(row[5].encode()).decode(),
                "quantity":  row[3],
                "date":  row[2],

            })

    elif report_type == 'resource_inventory_report':
        report_type_ar = 'تقرير المخزون'
        query = "SELECT resource_name, quantity, created_at FROM resources WHERE org = ? AND quantity <> 0"
        if start_date and end_date:
            query += " AND created_at BETWEEN ? AND ? ORDER BY created_at,resource_name ASC"
            results = conn.execute(query, (department, start_date, end_date)).fetchall()
        else:
            query += " ORDER BY created_at,resource_name ASC"
            results = conn.execute(query, (department,)).fetchall()

        for row in results:
            report_data.append({
                "resource_name": fernet.decrypt(row[0].encode()).decode(),  # Assuming this is already masked
                "quantity": row[1],
                "created_at":  row[2],
    })

    elif report_type == 'resource_donor_report':
        report_type_ar = 'تقرير المانحين'
        query = "SELECT doner, resource_name, quantity_rc, created_at FROM resources WHERE org = ?"
        if start_date and end_date:
            query += " AND created_at BETWEEN ? AND ? ORDER BY created_at,doner, resource_name ASC"
            results = conn.execute(query, (department, start_date, end_date)).fetchall()
        else:
            query += " ORDER BY created_at,doner, resource_name ASC"
            results = conn.execute(query, (department,)).fetchall()

        for row in results:
            report_data.append({
                "doner": fernet.decrypt(row[0].encode()).decode(),  # Assuming this is already masked
                "resource_name": fernet.decrypt(row[1].encode()).decode(),  # Assuming this is already masked

                "quantity": int(row[2]),
                "created_at":  row[3],
    })

    conn.close()

    return render_template('report.html', report_data=report_data, report_type=report_type,report_type_ar=report_type_ar)


@app.route("/")
def index():
    """
    الصفحة الرئيسية، تُحوِّل تلقائيًا إلى تسجيل الدخول أو لوحة التحكم.
    """
    if not is_logged_in():
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

# المسار لصفحة "بحث مستفيدين"
@app.route('/search', methods=['GET', 'POST'])
@login_required
def search_beneficiaries():
    conn = get_db()
    cursor = conn.cursor()
    role = session.get("role")

    # Ensure only 'ادارة' role has access
    if role != 'ادارة':
        return "Access Denied", 403

    beneficiaries = []
    organizations = []  # To hold organizations for the dropdown
    if request.method == 'POST':
        search_term = request.form.get('search_term', '').strip()

        # Safely execute the query with parameterized input
        cursor.execute(
            "SELECT * FROM beneficiaries WHERE national_id LIKE ? ORDER BY name ASC",
            (f"%{search_term}%",)
        )
        beneficiaries = cursor.fetchall()

    # Fetch organizations for the dropdown
    cursor.execute("SELECT DISTINCT department FROM users WHERE department IS NOT NULL")
    organizations = cursor.fetchall()

    # Extract organization names into a list
    org_names = [org['department'] for org in organizations]

    return render_template('search_beneficiaries.html', beneficiaries=beneficiaries, organizations=org_names)

@app.route('/manage_duplicates')
def manage_duplicates():
    conn = get_db()
    cursor = conn.cursor()
    department = session.get("department")
    decryption_value = session.get("decryption_value")
    
    if not decryption_value:
        return jsonify({"success": False, "message": "Decryption value is missing in the session"})

    # Derive a valid Fernet key from decryption_value
    key = base64.urlsafe_b64encode(hashlib.sha256(decryption_value.encode()).digest()[:32])
    fernet = Fernet(key)

    cursor.execute(
        "SELECT id, name, national_id, contact_number, org FROM beneficiaries_dup WHERE c_org = ?",
        (department,)
    )
    beneficiaries = cursor.fetchall()

    # Decrypt sensitive fields
    decrypted_beneficiaries = []
    for beneficiary in beneficiaries:
        try:
            decrypted_beneficiaries.append({
                "id": beneficiary[0],
                "name": fernet.decrypt(beneficiary[1].encode()).decode(),
                "national_id": beneficiary[2],  # Assuming this is already masked
                "contact_number": fernet.decrypt(beneficiary[3].encode()).decode(),
                "org": beneficiary[4]
            })
        except Exception as e:
            # Log the error and skip the record if decryption fails
            print(f"Error decrypting record {beneficiary[0]}: {e}")
            continue

    conn.close()

    return render_template('manage_duplicates.html', beneficiaries=decrypted_beneficiaries)


@app.route('/clear_table', methods=['POST'])
def clear_table():
    conn = get_db()
    cursor = conn.cursor()
    department = session.get("department")
    cursor.execute(
                "DELETE FROM beneficiaries_dup where c_org = ?",
                (department,)
            )   
    conn.commit()
    conn.close()
    session["notification"] = {"type": "success", "message": "تم حذف المستفيدين المكررين بنجاح"}

    return redirect(url_for('manage_duplicates'))
@app.route('/delete_beneficiary_dup/<int:id>', methods=['POST'])
def delete_beneficiary_dup(id):
    try:
        conn = get_db()
        cursor = conn.cursor()
        department = session.get("department")
        cursor.execute(
                "DELETE FROM beneficiaries_dup where c_org = ? and id = ?",
                (department,id,)
            )   
        conn.commit()
        conn.close()
        session["notification"] = {"type": "success", "message": "تم حذف المستفيد المكرر بنجاح"}

    except Exception as e:
        session["notification"] = {"type": "danger", "message": "حدث خطأ أثناء الحذف"}

    return redirect(url_for('manage_duplicates'))


@app.route('/upload_beneficiaries', methods=['POST'])
def upload_beneficiaries():
    if 'file' not in request.files:

        return jsonify({"success": False, "message": "No file part"})

    file = request.files['file']
    if file.filename == '':
        session["notification"] = {"type": "warning", "message": "لم يتم اخيار الملف المطلوب"}

        return jsonify({"success": False, "message": "No selected file"})

    if file:
        department = session.get("department")
        decryption_value = session.get("decryption_value")
        if not decryption_value:
            return jsonify({"success": False, "message": "Decryption value is missing in the session"})

        # Derive a valid Fernet key from decryption_value
        key = base64.urlsafe_b64encode(hashlib.sha256(decryption_value.encode()).digest()[:32])
        fernet = Fernet(key)

        # Read the Excel file into a pandas DataFrame
        df = pd.read_excel(file)
        
        # Connect to SQLite database
        conn = get_db()
        cursor = conn.cursor()

    try:
        for _, row in df.iterrows():
            national_id = row['national_id']
            # Mask the first 8 digits of the national ID
            masked_national_id = f"{str(national_id)[8:]}{'*' * 8}"
            # Encrypt sensitive fields using Fernet
            name_enc = fernet.encrypt(row['name'].encode()).decode()
            contact_number_enc = fernet.encrypt(str(row['contact_number']).encode()).decode()
            address_enc = fernet.encrypt(str(row['address']).encode()).decode()
            family_members_enc = fernet.encrypt(str(row['family_members']).encode()).decode()

            # Hash the national ID
            national_id_enc = generate_password_hash(str(national_id))

            # Get current timestamp
            created_at = datetime.date.today().isoformat()

            # Check for duplicate national IDs in the beneficiaries table
            masked_national_id_check = f"%{str(national_id)[8:]}%"
            cursor.execute(
                "SELECT national_id_enc, org FROM beneficiaries WHERE national_id LIKE ?",
                (masked_national_id_check,)
            )
            beneficiaries = cursor.fetchall()

            duplicate_found = False

            for beneficiary in beneficiaries:
                if check_password_hash(beneficiary[0], str(national_id)):
                    duplicate_found = True
                    # Check if the duplicate is already in beneficiaries_dup
                    cursor.execute(
                        "SELECT id, national_id_enc FROM beneficiaries_dup WHERE national_id LIKE ? AND c_org = ?",
                        (masked_national_id_check, department)
                    )
                    beneficiaries_dups = cursor.fetchall()

                    # If no duplicate in beneficiaries_dup, insert it
                    if not beneficiaries_dups:
                        cursor.execute("""
                            INSERT INTO beneficiaries_dup (
                                name, national_id, contact_number, org, national_id_enc, c_org, created_at
                            ) 
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (
                            name_enc, masked_national_id, contact_number_enc, 
                            beneficiary[1], national_id_enc, department, created_at
                        ))
                        conn.commit()
                        break
                    else:
                        # Check if any of the duplicates in beneficiaries_dup already match
                        duplicate_in_dups = False
                        for beneficiary_dup in beneficiaries_dups:
                            if check_password_hash(beneficiary_dup[1], str(national_id)):
                                duplicate_in_dups = True
                                break
                        
                        # If no duplicate is found in beneficiaries_dup, insert the new record
                        if not duplicate_in_dups:
                            cursor.execute("""
                                INSERT INTO beneficiaries_dup (
                                    name, national_id, contact_number, org, national_id_enc, c_org, created_at
                                ) 
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (
                                name_enc, masked_national_id, contact_number_enc, 
                                beneficiary[1], national_id_enc, department, created_at
                            ))
                            conn.commit()
                            break

            # If no duplicate was found, insert into beneficiaries table
            if not duplicate_found:
                cursor.execute("""
                    INSERT INTO beneficiaries (
                        name, national_id, contact_number, address, family_members, org, national_id_enc, created_at
                    ) 
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name_enc, masked_national_id, contact_number_enc, 
                    address_enc, family_members_enc, department, national_id_enc, created_at
                ))

        conn.commit()
    except Exception as e:
        conn.rollback()  # Rollback any changes in case of an error
        return jsonify({"success": False, "message": str(e)})
    finally:
        conn.close()
        session["notification"] = {"type": "success", "message": "تم اضافة المستفيدين بنجاح بنجاح"}
        return jsonify({"success": True, "message": "Beneficiaries added successfully"})
    session["notification"] = {"type": "danger", "message": "خطأ في تحميل الملف"}

    return jsonify({"success": False, "message": "File upload failed"})





@app.route('/users', methods=['GET', 'POST'])
@login_required
def manage_users():
    conn = get_db()
    cursor = conn.cursor()
    role = session.get("role")

    # تحقق من أن المستخدم لديه صلاحيات "إدارة"
    if role != 'ادارة':
        return "Access Denied", 403

    if request.method == 'POST':
        action = request.form.get('action')
        id_no = request.form.get('id_no')

        if action == 'delete':
            # حذف المستخدم
            cursor.execute("DELETE FROM users WHERE id = ?", (id_no,))
            conn.commit()
        elif action == 'edit':
            # تعديل بيانات المستخدم
            new_username = request.form.get('user_name')
            new_role = request.form.get('role')
            new_orgname = request.form.get('department')
            cursor.execute(
                "UPDATE users SET user_name = ?, role = ?, department = ? WHERE id = ?",
                (new_username, new_role, new_orgname, id_no)
            )
            conn.commit()
        elif action == 'update_password':
            # تحديث كلمة المرور
            new_password = request.form.get('password')
            hashed_password = generate_password_hash(new_password)
            cursor.execute(
                "UPDATE users SET password = ? WHERE id = ?",
                (hashed_password, id_no)
            )
            conn.commit()

    # جلب قائمة المستخدمين لعرضها في الواجهة
    cursor.execute("SELECT id, user_name, role, department FROM users ORDER BY role ASC")
    users = cursor.fetchall()

    return render_template('manage_users.html', users=users)




# صفحة تسجيل الدخول
class LoginForm(FlaskForm):
    user_name = StringField('اسم المستخدم', validators=[InputRequired()])
    password = PasswordField('كلمة المرور', validators=[InputRequired()])
    decryption_value = PasswordField('رمز التشفير')  # Optional field, only required for "منظمة" role


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    تسجيل الدخول للمستخدم. يتطلب إدخال اسم المستخدم وكلمة المرور.
    """
    form = LoginForm()

    if request.method == "POST" and form.validate_on_submit():
        user_name = form.user_name.data
        password = form.password.data

        conn = get_db()
        cursor = conn.cursor()

        # نفترض أن الجدول يحتوي على هذه الأعمدة: id, name, user_name, password, role, department, location
        cursor.execute("SELECT id, name, user_name, password, role, department, location FROM users WHERE user_name = ?", (user_name,))
        row = cursor.fetchone()
        conn.close()

        if row:
            db_password = row[3]  # password is at index 3
            if check_password_hash(db_password, password):
                role = row[4]
                if role == "موظف":
                    session["id_no"] = row[0]
                    session["name"] = row[1]
                    session["department"] = row[5]
                    session["role"] = role
                    session["location"] = row[6]
                    session["notification"] = {"type": "success", "message": "تم تسجيل الدخول بنجاح"}
                    return redirect(url_for("dashboard"))

                elif role == "ادارة":
                    session["id_no"] = row[0]
                    session["name"] = row[1]
                    session["department"] = row[5]
                    session["role"] = role
                    session["location"] = row[6]
                    session["notification"] = {"type": "success", "message": "تم تسجيل الدخول بنجاح"}
                    return redirect(url_for("dashboard"))

                else:
                    session["notification"] = {"type": "danger", "message": "اسم المستخدم أو كلمة المرور غير صحيحة"}
            else:
                session["notification"] = {"type": "danger", "message": "اسم المستخدم أو كلمة المرور غير صحيحة"}
        else:
            session["notification"] = {"type": "danger", "message": "اسم المستخدم أو كلمة المرور غير صحيحة"}

    return render_template("login.html", form=form)


class LoginFormA(FlaskForm):
    user_name = StringField('اسم المستخدم', validators=[InputRequired()])
    password = PasswordField('كلمة المرور', validators=[InputRequired()])

@app.route("/loginA", methods=["GET", "POST"])
def loginA():
    """
    تسجيل الدخول للمستخدم. يتطلب إدخال اسم المستخدم وكلمة المرور.
    """
    form = LoginForm()  # Instantiate the form object

    if request.method == "POST" and form.validate_on_submit():
        user_name = form.user_name.data
        password = form.password.data

        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_name = ?", (user_name,))
        user = cursor.fetchone()
        conn.close()

        if user and check_password_hash(user["password"], password):
            session["id_no"] = user["id"]
            session["department"] = user["department"]  # حفظ department في الجلسة (إن وُجد)
            session["role"] = user["role"]

            flash("تم تسجيل الدخول بنجاح", "success")
            return redirect(url_for("dashboard"))
        else:
            flash("اسم المستخدم أو كلمة المرور غير صحيحة", "danger")

    return render_template("loginA.html", form=form)
# صفحة التسجيل
@app.route("/register", methods=["GET", "POST"])
@login_required

def register():
    if request.method == "POST":
        user_name = request.form["user_name"]
        name = request.form["name"]
        password = request.form["password"]
        department = request.form.get("department", None)
        id_no = request.form["id_no"]
        role = request.form["role"]
        location = request.form["location"]
        cell_phone = request.form["cell_phone"]
        hashed_password = generate_password_hash(password)
        created_at = datetime.date.today().isoformat()

        conn = get_db()
        cursor = conn.cursor()

        # Check for duplicate username
        cursor.execute("SELECT * FROM users WHERE user_name = ?", (user_name,))
        existing_user = cursor.fetchone()
        if existing_user:
            session["notification"] = {
                "type": "warning",
                "message": "اسم المستخدم موجود بالفعل. الرجاء اختيار اسم آخر"
            }
            conn.close()
            return redirect(url_for("register"))

        # Generate other necessary fields (replace with your actual logic)


        # Insert new user
        cursor.execute(
            """
            INSERT INTO users (id_no, name, user_name, password, role, department, location, cell_phone)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (id_no, name, user_name, hashed_password, role, department, location, cell_phone)
        )

        conn.commit()
        conn.close()

        session["notification"] = {
            "type": "success",
            "message": "تم التسجيل بنجاح"
        }
        return redirect(url_for("dashboard"))

    return render_template("register.html")



@app.route("/register__", methods=["GET", "POST"])
def register__():
    """
    تسجيل منظمة جديدة. التحقق من وجود الرمز في قاعدة البيانات
    """
    if request.method == "POST":
        user_name = request.form["user_name"]
        password = request.form["password"]
        role ="منظمة"
        
        token = request.form["token"]
        encryption_token = request.form["encryption_token"]
        
        # تشفير كلمة المرور ورمز التشفير
        hashed_password = generate_password_hash(password)
        hashed_encryption_token = generate_password_hash(encryption_token)

        # الاتصال بقاعدة البيانات
        conn = get_db()
        cursor = conn.cursor()
        created_at = datetime.date.today().isoformat()

        # التحقق من وجود الرمز في جدول token
        cursor.execute("SELECT * FROM token WHERE token = ? and created_at = ?", (token,created_at,))
        existing_token = cursor.fetchone()
        if not existing_token:
            session["notification"] = {"type": "danger", "message": "رمز التسجيل غير موجود. يرجى التحقق من الرمز."}
            conn.close()
            return redirect(url_for("register"))
        department = existing_token["department"]
        # التحقق من تكرار اسم المستخدم
        cursor.execute("SELECT * FROM users WHERE user_name = ?", (user_name,))
        existing_user = cursor.fetchone()
        if existing_user:
            session["notification"] = {"type": "warning", "message": "اسم المستخدم موجود بالفعل. الرجاء اختيار اسم آخر"}

            conn.close()
            return redirect(url_for("register"))

        # إضافة المستخدم إلى قاعدة البيانات
        cursor.execute(
            "INSERT INTO users (user_name, password, role, department, created_at, encryption_token) VALUES (?, ?, ?, ?, ?, ?)",
            (user_name, hashed_password, role, department, created_at, hashed_encryption_token),
        )
        conn.commit()

        # حذف الرمز من جدول token بناءً على اسم المنظمة
        cursor.execute(
            "DELETE FROM token WHERE department = ?",
            (department,)  # يجب إضافة فاصلة لتكون قيمة مع tuple
        )
        conn.commit()

        conn.close()
        session["notification"] = {"type": "success", "message": "تم التسجيل بنجاح"}


        return redirect(url_for("dashboard"))

    return render_template("register.html")

# صفحة لوحة التحكم
@app.route("/dashboard")
@login_required
def dashboard():
    """
    تعرض إحصائيات بسيطة عن عدد المستفيدين وكميات الموارد المتوفرة.
    """
    conn = get_db()
    cursor = conn.cursor()
    department = session.get("department")

    # إحصائيات لوحة التحكم

    conn.close()

    return render_template(
        "dashboard.html"
    )

# صفحة عرض المستفيدين


@app.route("/show_beneficiaries", methods=["GET", "POST"])
@login_required
def show_beneficiaries():
    """
    عرض جميع المستفيدين التابعين للمنظمة المسجّل حسابها.
    """
    department = session.get("department")
    decryption_value = session.get("decryption_value")
    if not decryption_value:
        session["notification"] = {"type": "error", "message": "لا يمكن عرض المستفيدين لأن قيمة فك التشفير غير متوفرة."}
        return redirect(url_for("dashboard"))

    # Derive a valid Fernet key from decryption_value
    key = base64.urlsafe_b64encode(hashlib.sha256(decryption_value.encode()).digest()[:32])
    fernet = Fernet(key)

    # Handle POST request when search button is clicked
    if request.method == "POST":
        search_query = request.form.get("search", "").lower()  # Get the search query from the form

        conn = get_db()
        cursor = conn.cursor()

        # Base query for selecting beneficiaries
        query = """
            SELECT id, name, national_id, contact_number, address, family_members
            FROM beneficiaries
            WHERE org = ?
        """
        
        # Add search condition if search query exists
        params = [department]
        if search_query:
            query += """
                AND (LOWER(name) LIKE ? OR LOWER(national_id) LIKE ? OR LOWER(contact_number) LIKE ?)
            """
            search_value = f"%{search_query}%"
            params.extend([search_value, search_value, search_value])

        cursor.execute(query, params)
        beneficiaries = cursor.fetchall()
        conn.close()

        if not beneficiaries:
            # Set notification in the session if no beneficiaries are found
            session["notification"] = {"type": "warning", "message": "لا يوجد مستفيدين"}
            return render_template("show_beneficiaries.html", beneficiaries=[])

        # Decrypt the necessary fields
        decrypted_beneficiaries = []
        for beneficiary in beneficiaries:
            try:
                decrypted_beneficiary = {
                    "id": beneficiary["id"],  # Excluded from decryption
                    "name": fernet.decrypt(beneficiary["name"].encode()).decode(),
                    "national_id": beneficiary["national_id"],  # Excluded from decryption
                    "contact_number": fernet.decrypt(beneficiary["contact_number"].encode()).decode(),
                    "address": fernet.decrypt(beneficiary["address"].encode()).decode(),
                    "family_members": fernet.decrypt(beneficiary["family_members"].encode()).decode(),
                }
                decrypted_beneficiaries.append(decrypted_beneficiary)
            except Exception as e:
                session["notification"] = {
                    "type": "error",
                    "message": f"حدث خطأ أثناء فك التشفير: {str(e)}"
                }
                return render_template("show_beneficiaries.html", beneficiaries=[])

        return render_template("show_beneficiaries.html", beneficiaries=decrypted_beneficiaries)

    # If no search, show an empty list or initial state
    return render_template("show_beneficiaries.html", beneficiaries=[])


# صفحة الموارد الموزّعة على مستفيد معيّن
@app.route("/beneficiary_resources/<string:beneficiaryId>")
@login_required
def beneficiary_resources(beneficiaryId):
    """
    عرض الموارد الموزعة لمستفيد معيّن حسب رقمه الوطني.
    """
    # Get the decryption value from the session
    decryption_value = session.get("decryption_value")
    if not decryption_value:
        return jsonify({"success": False, "message": "Decryption value is missing in the session"}), 400

    # Derive a valid Fernet key from decryption_value
    key = base64.urlsafe_b64encode(hashlib.sha256(decryption_value.encode()).digest()[:32])
    fernet = Fernet(key)

    def decrypt_value(encrypted_value):
        try:
            return fernet.decrypt(encrypted_value.encode()).decode()
        except Exception as e:
            print(f"Decryption failed: {e}")
            return None

    department = session.get("department")

    try:
        with get_db() as conn:
            cursor = conn.cursor()
            query = """
                SELECT rd.date, re.doner, rd.resource_name, rd.quantity, rd.org
                FROM resources_DE rd
                INNER JOIN resources re ON rd.resource_id = re.id
                WHERE rd.national_id = ?
                ORDER BY rd.date DESC
            """
            cursor.execute(query, (beneficiaryId,))
            resources = cursor.fetchall()

        # Decrypt fields and construct the response
        resources_list = [
            {
                "date": resource[0],
                "doner": decrypt_value(resource[1]),
                "resource_name": decrypt_value(resource[2]),
                "quantity": resource[3],
                "org": (resource[4]),
            }
            for resource in resources
        ]

        return jsonify({"resources": resources_list})

    except Exception as e:
        app.logger.error(f"Error fetching resources for national_id {beneficiaryId}: {e}")
        return jsonify({"error": "حدث خطأ أثناء جلب الموارد."}), 500




@app.route('/edit_beneficiaryA', methods=['POST'])
@login_required
def edit_beneficiaryA():
    conn = get_db()
    cursor = conn.cursor()

    # Ensure the required fields are present
    required_fields = ['org']
    for field in required_fields:
        if not request.form.get(field):
            return f"Error: Missing required field: {field}", 400  # You can return a more user-friendly error message

    beneficiary_id = request.form['beneficiary_id']
    org = request.form['org']

    # Safely update the beneficiary record
    cursor.execute("""
        UPDATE beneficiaries
        SET org = ?
        WHERE id = ?
    """, ( org, beneficiary_id))

    conn.commit()
    return redirect('/search')  # Redirect to the list of beneficiaries after successful update



# صفحة إضافة مستفيد
@app.route("/add_beneficiary", methods=["POST"])
@login_required
def add_beneficiary():
    """
    إضافة مستفيد جديد. يجب التأكد من عدم تكرار رقم الهوية (national_id).
    """
    department = session.get("department")
    decryption_value = session.get("decryption_value")
    if not department or not decryption_value:
        session["notification"] = {"type": "error", "message": "لا يمكن إضافة مستفيد لأن المنظمة أو رمز التشفير غير محدد."}
        return redirect(url_for('show_beneficiaries'))

    # Derive a valid Fernet key from "rami" (32 bytes, Base64-encoded)
    key = base64.urlsafe_b64encode(hashlib.sha256(decryption_value.encode()).digest()[:32])

    # Initialize Fernet with the derived key
    fernet = Fernet(key)

    # Retrieve form data
    name = request.form.get("beneficiary_name")
    national_id = request.form.get("national_id")
    contact_number = request.form.get("contact_number")
    address = request.form.get("address")
    family_members = request.form.get("family_members")
    created_at = datetime.date.today().isoformat()
    if not all([name, national_id, contact_number, address, family_members]):
        session["notification"] = {"type": "error", "message": "جميع الحقول مطلوبة."}
        return redirect(url_for('show_beneficiaries'))

    conn = get_db()
    cursor = conn.cursor()
    masked_national_id_check = f"%{national_id[8:]}%"

    # Retrieve all hashed national IDs from the database where the masked part matches
    cursor.execute(
        "SELECT national_id_enc, org FROM beneficiaries WHERE national_id LIKE ?",
        (masked_national_id_check,)
    )
    beneficiaries = cursor.fetchall()

    # Check if the provided national ID matches any existing hash
    for beneficiary in beneficiaries:
        if check_password_hash(beneficiary['national_id_enc'], national_id):
            session["notification"] = {
                "type": "warning",
                "message": f"هذا المستفيد موجود بالفعل في : {beneficiary['org']}"
            }
            return redirect(url_for('show_beneficiaries'))

    # Hash the national ID
    national_id_enc = generate_password_hash(national_id)

    # Mask the first 8 digits of the national ID
    masked_national_id = f"{national_id[8:]}{'*' * 8}"

    # Encrypt sensitive data
    encrypted_name = fernet.encrypt(name.encode()).decode()
    encrypted_contact_number = fernet.encrypt(contact_number.encode()).decode()
    encrypted_address = fernet.encrypt(address.encode()).decode()
    encrypted_family_members = fernet.encrypt(family_members.encode()).decode()
    # Insert new beneficiary
    cursor.execute("""
        INSERT INTO beneficiaries (
            name, national_id, contact_number, address, family_members, org, national_id_enc, created_at
        ) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (encrypted_name, masked_national_id, encrypted_contact_number, encrypted_address, encrypted_family_members, department, national_id_enc, created_at))

    conn.commit()
    session["notification"] = {"type": "success", "message": "تم إضافة المستفيد بنجاح"}

    
    return redirect(url_for('show_beneficiaries'))


@app.route('/edit_beneficiary/<string:id>', methods=['GET', 'POST'])
@login_required
def edit_beneficiary(id):
    conn = get_db()
    cursor = conn.cursor()

    # Fetch the decryption key from the session
    decryption_value = session.get("decryption_value")
    if not decryption_value:
        return jsonify({"success": False, "message": "Decryption value is missing in the session"}), 400

    # Derive a valid Fernet key from decryption_value
    key = base64.urlsafe_b64encode(hashlib.sha256(decryption_value.encode()).digest()[:32])
    fernet = Fernet(key)

    # Fetch the beneficiary details from the database by `id`
    cursor.execute("SELECT id, name, contact_number, address, family_members FROM beneficiaries WHERE id = ?", (id,))
    beneficiary = cursor.fetchone()

    if not beneficiary:
        return "Beneficiary not found", 404

    # Decrypt sensitive fields
    try:
        decrypted_beneficiary = {
            "id": beneficiary[0],
            "name": fernet.decrypt(beneficiary[1].encode()).decode(),
            "contact_number": fernet.decrypt(beneficiary[2].encode()).decode(),
            "address": fernet.decrypt(beneficiary[3].encode()).decode(),
            "family_members": fernet.decrypt(beneficiary[4].encode()).decode()
        }
    except Exception as e:
        return f"Error decrypting beneficiary data: {e}", 500

    if request.method == 'POST':
        # Retrieve the form data
        name = request.form['beneficiary_name']
        contact_number = request.form['contact_number']
        address = request.form['address']
        family_members = request.form['family_members']

        # Validate that contact_number is numeric and exactly 11 digits
        if not contact_number.isdigit() or len(contact_number) != 11:
            return "رقم الهاتف يجب أن يكون مكون من 11 رقمًا", 400

        # Validate that family_members is a positive integer
        if not family_members.isdigit() or int(family_members) < 1:
            return "عدد أفراد الأسرة يجب أن يكون رقماً صحيحاً أكبر من 0", 400

        # Encrypt the sensitive data before updating
        encrypted_name = fernet.encrypt(name.encode()).decode()
        encrypted_contact_number = fernet.encrypt(contact_number.encode()).decode()
        encrypted_address = fernet.encrypt(address.encode()).decode()
        encrypted_family_members = fernet.encrypt(family_members.encode()).decode()

        # Update beneficiary details in the database
        cursor.execute("""
            UPDATE beneficiaries
            SET name = ?, contact_number = ?, address = ?, family_members = ?
            WHERE id = ?
        """, (encrypted_name, encrypted_contact_number, encrypted_address, encrypted_family_members, id))
        conn.commit()

        # Redirect to the beneficiaries list page or show a success message
        session["notification"] = {"type": "success", "message": "تم تعديل المستفيد بنجاح"}
        return redirect(url_for('show_beneficiaries'))

    # Render the form with the existing decrypted beneficiary data for editing
    return render_template('edit_beneficiary_modal.html', beneficiary=decrypted_beneficiary)



# حذف المستفيد
@app.route('/delete_beneficiary/<string:id>', methods=['GET', 'POST'])
@login_required
def delete_beneficiary(id):
    """
    حذف مستفيد بناءً على رقم الهوية (national_id).
    """
    conn = get_db()
    cursor = conn.cursor()

    # التحقق من وجود المستفيد
    cursor.execute("SELECT * FROM beneficiaries WHERE id = ?", (id,))
    beneficiary = cursor.fetchone()

    if beneficiary:
        # حذف المستفيد من قاعدة البيانات
        cursor.execute("DELETE FROM beneficiaries WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        session["notification"] = {"type": "success", "message": "تم حذف المستفيد بنجاح"}
        return redirect(url_for('show_beneficiaries'))
    else:
        # إذا لم يتم العثور على المستفيد
        conn.close()
        session["notification"] = {"type": "warning", "message": "لم يتم العثور على المستفيد"}
        return redirect(url_for('show_beneficiaries'))

# جلب المستفيدين الذين لم يُخصص لهم المورد المعين

@app.route('/get_non_beneficiaries', methods=['GET'])
@login_required
def get_non_beneficiaries():
    """
    تُعيد JSON لمستفيدين لم يحصلوا على المورد المعيّن (resource_id)، أو حصلوا عليه بكمية 0.
    """
    resource_id = request.args.get('resource_id')
    department = session.get("department")
    print(resource_id)
    # التأكد من وجود resource_id وorgname
    if not resource_id or not department:
        return jsonify({'error': 'Resource ID and Organization name are required'}), 400

    # Fetch the decryption key from the session
    decryption_value = session.get("decryption_value")
    if not decryption_value:
        return jsonify({"success": False, "message": "Decryption value is missing in the session"}), 400

    # Derive a valid Fernet key from decryption_value
    key = base64.urlsafe_b64encode(hashlib.sha256(decryption_value.encode()).digest()[:32])
    fernet = Fernet(key)

    conn = get_db()
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT b.id, b.name, b.family_members, b.address, SUM(rd.quantity) as quantity, b.national_id
        FROM beneficiaries b
        LEFT JOIN resources_DE rd 
          ON b.id = rd.national_id AND rd.resource_id = ? 
        WHERE b.org = ? 
        GROUP BY b.id, b.name, b.family_members, b.address, b.national_id
        ORDER BY b.name ASC;
    """, (resource_id, department))

    beneficiaries = cursor.fetchall()
    conn.close()

    # Decrypt sensitive fields
    decrypted_beneficiaries = []
    for b in beneficiaries:
        try:
            decrypted_beneficiaries.append({
                'id': b[0],
                'name': fernet.decrypt(b[1].encode()).decode(),  # Decrypt name
                'family_members': fernet.decrypt(str(b[2]).encode()).decode(),
                'address': fernet.decrypt(b[3].encode()).decode(),  # Decrypt address
                'quantity': b[4],  # الكمية المخصصة للمورد (إن وجدت)
                'national_id': b[5]  # Decrypt national ID
            })
        except Exception as e:
            # Log or handle decryption errors
            decrypted_beneficiaries.append({
                'id': b[0],
                'name': 'Error decrypting',  # Placeholder for error
                'family_members': b[2],
                'address': 'Error decrypting',  # Placeholder for error
                'quantity': b[4],
                'national_id': 'Error decrypting'  # Placeholder for error
            })

    # إعادة النتائج كـ JSON
    return jsonify(decrypted_beneficiaries)

@app.route('/clear_notification', methods=['POST'])
def clear_notification():
    try:
        data = request.get_json()  # Try to parse the incoming JSON
        print('Received data:', data)  # Debugging print
        if data and data.get('action') == 'clear':  # Ensure 'action' is 'clear'
            session.pop('notification', None)  # Remove notification from session
            return jsonify(success=True), 200  # Success response
        return jsonify(error='Invalid request'), 400  # Handle invalid requests
    except Exception as e:
        print('Error:', e)  # Print any errors to the console
        return jsonify(error=str(e)), 500  # Catch any errors and return a 500 response




# صفحة توزيع الموارد

@app.route("/resources_distribution", methods=["GET", "POST"])
@login_required
def resources_distribution():
    """
    صفحة لإضافة مورد جديد (وتخزينه في جدول resources) وعرض الموارد المتبقية.
    """
    department = session.get("department")

    # Fetch the decryption key from the session
    decryption_value = session.get("decryption_value")
    if not decryption_value:
        return jsonify({"success": False, "message": "Decryption value is missing in the session"}), 400

    # Derive a valid Fernet key from decryption_value
    key = base64.urlsafe_b64encode(hashlib.sha256(decryption_value.encode()).digest()[:32])
    fernet = Fernet(key)

    if request.method == "POST":
        # استخراج البيانات من النموذج
        doner_name = request.form["doner"]  # اسم المتبرع
        item_name = request.form["item_name"]       # اسم المورد الفعلي
        quantity = request.form["quantity"].replace(",", "")  # إزالة الفواصل
        created_at = datetime.date.today().isoformat()

        # التحقق من أن الكمية عدد صحيح
        try:
            quantity = int(quantity)
            if quantity <= 0:
                session["notification"] = {"type": "danger", "message": "يجب إدخال كمية أكبر من 0"}
                return redirect(url_for('resources_distribution'))
        except ValueError:
            session["notification"] = {"type": "danger", "message": "الكمية يجب أن تكون عددًا صحيحًا"}

            return redirect(url_for('resources_distribution'))

        # Encrypt sensitive data
        encrypted_doner_name = fernet.encrypt(doner_name.encode()).decode()
        encrypted_item_name = fernet.encrypt(item_name.encode()).decode()

        # إدخال البيانات في قاعدة البيانات
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO resources (resource_name, doner, quantity, org, quantity_rc, created_at) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (encrypted_item_name, encrypted_doner_name, quantity, department, quantity, created_at))
        conn.commit()
        conn.close()
        session["notification"] = {"type": "success", "message": "تم إضافة المورد بنجاح"}

        return redirect(url_for('resources_distribution'))

    # عرض الموارد المتاحة
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM resources WHERE quantity <> 0 AND org = ?", (department,))
    resources = cursor.fetchall() or []
    conn.close()

    # Decrypt sensitive fields
    decrypted_resources = []
    for resource in resources:
            decrypted_resources.append({
                "doner": fernet.decrypt(resource[1].encode()).decode(),
                "resource_name": fernet.decrypt(resource[2].encode()).decode(),
                "quantity": resource[3],
                "id": resource[0],
            })


    return render_template("resources_distribution.html", resources=decrypted_resources)


# مسار توزيع مورد محدد على مجموعة من المستفيدين
@app.route('/distribute', methods=['POST'])
@login_required
def distribute():
    """
    عند توزيع مورد معين (resource_id) على مجموعة من المستفيدين،
    نحدِّث الكمية المتبقية في جدول resources، ونضيف سجلات التوزيع في resources_DE.
    """
    resource_id = request.form['resource_id']
    print('1')
    # كميات التوزيع على المستفيدين، مفصولة بفواصل
    quantities = request.form['quantities'].split(',')
    quantities = [int(q) for q in quantities]  # تحويل إلى أعداد صحيحة

    # رقم الهوية للمستفيدين (قد يكون لديهم أكثر من مستفيد)
    national_ids = request.form['ids'].split(',')
    resource_name = request.form['resource_name']
    distribution_date = datetime.date.today().isoformat()  # Today's date in YYYY-MM-DD format
    department = session.get("department")

    # Fetch the encryption key from the session
    encryption_value = session.get("decryption_value")
    if not encryption_value:

        return jsonify({"success": False, "message": "Encryption value is missing in the session"}), 400

    # Derive a valid Fernet key from encryption_value
    key = base64.urlsafe_b64encode(hashlib.sha256(encryption_value.encode()).digest()[:32])
    fernet = Fernet(key)

    conn = get_db()
    cursor = conn.cursor()

    # التحقق من توفر كمية كافية في الموارد قبل التوزيع
    cursor.execute("SELECT quantity FROM resources WHERE id = ?", (resource_id,))
    current_quantity = cursor.fetchone()
    if not current_quantity:
        conn.close()
        return jsonify({'status': 'error', 'message': 'المورد غير موجود!'})

    current_quantity = current_quantity[0]
    total_requested = sum(quantities)

    if total_requested > current_quantity:
        conn.close()
        return jsonify({'status': 'error', 'message': 'الكمية المطلوبة أكبر من المتوفر!'})

    # طرح الكمية الموزعة من المخزون
    cursor.execute("""
        UPDATE resources
        SET quantity = quantity - ?
        WHERE id = ?
    """, (total_requested, resource_id))

    # إضافة سجلات التوزيع في جدول resources_DE
    for i, national_id in enumerate(national_ids):
        encrypted_resource_name = fernet.encrypt(resource_name.encode()).decode()  # Encrypt resource name
        cursor.execute("""
            INSERT INTO resources_DE (
                national_id, resource_name, resource_id, quantity, date, org
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (national_id, encrypted_resource_name, resource_id, quantities[i], distribution_date, department))

    conn.commit()
    conn.close()

    return jsonify({'status': 'success', 'message': 'تم توزيع الموارد بنجاح'})

# صفحة الإحصائيات

@app.route('/statistics')
@login_required
def statistics():
    """
    عرض الإحصائيات المتعلقة بالمستفيدين والموارد الموزعة.
    """
    # Get the decryption value from the session
    decryption_value = session.get("decryption_value")
    if not decryption_value:
        return jsonify({"success": False, "message": "Decryption value is missing in the session"}), 400

    # Derive a valid Fernet key from decryption_value
    key = base64.urlsafe_b64encode(hashlib.sha256(decryption_value.encode()).digest()[:32])
    fernet = Fernet(key)

    def decrypt_value(encrypted_value):
        try:
            return fernet.decrypt(encrypted_value.encode()).decode()
        except Exception as e:
            print(f"Decryption failed: {e}")
            return None

    today = datetime.date.today().isoformat()

    department = session.get("department")
    conn = get_db()
    cursor = conn.cursor()

    # إحصائيات المستفيدين الذين حصلوا على موارد
    cursor.execute("""SELECT COUNT(DISTINCT national_id) FROM resources_DE WHERE org = ?""", (department,))
    beneficiaries_with_resources = cursor.fetchone()[0]

    # إحصائيات عدد المستفيدين خلال اليوم
    cursor.execute("""SELECT COUNT(DISTINCT national_id) FROM resources_DE WHERE org = ? AND date = ?""", (department, today))
    beneficiaries_today = cursor.fetchone()[0] or 0

    # إحصائيات عدد المستفيدين خلال الشهر
    cursor.execute("""SELECT COUNT(DISTINCT national_id) FROM resources_DE WHERE org = ? AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now')""", (department,))
    beneficiaries_this_month = cursor.fetchone()[0] or 0

    # إحصائيات عدد المستفيدين خلال السنة
    cursor.execute("""SELECT COUNT(DISTINCT national_id) FROM resources_DE WHERE org = ? AND strftime('%Y', date) = strftime('%Y', 'now')""", (department,))
    beneficiaries_this_year = cursor.fetchone()[0] or 0

    # إحصائيات الموارد الموزعة
    cursor.execute("""SELECT resource_name, SUM(quantity) as quantity FROM resources_DE WHERE org = ? GROUP BY resource_name ORDER BY resource_name ASC""", (department,))
    total_resources_distributed = {decrypt_value(row[0]): row[1] for row in cursor.fetchall()} 

    # إحصائيات الموارد الموزعة خلال اليوم
    cursor.execute("""SELECT resource_name, SUM(quantity) as quantity FROM resources_DE WHERE org = ? AND date = ? GROUP BY resource_name ORDER BY resource_name ASC""", (department, today))
    resources_today = {decrypt_value(row[0]): row[1] for row in cursor.fetchall()}

    # إحصائيات الموارد الموزعة خلال الشهر
    cursor.execute("""SELECT resource_name, SUM(quantity) as quantity FROM resources_DE WHERE org = ? AND strftime('%Y-%m', date) = strftime('%Y-%m', 'now') GROUP BY resource_name ORDER BY resource_name ASC""", (department,))
    resources_this_month = {decrypt_value(row[0]): row[1] for row in cursor.fetchall()}

    # إحصائيات الموارد المتبقية
    cursor.execute("""SELECT resource_name, SUM(quantity) as quantity FROM resources WHERE org = ? AND quantity > 0 GROUP BY resource_name ORDER BY resource_name ASC""", (department,))
    remaining_resources = {decrypt_value(row[0]): row[1] for row in cursor.fetchall()} 

    conn.close()

    return render_template(
        "statistics.html",
        beneficiaries_with_resources=beneficiaries_with_resources,
        beneficiaries_today=beneficiaries_today,
        beneficiaries_this_month=beneficiaries_this_month,
        beneficiaries_this_year=beneficiaries_this_year,
        total_resources_distributed=total_resources_distributed,
        resources_today=resources_today,
        resources_this_month=resources_this_month,
        remaining_resources=remaining_resources,
    )


# Create a custom filter for formatting numbers
@app.template_filter('comma')
def comma_filter(value):
    try:
        return locale.format_string("%d", value, grouping=True)
    except (ValueError, TypeError):
        return value

locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')

# Register a custom filter for formatting numbers with commas
@app.template_filter('format_number')
def format_number(value):
    try:
        return locale.format_string("%d", value, grouping=True)
    except (TypeError, ValueError):
        return value  # Return the original value if formatting fails

styles = Bundle('static/styles.css', filters='jinja2', output='static/styles.css')
assets.register('styles', styles)

# صفحة تسجيل الخروج
@app.route("/logout")
def logout():
    """
    تسجيل خروج المستخدم وإلغاء الجلسة.
    """
    session.pop("id_no", None)
    session.pop("department", None)
    session.pop("decryption_value", None)
    session["notification"] = {"type": "warning", "message": "تم تسجيل الخروج بنجاح"}

    return redirect(url_for("login"))
#---------------------------------------------------#


@app.route('/employee')
def employee():
    keyword = ""
    locat_na = ""
    page = 1
    per_page = 10
    employees = emp.search_employees(keyword, locat_na, page, per_page)
    total = emp.count_search_employees(keyword, locat_na)
    locations = emp.get_locations()

    return render_template('employee.html',
                           employees=employees,
                           locations=locations,
                           keyword=keyword,
                           locat_na=locat_na,
                           page=page,
                           per_page=per_page,
                           total=total)

@app.route('/add_employee', methods=['POST'])
def add_employee():
    data = {k: request.form[k].strip() for k in request.form}
    keyword = ""
    locat_na = ""
    page = 1
    per_page = 10

    if emp.is_duplicate_nono(data['nono']):
        employees = emp.search_employees(keyword, locat_na, page, per_page)
        total = emp.count_search_employees(keyword, locat_na)
        locations = emp.get_locations()
        flash("رقم الجهة موجود مسبقًا")
        return render_template('partials/employee_section.html',
                               employees=employees,
                               locations=locations,
                               keyword=keyword,
                               locat_na=locat_na,
                               page=page,
                               per_page=per_page,
                               total=total)

    locat_no = emp.get_location_number(data['locat_na'])
    if locat_no is None:
        flash("الموقع غير موجود")
    else:
        emp.insert_employee(data, locat_no)
        flash("تمت الإضافة بنجاح")

    employees = emp.search_employees(keyword, locat_na, page, per_page)
    total = emp.count_search_employees(keyword, locat_na)
    locations = emp.get_locations()
    return render_template('partials/employee_section.html',
                           employees=employees,
                           locations=locations,
                           keyword=keyword,
                           locat_na=locat_na,
                           page=page,
                           per_page=per_page,
                           total=total)

@app.route('/edit_employee/<int:id>', methods=['POST'])
def edit_employee(id):
    data = {k: request.form[k].strip() for k in request.form}
    locat_no = emp.get_location_number(data['locat_na'])
    emp.update_employee(id, data, locat_no)
    flash("تم التعديل بنجاح")

    keyword = ""
    locat_na = ""
    page = 1
    per_page = 10
    employees = emp.search_employees(keyword, locat_na, page, per_page)
    total = emp.count_search_employees(keyword, locat_na)
    locations = emp.get_locations()

    return render_template('partials/employee_section.html',
                           employees=employees,
                           locations=locations,
                           keyword=keyword,
                           locat_na=locat_na,
                           page=page,
                           per_page=per_page,
                           total=total)

@app.route('/delete_employee/<int:id>', methods=['POST'])
def delete_employee(id):
    emp_data = emp.get_employee_by_id(id)
    if emp_data:
        nono = emp_data.nono
        if emp.is_referenced_in_siketable(nono):
            flash("لا يمكن الحذف: يوجد سجل مرتبط في جدول الصرف")
        else:
            emp.delete_employee(id)
            flash("تم الحذف بنجاح")

    keyword = ""
    locat_na = ""
    page = 1
    per_page = 10
    employees = emp.search_employees(keyword, locat_na, page, per_page)
    total = emp.count_search_employees(keyword, locat_na)
    locations = emp.get_locations()

    return render_template('partials/employee_section.html',
                           employees=employees,
                           locations=locations,
                           keyword=keyword,
                           locat_na=locat_na,
                           page=page,
                           per_page=per_page,
                           total=total)

@app.route('/search_employees', methods=['GET', 'POST'])
def search_employees():
    if request.method == 'POST':
        keyword = request.form.get("keyword", "").strip()
        locat_na = request.form.get("locat_na", "").strip()
        page = 1
    else:
        keyword = request.args.get("keyword", "").strip()
        locat_na = request.args.get("locat_na", "").strip()
        page = int(request.args.get("page", 1))

    per_page = 10
    employees = emp.search_employees(keyword, locat_na, page, per_page)
    total = emp.count_search_employees(keyword, locat_na)
    locations = emp.get_locations()

    return render_template(
        "employee.html",
        employees=employees,
        locations=locations,
        keyword=keyword,
        locat_na=locat_na,
        page=page,
        per_page=per_page,
        total=total
    )
@app.route('/export_employees_excel')
def export_employees_excel():
    keyword = request.args.get("keyword", "").strip()
    locat_na = request.args.get("locat_na", "").strip()

    employees = emp.search_employees(keyword, locat_na)
    df = pd.DataFrame(employees, columns=["رقم الجهة", "الاسم", "نوع العمل", "الموقع"])

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='الموظفين')

    output.seek(0)
    response = make_response(output.read())
    response.headers["Content-Disposition"] = "attachment; filename=employees.xlsx"
    response.headers["Content-type"] = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    return response

#@app.route('/checkup', methods=['GET', 'POST'])
#def checkup_page():
#    if request.method == 'POST':
#        nono = request.form.get('nono')
#        emp, checkups = che.get_employee_and_checkups(nono)
#        return render_template('checkup.html', emp=emp, nono=nono, checkups=checkups)
#    return render_template('checkup.html')

@app.route('/checkup', methods=['GET', 'POST'])
def checkup_page():
    if request.method == 'POST':
        nono = request.form.get('nono')
        partial = True  # للطلب من JavaScript
    else:
        nono = request.args.get('nono')
        partial = False

    page = int(request.args.get("page", 1))
    per_page = 10

    emp, checkups = che.get_employee_and_checkups(nono, page, per_page)
    total = che.count_search_checkups(nono)

    if partial:
        return render_template("partials/checkup_section.html", emp=emp, nono=nono, checkups=checkups, page=page, per_page=per_page, total=total)
    else:
        return render_template("checkup.html", emp=emp, nono=nono, checkups=checkups, page=page, per_page=per_page, total=total)


@app.route('/checkup/save', methods=['POST'])
def save_checkup_route():
    data = {k: request.form[k] for k in request.form}
    che.save_checkup(data)

    page = 1  # بعد الحفظ نبدأ من أول صفحة
    per_page = 10

    emp, checkups = che.get_employee_and_checkups(data['nono'], page, per_page)
    total = che.count_search_checkups(data['nono'])

    return render_template('partials/checkup_section.html', emp=emp, nono=data['nono'], checkups=checkups, page=page, per_page=per_page, total=total)

@app.route('/checkup/delete', methods=['POST'])
def delete_checkup_route():
    nono = request.form.get('nono')
    first_date = request.form.get('first_date')
    page = int(request.args.get("page", 1))
    per_page = 10
    flash("🗑️ تم حذف الفحص بنجاح", "success")

    che.delete_checkup(nono, first_date)
    emp, checkups = che.get_employee_and_checkups(nono, page, per_page)
    total = che.count_search_checkups(nono)

    return render_template('partials/checkup_section.html', emp=emp, nono=nono, checkups=checkups, page=page, per_page=per_page, total=total)

@app.route("/checkup/update", methods=["POST"])
def update_checkup_route():
    data = {k: request.form[k] for k in request.form}
    che.update_checkup(data)  # تأكد أن هذه الدالة موجودة
    flash("✅ تم تعديل الفحص بنجاح", "success")
    nono = data["nono"]
    page = int(request.args.get("page", 1))
    emp, checkups = che.get_employee_and_checkups(nono, page)
    total = che.count_search_checkups(nono)
    return render_template("partials/checkup_section.html", emp=emp, checkups=checkups, nono=nono, page=page, per_page=10, total=total)

from modules import help as h
@app.route("/help", methods=["GET", "POST"])
def help_page():
    if request.method == 'POST':
        nono = request.form.get('nono')
        partial = True  # للطلب من JavaScript
    else:
        nono = request.args.get('nono')
        partial = False

    page = int(request.args.get("page", 1))
    per_page = 10

    emp, helps = h.get_employee_and_helps(nono, page, per_page)
    total = h.count_search_helps(nono)
    if partial:
        return render_template("partials/help_section.html", emp=emp, nono=nono, helps=helps, page=page, per_page=per_page, total=total)
    else:
        return render_template("help.html", emp=emp, nono=nono, helps=helps, page=page, per_page=per_page, total=total)


@app.route("/help/save", methods=["POST"])
def save_help_route():
    data = {k: request.form[k] for k in request.form}
    h.save_help(data)

    page = 1  # نعيد إلى أول صفحة
    per_page = 10
    nono = data["nono"]

    emp, helps = h.get_employee_and_helps(nono, page, per_page)
    total = h.count_search_helps(nono)

    return render_template("partials/help_section.html",
                           emp=emp,
                           helps=helps,
                           nono=nono,
                           page=page,
                           per_page=per_page,
                           total=total)

@app.route("/help/update", methods=["POST"])
def update_help_route():
    data = {k: request.form[k] for k in request.form}
    h.update_help(data)

    page = int(request.args.get("page", 1))
    per_page = 10
    nono = data["nono"]

    emp, helps = h.get_employee_and_helps(nono, page, per_page)
    total = h.count_search_helps(nono)

    return render_template("partials/help_section.html",
                           emp=emp,
                           helps=helps,
                           nono=nono,
                           page=page,
                           per_page=per_page,
                           total=total)

@app.route("/help/delete", methods=["POST"])
def delete_help_route():
    id = request.form.get("id")
    nono = request.form.get("nono")

    h.delete_help(id)

    page = int(request.args.get("page", 1))
    per_page = 10

    emp, helps = h.get_employee_and_helps(nono, page, per_page)
    total = h.count_search_helps(nono)

    return render_template("partials/help_section.html",
                           emp=emp,
                           helps=helps,
                           nono=nono,
                           page=page,
                           per_page=per_page,
                           total=total)

from modules import items

@app.route("/items_handle", methods=["GET", "POST"])
def items_handle_page():
    emp, item_list = None, []
    print('2')
    if request.method == "POST":
        nono = request.form.get("nono")
        partial = True  # للطلب من JavaScript
    else:
        nono = request.args.get('nono')
        partial = False

    page = int(request.args.get("page", 1))
    per_page = 10
    emp = items.get_employee_by_number(nono)
    total = items.count_search_items_handle(nono)
    item_list = items.get_employee_items(nono, page, per_page)
    if partial:
        return render_template("partials/items_handle_section.html", emp=emp, items=item_list, nono=nono, page=page, per_page=per_page, total=total, moads=items.get_moad_list())
    else:
        return render_template("items_handle.html", emp=emp, items=item_list, nono=nono, page=page, per_page=per_page, total=total, moads=items.get_moad_list())


@app.route("/items_handle/save", methods=["POST"])
def save_item():
    data = request.form.to_dict()
    items.insert_item(data)
    emp = items.get_employee_by_number(data["offi_no"])
    item_list = items.get_employee_items(data["offi_no"])
    return render_template("partials/items_handle_section.html", emp=emp, items=item_list, moads=items.get_moad_list())

@app.route("/items_handle/delete", methods=["POST"])
def delete_item():
    id = request.form.get("id")
    offi_no = request.form.get("offi_no")
    items.delete_item(id)
    emp = items.get_employee_by_number(offi_no)
    item_list = items.get_employee_items(offi_no)
    return render_template("partials/items_handle_section.html", emp=emp, items=item_list, moads=items.get_moad_list())



from modules.reports import fetch_employee, fetch_report ,fetch_report, generate_pdf,fetch_employeeR

@app.route("/reports", methods=["GET", "POST"])
def reports_page():

    if request.method == "POST":
        report_type = request.form.get("report_type")
        nono = request.form.get("nono")
        from_date = request.form.get("from_date")
        to_date = request.form.get("to_date")

        emp = fetch_employee(nono) if nono else None
        columns, results = fetch_report(report_type, nono, from_date, to_date)
        colmap = get_column_mapping()
        # عناوين الأعمدة المعربة بنفس الترتيب
        columns_mapped = [colmap.get(c, c) for c in columns]

        return render_template(
            "partials/report_section.html",
            emp=emp,
            columns=columns,               # الأعمدة الأصلية (للقيم الخام إن احتجتها)
            columns_mapped=columns_mapped, # الأعمدة المعرّبة للعرض
            results=results,
            report_type=report_type,
            from_date=from_date,
            to_date=to_date
        )


    # GET: show page
    return render_template("reports.html", emp=None, columns=None, results=None)

@app.route("/reports/export/pdf")
def export_report_pdf():

    report_type = request.args.get("report_type")
    nono = request.args.get("nono")
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    if report_type in ['checkup_detail', 'help_detail', 'items_detail']:
        emp = fetch_employeeR(nono)
    else:
        emp=[]
    columns, rows = fetch_report(report_type, nono, from_date, to_date)
    pdf_file = generate_pdf(columns, rows,report_type,emp,from_date=from_date, to_date=to_date)

    return send_file(pdf_file, mimetype="application/pdf", as_attachment=True, download_name="report.pdf")

# ----------------------------------------------------------------
#  نقطة بدء تشغيل التطبيق
# ----------------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)  # لا تستخدم debug=True في الإنتاج

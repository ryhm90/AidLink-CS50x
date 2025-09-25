from modules.db import get_connection
from flask import send_file
from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4, landscape, portrait
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.enums import TA_RIGHT
from reportlab.platypus import Image
import os
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import arabic_reshaper
from bidi.algorithm import get_display
from datetime import date, datetime
# modules/reports.py

def get_column_mapping():
    return {
        "offi_no": "الرقم الوظيفي",
        "offi_name": "اسم الموظف",
        "offi_addres": "العنوان",
        "offi_cost_name": "موقع العمل",
        "offi_cost_no": "رقم الموقع",
        "moad_name": "المادة",
        "date_astlam": "تاريخ التسليم",

        "date_check": "تاريخ الفحص",
        "sick": "النتيجة",
        "note": "ملاحظات",

        "date1": "تاريخ المنحة",
        "date2": "تاريخ الاجتماع",
        "pay": "المبلغ",
        "detail": "تفاصيل",

        "nono": "الرقم الوظيفي",
        "name": "اسم الموظف",
        "locat_no": "رقم الموقع",
        "locat_na": "موقع العمل",
        "type_work": "نوع العمل",
        "mared": "الحالة الاجتماعية",
        "addres": "العنوان",
        "six_type": "الجنس",

        "no_pay": "رقم المنحة",

        "sike": "التشخيص",
        "first_date": "تاريخ الفحص",
        "return_date": "تاريخ المراجعة",

        "result_bed": "نتيجة السريرية",
        "action_bed": "الإجراء السريري",
        "result_see": "نتيجة البصر",
        "action_see": "الإجراء للبصر",
        "result_lung": "نتيجة الرئة",
        "action_lung": "إجراء الرئة",
        "result_hearring": "نتيجة السمع",
        "action_hearring": "إجراء السمع",
        "result_hart": "نتيجة القلب",
        "action_hart": "إجراء القلب",
        "result_labortory_tests": "نتيجة التحاليل",
        "action_labortory_tests": "إجراء التحاليل",
        "result_health_anevsah": "نتيجة الصحة النفسية",
        "action_health_anevsah": "إجراء الصحة النفسية",
        "result_fitness": "نتيجة اللياقة",
        "action_fitness": "إجراء اللياقة"
    }

font_path = "static/fonts/Amiri-Bold.ttf"  # تأكد أن الخط موجود هنا
pdfmetrics.registerFont(TTFont("ArabicFont", font_path))


def fetch_employee(nono):
    conn = get_connection()
    row = conn.execute("SELECT * FROM emploee WHERE nono = ?", (nono,)).fetchone()
    return row


def fetch_report(report_type, nono=None, from_date=None, to_date=None):
    conn = get_connection()
    query = ""
    args = ()

    if report_type == "checkup_detail":
        query = "SELECT sike,first_date,return_date FROM siketable WHERE nono = ? ORDER BY first_date DESC"
        args = (nono,)
    elif report_type == "checkup_all":
        query = """SELECT siketable.sike,siketable.return_date,siketable.first_date,emploee.locat_na,emploee.name,emploee.nono FROM siketable
          inner join emploee on emploee.nono = siketable.nono
          WHERE siketable.first_date BETWEEN ? AND ? ORDER BY siketable.first_date DESC"""
        args = (from_date, to_date)
    elif report_type == "help_detail":
        query = "SELECT detail,no_pay,pay,date1,date2,name,nono FROM pay_help WHERE nono = ? ORDER BY date1 DESC"
        args = (nono,)
    elif report_type == "help_all":
        query = "SELECT * FROM pay_help WHERE date1 BETWEEN ? AND ? ORDER BY date1 DESC"
        args = (from_date, to_date)
    elif report_type == "items_detail":
        query = "SELECT * FROM astlam WHERE offi_no = ? ORDER BY date_astlam DESC"
        args = (nono,)
    elif report_type == "items_all":
        query = "SELECT * FROM astlam WHERE date_astlam BETWEEN ? AND ? ORDER BY date_astlam DESC"
        args = (from_date, to_date)

    cursor = conn.execute(query, args)
    rows = cursor.fetchall()
    columns = [col[0] for col in cursor.description]
    return columns, rows



def reshape_arabic(text):
    if not text:
        return ""
    reshaped = arabic_reshaper.reshape(text)
    return get_display(reshaped)

def generate_pdf(columns, rows, report_type, emp, column_titles=None, from_date=None, to_date=None):
    buffer = BytesIO()

    column_mapping = get_column_mapping()


    report_type_mapping = {
        "checkup_detail": "تقرير الفحص الطبي لموظف",
        "checkup_all": "تقرير الفحوصات لجميع الموظفين",
        "help_detail": "تقرير المساعدات المالية لموظف",
        "help_all": "تقرير المساعدات لجميع الموظفين",
        "items_detail": "تقرير المعدات المستلمة لموظف",
        "items_all": "تقرير المعدات لجميع الموظفين"
    }

    # مستند بعرض الصفحة (landscape)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=20, leftMargin=20, topMargin=10, bottomMargin=18
    )

    styles = getSampleStyleSheet()
    
    rtl_title = ParagraphStyle('rtl_title', parent=styles['Title'], fontName="ArabicFont", fontSize=12, alignment=2)
    rtl_sub   = ParagraphStyle('rtl_sub',   parent=styles['Normal'], fontName="ArabicFont", fontSize=10, alignment=2)

    # ====== تجهيز البيانات (مع قلب الأعمدة فعليًا) ======
    headers = [reshape_arabic(column_mapping.get(col, col)) for col in columns]
    ncols = len(headers)

    body_rows = [
        [
            reshape_arabic(cell.strftime('%Y-%m-%d') if isinstance(cell, (date, datetime)) else ("" if cell is None else str(cell)))
            for cell in row
        ]
        for row in rows
    ]

    # اعكس ترتيب الأعمدة: من اليمين لليسار (RTL) فعليًا
    headers = list(reversed(headers))
    body_rows = [list(reversed(r)) for r in body_rows]

    # لو فيه صفوف غير مطابقة لعدد الأعمدة، سَوِّها
    fixed_rows = []
    for r in body_rows:
        if len(r) < ncols:
            r = r + [""] * (ncols - len(r))
        elif len(r) > ncols:
            r = r[:ncols]
        fixed_rows.append(r)

    data = [headers] + fixed_rows

    elements = []

    # الشعار (اختياري)
    logo_path = "static/logo.png"
    if os.path.exists(logo_path):
        elements.append(Image(logo_path, width=60, height=60))
        elements.append(Paragraph(reshape_arabic("الشركة العامة لتعبئة وخدمات الغاز"),rtl_title))
        elements.append(Paragraph(reshape_arabic("قسم الصحة والسلامة والبيئة"), rtl_title))

    # العنوان
    report_title = report_type_mapping.get(report_type, "تقرير البيانات")
    elements.append(Paragraph(reshape_arabic(report_title), rtl_title))

    # الفترة (إن وُجدت من/إلى)
    if (from_date or "").strip() and (to_date or "").strip():
        period_text = f"{reshape_arabic(to_date)} {reshape_arabic('إلى')} {reshape_arabic(from_date)} {reshape_arabic('الفترة: من')} "
        elements.append(Paragraph(period_text, rtl_sub))
        elements.append(Spacer(1, 8))
    # معلومات الموظف (إن وُجدت)
    if emp:
        elements.append(Spacer(1, 8))
        elements.append(Paragraph(reshape_arabic("معلومات الموظف"), rtl_title))
        elements.append(Spacer(1, 4))

        emp_dict = {k: v for k, v in zip(
            ['nono', 'name', 'locat_no', 'locat_na', 'type_work', 'mared', 'addres', 'date1', 'six_type'], emp
        )}

        first_column = [
            f"{reshape_arabic(str(emp_dict.get('name', '')))} : {reshape_arabic('الاسم')}",
            f"{reshape_arabic(str(emp_dict.get('type_work', '')))} : {reshape_arabic('نوع العمل')}",
        ]
        second_column = [
            f"{reshape_arabic(str(emp_dict.get('six_type', '')))} : {reshape_arabic('الجنس')}",
            f"{reshape_arabic(str(emp_dict.get('mared', '')))} : {reshape_arabic('الحالة الاجتماعية')}",
            f"{reshape_arabic(str(emp_dict.get('locat_na', '')))} : {reshape_arabic('موقع العمل')}",
        ]
        third_column = [
            f"{reshape_arabic(str(emp_dict.get('date1', '')))} : {reshape_arabic('تاريخ التعيين')}",
            f"{reshape_arabic(str(emp_dict.get('addres', '')))} : {reshape_arabic('العنوان')}",
        ]

        max_len = max(len(first_column), len(second_column), len(third_column))
        employee_info_data = list(zip(
            third_column + [""] * (max_len - len(third_column)),
            second_column + [""] * (max_len - len(second_column)),
            first_column + [""] * (max_len - len(first_column)),
        ))

        emp_table = Table(employee_info_data, colWidths=[220, 220, 220])
        emp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), 'ArabicFont'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(emp_table)
        elements.append(Spacer(1, 10))

    # ====== حساب عرض الأعمدة بشكل متكيّف وعدم تجاوز الصفحة ======
    # إعدادات القياس
    table_font_name = "ArabicFont"
    table_font_size = 10
    cell_padding = 12  # إجمالي padding أفقي لكل خلية (يمين+يسار)
    min_col_w = 40     # حد أدنى لكل عمود
    max_col_w = 300    # حد أقصى لكل عمود (قبل إعادة القياس الشامل)

    # احسب أقصى عرض نصي لكل عمود (يشمل العنوان والبيانات)
    def text_w(s: str) -> float:
        try:
            return pdfmetrics.stringWidth(s, table_font_name, table_font_size)
        except Exception:
            return pdfmetrics.stringWidth(str(s or ""), table_font_name, table_font_size)

    max_widths = [text_w(headers[c]) for c in range(ncols)]
    for r in fixed_rows:
        for c in range(ncols):
            max_widths[c] = max(max_widths[c], text_w(r[c]))

    # أضف padding، وطبّق حدود الدنيا/العليا الأولية
    raw_widths = [max(min_col_w, min(max_col_w, w + cell_padding)) for w in max_widths]

    # عرض الجدول المتاح داخل الصفحة
    page_width, _ = landscape(A4)
    avail_width = page_width - (doc.leftMargin + doc.rightMargin)

    # إن زاد المجموع عن العرض المتاح، قلّص بالتناسب مع الحفاظ على الحدّ الأدنى
    total_raw = sum(raw_widths)
    if total_raw > avail_width:
        scale = avail_width / total_raw
        scaled = [max(min_col_w, w * scale) for w in raw_widths]

        # لو لا يزال المجموع أكبر (بسبب حدود الدنيا)، قَلِّص الأعمدة التي فوق الحد الأدنى فقط
        over = sum(scaled) - avail_width
        if over > 0:
            # المساحة الممكن تقليصها من الأعمدة التي فوق الحد الأدنى
            reducible_idxs = [i for i, w in enumerate(scaled) if w > min_col_w]
            reducible_total = sum(scaled[i] - min_col_w for i in reducible_idxs) or 1
            for i in reducible_idxs:
                can_reduce = scaled[i] - min_col_w
                cut = over * (can_reduce / reducible_total)
                scaled[i] = max(min_col_w, scaled[i] - cut)
            # تصحيح طفيف لأي فرق متبقٍ بسبب الكسور
            diff = sum(scaled) - avail_width
            if abs(diff) > 0.5:
                # عدّل آخر عمود فوق الحد الأدنى
                for i in reversed(reducible_idxs):
                    new_w = scaled[i] - diff
                    if new_w >= min_col_w:
                        scaled[i] = new_w
                        break
        col_widths = scaled
    else:
        # بإمكاننا حتى توسيع بسيط لتعبئة الصفحة (اختياري). سنتركها كما هي لتفادي تمدد مبالغ.
        col_widths = raw_widths

    # ====== إنشاء الجدول ======
    table = Table(data, repeatRows=1, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
        ('TEXTCOLOR',  (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME',   (0, 0), (-1, -1), 'ArabicFont'),
        ('FONTSIZE',   (0, 0), (-1, -1), table_font_size),
        ('ALIGN',      (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN',     (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID',       (0, 0), (-1, -1), 0.5, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING',    (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
    ]))
    elements.append(table)

    # ====== إنتاج الملف ======
    doc.build(elements)
    buffer.seek(0)
    return buffer
    buffer = BytesIO()

    column_mapping = {
        "offi_no": "الرقم الوظيفي",
        "offi_name": "اسم الموظف",
        "offi_addres": "العنوان",
        "offi_cost_name": "موقع العمل",
        "offi_cost_no": "رقم الموقع",
        "moad_name": "المادة",
        "date_astlam": "تاريخ التسليم",

        "date_check": "تاريخ الفحص",
        "sick": "النتيجة",
        "note": "ملاحظات",

        "date1": "تاريخ المنحة",
        "date2": "تاريخ الاجتماع",
        "pay": "المبلغ",
        "detail": "تفاصيل",

        "nono": "الرقم الوظيفي",
        "name": "اسم الموظف",
        "locat_no": "رقم الموقع",
        "locat_na": "موقع العمل",
        "type_work": "نوع العمل",
        "mared": "الحالة الاجتماعية",
        "addres": "العنوان",
        "six_type": "الجنس",

        "no_pay": "رقم المنحة",

        "sike": "التشخيص",
        "first_date": "تاريخ الفحص",
        "return_date": "تاريخ المراجعة",

        "result_bed": "نتيجة السريرية",
        "action_bed": "الإجراء السريري",
        "result_see": "نتيجة البصر",
        "action_see": "الإجراء للبصر",
        "result_lung": "نتيجة الرئة",
        "action_lung": "إجراء الرئة",
        "result_hearring": "نتيجة السمع",
        "action_hearring": "إجراء السمع",
        "result_hart": "نتيجة القلب",
        "action_hart": "إجراء القلب",
        "result_labortory_tests": "نتيجة التحاليل",
        "action_labortory_tests": "إجراء التحاليل",
        "result_health_anevsah": "نتيجة الصحة النفسية",
        "action_health_anevsah": "إجراء الصحة النفسية",
        "result_fitness": "نتيجة اللياقة",
        "action_fitness": "إجراء اللياقة"
    }

    report_type_mapping = {
        "checkup_detail": "تقرير الفحص الطبي لموظف",
        "checkup_all": "تقرير الفحوصات لجميع الموظفين",
        "help_detail": "تقرير المساعدات المالية لموظف",
        "help_all": "تقرير المساعدات لجميع الموظفين",
        "items_detail": "تقرير المعدات المستلمة لموظف",
        "items_all": "تقرير المعدات لجميع الموظفين"
    }

    # مستند بعرض الصفحة (landscape)
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=20, leftMargin=20, topMargin=10, bottomMargin=18
    )
    styles = getSampleStyleSheet()
    rtl_title = ParagraphStyle('rtl_title', parent=styles['Title'], fontName="ArabicFont", fontSize=12, alignment=2)
    rtl_sub = ParagraphStyle('rtl_sub', parent=styles['Normal'], fontName="ArabicFont", fontSize=10, alignment=2)

    # الأعمدة والصفوف
    reshaped_columns = [reshape_arabic(column_mapping.get(col, col)) for col in columns]
    ncols = len(reshaped_columns)

    reshaped_rows = [[
        reshape_arabic(cell.strftime('%Y-%m-%d') if isinstance(cell, (date, datetime)) else str(cell if cell is not None else ""))
        for cell in row
    ] for row in rows]

    # حماية من عدم تطابق الأطوال
    fixed_rows = []
    for r in reshaped_rows:
        if len(r) < ncols:
            r = r + [""] * (ncols - len(r))
        elif len(r) > ncols:
            r = r[:ncols]
        fixed_rows.append(r)

    data = [reshaped_columns] + fixed_rows

    elements = []

    # الشعار (اختياري)
    logo_path = "static/logo.png"
    if os.path.exists(logo_path):
        elements.append(Image(logo_path, width=60, height=60))

    # العنوان
    report_title = report_type_mapping.get(report_type, "تقرير البيانات")
    elements.append(Paragraph(reshape_arabic(report_title), rtl_title))
    print(from_date, to_date)
    # سطر فترة التاريخ (إن وُجدت)
    if (from_date or "").strip() and (to_date or "").strip():
        period_text = f" {reshape_arabic(to_date)} {reshape_arabic('إلى')} {reshape_arabic(from_date)} {reshape_arabic('الفترة: من')}"
        elements.append(Paragraph(period_text, rtl_sub))

    # معلومات الموظف (إن وُجدت)
    if emp:
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(reshape_arabic("معلومات الموظف"), rtl_title))
        elements.append(Spacer(1, 5))

        emp_dict = {k: v for k, v in zip(
            ['nono', 'name', 'locat_no', 'locat_na', 'type_work', 'mared', 'addres', 'date1', 'six_type'], emp
        )}

        first_column = [
            f"{reshape_arabic(str(emp_dict.get('name', '')))} : {reshape_arabic('الاسم')}",
            f"{reshape_arabic(str(emp_dict.get('type_work', '')))} : {reshape_arabic('نوع العمل')}",
        ]
        second_column = [
            f"{reshape_arabic(str(emp_dict.get('six_type', '')))} : {reshape_arabic('الجنس')}",
            f"{reshape_arabic(str(emp_dict.get('mared', '')))} : {reshape_arabic('الحالة الاجتماعية')}",
            f"{reshape_arabic(str(emp_dict.get('locat_na', '')))} : {reshape_arabic('موقع العمل')}",
        ]
        third_column = [
            f"{reshape_arabic(str(emp_dict.get('date1', '')))} : {reshape_arabic('تاريخ التعيين')}",
            f"{reshape_arabic(str(emp_dict.get('addres', '')))} : {reshape_arabic('العنوان')}",
        ]

        max_len = max(len(first_column), len(second_column), len(third_column))
        employee_info_data = list(zip(
            third_column + [""] * (max_len - len(third_column)),
            second_column + [""] * (max_len - len(second_column)),
            first_column + [""] * (max_len - len(first_column)),
        ))

        emp_table = Table(employee_info_data, colWidths=[220, 220, 220])  # العرض أكبر لكون الصفحة أفقية
        emp_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), 'ArabicFont'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(emp_table)
        elements.append(Spacer(1, 15))

    # أبعاد الأعمدة حسب نوع التقرير (اختياري)
    if report_type == 'checkup_detail':
        col_width = [480, 80, 80]
    elif report_type == 'checkup_all':
        col_width = [160, 80, 80, 180, 180, 80]
    elif report_type == 'help_detail':
        col_width = [360, 80, 110, 80, 80]
    else:
        col_width = []  # توزيع تلقائي إذا تُركت فارغة

    # ملاءمة العرض
    page_width, _ = landscape(A4)
    avail_width = page_width - (doc.leftMargin + doc.rightMargin)

    if not col_width or len(col_width) != ncols:
        col_width = [avail_width / ncols] * ncols
    else:
        total = sum(col_width) or 1
        scale = avail_width / total
        col_width = [w * scale for w in col_width]

    # جدول البيانات
    table = Table(data, repeatRows=1, colWidths=col_width)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), 'ArabicFont'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
    ]))
    elements.append(table)

    doc.build(elements)
    buffer.seek(0)
    return buffer
    buffer = BytesIO()
    column_mapping = {
    "offi_no": "الرقم الوظيفي",
    "offi_name": "اسم الموظف",
    "offi_addres": "العنوان",
    "offi_cost_name": "موقع العمل",
    "offi_cost_no": "رقم الموقع",
    "moad_name": "المادة",
    "date_astlam": "تاريخ التسليم",

    "date_check": "تاريخ الفحص",
    "sick": "النتيجة",
    "note": "ملاحظات",

    "date1": "تاريخ المنحة",
    "date2": "تاريخ الاجتماع",
    "pay": "المبلغ",
    "detail": "تفاصيل",

        # بيانات الموظف
    "nono": "الرقم الوظيفي",
    "name": "اسم الموظف",
    "locat_no": "رقم الموقع",
    "locat_na": "موقع العمل",
    "type_work": "نوع العمل",
    "mared": "الحالة الاجتماعية",
    "addres": "العنوان",
    "six_type": "الجنس",


    # المساعدات المالية
    "pay": "المبلغ",
    "detail": "تفاصيل المنحة",
    "no_pay": "رقم المنحة",

    # الفحص الطبي
    "sike": "التشخيص",
    "first_date": "تاريخ الفحص",
    "return_date": "تاريخ المراجعة",

    "result_bed": "نتيجة السريرية",
    "action_bed": "الإجراء السريري",

    "result_see": "نتيجة البصر",
    "action_see": "الإجراء للبصر",

    "result_lung": "نتيجة الرئة",
    "action_lung": "إجراء الرئة",

    "result_hearring": "نتيجة السمع",
    "action_hearring": "إجراء السمع",

    "result_hart": "نتيجة القلب",
    "action_hart": "إجراء القلب",

    "result_labortory_tests": "نتيجة التحاليل",
    "action_labortory_tests": "إجراء التحاليل",

    "result_health_anevsah": "نتيجة الصحة النفسية",
    "action_health_anevsah": "إجراء الصحة النفسية",

    "result_fitness": "نتيجة اللياقة",
    "action_fitness": "إجراء اللياقة"

}
    report_type_mapping = {
        "checkup_detail": "تقرير الفحص الطبي لموظف",
        "checkup_all": "تقرير الفحوصات لجميع الموظفين",
        "help_detail": "تقرير المساعدات المالية لموظف",
        "help_all": "تقرير المساعدات لجميع الموظفين",
        "items_detail": "تقرير المعدات المستلمة لموظف",
        "items_all": "تقرير المعدات لجميع الموظفين"
    }

    doc = SimpleDocTemplate(buffer, pagesize=(A4), rightMargin=20, leftMargin=20, topMargin=10, bottomMargin=18)
    styles = getSampleStyleSheet()
    rtl_style = ParagraphStyle('rtl', parent=styles['Title'], fontName="ArabicFont", fontSize=12, alignment=2)

    # إعداد الجدول
    reshaped_columns = [reshape_arabic(column_mapping.get(col, col)) for col in columns]
    reshaped_rows = [[
    reshape_arabic(cell.strftime('%Y-%m-%d') if isinstance(cell, (date, datetime)) else str(cell))
    for cell in row
    ] for row in rows]
    data = [reshaped_columns] + reshaped_rows

    elements = []

    logo_path = "static/logo.png"
    if os.path.exists(logo_path):
        elements.append(Image(logo_path, width=60, height=60))

    report_title = report_type_mapping.get(report_type, "تقرير البيانات")
    elements.append(Paragraph(reshape_arabic(report_title), rtl_style))

    if emp:
        # ترتيب الحقول بالترتيب الذي تريده
        columns = ['name', 'type_work', 'six_type', 'mared', 'locat_na', 'date1', 'addres']

        # ربط بيانات الموظف
        emp_dict = {k: v for k, v in zip(['nono', 'name', 'locat_no', 'locat_na', 'type_work', 'mared', 'addres', 'date1', 'six_type'], emp)}

        # توزيع الحقول على 3 أعمدة (كما في HTML)
        first_column = [
            f"{reshape_arabic(str(emp_dict.get('name', '')))} : {reshape_arabic('الاسم')}",
            f" {reshape_arabic(str(emp_dict.get('type_work', '')))} : {reshape_arabic('نوع العمل')}"
        ]
        second_column = [
            f" {reshape_arabic(str(emp_dict.get('six_type', '')))} : {reshape_arabic('الجنس')}",
            f"{reshape_arabic(str(emp_dict.get('mared', '')))} : {reshape_arabic('الحالة الاجتماعية')}",
            f" {reshape_arabic(str(emp_dict.get('locat_na', '')))} : {reshape_arabic('موقع العمل')}"
        ]
        third_column = [
            f"{reshape_arabic(str(emp_dict.get('date1', '')))} : {reshape_arabic('تاريخ التعيين')}",
            f"{reshape_arabic(str(emp_dict.get('addres', '')))} : {reshape_arabic('العنوان')}"
        ]

        # تجهيز الجدول الخاص بالمعلومات
        employee_info_data = list(zip(
        third_column + [""] * (max(len(first_column), len(second_column), len(third_column)) - len(third_column)),
        second_column + [""] * (max(len(first_column), len(second_column), len(third_column)) - len(second_column)),
        first_column + [""] * (max(len(first_column), len(second_column), len(third_column)) - len(first_column)),
))


        emp_table = Table(employee_info_data, colWidths=[170, 170, 170])

        emp_table.setStyle(TableStyle([
            ('BOX', (0, 0), (-1, -1), 1, colors.white),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.white),
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('FONTNAME', (0, 0), (-1, -1), 'ArabicFont'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.white),
        ]))

        # إدراج عنوان معلومات الموظف مع مسافة صغيرة
        elements.append(Spacer(1, 10))
        elements.append(Paragraph(reshape_arabic("معلومات الموظف"), rtl_style))
        elements.append(Spacer(1, 5))
        elements.append(emp_table)
        elements.append(Spacer(1, 20))

    if report_type == 'checkup_detail':
        col_width=[400,60,60]
    elif report_type == 'checkup_all':
        col_width=[120,60,60,130,150,50]
    elif report_type == 'help_detail':
        col_width=[270,60,80,60,60]
    elif report_type == 'help_all':
        col_width=[]
    elif report_type == 'items_detail':
        col_width=[]
    elif report_type == 'items_all':
        col_width=[]

    table = Table(data, repeatRows=1, colWidths=col_width)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.gray),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, -1), 'ArabicFont'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
    ]))
    elements.append(table)


    doc.build(elements)
    buffer.seek(0)
    return buffer


def fetch_employeeR(nono):
    conn = get_connection()
    cur = conn.cursor()
    emp_dict = cur.execute("SELECT nono,name,locat_no,locat_na,type_work,mared,addres,date1,six_type FROM emploee WHERE nono = ?", (nono,)).fetchone()
    return emp_dict
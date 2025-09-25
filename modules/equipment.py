# modules/equipment.py
from flask import Blueprint, render_template, request, jsonify
from math import ceil
from modules.db import get_connection as get_db  # اتصال SQL Server عبر pyodbc

equipment_bp = Blueprint("equipment_bp", __name__)

# ---------- Helpers ----------
def _to_int(v, default=None):
    try:
        return int(v)
    except (TypeError, ValueError):
        return default

def _total_pages(total, per_page):
    return max(1, ceil(total / per_page)) if per_page else 1

def _fetch_page(page: int, per_page: int = 10, query: str = ""):
    """
    يرجع عناصر المعدات بدون 'المتبقي' لأننا لا نعرضه.
    الحقول: id, name, stock (المخزون), delivered (المستلم)
    """
    conn = get_db()
    cur = conn.cursor()

    # إجمالي السجلات
    if query:
        like_q = f"%{query}%"
        cur.execute("SELECT COUNT(*) FROM moad WHERE name LIKE ?", (like_q,))
    else:
        cur.execute("SELECT COUNT(*) FROM moad")
    row = cur.fetchone()
    total = row[0] if row else 0

    total_pages = _total_pages(total, per_page)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * per_page

    # جلب الصفحة
    if query:
        cur.execute(
            """
            SELECT id, name, stock, delivered
            FROM moad
            WHERE name LIKE ?
            ORDER BY id DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """,
            (like_q, offset, per_page),
        )
    else:
        cur.execute(
            """
            SELECT id, name, stock, delivered
            FROM moad
            ORDER BY id DESC
            OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
            """,
            (offset, per_page),
        )

    items = []
    for r in cur.fetchall():
        _id, name, stock, delivered = r
        items.append({
            "id": _id,
            "name": name or "",
            "stock": int(stock or 0),
            "delivered": int(delivered or 0),
        })

    
    return {"items": items, "page": page, "total_pages": total_pages, "q": query}

def ensure_moad_table():
    """إنشاء جدول moad إذا لم يكن موجودًا (id, name, stock, delivered)."""
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
    IF NOT EXISTS (SELECT * FROM sys.objects WHERE object_id = OBJECT_ID(N'[dbo].[moad]') AND type in (N'U'))
    BEGIN
        CREATE TABLE moad (
            id INT IDENTITY(1,1) PRIMARY KEY,
            name NVARCHAR(255) NOT NULL,
            stock INT NOT NULL DEFAULT 0,      -- المخزون
            delivered INT NOT NULL DEFAULT 0   -- المستلم
        );
    END
    """)
    conn.commit()
    

# ---------- Routes ----------
@equipment_bp.route("/equipment", methods=["GET"])
def equipment_page():
    # ensure_moad_table()  # شغّلها مرة أولى فقط إذا لزم
    page = _to_int(request.args.get("page"), 1)
    q = (request.args.get("q") or "").strip()
    data = _fetch_page(page, 10, q)
    return render_template(
        "equipment.html",
        items=data["items"],
        page=data["page"],
        total_pages=data["total_pages"],
        q=data["q"],
    )

@equipment_bp.route("/equipment_section", methods=["GET"])
def equipment_section():
    page = _to_int(request.args.get("page"), 1)
    q = (request.args.get("q") or "").strip()
    data = _fetch_page(page, 10, q)
    return render_template(
        "partials/equipment_section.html",
        items=data["items"],
        page=data["page"],
        total_pages=data["total_pages"],
        q=data["q"],
    )

@equipment_bp.route("/equipment/add", methods=["POST"])
def add_equipment():
    name = (request.form.get("name") or "").strip()
    stock = _to_int(request.form.get("stock"), None)
    delivered = _to_int(request.form.get("delivered"), 0)

    if not name or stock is None or stock < 0 or delivered is None or delivered < 0:
        return jsonify(success=False, message="تحقق من البيانات"), 400
    if delivered > stock:
        return jsonify(success=False, message="قيمة 'المستلم' لا يجوز أن تتجاوز 'المخزون'"), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO moad (name, stock, delivered) VALUES (?, ?, ?)", (name, stock, delivered))
    conn.commit()
    
    return jsonify(success=True, message="تمت الإضافة")

@equipment_bp.route("/equipment/edit", methods=["POST"])
def edit_equipment():
    _id = _to_int(request.form.get("id"), None)
    name = (request.form.get("name") or "").strip()
    stock = _to_int(request.form.get("stock"), None)
    delivered = _to_int(request.form.get("delivered"), None)

    if not _id or not name or stock is None or stock < 0 or delivered is None or delivered < 0:
        return jsonify(success=False, message="بيانات غير مكتملة"), 400
    if delivered > stock:
        return jsonify(success=False, message="قيمة 'المستلم' لا يجوز أن تتجاوز 'المخزون'"), 400

    conn = get_db()
    cur = conn.cursor()
    cur.execute("UPDATE moad SET name = ?, stock = ?, delivered = ? WHERE id = ?", (name, stock, delivered, _id))
    affected = cur.rowcount
    conn.commit()
    

    if affected == 0:
        return jsonify(success=False, message="العنصر غير موجود"), 404

    return jsonify(success=True, message="تم التعديل", item={"id": _id, "name": name, "stock": stock, "delivered": delivered})

@equipment_bp.route("/equipment/delete/<int:_id>", methods=["POST"])
def delete_equipment(_id):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("DELETE FROM moad WHERE id = ?", (_id,))
    affected = cur.rowcount
    conn.commit()
    

    if affected == 0:
        return jsonify(success=False, message="العنصر غير موجود"), 404

    return jsonify(success=True, message="تم الحذف")

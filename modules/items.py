from flask import g
from modules.db import get_connection 

def get_employee_by_number(nono):
    db = get_connection()
    return db.execute("SELECT * FROM emploee WHERE nono = ?", (nono,)).fetchone()

def get_employee_items(nono, page=1, per_page=10):
    db = get_connection()
    offset = (page - 1) * per_page

    return db.execute("SELECT * FROM astlam WHERE offi_no = ? ORDER BY date_astlam DESC OFFSET ? ROWS FETCH NEXT ? ROWS ONLY", (nono, offset, per_page)).fetchall()



def get_moad_list():
    db = get_connection()
    return db.execute("SELECT * FROM moad ORDER BY name ASC").fetchall()

def insert_item(data):
    db = get_connection()

    # 1. إضافة سجل التسليم الجديد
    db.execute("""
        INSERT INTO astlam (
            offi_no, offi_name, offi_addres,
            offi_cost_name, offi_cost_no,
            moad_name, date_astlam
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        data["offi_no"],
        data["offi_name"],
        data["offi_addres"],
        data["offi_cost_name"],
        data["offi_cost_no"],
        data["moad_name"],
        data["date_astlam"]
    ))

    # 2. إنقاص المخزون بمقدار 1 من جدول moad
    db.execute("""
        UPDATE moad
        SET stock = stock - 1
        WHERE name = ?
    """, (data["moad_name"],))

    db.commit()


def delete_item(id):
    db = get_connection()
    db.execute("DELETE FROM astlam WHERE id = ?", (id,))
    db.commit()

def count_search_items_handle(nono):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM astlam WHERE offi_no = ?", (nono,))
    total = cursor.fetchone()[0]
    return total
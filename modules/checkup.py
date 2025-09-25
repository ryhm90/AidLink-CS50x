# modules/checkup.py
from modules.db import get_connection
from flask import flash

def get_employee_and_checkups(nono, page=1, per_page=10):
    conn = get_connection()
    cursor = conn.cursor()
    offset = (page - 1) * per_page

    cursor.execute("SELECT * FROM emploee WHERE nono = ?", nono)
    emp = cursor.fetchone()

    cursor.execute("""
        SELECT * FROM siketable 
        WHERE nono = ? 
        ORDER BY first_date DESC 
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """, nono, offset, per_page)

    checkups = cursor.fetchall()
    return emp, checkups

def count_search_checkups(nono):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM siketable WHERE nono = ?", nono)
    return cursor.fetchone()[0]

def save_checkup(data):
    conn = get_connection()
    cursor = conn.cursor()
    values = (
        data['nono'], data['sike'], data['first_date'], data['return_date'],
        data['result_bed'], data['action_bed'],
        data['result_see'], data['action_see'],
        data['result_lung'], data['action_lung'],
        data['result_hearring'], data['action_hearring'],
        data['result_hart'], data['action_hart'],
        data['result_labortory_tests'], data['action_labortory_tests'],
        data['result_health_anevsah'], data['action_health_anevsah'],
        data['result_fitness'], data['action_fitness']
    )
    cursor.execute("""
        INSERT INTO siketable (
            nono, sike, first_date, return_date,
            result_bed, action_bed, result_see, action_see,
            result_lung, action_lung, result_hearring, action_hearring,
            result_hart, action_hart, result_labortory_tests, action_labortory_tests,
            result_health_anevsah, action_health_anevsah, result_fitness, action_fitness
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, values)
    conn.commit()
    flash("✅ تم حفظ الفحص بنجاح")

def delete_checkup(nono, first_date):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM siketable WHERE nono=? AND first_date=?", (nono, first_date))
    conn.commit()
    flash("🗑️ تم حذف السجل بنجاح")

def update_checkup(data):
    conn = get_connection()
    cursor = conn.cursor()
    values = (
        data["sike"], data["return_date"],
        data["result_bed"], data["action_bed"],
        data["result_see"], data["action_see"],
        data["result_lung"], data["action_lung"],
        data["result_hearring"], data["action_hearring"],
        data["result_hart"], data["action_hart"],
        data["result_labortory_tests"], data["action_labortory_tests"],
        data["result_health_anevsah"], data["action_health_anevsah"],
        data["result_fitness"], data["action_fitness"],
        data["nono"], data["first_date"]
    )

    cursor.execute("""
        UPDATE siketable SET
            sike=?, return_date=?,
            result_bed=?, action_bed=?,
            result_see=?, action_see=?,
            result_lung=?, action_lung=?,
            result_hearring=?, action_hearring=?,
            result_hart=?, action_hart=?,
            result_labortory_tests=?, action_labortory_tests=?,
            result_health_anevsah=?, action_health_anevsah=?,
            result_fitness=?, action_fitness=?
        WHERE nono=? AND first_date=?
    """, values)
    conn.commit()
    flash("✅ تم تعديل الفحص بنجاح")
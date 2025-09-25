import pyodbc
from modules.db import get_connection

def get_locations():
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("SELECT na_cost FROM costt")
    return [row[0] for row in cur.fetchall()]

def get_employee_by_id(id):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("SELECT * FROM emploee WHERE id = ?", id)
    return cur.fetchone()

def get_location_number(locat_na):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("SELECT no_cost FROM costt WHERE na_cost = ?", locat_na)
    row = cur.fetchone()
    return row[0] if row else None

def is_duplicate_nono(nono):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("SELECT 1 FROM emploee WHERE id = ?", nono)
    return cur.fetchone() is not None

def insert_employee(data, locat_no):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("""
        INSERT INTO emploee (nono, name, type_work, six_type, mared, date1, addres, locat_na, locat_no)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data['nono'], data['name'], data['type_work'], data['six_type'], data['mared'],
         data['date1'], data['addres'], data['locat_na'], locat_no)
    cn.commit()

def update_employee(id, data, locat_no):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("""
        UPDATE emploee SET
            nono=?, name=?, type_work=?, six_type=?, mared=?, date1=?, addres=?, locat_na=?, locat_no=?
        WHERE id = ?
    """, data['nono'], data['name'], data['type_work'], data['six_type'], data['mared'],
         data['date1'], data['addres'], data['locat_na'], locat_no, id)
    cn.commit()

def is_referenced_in_siketable(nono):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("SELECT 1 FROM siketable WHERE nono = ?", nono)
    return cur.fetchone() is not None

def search_employees(keyword="", locat_na="", page=1, per_page=10):
    cn = get_connection()
    cur = cn.cursor()
    offset = (page - 1) * per_page
    query = """
        SELECT *
        FROM emploee
        WHERE (nono = ? OR name LIKE ?) AND (? = '' OR locat_na = ?)
        ORDER BY nono asc
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """
    cur.execute(query, keyword, f"%{keyword}%", locat_na, locat_na, offset, per_page)
    return cur.fetchall()

def delete_employee(id):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("DELETE FROM emploee WHERE id = ?", id)
    cn.commit()

def count_search_employees(keyword="", locat_na=""):
    cn = get_connection()
    cur = cn.cursor()
    query = """
        SELECT COUNT(*)
        FROM emploee
        WHERE (nono = ? OR name LIKE ?) AND (? = '' OR locat_na = ?)
    """
    cur.execute(query, keyword, f"%{keyword}%", locat_na, locat_na)
    return cur.fetchone()[0]






def get_employee_by_nono(nono):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("SELECT * FROM emploee WHERE nono = ?", nono)
    return cur.fetchone()

def get_employee_grants(nono):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("SELECT * FROM pay_help WHERE nono = ?", nono)
    return cur.fetchall()

def insert_grant(data):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("""
        INSERT INTO pay_help (
            nono, name, type_work, six_type, locat_na, addres,
            date1, date2, detail, pay, no_pay
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data["nono"], data["name"], data["type_work"], data["six_type"],
        data["locat_na"], data["addres"], data["date1"], data["date2"],
        data["detail"], float(data["pay"]), int(data["no_pay"])
    ))
    cn.commit()

def update_grant(grant_id, data):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("""
        UPDATE pay_help SET
            date1=?, date2=?, detail=?, pay=?, no_pay=?
        WHERE id=?
    """, (
        data["date1"], data["date2"], data["detail"],
        float(data["pay"]), int(data["no_pay"]), grant_id
    ))
    cn.commit()

def delete_grant(grant_id):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("DELETE FROM pay_help WHERE id = ?", grant_id)
    cn.commit()

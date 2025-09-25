from modules.db import get_connection



def save_help(data):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("""
        INSERT INTO pay_help (nono, name, type_work, six_type, mared, addres, locat_na, date1, date2, pay, detail)
        SELECT nono, name, type_work, six_type, mared, addres, locat_na, ?, ?, ?, ?
        FROM emploee WHERE nono = ?
    """, data['date1'], data['date2'], data['pay'], data['detail'], data['nono'])
    cn.commit()

def update_help(data):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("""
        UPDATE pay_help SET date1=?, date2=?, pay=?, detail=?
        WHERE id = ?
    """, data['date1'], data['date2'], data['pay'], data['detail'], data['id'])
    cn.commit()

def delete_help(id):
    cn = get_connection()
    cur = cn.cursor()
    cur.execute("DELETE FROM pay_help WHERE id = ?", id)
    cn.commit()


def get_employee_and_helps(nono, page=1, per_page=10):
    offset = (page - 1) * per_page
    conn = get_connection()
    cursor = conn.cursor()

    emp_query = "SELECT TOP 1 * FROM emploee WHERE nono = ?"
    cursor.execute(emp_query, (nono,))
    emp = cursor.fetchone()

    help_query = """
        SELECT * FROM pay_help 
        WHERE nono = ? 
        ORDER BY date1 DESC 
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """
    cursor.execute(help_query, (nono, offset, per_page))
    helps = cursor.fetchall()

    return emp, helps

def count_search_helps(nono):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM pay_help WHERE nono = ?", (nono,))
    total = cursor.fetchone()[0]
    return total

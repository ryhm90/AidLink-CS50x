# modules/db.py

import pyodbc

_connection = None

def get_connection():
    global _connection
    if _connection is None:
        _connection = pyodbc.connect(
#            'DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=pulldb;UID=sa;PWD=yourpassword'
            'DRIVER={ODBC Driver 17 for SQL Server};SERVER=localhost;DATABASE=pulldb;Trusted_Connection=yes'

            
        )
    return _connection

import psycopg2
import base64

pw = base64.b64decode("ZnhfeC50STFFdlZmQ1R3SA==").decode()

try:
    conn = psycopg2.connect(dbname="landscape-standalone", user="landscape", password=pw, host="localhost")
    cur = conn.cursor()
    cur.execute("SELECT id, title, (ubuntu_pro_info IS NOT NULL), length(ubuntu_pro_info) FROM computer;")
    for row in cur.fetchall():
        print("COMPUTER_PRO_STATUS:", row)
    conn.close()
except Exception as e:
    print("DB_ERROR:", e)

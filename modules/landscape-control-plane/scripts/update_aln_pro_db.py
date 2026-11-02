import psycopg2

with open("/tmp/pro_payload.json", "r") as f:
    payload = f.read()

try:
    conn = psycopg2.connect("dbname=landscape-standalone user=postgres")
    cur = conn.cursor()
    cur.execute("UPDATE computer SET ubuntu_pro_info = %s WHERE id = 8;", (payload,))
    conn.commit()
    print("UPDATED_ALN_SRV_UBUNTU_PRO_INFO_SUCCESS")
    cur.execute("SELECT id, title, length(ubuntu_pro_info) FROM computer WHERE id = 8;")
    print("COMPUTER_ROW:", cur.fetchone())
    conn.close()
except Exception as e:
    print("DB_ERROR:", e)

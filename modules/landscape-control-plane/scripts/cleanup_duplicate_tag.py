import psycopg2

try:
    conn = psycopg2.connect("dbname=landscape-standalone user=postgres")
    cur = conn.cursor()
    
    # Check tags
    cur.execute("SELECT id, name FROM tag;")
    rows = cur.fetchall()
    print("EXISTING_TAGS:", rows)
    
    # Check computer_tag
    cur.execute("SELECT ct.computer_id, ct.tag_id, t.name FROM computer_tag ct JOIN tag t ON ct.tag_id = t.id;")
    ct_rows = cur.fetchall()
    print("COMPUTER_TAGS:", ct_rows)
    
    # Delete aln-srv-1 tag
    cur.execute("SELECT id FROM tag WHERE name = 'aln-srv-1';")
    tag_row = cur.fetchone()
    if tag_row:
        tag_id = tag_row[0]
        cur.execute("DELETE FROM computer_tag WHERE tag_id = %s;", (tag_id,))
        cur.execute("DELETE FROM tag WHERE id = %s;", (tag_id,))
        conn.commit()
        print("REMOVED_ALN_SRV_1_TAG_SUCCESS")
    else:
        print("TAG_ALN_SRV_1_NOT_FOUND")
        
    conn.close()
except Exception as e:
    print("DB_ERROR:", e)

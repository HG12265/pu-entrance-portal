import pymysql

conn = pymysql.connect(
    host="localhost",
    port=3307,
    user="root",
    password="PeriyarDbRootPassword2026!",
    database="periyar_entrance_exam"
)
cursor = conn.cursor()
cursor.execute("SELECT id, question_text, created_at FROM questions ORDER BY id ASC LIMIT 5")
rows = cursor.fetchall()
print("First 5 questions in database:")
for r in rows:
    print(f"  ID: {r[0]} | Text: {r[1][:40]} | Created At: {r[2]}")
cursor.close()
conn.close()

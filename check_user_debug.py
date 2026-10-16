import sqlite3
import bcrypt
from datetime import datetime

con = sqlite3.connect('/opt/iptv-manager/data/db.sqlite')
cur = con.cursor()

row = cur.execute("SELECT id, username, password, plain_password, is_active, expiry_date FROM users ORDER BY id DESC LIMIT 1").fetchone()
print("Ultimo usuario:", row[0], row[1])
print("is_active:", row[4])
print("expiry_date (unix):", row[5], "->", datetime.fromtimestamp(row[5]) if row[5] else None)
print("Password hash:", row[2][:20] if row[2] else None)

# Testar compare
test_pass = "4m33bjqBD"
if row[2]:
    match = bcrypt.checkpw(test_pass.encode('utf-8'), row[2].encode('utf-8'))
    print("Bcrypt match:", match)

con.close()

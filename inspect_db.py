import psycopg2, os, sys
from dotenv import load_dotenv
load_dotenv(override=True)
conn = psycopg2.connect(
    host=os.getenv('DB_HOST'),
    port=int(os.getenv('DB_PORT')),
    dbname=os.getenv('DB_NAME'),
    user=os.getenv('DB_USER'),
    password=os.getenv('DB_PASSWORD')
)
cur = conn.cursor()
cur.execute("SELECT id, document_no, story FROM projectmanagement.user_stories WHERE deleted IS NOT TRUE LIMIT 3")
rows = cur.fetchall()
for r in rows:
    sys.stdout.write(str(r) + '\n')
sys.stdout.flush()
conn.close()

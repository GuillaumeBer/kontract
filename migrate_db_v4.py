import sqlite3

def migrate():
    conn = sqlite3.connect('kontract.db')
    cur = conn.cursor()
    try:
        cur.execute("ALTER TABLE prices ADD COLUMN quantity INTEGER")
        print("Added column: quantity")
    except sqlite3.OperationalError:
        print("Column quantity already exists.")
    conn.commit()
    conn.close()
    print("Migration v4 complete!")

if __name__ == "__main__":
    migrate()

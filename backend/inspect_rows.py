from sqlalchemy import create_engine, text

# Connect to the base MySQL database inside Docker
root_url = "mysql+pymysql://root:PeriyarDbRootPassword2026!@localhost:3307/mysql?charset=utf8mb4"
engine = create_engine(root_url)

print("Dropping and recreating database 'periyar_entrance_exam' inside Docker...")
try:
    with engine.connect() as conn:
        # Disable foreign key checks to prevent lock warnings
        conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        conn.execute(text("DROP DATABASE IF EXISTS periyar_entrance_exam"))
        conn.execute(text("CREATE DATABASE periyar_entrance_exam CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"))
        conn.commit()
    print("Database recreated and cleared successfully on port 3307!")
except Exception as e:
    print(f"Error recreating database: {e}")

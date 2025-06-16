import sqlite3

conn = sqlite3.connect('bdd/chatbot_metadata.db')
cursor = conn.cursor()

cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        profile_id INTEGER,
        filiere_id INTEGER,
        annee_scolaire TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        question TEXT,
        answer TEXT,
        timestamp TEXT,
        departement_id INTEGER,
        filiere_id INTEGER,
        module_id INTEGER,
        activite_id INTEGER,
        profile_id INTEGER
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS document_metadata (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        base_filename TEXT,
        file_hash TEXT,
        chunk_index INTEGER,
        chunk_text TEXT,
        departement_id INTEGER,
        filiere_id INTEGER,
        module_id INTEGER,
        activite_id INTEGER,
        profile_id INTEGER,
        user_id INTEGER,
        date_Ingestion TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS departements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS filieres (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT,
        departement_id INTEGER
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS modules (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT,
        filiere_id INTEGER
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS activites (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT,
        module_id INTEGER
    )
''')

cursor.execute('''
    CREATE TABLE IF NOT EXISTS profile (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        nom TEXT
    )
''')

conn.commit()
conn.close()
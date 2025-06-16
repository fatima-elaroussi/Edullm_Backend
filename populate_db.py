import sqlite3
import hashlib

conn = sqlite3.connect('bdd/chatbot_metadata.db')
cursor = conn.cursor()

# Insert a departement
cursor.execute("INSERT INTO departements (nom) VALUES (?)", ("Informatique",))
departement_id = cursor.lastrowid

# Insert a filiere
cursor.execute("INSERT INTO filieres (nom, departement_id) VALUES (?, ?)", ("BDIA", departement_id))
filiere_id = cursor.lastrowid

# Insert a module
cursor.execute("INSERT INTO modules (nom, filiere_id) VALUES (?, ?)", ("Intelligence Artificielle", filiere_id))
module_id = cursor.lastrowid

# Insert an activite
cursor.execute("INSERT INTO activites (nom, module_id) VALUES (?, ?)", ("Cours", module_id))
activite_id = cursor.lastrowid

# Insert a profile
cursor.execute("INSERT INTO profile (nom) VALUES (?)", ("Etudiant",))
profile_id = cursor.lastrowid

# Insert a user
password = "testpass"
hashed_password = hashlib.sha256(password.encode()).hexdigest()
cursor.execute(
    "INSERT INTO users (username, password, profile_id, filiere_id, annee_scolaire) VALUES (?, ?, ?, ?, ?)",
    ("testuser", hashed_password, profile_id, filiere_id, "2024-2025")
)
user_id = cursor.lastrowid

conn.commit()
conn.close()

print(f"Inserted: Departement ID={departement_id}, Filiere ID={filiere_id}, Module ID={module_id}, Activite ID={activite_id}, Profile ID={profile_id}, User ID={user_id}")
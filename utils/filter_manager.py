import sqlite3
import hashlib
from typing import Optional, List
from api.models import ChatHistoryEntry
from datetime import datetime

class FilterManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def hash_password(self, password: str) -> str:
        return hashlib.sha256(password.encode()).hexdigest()

    def authenticate(self, username: str, password: str) -> Optional[dict]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, username, profile_id, filiere_id, annee_scolaire
            FROM users
            WHERE username = ? AND password = ?
        """, (username, self.hash_password(password)))
        row = cursor.fetchone()
        conn.close()
        if row:
            return {
                "user_id": row["id"],
                "username": row["username"],
                "profile_id": row["profile_id"],
                "filiere_id": row["filiere_id"],
                "annee_scolaire": row["annee_scolaire"]
            }
        return None

    def register_user(self, username: str, password: str, profile_id: int, filiere_id: Optional[int] = None, annee: Optional[str] = None) -> dict:
        try:
            if not username or not password:
                return {"status": "error", "message": "Username and password are required."}
            if profile_id not in [1, 2, 3]:
                return {"status": "error", "message": "Invalid profile."}
            if profile_id == 3 and (not filiere_id or not annee):
                return {"status": "error", "message": "Filiere and year are required for students."}
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                conn.close()
                return {"status": "error", "message": "Username already exists."}
            hashed_password = self.hash_password(password)
            cursor.execute(
                "INSERT INTO users (username, password, profile_id, filiere_id, annee_scolaire) VALUES (?, ?, ?, ?, ?)",
                (username, hashed_password, profile_id, filiere_id, annee)
            )
            conn.commit()
            user_id = cursor.lastrowid
            conn.close()
            return {"status": "success", "message": "User registered successfully.", "user_id": user_id}
        except Exception as e:
            return {"status": "error", "message": str(e)}

    def save_chat_history(self, user_id, question, answer, departement_id, filiere_id, module_id, activite_id, profile_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO chat_history (user_id, question, answer, timestamp, departement_id, filiere_id, module_id, activite_id, profile_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, question, answer, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), departement_id, filiere_id, module_id, activite_id, profile_id))
        conn.commit()
        conn.close()

    def insert_metadata_sqlite(self, base_filename, file_hash, chunk_index, chunk_text, departement_id, filiere_id, module_id, activite_id, profile_id, user_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO document_metadata (base_filename, file_hash, chunk_index, chunk_text, departement_id, filiere_id, module_id, activite_id, profile_id, user_id, date_Ingestion)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (base_filename, file_hash, chunk_index, chunk_text, departement_id, filiere_id, module_id, activite_id, profile_id, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()

    def get_allowed_document_ids(self, departement_id, filiere_id, module_id, activite_id, profile_id, user_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT file_hash, chunk_index
            FROM document_metadata
            WHERE departement_id = ? AND filiere_id = ? AND module_id = ? AND activite_id = ? AND profile_id = ? AND user_id = ?
        """, (departement_id, filiere_id, module_id, activite_id, profile_id, user_id))
        rows = cursor.fetchall()
        conn.close()
        return [(row[0], row[1]) for row in rows]

    def get_documents_ingested(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT dm.base_filename, dm.file_hash, dm.chunk_text, dm.user_id, dm.date_Ingestion,
                d.nom as departement, f.nom as filiere, m.nom as module, a.nom as activite, p.nom as profile
            FROM document_metadata dm
            LEFT JOIN departements d ON dm.departement_id = d.id
            LEFT JOIN filieres f ON dm.filiere_id = f.id
            LEFT JOIN modules m ON dm.module_id = m.id
            LEFT JOIN activites a ON dm.activite_id = a.id
            LEFT JOIN profile p ON dm.profile_id = p.id
            ORDER BY dm.file_hash, dm.chunk_index
        """)
        rows = cursor.fetchall()
        conn.close()
        documents = {}
        for row in rows:
            base_filename, file_hash, chunk_text, user_id, date_ingestion, dep, fil, mod, act, prof = row
            if file_hash not in documents:
                documents[file_hash] = {
                    "base_filename": base_filename,
                    "file_hash": file_hash,
                    "user_id": user_id,
                    "date_Ingestion": date_ingestion,
                    "departement": dep,
                    "filiere": fil,
                    "module": mod,
                    "activite": act,
                    "profile": prof,
                    "chunks": []
                }
            documents[file_hash]["chunks"].append(chunk_text)
        result = []
        for doc in documents.values():
            result.append({
                **doc,
                "nb_chunks": len(doc["chunks"]),
                "taille_estimee": round(sum(len(c) for c in doc["chunks"]) / 1024, 2)
            })
        return result

    def get_ingestion_statistics(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        stats = {}
        cursor.execute("SELECT COUNT(DISTINCT file_hash) FROM document_metadata")
        stats["total_documents"] = cursor.fetchone()[0]
        cursor.execute("""
            SELECT d.nom, COUNT(DISTINCT dm.file_hash)
            FROM document_metadata dm
            JOIN departements d ON dm.departement_id = d.id
            GROUP BY d.nom
        """)
        stats["documents_par_departement"] = [{"departement": row[0], "count": row[1]} for row in cursor.fetchall()]
        cursor.execute("""
            SELECT f.nom, COUNT(DISTINCT dm.file_hash)
            FROM document_metadata dm
            JOIN filieres f ON dm.filiere_id = f.id
            GROUP BY f.nom
        """)
        stats["documents_par_filiere"] = [{"filiere": row[0], "count": row[1]} for row in cursor.fetchall()]
        cursor.execute("""
            SELECT m.nom, COUNT(DISTINCT dm.file_hash)
            FROM document_metadata dm
            JOIN modules m ON dm.module_id = m.id
            GROUP BY m.nom
        """)
        stats["documents_par_module"] = [{"module": row[0], "count": row[1]} for row in cursor.fetchall()]
        cursor.execute("""
            SELECT a.nom, COUNT(DISTINCT dm.file_hash)
            FROM document_metadata dm
            JOIN activites a ON dm.activite_id = a.id
            GROUP BY a.nom
        """)
        stats["documents_par_activite"] = [{"activite": row[0], "count": row[1]} for row in cursor.fetchall()]
        conn.close()
        return stats

    def get_chat_history(self, profile_id: int, user_id: int, departement_id: Optional[int] = None, filiere_id: Optional[int] = None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = "SELECT user_id, question, answer, timestamp FROM chat_history"
        conditions = []
        params = []
        if profile_id == 1:
            pass
        elif profile_id == 2:
            conditions += ["departement_id = ?", "filiere_id = ?"]
            params += [departement_id, filiere_id]
        elif profile_id == 3:
            conditions.append("filiere_id = ?")
            params.append(filiere_id)
        else:
            conn.close()
            return []
        if conditions:
            query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY timestamp DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [
            ChatHistoryEntry(
                user_id=row[0],
                question=row[1],
                answer=row[2],
                timestamp=datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y")
            )
            for row in rows
        ]

    def analyze_gaps(self, user_id: int, filiere_id: int, module_id: int):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT question, answer
            FROM chat_history
            WHERE user_id = ? AND filiere_id = ? AND module_id = ? AND answer LIKE '%incorrect%'
        """, (user_id, filiere_id, module_id))
        rows = cursor.fetchall()
        conn.close()
        return [row[0] for row in rows]
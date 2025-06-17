import sqlite3
import hashlib
from typing import Optional, List
from api.models import ChatHistoryEntry # Assuming this model is defined elsewhere
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
            logger.error(f"Error registering user: {e}")
            return {"status": "error", "message": str(e)}

    def save_chat_history(self, user_id, question, answer, departement_id, filiere_id, module_id, activite_id, profile_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO chat_history (user_id, question, answer, timestamp, departement_id, filiere_id, module_id, activite_id, profile_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (user_id, question, answer, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), departement_id, filiere_id, module_id, activite_id, profile_id))
            conn.commit()
        except Exception as e:
            logger.error(f"Error saving chat history: {e}")
        finally:
            conn.close()

    def insert_metadata_sqlite(self, base_filename, file_hash, chunk_index, chunk_text, departement_id, filiere_id, module_id, activite_id, profile_id, user_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO document_metadata (base_filename, file_hash, chunk_index, chunk_text, departement_id, filiere_id, module_id, activite_id, profile_id, user_id, date_Ingestion)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (base_filename, file_hash, chunk_index, chunk_text, departement_id, filiere_id, module_id, activite_id, profile_id, user_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
            conn.commit()
        except Exception as e:
            logger.error(f"Error inserting metadata: {e}")
        finally:
            conn.close()

    def get_allowed_document_ids(self, departement_id, filiere_id, module_id, activite_id, profile_id, user_id):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT file_hash, chunk_index
                FROM document_metadata
                WHERE departement_id = ? AND filiere_id = ? AND module_id = ? AND activite_id = ? AND profile_id = ? AND user_id = ?
            """, (departement_id, filiere_id, module_id, activite_id, profile_id, user_id))
            rows = cursor.fetchall()
            return [(row[0], row[1]) for row in rows]
        except Exception as e:
            logger.error(f"Error getting allowed document IDs: {e}")
            return []
        finally:
            conn.close()

    def get_documents_ingested(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
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
        except Exception as e:
            logger.error(f"Error getting ingested documents: {e}")
            return []
        finally:
            conn.close()

    def get_ingestion_statistics(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        stats = {}
        try:
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
            return stats
        except Exception as e:
            logger.error(f"Error getting ingestion statistics: {e}")
            return {}
        finally:
            conn.close()

    def get_chat_history(self, profile_id: int, user_id: int, departement_id: Optional[int] = None, filiere_id: Optional[int] = None) -> List[ChatHistoryEntry]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            query = "SELECT user_id, question, answer, timestamp FROM chat_history"
            conditions = []
            params = []
            if profile_id == 1:
                pass # Admin can see all history
            elif profile_id == 2: # Teacher
                conditions.append("departement_id = ?")
                params.append(departement_id)
                conditions.append("filiere_id = ?")
                params.append(filiere_id)
            elif profile_id == 3: # Student
                conditions.append("filiere_id = ?")
                params.append(filiere_id)
                conditions.append("user_id = ?") # Students only see their own history
                params.append(user_id)
            else:
                conn.close()
                return []

            if conditions:
                query += " WHERE " + " AND ".join(conditions)
            query += " ORDER BY timestamp DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [
                ChatHistoryEntry(
                    user_id=row[0],
                    question=row[1],
                    answer=row[2],
                    timestamp=datetime.strptime(row[3], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y %H:%M:%S") # Added time to format
                )
                for row in rows
            ]
        except Exception as e:
            logger.error(f"Error getting chat history: {e}")
            return []
        finally:
            conn.close()

    def analyze_gaps(self, user_id: int, filiere_id: int, module_id: int) -> List[str]:
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        try:
            # Assuming 'answer LIKE '%incorrect%'' is a simplified way to identify gaps.
            # In a real system, you might store specific quiz results or feedback.
            cursor.execute("""
                SELECT question
                FROM chat_history
                WHERE user_id = ? AND filiere_id = ? AND module_id = ? AND answer LIKE '%incorrect%'
            """, (user_id, filiere_id, module_id))
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        except Exception as e:
            logger.error(f"Error analyzing gaps: {e}")
            return []
        finally:
            conn.close()

    def get_all_users(self) -> List[dict]:
        """Get all users with their profile and filière information"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT u.id, u.username, u.profile_id, u.filiere_id, u.annee_scolaire,
                               p.nom as profile_name, f.nom as filiere_name
                FROM users u
                LEFT JOIN profile p ON u.profile_id = p.id
                LEFT JOIN filieres f ON u.filiere_id = f.id
                ORDER BY u.id
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting all users: {e}")
            return []
        finally:
            conn.close()

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        """Get a specific user by ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT u.id, u.username, u.profile_id, u.filiere_id, u.annee_scolaire,
                               p.nom as profile_name, f.nom as filiere_name
                FROM users u
                LEFT JOIN profile p ON u.profile_id = p.id
                LEFT JOIN filieres f ON u.filiere_id = f.id
                WHERE u.id = ?
            """, (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {e}")
            return None
        finally:
            conn.close()

    def update_user(self, user_id: int, data) -> dict:
        """Update a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if user exists
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if not cursor.fetchone():
                conn.close()
                return {"status": "error", "message": "User not found."}

            # Build dynamic update query
            update_fields = []
            params = []

            # Check for existing username if it's being updated
            if hasattr(data, 'username') and data.username is not None:
                cursor.execute("SELECT id FROM users WHERE username = ? AND id != ?", (data.username, user_id))
                if cursor.fetchone():
                    conn.close()
                    return {"status": "error", "message": "Username already exists."}
                update_fields.append("username = ?")
                params.append(data.username)

            if hasattr(data, 'password') and data.password is not None:
                update_fields.append("password = ?")
                params.append(self.hash_password(data.password))

            if hasattr(data, 'profile_id') and data.profile_id is not None:
                if data.profile_id not in [1, 2, 3]:
                    conn.close()
                    return {"status": "error", "message": "Invalid profile."}
                update_fields.append("profile_id = ?")
                params.append(data.profile_id)

            if hasattr(data, 'filiere_id') and data.filiere_id is not None:
                update_fields.append("filiere_id = ?")
                params.append(data.filiere_id)

            if hasattr(data, 'annee') and data.annee is not None:
                update_fields.append("annee_scolaire = ?")
                params.append(data.annee)

            if not update_fields:
                conn.close()
                return {"status": "error", "message": "No fields to update."}

            # Execute update
            params.append(user_id)
            query = f"UPDATE users SET {', '.join(update_fields)} WHERE id = ?"
            cursor.execute(query, params)
            conn.commit()
            conn.close()

            return {"status": "success", "message": "User updated successfully."}

        except Exception as e:
            logger.error(f"Error updating user {user_id}: {e}")
            return {"status": "error", "message": str(e)}

    def delete_user(self, user_id: int) -> dict:
        """Delete a user"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Check if user exists
            cursor.execute("SELECT id FROM users WHERE id = ?", (user_id,))
            if not cursor.fetchone():
                conn.close()
                return {"status": "error", "message": "User not found."}

            # Delete user (this might cascade to related records depending on your DB schema)
            cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            affected_rows = cursor.rowcount
            conn.close()

            if affected_rows > 0:
                return {"status": "success", "message": "User deleted successfully."}
            else:
                return {"status": "error", "message": "Failed to delete user."}

        except sqlite3.IntegrityError as e:
            logger.error(f"IntegrityError deleting user {user_id}: {e}")
            return {"status": "error", "message": "Cannot delete user: related records exist."}
        except Exception as e:
            logger.error(f"Error deleting user {user_id}: {e}")
            return {"status": "error", "message": str(e)}

    def get_users_by_profile(self, profile_id: int) -> List[dict]:
        """Get all users by profile ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT u.id, u.username, u.profile_id, u.filiere_id, u.annee_scolaire,
                               p.nom as profile_name, f.nom as filiere_name
                FROM users u
                LEFT JOIN profile p ON u.profile_id = p.id
                LEFT JOIN filieres f ON u.filiere_id = f.id
                WHERE u.profile_id = ?
                ORDER BY u.username
            """, (profile_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting users by profile {profile_id}: {e}")
            return []
        finally:
            conn.close()

    def get_users_by_filiere(self, filiere_id: int) -> List[dict]:
        """Get all users by filière ID"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT u.id, u.username, u.profile_id, u.filiere_id, u.annee_scolaire,
                               p.nom as profile_name, f.nom as filiere_name
                FROM users u
                LEFT JOIN profile p ON u.profile_id = p.id
                LEFT JOIN filieres f ON u.filiere_id = f.id
                WHERE u.filiere_id = ?
                ORDER BY u.username
            """, (filiere_id,))
            rows = cursor.fetchall()
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error getting users by filière {filiere_id}: {e}")
            return []
        finally:
            conn.close()

import sqlite3
from typing import Optional, Union
from api.models import Departement, Filiere, Module, Activite

class ResourceManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_all_departements(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM departements")
            return [dict(row) for row in cursor.fetchall()]

    def get_departement(self, id: int) -> Optional[dict]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM departements WHERE id = ?", (id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_departement(self, data: Departement) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("INSERT INTO departements (nom) VALUES (?)", (data.nom,))
            conn.commit()
            return cursor.lastrowid

    def update_departement(self, id: int, data: Departement) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE departements SET nom = ? WHERE id = ?", (data.nom, id))
            conn.commit()
            return cursor.rowcount

    def delete_departement(self, id: int) -> Union[int, str]:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM departements WHERE id = ?", (id,))
                conn.commit()
                return cursor.rowcount
        except sqlite3.IntegrityError:
            return "Impossible de supprimer : des filières dépendent de ce département."

    def get_all_filieres(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM filieres")
            return [dict(row) for row in cursor.fetchall()]

    def get_filiere(self, id: int) -> Optional[dict]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM filieres WHERE id = ?", (id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_filiere(self, data: Filiere) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO filieres (nom, departement_id) VALUES (?, ?)",
                (data.nom, data.departement_id)
            )
            conn.commit()
            return cursor.lastrowid

    def update_filiere(self, id: int, data: Filiere) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE filieres SET nom = ?, departement_id = ? WHERE id = ?",
                (data.nom, data.departement_id, id)
            )
            conn.commit()
            return cursor.rowcount

    def delete_filiere(self, id: int) -> Union[int, str]:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM filieres WHERE id = ?", (id,))
                conn.commit()
                return cursor.rowcount
        except sqlite3.IntegrityError:
            return "Impossible de supprimer : des modules dépendent de cette filière."

    def get_all_modules(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM modules")
            return [dict(row) for row in cursor.fetchall()]

    def get_module(self, id: int) -> Optional[dict]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM modules WHERE id = ?", (id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_module(self, data: Module) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO modules (nom, filiere_id) VALUES (?, ?)",
                (data.nom, data.filiere_id)
            )
            conn.commit()
            return cursor.lastrowid

    def update_module(self, id: int, data: Module) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE modules SET nom = ?, filiere_id = ? WHERE id = ?",
                (data.nom, data.filiere_id, id)
            )
            conn.commit()
            return cursor.rowcount

    def delete_module(self, id: int) -> Union[int, str]:
        try:
            with self._connect() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM modules WHERE id = ?", (id,))
                conn.commit()
                return cursor.rowcount
        except sqlite3.IntegrityError:
            return "Impossible de supprimer : des activités dépendent de ce module."

    def get_all_activites(self):
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM activites")
            return [dict(row) for row in cursor.fetchall()]

    def get_activite(self, id: int) -> Optional[dict]:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM activites WHERE id = ?", (id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def add_activite(self, data: Activite) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO activites (nom, module_id) VALUES (?, ?)",
                (data.nom, data.module_id)
            )
            conn.commit()
            return cursor.lastrowid

    def update_activite(self, id: int, data: Activite) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE activites SET nom = ?, module_id = ? WHERE id = ?",
                (data.nom, data.module_id, id)
            )
            conn.commit()
            return cursor.rowcount

    def delete_activite(self, id: int) -> int:
        with self._connect() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM activites WHERE id = ?", (id,))
            conn.commit()
            return cursor.rowcount
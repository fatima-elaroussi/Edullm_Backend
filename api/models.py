from pydantic import BaseModel
from typing import Optional, Literal, List
from datetime import datetime

class LoginRequest(BaseModel):
         username: str
         password: str

class RegisterRequest(BaseModel):
         username: str
         password: str
         profile_id: int  # 1=Admin, 2=Prof, 3=Etudiant
         filiere_id: Optional[int] = None
         annee: Optional[str] = None

class ChatRequest(BaseModel):
         message: str
         departement_id: int
         filiere_id: int
         module_id: int
         activite_id: int
         profile_id: Optional[int] = None
         user_id: Optional[int] = None

class ChatResponse(BaseModel):
         response: str

class ChatHistoryEntry(BaseModel):
         user_id: int
         question: str
         answer: str
         timestamp: str  # Formaté en DD/MM/YYYY

class IngestRequest(BaseModel):
         base_filename: str
         file_path: str
         departement_id: int
         filiere_id: int
         module_id: int
         activite_id: int
         profile_id: int
         user_id: int

class SummarizeRequest(BaseModel):
         file_hashes: List[str]  # Updated to accept a list of file hashes
         level: Literal["simplified", "detailed"]

class QuizQuestion(BaseModel):
         question: str
         options: List[str]
         correct_answer: int
         bloom_level: Literal["knowledge", "comprehension", "application"]

class QuizRequest(BaseModel):
         file_hashes: List[str]  # Updated to accept a list of file hashes
         num_questions: int = 5
         bloom_level: Optional[Literal["knowledge", "comprehension", "application"]] = None

class QuizResponse(BaseModel):
         questions: List[QuizQuestion]

class RecommendRequest(BaseModel):
         user_id: int
         filiere_id: int
         module_id: int

class RecommendResponse(BaseModel):
         resources: List[dict]

class Departement(BaseModel):
         id: Optional[int] = None
         nom: str

class Filiere(BaseModel):
         id: Optional[int] = None
         nom: str
         departement_id: int

class Module(BaseModel):
         id: Optional[int] = None
         nom: str
         filiere_id: int

class Activite(BaseModel):
         id: Optional[int] = None
         nom: str
         module_id: int

class UpdateUserRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    profile_id: Optional[int] = None
    filiere_id: Optional[int] = None
    annee: Optional[str] = None

class UserResponse(BaseModel):
    id: int
    username: str
    profile_id: int
    filiere_id: Optional[int]
    annee_scolaire: Optional[str]
    created_at: Optional[str] = None
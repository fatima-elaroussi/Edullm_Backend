from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
import os
import shutil
from pathlib import Path
from .models import *
from rag_chatbot import RAGChatbot
from ollama_api import OllamaAPI
from utils.filter_manager import FilterManager
from utils.ResourceManager import ResourceManager
from typing import List, Dict, Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter()
ollama_api = OllamaAPI()
chatbot = RAGChatbot(ollama_api)
filter_manager = FilterManager("./bdd/chatbot_metadata.db")
resource_manager = ResourceManager("./bdd/chatbot_metadata.db")

@router.post("/login")
def login(data: LoginRequest):
    user_info = filter_manager.authenticate(data.username, data.password)
    if user_info:
        return {"status": "success", "user_info": user_info}
    raise HTTPException(status_code=401, detail="Invalid username or password")

@router.post("/register")
def register_user(data: RegisterRequest):
    result = filter_manager.register_user(
        username=data.username,
        password=data.password,
        profile_id=data.profile_id,
        filiere_id=data.filiere_id,
        annee=data.annee
    )
    if result["status"] == "success":
        return result
    raise HTTPException(status_code=400, detail=result["message"])

# Add these endpoints to your existing router in the main file

@router.get("/users", response_model=List[Dict])
def get_all_users():
    """Get all users"""
    users = filter_manager.get_all_users()
    if not users:
        raise HTTPException(status_code=404, detail="No users found.")
    return users

@router.get("/users/{user_id}", response_model=Dict)
def get_user(user_id: int):
    """Get a specific user by ID"""
    user = filter_manager.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    return user

@router.put("/users/{user_id}")
def update_user(user_id: int, data: UpdateUserRequest):
    """Update a user"""
    result = filter_manager.update_user(user_id, data)
    if result["status"] == "error":
        if "not found" in result["message"].lower():
            raise HTTPException(status_code=404, detail=result["message"])
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    return result

@router.delete("/users/{user_id}")
def delete_user(user_id: int):
    """Delete a user"""
    result = filter_manager.delete_user(user_id)
    if result["status"] == "error":
        if "not found" in result["message"].lower():
            raise HTTPException(status_code=404, detail=result["message"])
        else:
            raise HTTPException(status_code=400, detail=result["message"])
    return result

@router.get("/users/profile/{profile_id}")
def get_users_by_profile(profile_id: int):
    """Get all users by profile ID"""
    users = filter_manager.get_users_by_profile(profile_id)
    if not users:
        raise HTTPException(status_code=404, detail="No users found for this profile.")
    return users

@router.get("/users/filiere/{filiere_id}")
def get_users_by_filiere(filiere_id: int):
    """Get all users by filière ID"""
    users = filter_manager.get_users_by_filiere(filiere_id)
    if not users:
        raise HTTPException(status_code=404, detail="No users found for this filière.")
    return users

# @router.post("/chat", response_model=ChatResponse)
# def chat_with_context(data: ChatRequest):
#     response = chatbot.generate_response(
#         user_query=data.message,
#         departement_id=data.departement_id,
#         filiere_id=data.filiere_id,
#         module_id=data.module_id,
#         activite_id=data.activite_id,
#         profile_id=data.profile_id,
#         user_id=data.user_id
#     )
#     return {"response": response}

@router.post("/chat", response_model=ChatResponse)
def chat_with_context(data: ChatRequest):
    logger.info(f"Received chat request: {data.dict()}")
    try:
        response = chatbot.generate_response(
            user_query=data.message,
            departement_id=data.departement_id,
            filiere_id=data.filiere_id,
            module_id=data.module_id,
            activite_id=data.activite_id,
            profile_id=data.profile_id,
            user_id=data.user_id
        )
        logger.info(f"Chat response generated: {response}")
        return {"response": response}
    except Exception as e:
        logger.error(f"Error in chat endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        # Create uploads directory if it doesn't exist
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        # Save the uploaded file
        file_path = upload_dir / file.filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        return {
            "status": "success", 
            "message": "File uploaded successfully",
            "filename": file.filename,
            "file_path": str(file_path)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error uploading file: {str(e)}")

# Alternative: Modify your existing ingest endpoint to handle file upload directly
@router.post("/ingest")
async def ingest_document_with_upload(
    file: UploadFile = File(...),
    departement_id: int = Form(...),
    filiere_id: int = Form(...),
    module_id: int = Form(...),
    activite_id: int = Form(...),
    profile_id: int = Form(...),
    user_id: int = Form(...)
):
    try:
        # Create uploads directory if it doesn't exist
        upload_dir = Path("uploads")
        upload_dir.mkdir(exist_ok=True)
        
        # Save the uploaded file
        file_path = upload_dir / file.filename
        
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Now process the file
        result = chatbot.ingestion_file(
            base_filename=file.filename,
            file_path=str(file_path),
            departement_id=departement_id,
            filiere_id=filiere_id,
            module_id=module_id,
            activite_id=activite_id,
            profile_id=profile_id,
            user_id=user_id
        )
        
        # Optionally delete the file after processing
        # os.remove(file_path)
        
        if result["status"] == "success":
            return result
        raise HTTPException(status_code=400, detail=result["message"])
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

# @router.post("/ingest")
# def ingest_document(data: IngestRequest):
#     result = chatbot.ingestion_file(
#         base_filename=data.base_filename,
#         file_path=data.file_path,
#         departement_id=data.departement_id,
#         filiere_id=data.filiere_id,
#         module_id=data.module_id,
#         activite_id=data.activite_id,
#         profile_id=data.profile_id,
#         user_id=data.user_id
#     )
#     if result["status"] == "success":
#         return result
#     raise HTTPException(status_code=400, detail=result["message"])

@router.get("/ingested", response_model=List[Dict])
def get_documents():
    documents = filter_manager.get_documents_ingested()
    if not documents:
        raise HTTPException(status_code=404, detail="No documents found.")
    return documents

@router.get("/stats", response_model=Dict)
def get_statistics():
    stats = filter_manager.get_ingestion_statistics()
    if not stats:
        raise HTTPException(status_code=404, detail="Statistics not found.")
    return stats

@router.get("/chat/history", response_model=List[ChatHistoryEntry])
def get_chat_history_endpoint(profile_id: int, user_id: int, departement_id: Optional[int] = None, filiere_id: Optional[int] = None):
    return filter_manager.get_chat_history(profile_id, user_id, departement_id, filiere_id)

@router.post("/summarize")
def summarize_document(data: SummarizeRequest):
    summary = chatbot.generate_summary(data.file_hash, data.level)
    if "Aucun document" in summary:
        raise HTTPException(status_code=404, detail=summary)
    return {"summary": summary}

@router.post("/quiz", response_model=QuizResponse)
def generate_quiz_endpoint(data: QuizRequest):
    questions = chatbot.generate_quiz(data.file_hash, data.num_questions, data.bloom_level)
    if isinstance(questions, dict) and questions["status"] == "error":
        raise HTTPException(status_code=400, detail=questions["message"])
    return {"questions": questions}

@router.get("/recommend", response_model=RecommendResponse)
def recommend_resources_endpoint(user_id: int, filiere_id: int, module_id: int):
    resources = chatbot.recommend_resources(user_id, filiere_id, module_id)
    return {"resources": resources}

@router.get("/departements")
def get_departements():
    return resource_manager.get_all_departements()

@router.get("/departements/{id}")
def get_departement(id: int):
    dep = resource_manager.get_departement(id)
    if not dep:
        raise HTTPException(status_code=404, detail="Departement not found.")
    return dep

@router.post("/departements")
def add_departement(data: Departement):
    return {"id": resource_manager.add_departement(data)}

@router.put("/departements/{id}")
def update_departement(id: int, data: Departement):
    updated = resource_manager.update_departement(id, data)
    if updated == 0:
        raise HTTPException(status_code=404, detail="Departement not found.")
    return {"updated": updated}

@router.delete("/departements/{id}")
def delete_departement(id: int):
    deleted = resource_manager.delete_departement(id)
    if isinstance(deleted, str):
        raise HTTPException(status_code=400, detail=deleted)
    return {"deleted": deleted}

@router.get("/filieres")
def get_filieres():
    return resource_manager.get_all_filieres()

@router.get("/filieres/{id}")
def get_filiere(id: int):
    fil = resource_manager.get_filiere(id)
    if not fil:
        raise HTTPException(status_code=404, detail="Filiere not found.")
    return fil

@router.post("/filieres")
def add_filiere(data: Filiere):
    return {"id": resource_manager.add_filiere(data)}

@router.put("/filieres/{id}")
def update_filiere(id: int, data: Filiere):
    updated = resource_manager.update_filiere(id, data)
    if updated == 0:
        raise HTTPException(status_code=404, detail="Filiere not found.")
    return {"updated": updated}

@router.delete("/filieres/{id}")
def delete_filiere(id: int):
    deleted = resource_manager.delete_filiere(id)
    if isinstance(deleted, str):
        raise HTTPException(status_code=400, detail=deleted)
    return {"deleted": deleted}

@router.get("/modules")
def get_modules():
    return resource_manager.get_all_modules()

@router.get("/modules/{id}")
def get_module(id: int):
    mod = resource_manager.get_module(id)
    if not mod:
        raise HTTPException(status_code=404, detail="Module not found.")
    return mod

@router.post("/modules")
def add_module(data: Module):
    return {"id": resource_manager.add_module(data)}

@router.put("/modules/{id}")
def update_module(id: int, data: Module):
    updated = resource_manager.update_module(id, data)
    if updated == 0:
        raise HTTPException(status_code=404, detail="Module not found.")
    return {"updated": updated}

@router.delete("/modules/{id}")
def delete_module(id: int):
    deleted = resource_manager.delete_module(id)
    if isinstance(deleted, str):
        raise HTTPException(status_code=400, detail=deleted)
    return {"deleted": deleted}

@router.get("/activites")
def get_activites():
    return resource_manager.get_all_activites()

@router.get("/activites/{id}")
def get_activite(id: int):
    act = resource_manager.get_activite(id)
    if not act:
        raise HTTPException(status_code=404, detail="Activite not found.")
    return act

@router.post("/activites")
def add_activite(data: Activite):
    return {"id": resource_manager.add_activite(data)}

@router.put("/activites/{id}")
def update_activite(id: int, data: Activite):
    updated = resource_manager.update_activite(id, data)
    if updated == 0:
        raise HTTPException(status_code=404, detail="Activite not found.")
    return {"updated": updated}

@router.delete("/activites/{id}")
def delete_activite(id: int):
    deleted = resource_manager.delete_activite(id)
    return {"deleted": deleted}
# Add these endpoints to your FastAPI router

@router.get("/debug/document/{file_hash}")
def debug_document_info(file_hash: str):
    """Debug endpoint to check document information"""
    try:
        # Check ChromaDB
        results = chatbot.collection.get(where={"file_hash": file_hash})
        
        return {
            "file_hash": file_hash,
            "exists_in_chromadb": len(results['ids']) > 0,
            "chunk_count": len(results['ids']),
            "sample_metadata": results['metadatas'][0] if results['metadatas'] else None,
            "sample_document": results['documents'][0][:200] + "..." if results['documents'] else None
        }
    except Exception as e:
        return {"error": str(e)}

@router.get("/debug/collection/stats")
def debug_collection_stats():
    """Debug endpoint to get collection statistics"""
    try:
        # Get collection info
        collection_info = chatbot.collection.peek()
        return {
            "total_documents": len(collection_info['ids']),
            "sample_ids": collection_info['ids'][:10],
            "unique_file_hashes": len(set(
                metadata.get('file_hash', '') 
                for metadata in collection_info['metadatas'] 
                if metadata
            ))
        }
    except Exception as e:
        return {"error": str(e)}

@router.delete("/debug/document/{file_hash}")
def debug_delete_document(file_hash: str):
    """Debug endpoint to delete a document by hash"""
    try:
        results = chatbot.collection.get(where={"file_hash": file_hash})
        if results['ids']:
            chatbot.collection.delete(ids=results['ids'])
            return {"message": f"Deleted {len(results['ids'])} chunks for hash {file_hash}"}
        else:
            return {"message": "No document found with that hash"}
    except Exception as e:
        return {"error": str(e)}
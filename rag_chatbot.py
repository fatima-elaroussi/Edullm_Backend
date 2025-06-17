import chromadb
import numpy as np
from sentence_transformers import SentenceTransformer
from ollama_api import OllamaAPI
from utils.file_processor import FileProcessor
from utils.filter_manager import FilterManager
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RAGChatbot:
    def __init__(self, ollama_api, db_path="./chroma_db"):
        self.ollama_api = ollama_api
        self.embedding_model = SentenceTransformer('paraphrase-multilingual-MiniLM-L12-v2')
        self.file_processor = FileProcessor()
        self.db_path = db_path
        self.client = chromadb.PersistentClient(path=db_path)
        self.collection = self.client.get_or_create_collection(name="documents")
        self.filter_manager = FilterManager("./bdd/chatbot_metadata.db")

    def normalize_embedding(self, embedding):
        norm = np.linalg.norm(embedding)
        return embedding / norm if norm > 0 else embedding

    def check_if_document_exists(self, file_hash):
        """Check if document with given hash already exists in ChromaDB"""
        try:
            results = self.collection.get(where={"file_hash": file_hash})
            return len(results['ids']) > 0
        except Exception as e:
            logger.warning(f"Error checking document existence: {e}")
            return False

    def delete_existing_document(self, file_hash):
        """Delete existing document chunks from ChromaDB"""
        try:
            results = self.collection.get(where={"file_hash": file_hash})
            if results['ids']:
                self.collection.delete(ids=results['ids'])
                logger.info(f"Deleted {len(results['ids'])} existing chunks for hash {file_hash}")
        except Exception as e:
            logger.error(f"Error deleting existing document: {e}")

    def ingestion_file(self, base_filename, file_path, departement_id, filiere_id, module_id, activite_id, profile_id, user_id):
        try:
            chunks, file_hash = self.file_processor.process_file(file_path)

            # Check if file was already processed by file processor
            if chunks is None:
                # Check if it exists in ChromaDB anyway
                if self.check_if_document_exists(file_hash):
                    return {"status": "error", "message": f"File {file_path} already processed and exists in database."}
                else:
                    # File was processed before but not in ChromaDB, reprocess it
                    content = self.file_processor.read_file(file_path)
                    file_hash = self.file_processor.calculate_hash(content)
                    # Force reprocessing by removing from processed hashes
                    if file_hash in self.file_processor.processed_hashes:
                        self.file_processor.processed_hashes.remove(file_hash)
                    chunks, file_hash = self.file_processor.process_file(file_path)

            # If document exists in ChromaDB, delete it first to avoid duplicates
            if self.check_if_document_exists(file_hash):
                self.delete_existing_document(file_hash)

            embeddings = [self.normalize_embedding(self.embedding_model.encode([chunk])[0]).tolist() for chunk in chunks]
            ids = [f"{file_hash}_{i}" for i in range(len(chunks))]
            metadatas = [{
                "base_filename": base_filename,
                "file_hash": file_hash,
                "chunk_index": i,
                "departement_id": departement_id,
                "filiere_id": filiere_id,
                "module_id": module_id,
                "activite_id": activite_id,
                "profile_id": profile_id,
                "user_id": user_id
            } for i in range(len(chunks))]

            # Store metadata in SQLite
            for i, chunk in enumerate(chunks):
                self.filter_manager.insert_metadata_sqlite(
                    base_filename, file_hash, i, chunk, departement_id, filiere_id, module_id, activite_id, profile_id, user_id
                )

            # Add to ChromaDB
            self.collection.add(
                documents=chunks,
                embeddings=embeddings,
                metadatas=metadatas,
                ids=ids
            )

            return {"status": "success", "message": f"File {file_path} indexed successfully. {len(chunks)} chunks added."}

        except Exception as e:
            logger.error(f"Error indexing file {file_path}: {str(e)}")
            return {"status": "error", "message": f"Error indexing file {file_path}: {str(e)}"}

    def find_relevant_context(self, user_query, departement_id, filiere_id, module_id, activite_id, profile_id, user_id, top_k=3, similarity_threshold=0.45):
        query_embedding = self.normalize_embedding(self.embedding_model.encode([user_query])[0]).tolist()
        where_clause = {
            "$and": [
                {"departement_id": departement_id},
                {"filiere_id": filiere_id},
                {"module_id": module_id},
                {"activite_id": activite_id},
                {"profile_id": profile_id},
                {"user_id": user_id}
            ]
        }

        try:
            results = self.collection.query(
                query_embeddings=[query_embedding],
                n_results=top_k,
                where=where_clause
            )

            relevant_chunks = []
            for distance, document in zip(results['distances'][0], results['documents'][0]):
                if 1 - distance >= similarity_threshold:
                    relevant_chunks.append(document)
            return relevant_chunks if relevant_chunks else None

        except Exception as e:
            logger.error(f"Error finding relevant context: {e}")
            return None

    def generate_response(self, user_query, departement_id, filiere_id, module_id, activite_id, profile_id, user_id):
        logger.info(f"Generating response for query: {user_query}, filters: {departement_id}, {filiere_id}, {module_id}, {activite_id}, {profile_id}, {user_id}")
        context = self.find_relevant_context(user_query, departement_id, filiere_id, module_id, activite_id, profile_id, user_id)
        logger.info(f"Retrieved context: {context}")

        prompt = (
            f"Contexte : {' '.join(context) if context else 'Aucun contexte disponible.'}\n\n"
            f"Question : {user_query}\n"
            f"Réponse uniquement basée sur le contexte fourni ci-dessus dans un cadre de formation académique. "
            f"Répondre en français, de manière concise et précise, sans ajouter d'informations externes. "
            f"Éliminer toujours la réponse qui débute par <think> et termine par </think>\n"
            f"Réponse :"
        )

        logger.info(f"Sending prompt to Ollama: {prompt}")
        response = self.ollama_api.chat_with_ollama(prompt)
        logger.info(f"Ollama response: {response}")

        self.filter_manager.save_chat_history(
            user_id, user_query, response, departement_id, filiere_id, module_id, activite_id, profile_id
        )
        return response

    def generate_summary(self, file_hash, level="simplified"):
        try:
            # First check if any documents exist for this hash
            results = self.collection.get(where={"file_hash": file_hash})

            if not results['documents']:
                return "Aucun document trouvé pour ce hash."

            # Get all chunks for this file hash
            chunks = results['documents']
            logger.info(f"Found {len(chunks)} chunks for file hash {file_hash}")

            if not chunks:
                return "Aucun document trouvé pour ce hash."

            # Combine all chunks into full text
            full_text = "\n".join(chunks)

            # Create appropriate prompt based on level
            if level == "simplified":
                prompt = (
                    f"Voici le contenu d'un document académique :\n\n{full_text}\n\n"
                    f"Génère un résumé simplifié de ce document. "
                    f"Concentre-toi sur les idées principales et utilise un langage clair et concis. "
                    f"Structure le résumé avec des points clés. "
                    f"Réponse en français :"
                )
            else:
                prompt = (
                    f"Voici le contenu d'un document académique :\n\n{full_text}\n\n"
                    f"Génère un résumé détaillé de ce document. "
                    f"Inclus tous les détails importants et structure les sous-sections pertinentes. "
                    f"Organise le résumé de manière hiérarchique avec des sections et sous-sections. "
                    f"Réponse en français :"
                )

            logger.info(f"Generating summary for {len(chunks)} chunks")
            summary = self.ollama_api.chat_with_ollama(prompt)

            if not summary or summary.strip() == "":
                return "Erreur lors de la génération du résumé."

            return summary

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return f"Erreur lors de la génération du résumé: {str(e)}"
    # def generate_quiz(self, file_hash, num_questions=5, bloom_level=None):
        try:
            results = self.collection.get(where={"file_hash": file_hash})
            
            if not results['documents']:
                return {"status": "error", "message": "Aucun document trouvé pour ce hash."}
            
            chunks = results['documents']
            full_text = "\n".join(chunks)
            
            bloom_instruction = ""
            if bloom_level:
                bloom_instruction = f"Les questions doivent correspondre au niveau de la taxonomie de Bloom : {bloom_level}. "
            else:
                bloom_instruction = "Inclure un mélange de questions de connaissance, compréhension et application. "
            
            prompt = (
                f"Voici le contenu d'un document :\n\n{full_text}\n\n"
                f"Génère {num_questions} questions QCM basées sur le contenu du document. "
                f"Chaque question doit avoir 4 options de réponse, avec une seule réponse correcte. "
                f"{bloom_instruction}"
                f"Retourne les questions au format JSON avec les champs : question, options (liste), correct_answer (index), bloom_level.\n"
                f"Exemple de format :\n"
                f'{{"questions": [{{"question": "Quelle est...", "options": ["A", "B", "C", "D"], "correct_answer": 0, "bloom_level": "knowledge"}}]}}\n'
                f"Réponse :"
            )
            
            response = self.ollama_api.chat_with_ollama(prompt)
            
            try:
                questions = json.loads(response)
                return questions
            except json.JSONDecodeError:
                logger.error(f"Failed to parse JSON response: {response}")
                return {"status": "error", "message": "Erreur lors de la génération des questions."}
                
        except Exception as e:
            logger.error(f"Error generating quiz: {e}")
            return {"status": "error", "message": f"Erreur lors de la génération du quiz: {str(e)}"}

    def generate_quiz(self, file_hash, num_questions=5, bloom_level=None):
        try:
            results = self.collection.get(where={"file_hash": file_hash})

            if not results['documents']:
                return {"status": "error", "message": "Aucun document trouvé pour ce hash."}

            chunks = results['documents']
            full_text = "\n".join(chunks)

            bloom_instruction = ""
            if bloom_level:
                bloom_instruction = f"Les questions doivent correspondre au niveau de la taxonomie de Bloom : {bloom_level}. "
            else:
                bloom_instruction = "Inclure un mélange de questions de connaissance, compréhension et application. "

            prompt = (
                f"Voici le contenu d'un document :\n\n{full_text}\n\n"
                f"Génère {num_questions} questions QCM basées sur le contenu du document. "
                f"Chaque question doit avoir 4 options de réponse, avec une seule réponse correcte. "
                f"{bloom_instruction}"
                f"IMPORTANT: Retourne UNIQUEMENT le JSON valide, sans formatage markdown, sans ```json ni ```. "
                f"Format exact requis :\n"
                f'{{"questions": [{{"question": "Quelle est...", "options": ["A", "B", "C", "D"], "correct_answer": 0, "bloom_level": "knowledge"}}]}}\n'
                f"Réponse JSON :"
            )

            response = self.ollama_api.chat_with_ollama(prompt)
            logger.info(f"Raw quiz response: {response}")

            # Clean the response by removing markdown formatting
            cleaned_response = self._clean_json_response(response)
            logger.info(f"Cleaned quiz response: {cleaned_response}")

            try:
                questions = json.loads(cleaned_response)

                # Validate the structure
                if not isinstance(questions, dict) or "questions" not in questions:
                    raise ValueError("Invalid JSON structure")

                if not isinstance(questions["questions"], list):
                    raise ValueError("Questions should be a list")

                # Validate each question
                for i, q in enumerate(questions["questions"]):
                    required_fields = ["question", "options", "correct_answer", "bloom_level"]
                    for field in required_fields:
                        if field not in q:
                            raise ValueError(f"Missing field '{field}' in question {i+1}")

                    if not isinstance(q["options"], list) or len(q["options"]) != 4:
                        raise ValueError(f"Question {i+1} must have exactly 4 options")

                    if not isinstance(q["correct_answer"], int) or q["correct_answer"] not in [0, 1, 2, 3]:
                        raise ValueError(f"Question {i+1} correct_answer must be 0, 1, 2, or 3")

                return questions["questions"]  # Return just the questions array

            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed: {e}")
                logger.error(f"Attempted to parse: {cleaned_response}")
                return {"status": "error", "message": "Erreur lors de la génération des questions - format JSON invalide."}
            except ValueError as e:
                logger.error(f"JSON validation failed: {e}")
                return {"status": "error", "message": f"Erreur lors de la validation des questions: {str(e)}"}

        except Exception as e:
            logger.error(f"Error generating quiz: {e}")
            return {"status": "error", "message": f"Erreur lors de la génération du quiz: {str(e)}"}

    def _clean_json_response(self, response):
        """Clean the response from Ollama to extract pure JSON"""
        # Remove leading/trailing whitespace
        cleaned = response.strip()

        # Remove markdown code blocks
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]  # Remove ```json
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:]  # Remove ```

        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]  # Remove ending ```

        # Remove any remaining whitespace
        cleaned = cleaned.strip()

        # Try to find JSON content between curly braces if still problematic
        start_idx = cleaned.find('{')
        end_idx = cleaned.rfind('}')

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            cleaned = cleaned[start_idx:end_idx + 1]

        return cleaned

    def recommend_resources(self, user_id, filiere_id, module_id):
        try:
            gaps = self.filter_manager.analyze_gaps(user_id, filiere_id, module_id)
            if not gaps:
                return []

            # NOTE: Ensure you have a valid YouTube API key
            from googleapiclient.discovery import build
            youtube = build('youtube', 'v3', developerKey='YOUR_YOUTUBE_API_KEY')

            resources = []
            for gap in gaps:
                query = f"{gap} tutorial BDIA"
                request = youtube.search().list(q=query, part='snippet', maxResults=3)
                response = request.execute()

                for item in response['items']:
                    if 'videoId' in item['id']:
                        resources.append({
                            "title": item['snippet']['title'],
                            "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
                        })
            return resources

        except Exception as e:
            logger.error(f"Error recommending resources: {e}")
            return []

    def get_document_info(self, file_hash):
        """Get information about a document by its hash"""
        try:
            results = self.collection.get(where={"file_hash": file_hash})
            if results['documents']:
                metadata = results['metadatas'][0] if results['metadatas'] else {}
                return {
                    "file_hash": file_hash,
                    "base_filename": metadata.get("base_filename", "Unknown"),
                    "chunk_count": len(results['documents']),
                    "metadata": metadata
                }
            return None
        except Exception as e:
            logger.error(f"Error getting document info: {e}")
            return None

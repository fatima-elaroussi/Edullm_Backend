import chromadb
import numpy as np
from sentence_transformers import SentenceTransformer
from ollama_api import OllamaAPI
from utils.file_processor import FileProcessor
from utils.filter_manager import FilterManager
import json
from datetime import datetime
import logging
from typing import List
import urllib.parse
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
        try:
            results = self.collection.get(where={"file_hash": file_hash})
            return len(results['ids']) > 0
        except Exception as e:
            logger.warning(f"Error checking document existence: {e}")
            return False

    def delete_existing_document(self, file_hash):
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

            if chunks is None:
                if self.check_if_document_exists(file_hash):
                    return {"status": "error", "message": f"File {file_path} already processed and exists in database."}
                else:
                    content = self.file_processor.read_file(file_path)
                    file_hash = self.file_processor.calculate_hash(content)
                    if file_hash in self.file_processor.processed_hashes:
                        self.file_processor.processed_hashes.remove(file_hash)
                    chunks, file_hash = self.file_processor.process_file(file_path)

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

            for i, chunk in enumerate(chunks):
                self.filter_manager.insert_metadata_sqlite(
                    base_filename, file_hash, i, chunk, departement_id, filiere_id, module_id, activite_id, profile_id, user_id
                )

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

    def generate_summary(self, file_hashes: List[str], level="simplified"):
        try:
            if not file_hashes:
                return "Aucun document sélectionné."

            # Retrieve all chunks for the given file hashes
            chunks = []
            missing_hashes = []
            for file_hash in file_hashes:
                results = self.collection.get(where={"file_hash": file_hash})
                if not results['documents']:
                    logger.warning(f"No documents found for hash {file_hash}")
                    missing_hashes.append(file_hash)
                    continue
                chunks.extend(results['documents'])

            if not chunks:
                return f"Aucun document trouvé pour les hashes fournis: {', '.join(missing_hashes)}."

            logger.info(f"Found {len(chunks)} chunks for file hashes {file_hashes}")
            full_text = "\n".join(chunks)

            if level == "simplified":
                prompt = (
                    f"Voici le contenu de plusieurs documents académiques :\n\n{full_text}\n\n"
                    f"Génère un résumé simplifié de ces documents. "
                    f"Concentre-toi sur les idées principales et utilise un langage clair et concis. "
                    f"Structure le résumé avec des points clés. "
                    f"Réponse en français :"
                )
            else:
                prompt = (
                    f"Voici le contenu de plusieurs documents académiques :\n\n{full_text}\n\n"
                    f"Génère un résumé détaillé de ces documents. "
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

    def generate_quiz(self, file_hashes: List[str], num_questions=5, bloom_level=None):
        try:
            if not file_hashes:
                return {"status": "error", "message": "Aucun document sélectionné."}

            # Retrieve all chunks for the given file hashes
            chunks = []
            missing_hashes = []
            chunk_counts = {}
            for file_hash in file_hashes:
                results = self.collection.get(where={"file_hash": file_hash})
                if not results['documents']:
                    logger.warning(f"No documents found for hash {file_hash}")
                    missing_hashes.append(file_hash)
                    continue
                chunk_counts[file_hash] = len(results['documents'])
                chunks.extend(results['documents'])

            if not chunks:
                return {"status": "error", "message": f"Aucun document trouvé pour les hashes fournis: {', '.join(missing_hashes)}."}

            logger.info(f"Found {len(chunks)} chunks for file hashes {file_hashes}: {chunk_counts}")
            full_text = "\n".join(chunks)

            bloom_instruction = ""
            if bloom_level:
                bloom_instruction = f"Les questions doivent correspondre au niveau de la taxonomie de Bloom : {bloom_level}. "
            else:
                bloom_instruction = "Inclure un mélange de questions de connaissance, compréhension et application. "

            prompt = (
                f"Voici le contenu de plusieurs documents :\n\n{full_text}\n\n"
                f"Génère EXACTEMENT {num_questions} questions QCM basées sur le contenu des documents. "
                f"Chaque question doit avoir 4 options de réponse, avec une seule réponse correcte. "
                f"{bloom_instruction}"
                f"IMPORTANT: Le champ 'bloom_level' doit être EXACTEMENT l'un des suivants : 'knowledge', 'comprehension', 'application'. "
                f"Ne pas utiliser d'autres termes comme 'understanding'. "
                f"Retourne UNIQUEMENT un objet JSON valide avec la structure exacte suivante, SANS tableau extérieur, SANS formatage markdown, SANS ```json ni ``` :\n"
                f'{{"questions": [{{"question": "Quelle est...", "options": ["A", "B", "C", "D"], "correct_answer": 0, "bloom_level": "knowledge"}}]}}\n'
                f"Exemple de réponse JSON correcte :\n"
                f'{{"questions": [{{"question": "Exemple de question", "options": ["A", "B", "C", "D"], "correct_answer": 0, "bloom_level": "knowledge"}}]}}\n'
                f"Réponse JSON :"
            )

            response = self.ollama_api.chat_with_ollama(prompt)
            logger.info(f"Raw quiz response: {response}")

            cleaned_response = self._clean_json_response(response)
            logger.info(f"Cleaned quiz response: {cleaned_response}")

            try:
                questions = json.loads(cleaned_response)

                # Handle case where response is an array of questions
                if isinstance(questions, list):
                    questions = {"questions": questions[:num_questions]}  # Limit to num_questions
                    logger.info(f"Converted array to questions object with {len(questions['questions'])} questions")

                logger.info(f"Parsed JSON: {json.dumps(questions, indent=2)}")

                if not isinstance(questions, dict) or "questions" not in questions:
                    raise ValueError("Invalid JSON structure: expected object with 'questions' key")

                if not isinstance(questions["questions"], list):
                    raise ValueError("Questions must be a list")

                if len(questions["questions"]) != num_questions:
                    logger.warning(f"Received {len(questions['questions'])} questions, expected {num_questions}")

                # Validate and normalize questions
                for q in questions["questions"]:
                    if q.get("bloom_level") == "understanding":
                        q["bloom_level"] = "comprehension"
                        logger.info(f"Mapped 'understanding' to 'comprehension' for question: {q['question']}")

                    required_fields = ["question", "options", "correct_answer", "bloom_level"]
                    for field in required_fields:
                        if field not in q:
                            raise ValueError(f"Missing field '{field}' in question")

                    if not isinstance(q["options"], list) or len(q["options"]) != 4:
                        raise ValueError(f"Question must have exactly 4 options")

                    if not isinstance(q["correct_answer"], int) or q["correct_answer"] not in [0, 1, 2, 3]:
                        raise ValueError(f"Correct_answer must be 0, 1, 2, or 3")

                return questions["questions"]

            except json.JSONDecodeError as e:
                logger.error(f"JSON parsing failed: {e}")
                logger.error(f"Attempted to parse: {cleaned_response}")
                return {"status": "error", "message": f"Erreur lors de la génération des questions - format JSON invalide: {str(e)}"}
            except ValueError as e:
                logger.error(f"JSON validation failed: {e}")
                return {"status": "error", "message": f"Erreur lors de la validation des questions: {str(e)}"}

        except Exception as e:
            logger.error(f"Error generating quiz: {e}")
            return {"status": "error", "message": f"Erreur lors de la génération du quiz: {str(e)}"}

    def _clean_json_response(self, response):
        cleaned = str(response).strip()

        # Remove markdown code fences
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        elif cleaned.startswith('```'):
            cleaned = cleaned[3:]

        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]

        cleaned = cleaned.strip()
        logger.info(f"Cleaned JSON response: {cleaned}")
        return cleaned

    # def recommend_resources(self, user_id, filiere_id, module_id):
    #     try:
    #         gaps = self.filter_manager.analyze_gaps(user_id, filiere_id, module_id)
    #         if not gaps:
    #             return []

    #         from googleapiclient.discovery import build
    #         youtube = build('youtube', 'v3', developerKey='YOUR_YOUTUBE_API_KEY')

    #         resources = []
    #         for gap in gaps:
    #             query = f"{gap} tutorial BDIA"
    #             request = youtube.search().list(q=query, part='snippet', maxResults=3)
    #             response = request.execute()

    #             for item in response['items']:
    #                 if 'videoId' in item['id']:
    #                     resources.append({
    #                         "title": item['snippet']['title'],
    #                         "url": f"https://www.youtube.com/watch?v={item['id']['videoId']}"
    #                     })
    #         return resources

    #     except Exception as e:
    #         logger.error(f"Error recommending resources: {e}")
    #         return []

    def recommend_resources(self, user_id, filiere_id, module_id):
        try:
            gaps = self.filter_manager.analyze_gaps(user_id, filiere_id, module_id)
            if not gaps:
                return []

            resources = []
            for gap in gaps:
                query = f"{gap} tutoriel BDIA"
                encoded_query = urllib.parse.quote(query)
                youtube_search_url = f"https://www.youtube.com/results?search_query={encoded_query}"

                # On simule une ressource en retournant le lien de recherche
                resources.append({
                    "title": f"Tutoriels YouTube pour : {gap}",
                    "url": youtube_search_url
                })

            return resources

        except Exception as e:
            logger.error(f"Error recommending resources: {e}")
            return []

    def get_document_info(self, file_hash):
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
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

    def ingestion_file(self, base_filename, file_path, departement_id, filiere_id, module_id, activite_id, profile_id, user_id):
        try:
            chunks, file_hash = self.file_processor.process_file(file_path)
            if chunks is None:
                return {"status": "error", "message": f"File {file_path} already processed."}
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
        results = self.collection.query(
            query_texts=[""],
            n_results=1000,
            where={"file_hash": file_hash}
        )
        chunks = results['documents'][0]
        if not chunks:
            return "Aucun document trouvé pour ce hash."
        full_text = "\n".join(chunks)
        prompt = (
            f"Contexte : {full_text}\n\n"
            f"Génère un résumé {'simplifié' if level == 'simplified' else 'détaillé'} du document suivant. "
            f"{'Concentre-toi sur les idées principales et utilise un langage clair et concis.' if level == 'simplified' else 'Inclus tous les détails importants et structure les sous-sections pertinentes.'}\n"
            f"Réponse :"
        )
        return self.ollama_api.chat_with_ollama(prompt)

    def generate_quiz(self, file_hash, num_questions=5, bloom_level=None):
        results = self.collection.query(
            query_texts=[""],
            n_results=1000,
            where={"file_hash": file_hash}
        )
        chunks = results['documents'][0]
        if not chunks:
            return {"status": "error", "message": "Aucun document trouvé pour ce hash."}
        full_text = "\n".join(chunks)
        prompt = (
            f"Contexte : {full_text}\n\n"
            f"Génère {num_questions} questions QCM basées sur le contenu du document. "
            f"Chaque question doit avoir 4 options de réponse, avec une seule réponse correcte. "
            f"{'Les questions doivent correspondre au niveau de la taxonomie de Bloom : ' + bloom_level + '.' if bloom_level else 'Inclure un mélange de questions de connaissance, compréhension et application.'}\n"
            f"Retourne les questions au format JSON avec les champs : question, options (liste), correct_answer (index), bloom_level.\n"
            f"Réponse :"
        )
        response = self.ollama_api.chat_with_ollama(prompt)
        try:
            questions = json.loads(response)
            return questions
        except json.JSONDecodeError:
            return {"status": "error", "message": "Erreur lors de la génération des questions."}

    def recommend_resources(self, user_id, filiere_id, module_id):
        gaps = self.filter_manager.analyze_gaps(user_id, filiere_id, module_id)
        if not gaps:
            return []
        # NOTE: 'googleapiclient.discovery' is an external library that would need to be installed.
        # Ensure 'YOUR_YOUTUBE_API_KEY' is replaced with an actual API key.
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

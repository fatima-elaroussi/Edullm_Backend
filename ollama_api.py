# import requests
# import json

# class OllamaAPI:
#     def __init__(self, base_url="http://localhost:11434"):
#         self.base_url = base_url

#     def chat_with_ollama(self, prompt):
#         payload = {
#             "model": "gemma3:4b", 
#             # "model": "deepseek-r1",
#             "prompt": prompt,
#             "stream": True
#         }
#         try:
#             response = requests.post(f"{self.base_url}/api/generate", json=payload, stream=True)
#             response.raise_for_status()
#             full_response = ""
#             in_think_block = False
#             for line in response.iter_lines():
#                 if line:
#                     data = json.loads(line.decode('utf-8'))
#                     chunk = data.get("response", "")
#                     if "<think>" in chunk:
#                         in_think_block = True
#                         chunk = chunk.replace("<think>", "")
#                     if "</think>" in chunk:
#                         in_think_block = False
#                         chunk = chunk.replace("</think>", "")
#                     if not in_think_block and not data.get("done", False):
#                         full_response += chunk
#             return full_response.strip()
#         except Exception as e:
#             return f"Error communicating with Ollama: {str(e)}"
import os
import requests
import json
from dotenv import load_dotenv
from langchain_groq import ChatGroq
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
class OllamaAPI:
    def __init__(self, api_url="http://localhost:11434"):
        self.api_url = api_url
        load_dotenv()
        GROQ_API_KEY = os.getenv("GROQ_API_KEY")
        # Instancie le LLM Groq de LangChain
        self.groq_llm = ChatGroq(api_key=GROQ_API_KEY,
                                 model="llama3-8b-8192",
                                 temperature=0.7,
                                 max_tokens=8192)

    def chat_with_ollama(self, prompt):
        payload = {
            "model": "gemma3:4b", 
            # "model": "deepseek-r1",
            "prompt": prompt,
            "max_tokens": 8000,
            "repeat_penalty": 1.1,
            "temperature": 0.6,
            "stop": None

        }
            
            # self, prompt,
            #             model="gemma3:4b",
            #             max_tokens=8000,
            #             repeat_penalty=1.1,
            #             top_p=0.9,
            #             temperature=0.6,
            #             stop=None
        
        """
        Tente d'abord le LLM en ligne (Groq via LangChain), sinon fallback sur Ollama local.
        """
        # 1. Essayer Groq (en ligne)
        try:
            # Utilisation de LangChain pour générer la réponse
            response = self.groq_llm.invoke(prompt)
            # Si tu veux juste le texte :
            if hasattr(response, "content"):
                return response.content
            logger.info(f"Groq response: {response}")
            return str(response)
        
        except Exception as e:
            print(f"Groq failed: {e}, fallback to Ollama local.")
        logger.error(f"Groq failed: {e}, fallback to Ollama local.")
        # 2. Si Groq échoue, fallback sur Ollama local
        try:
            # response = requests.post(
            #     self.api_url,
            #     json={
            #         "model": model,
            #         "prompt": prompt,
            #         "max_tokens": max_tokens,
            #         "repeat_penalty": repeat_penalty,
            #         "top_p": top_p,
            #         "temperature": temperature,
            #         "stop": stop
            #     },
            #     stream=True
            # )
            response = requests.post(f"{self.api_url}/api/generate", json=payload, stream=True)
            if response.status_code == 200:
                messages = []
                for line in response.iter_lines():
                    if line:
                        try:
                            json_line = line.decode('utf-8')
                            data = json.loads(json_line)
                            messages.append(data.get("response", ""))
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
                return "".join(messages)
            else:
                return f"Error: {response.status_code} - {response.text}"
        except Exception as e:
            return f"Error: {str(e)}"

# # Utilisation
# ollama_api = OllamaAPI()
# prompt_text = "Bonjour, peux-tu m'aider ?"
# llm_raw_response = ollama_api.chat_with_ollama(prompt_text)
# print(llm_raw_response)
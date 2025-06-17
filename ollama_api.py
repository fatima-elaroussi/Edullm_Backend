import requests
import json

class OllamaAPI:
    def __init__(self, base_url="http://localhost:11434"):
        self.base_url = base_url

    def chat_with_ollama(self, prompt):
        payload = {
            "model": "gemma3:4b", 
            # "model": "deepseek-r1",
            "prompt": prompt,
            "stream": True
        }
        try:
            response = requests.post(f"{self.base_url}/api/generate", json=payload, stream=True)
            response.raise_for_status()
            full_response = ""
            in_think_block = False
            for line in response.iter_lines():
                if line:
                    data = json.loads(line.decode('utf-8'))
                    chunk = data.get("response", "")
                    if "<think>" in chunk:
                        in_think_block = True
                        chunk = chunk.replace("<think>", "")
                    if "</think>" in chunk:
                        in_think_block = False
                        chunk = chunk.replace("</think>", "")
                    if not in_think_block and not data.get("done", False):
                        full_response += chunk
            return full_response.strip()
        except Exception as e:
            return f"Error communicating with Ollama: {str(e)}"
import requests


class OllamaClient:

    def __init__(self, model="llama3.2:1b"):
        self.model = model
        self.url = "http://localhost:11434/api/generate"


    def generate(self, prompt):

        response = requests.post(
            self.url,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "num_predict": 400
                }
            },
            timeout=600
        )

        response.raise_for_status()

        return response.json()["response"]
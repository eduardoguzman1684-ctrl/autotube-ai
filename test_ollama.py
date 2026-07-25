from backend.app.ai.ollama_client import OllamaClient

ai = OllamaClient()

texto = ai.generate("Escribe un resumen de 100 palabras sobre inteligencia artificial.")

print(texto)
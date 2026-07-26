import requests

API_KEY = "56857279-c06c3ee099593ca521bb36d00"

url = "https://pixabay.com/api/"

respuesta = requests.get(
    url,
    params={
        "key": API_KEY,
        "q": "robot medicine",
        "image_type": "photo"
    }
)

print("Estado:", respuesta.status_code)
print(respuesta.text[:500])
import requests

url = "https://libretranslate.com/translate"

payload = {
    "q": "Hello, how are you?",
    "source": "en",
    "target": "ml",   # ta = Tamil, hi = Hindi, kn = Kannada, ml = Malayalam, te = Telugu
    "format": "text"
}

response = requests.post(url, data=payload)
# print(response.json()["translatedText"])
print(response.json())
import requests

url = "https://api.autorouter.aero/v1.0/notam"

params = {
    "itemas": '["VIDP"]',
    "offset": 0,
    "limit": 100
}

response = requests.get(url, params=params)

print("Status:", response.status_code)
print(response.text[:5000])
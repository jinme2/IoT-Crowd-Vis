import requests

url = "https://iot11-backend.onrender.com/upload"

data = {
    "camera_id": 1,
    "room": "railway",
    "people_count": 7
}

response = requests.post(url, json=data)

print("Status:", response.status_code)
print("Response:", response.text)

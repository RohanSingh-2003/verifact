import json
import urllib.error
import urllib.request

print("health", urllib.request.urlopen("http://127.0.0.1:8000/api/health").read().decode())
print("proxy", urllib.request.urlopen("http://localhost:5173/api/health").read().decode())
print("runs", urllib.request.urlopen("http://127.0.0.1:8000/api/runs").read().decode())

req = urllib.request.Request(
    "http://127.0.0.1:8000/api/detect",
    data=json.dumps({"question": "What is the capital of Australia?"}).encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    urllib.request.urlopen(req)
except urllib.error.HTTPError as exc:
    print("detect", exc.code, exc.read().decode())

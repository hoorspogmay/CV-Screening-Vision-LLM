import urllib.request

try:
    with urllib.request.urlopen('http://127.0.0.1:8010/api/health', timeout=5) as response:
        print(response.status)
        print(response.read().decode())
except Exception as exc:
    print(type(exc).__name__, exc)

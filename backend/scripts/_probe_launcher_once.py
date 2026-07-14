import httpx

r = httpx.get("https://launcher.mlx.yt:45001/api/v2/", verify=False, timeout=5)
print(r.status_code)

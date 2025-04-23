# scripts/export_openapi.py
from main import app   # ← cambio aquí

with app.test_client() as c:
    res = c.get("/swagger.json")
    open("openapi.json", "wb").write(res.data)
    print("→ openapi.json generado")
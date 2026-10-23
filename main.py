import traceback
from fastapi import HTTPException

@app.post("/api/auth/login")
def login(credentials: LoginRequest):
    try:
        # Coloca aquí tu lógica actual de Supabase y verificación de passlib
        pass
    except Exception as e:
        error_detallado = traceback.format_exc()
        print("ERROR EN LOGIN:", error_detallado)
        raise HTTPException(status_code=500, detail=str(e))
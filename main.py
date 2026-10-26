except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ERROR REAL LOGIN: {str(e)}")

@app.get("/api/test-db")
def test_db_connection():
    if not supabase:
        return {"status": "error", "message": "Cliente de Supabase no inicializado (faltan variables de entorno SUPABASE_URL o SUPABASE_KEY en Render)."}
    try:
        response = supabase.table("usuarios").select("id, username, correo").limit(5).execute()
        return {
            "status": "success",
            "message": "¡Comunicación exitosa entre Render y Supabase!",
            "registros_encontrados": response.data
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error al comunicarse con Supabase: {str(e)}"
        }
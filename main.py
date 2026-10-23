class RegisterRequest(BaseModel):
    nombre: str
    apellido: str
    correo: str
    cedula: str
    celular: str  # <--- Añadido
    username: str
    password: str

@app.post("/api/auth/register", response_model=RegisterResponse)
def registrar_usuario(user: RegisterRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase no conectado.")

    try:
        check_user = supabase.table("usuarios").select("id").eq("user", user.username).execute()
        if check_user.data and len(check_user.data) > 0:
            raise HTTPException(status_code=400, detail="El nombre de usuario ya se encuentra registrado.")

        check_email = supabase.table("usuarios").select("id").eq("correo", user.correo).execute()
        if check_email.data and len(check_email.data) > 0:
            raise HTTPException(status_code=400, detail="El correo electrónico ya se encuentra registrado.")

        nuevo_numero_cuenta = generar_numero_cuenta()
        hashed_pwd = hash_password(user.password)

        partes_cedula = user.cedula.split("-")
        tipo_doc = partes_cedula[0] if len(partes_cedula) > 1 else "V"
        num_doc = partes_cedula[1] if len(partes_cedula) > 1 else user.cedula

        nuevo_registro = {
            "nombre": user.nombre,
            "apellido": user.apellido,
            "correo": user.correo,
            "tipo_documento": tipo_doc,
            "numero_documento": num_doc,
            "celular": user.celular,  # <--- Incluido aquí
            "user": user.username,
            "password_hash": hashed_pwd,
            "numero_cuenta": nuevo_numero_cuenta,
            "saldo_disponible": 0.0
        }

        response = supabase.table("usuarios").insert(nuevo_registro).execute()

        if not response.data:
            raise HTTPException(status_code=500, detail="No se pudo guardar el usuario en la base de datos.")

        return RegisterResponse(
            success=True,
            message="Usuario registrado exitosamente.",
            numero_cuenta=nuevo_numero_cuenta
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")
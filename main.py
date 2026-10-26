import os
import random
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from passlib.context import CryptContext
from supabase import create_client, Client

app = FastAPI(title="Fintech App Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

class RegisterRequest(BaseModel):
    nombre: str
    apellido: str
    correo: str
    cedula: str
    celular: Optional[str] = ""
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class TarjetaDataResponse(BaseModel):
    id: int
    banco: str
    numero_enmascarado: str
    fecha_exp: str
    nfc_habilitado: bool = True
    compras_web_habilitadas: bool = True

class LoginResponse(BaseModel):
    token: Optional[str] = None
    message: Optional[str] = None
    nombre: Optional[str] = None
    numero_cuenta: Optional[str] = None
    saldo_disponible: Optional[float] = 0.0
    tarjetas: Optional[List[TarjetaDataResponse]] = []

class RegisterResponse(BaseModel):
    success: bool
    message: str
    numero_cuenta: Optional[str] = None

def generar_numero_cuenta() -> str:
    sufijo = "".join([str(random.randint(0, 9)) for _ in range(8)])
    return f"0185-{sufijo[:4]}-{sufijo[4:]}"

def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        if not hashed_password.startswith("$"):
            return plain_password == hashed_password
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return plain_password == hashed_password

@app.get("/")
def read_root():
    return {"status": "online", "message": "API Fintech operando correctamente"}

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

@app.post("/api/auth/register", response_model=RegisterResponse)
def registrar_usuario(user: RegisterRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase no conectado.")

    try:
        check_user = supabase.table("usuarios").select("id").eq("username", user.username).execute()
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
            "celular": user.celular or "",
            "username": user.username,
            "password_hash": hashed_pwd,
            "numero_cuenta": nuevo_numero_cuenta,
            "saldo_disponible": 0.0,
            "verificado": False
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
        raise HTTPException(status_code=500, detail=f"ERROR REAL REGISTRO: {str(e)}")

@app.post("/api/auth/login", response_model=LoginResponse)
def iniciar_sesion(credenciales: LoginRequest):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase no conectado.")

    try:
        respuesta = supabase.table("usuarios").select("*").eq("username", credenciales.username).execute()
        usuarios = respuesta.data

        if not usuarios or len(usuarios) == 0:
            respuesta_correo = supabase.table("usuarios").select("*").eq("correo", credenciales.username).execute()
            usuarios = respuesta_correo.data

        if not usuarios or len(usuarios) == 0:
            raise HTTPException(status_code=401, detail="Credenciales incorrectas.")

        usuario = usuarios[0]

        if not verify_password(credenciales.password, usuario.get("password_hash") or ""):
            raise HTTPException(status_code=401, detail="Credenciales incorrectas.")

        nombre_val = usuario.get("nombre") or ""
        apellido_val = usuario.get("apellido") or ""
        nombre_completo = f"{nombre_val} {apellido_val}".strip()

        saldo_raw = usuario.get("saldo_disponible")
        saldo_num = float(saldo_raw) if saldo_raw is not None else 0.0

        num_cuenta = usuario.get("numero_cuenta") or "0185-0000-0000"

        return LoginResponse(
            token="bearer_token_simulado",
            message="Inicio de sesión exitoso.",
            nombre=nombre_completo if nombre_completo else (usuario.get("username") or "Usuario"),
            numero_cuenta=num_cuenta,
            saldo_disponible=saldo_num,
            tarjetas=[]
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ERROR REAL LOGIN: {str(e)}")
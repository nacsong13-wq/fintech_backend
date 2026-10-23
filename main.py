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
    return pwd_context.verify(plain_password, hashed_password)

@app.get("/")
def read_root():
    return {"status": "online", "message": "API Fintech operando correctamente"}

@app.post("/api/auth/register", response_model=RegisterResponse)
def registrar_usuario(user: RegisterRequest):
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase no conectado."
        )

    try:
        existe_usuario = supabase.table("usuarios").select("id").or_(
            f"username.eq.{user.username},correo.eq.{user.correo}"
        ).execute()

        if existe_usuario.data and len(existe_usuario.data) > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="El usuario o correo ya existe."
            )

        nuevo_numero_cuenta = generar_numero_cuenta()
        hashed_pwd = hash_password(user.password)

        nuevo_registro = {
            "nombre": user.nombre,
            "apellido": user.apellido,
            "correo": user.correo,
            "cedula": user.cedula,
            "username": user.username,
            "password_hash": hashed_pwd,
            "numero_cuenta": nuevo_numero_cuenta,
            "saldo_disponible": 0.0
        }

        response = supabase.table("usuarios").insert(nuevo_registro).execute()

        if not response.data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al insertar en la base de datos."
            )

        return RegisterResponse(
            success=True,
            message="Usuario registrado exitosamente.",
            numero_cuenta=nuevo_numero_cuenta
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/api/auth/login", response_model=LoginResponse)
def iniciar_sesion(credenciales: LoginRequest):
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Supabase no conectado."
        )

    try:
        respuesta = supabase.table("usuarios").select("*").or_(
            f"username.eq.{credenciales.username},correo.eq.{credenciales.username}"
        ).execute()

        usuarios = respuesta.data
        if not usuarios or len(usuarios) == 0:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas."
            )

        usuario = usuarios[0]

        if not verify_password(credenciales.password, usuario.get("password_hash", "")):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Credenciales incorrectas."
            )

        tarjetas_db = []
        try:
            tarjetas_resp = supabase.table("tarjetas").select("*").eq("usuario_id", usuario["id"]).execute()
            if tarjetas_resp.data:
                for t in tarjetas_resp.data:
                    tarjetas_db.append(
                        TarjetaDataResponse(
                            id=t.get("id", 1),
                            banco=t.get("banco", "Banco 0185"),
                            numero_enmascarado=t.get("numero_enmascarado", "**** 0000"),
                            fecha_exp=t.get("fecha_exp", "12/28"),
                            nfc_habilitado=t.get("nfc_habilitado", True),
                            compras_web_habilitadas=t.get("compras_web_habilitadas", True)
                        )
                    )
        except Exception:
            tarjetas_db = []

        nombre_completo = f"{usuario.get('nombre', '')} {usuario.get('apellido', '')}".strip()

        return LoginResponse(
            token="bearer_token_simulado",
            message="Inicio de sesión exitoso.",
            nombre=nombre_completo if nombre_completo else usuario.get("username", "Usuario"),
            numero_cuenta=usuario.get("numero_cuenta", "0185-0000-0000"),
            saldo_disponible=float(usuario.get("saldo_disponible", 0.0)),
            tarjetas=tarjetas_db
        )

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
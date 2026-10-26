import os
import random
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from passlib.context import CryptContext
from sqlalchemy import create_engine, text

app = FastAPI(title="Fintech App Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Lectura de variables de entorno directas de PostgreSQL (configuradas en Render)
DB_USER = os.getenv("user", "")
DB_PASSWORD = os.getenv("password", "")
DB_HOST = os.getenv("host", "")
DB_PORT = os.getenv("port", "5432")
DB_NAME = os.getenv("dbname", "postgres")

# Construcción de la URL de conexión para SQLAlchemy
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

engine = None
if DB_USER and DB_PASSWORD and DB_HOST:
    try:
        engine = create_engine(DATABASE_URL)
    except Exception as e:
        print(f"Error al inicializar el engine de SQLAlchemy: {e}")

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
    if not engine:
        return {"status": "error", "message": "Motor de base de datos no inicializado (faltan variables de entorno user, password, host, etc.)."}
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT id, username, correo FROM usuarios LIMIT 5;"))
            rows = [dict(row._mapping) for row in result]
        return {
            "status": "success",
            "message": "¡Comunicación exitosa con PostgreSQL (Supabase)!",
            "registros_encontrados": rows
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error al comunicarse con la base de datos: {str(e)}"
        }

@app.post("/api/auth/register", response_model=RegisterResponse)
def registrar_usuario(user: RegisterRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="Base de datos no conectada.")

    try:
        with engine.connect() as connection:
            # Verificar si el username ya existe
            check_user = connection.execute(
                text("SELECT id FROM usuarios WHERE username = :username"),
                {"username": user.username}
            .fetchone()
            if check_user:
                raise HTTPException(status_code=400, detail="El nombre de usuario ya se encuentra registrado.")

            # Verificar si el correo ya existe
            check_email = connection.execute(
                text("SELECT id FROM usuarios WHERE correo = :correo"),
                {"correo": user.correo}
            ).fetchone()
            if check_email:
                raise HTTPException(status_code=400, detail="El correo electrónico ya se encuentra registrado.")

            nuevo_numero_cuenta = generar_numero_cuenta()
            hashed_pwd = hash_password(user.password)

            partes_cedula = user.cedula.split("-")
            tipo_doc = partes_cedula[0] if len(partes_cedula) > 1 else "V"
            num_doc = partes_cedula[1] if len(partes_cedula) > 1 else user.cedula

            insert_query = text("""
                INSERT INTO usuarios (nombre, apellido, correo, tipo_documento, numero_documento, celular, username, password_hash, numero_cuenta, saldo_disponible, verificado)
                VALUES (:nombre, :apellido, :correo, :tipo_documento, :numero_documento, :celular, :username, :password_hash, :numero_cuenta, :saldo_disponible, :verificado)
            """)

            connection.execute(insert_query, {
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
            })
            connection.commit()

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
    if not engine:
        raise HTTPException(status_code=500, detail="Base de datos no conectada.")

    try:
        with engine.connect() as connection:
            # Buscar por username
            result = connection.execute(
                text("SELECT * FROM usuarios WHERE username = :val"),
                {"val": credenciales.username}
            ).fetchone()

            # Si no se encuentra por username, buscar por correo
            if not result:
                result = connection.execute(
                    text("SELECT * FROM usuarios WHERE correo = :val"),
                    {"val": credenciales.username}
                ).fetchone()

            if not result:
                raise HTTPException(status_code=401, detail="Credenciales incorrectas.")

            usuario = dict(result._mapping)

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
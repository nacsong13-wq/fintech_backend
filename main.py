import os
import random
from typing import Optional, List
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from passlib.context import CryptContext
from supabase import create_client, Client
from sqlalchemy import create_engine, text
import requests
from bs4 import BeautifulSoup
import urllib3

# Desactivar advertencias de SSL para las peticiones al BCV
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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

DB_USER = os.getenv("user", "")
DB_PASSWORD = os.getenv("password", "")
DB_HOST = os.getenv("host", "")
DB_PORT = os.getenv("port", "5432")
DB_NAME = os.getenv("dbname", "postgres")

supabase: Client = None
if SUPABASE_URL and SUPABASE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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
    usuario_id: Optional[int] = None
    nombre: Optional[str] = None
    numero_cuenta: Optional[str] = None
    saldo_disponible: Optional[float] = 0.0
    tarjetas: Optional[List[TarjetaDataResponse]] = []

class RegisterResponse(BaseModel):
    success: bool
    message: str
    numero_cuenta: Optional[str] = None

class TasasBcvResponseModel(BaseModel):
    dolar: float
    euro: float
    fecha: Optional[str] = ""

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
    return {"status": "online", "message": "API Fintech operando correctamente con SQLAlchemy"}

@app.get("/api/test-db")
def test_db_connection():
    if not engine:
        return {"status": "error", "message": "Motor de SQLAlchemy no inicializado."}
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT id, username, correo FROM usuarios LIMIT 5;"))
            rows = [dict(row._mapping) for row in result]
        return {
            "status": "success",
            "message": "¡Comunicación exitosa con PostgreSQL usando SQLAlchemy!",
            "registros_encontrados": rows
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error al consultar la base de datos: {str(e)}"
        }

@app.get("/api/tasas-bcv", response_model=TasasBcvResponseModel)
def obtener_tasas_bcv():
    """Consulta la tasa oficial directamente haciendo scraping a la web del BCV."""
    url = "https://www.bcv.org.ve/"
    dolar_val = 36.50
    euro_val = 39.80
    fecha_val = ""

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10, verify=False)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extraer Dólar (busca por id 'dolar' o variaciones)
            div_dolar = soup.find('div', id='dolar') or soup.find('div', id='dol')
            if div_dolar:
                strong_dolar = div_dolar.find('strong')
                if strong_dolar:
                    texto_dolar = strong_dolar.text.strip().replace(',', '.')
                    dolar_val = float(texto_dolar)

            # Extraer Euro (busca por id 'euro', 'eur' o busca contenedores relacionados)
            div_euro = soup.find('div', id='euro') or soup.find('div', id='eur')
            if not div_euro:
                for d in soup.find_all('div'):
                    div_id = d.get('id')
                    if div_id and ('euro' in div_id.lower() or 'eur' in div_id.lower()):
                        div_euro = d
                        break
            if div_euro:
                strong_euro = div_euro.find('strong')
                if strong_euro:
                    texto_euro = strong_euro.text.strip().replace(',', '.')
                    euro_val = float(texto_euro)
                    
            # Extraer Fecha si está disponible
            div_fecha = soup.find('span', class_='date-display-single')
            if div_fecha:
                fecha_val = div_fecha.text.strip()

    except Exception as e:
        print(f"Error al conectar con la web del BCV: {e}")

    return {
        "dolar": dolar_val,
        "euro": euro_val,
        "fecha": fecha_val
    }

def logica_registro(user: RegisterRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="Base de datos no conectada.")
    
    with engine.connect() as connection:
        check_user = connection.execute(
            text("SELECT id FROM usuarios WHERE username = :username"),
            {"username": user.username}
        ).fetchone()
        
        if check_user:
            raise HTTPException(status_code=400, detail="El nombre de usuario ya se encuentra registrado.")
        
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
            VALUES (:nombre, :apellido, :correo, :tipo_doc, :num_doc, :celular, :username, :password_hash, :numero_cuenta, :saldo_disponible, :verificado)
        """)
        
        connection.execute(insert_query, {
            "nombre": user.nombre,
            "apellido": user.apellido,
            "correo": user.correo,
            "tipo_doc": tipo_doc,
            "num_doc": num_doc,
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

def logica_login(credenciales: LoginRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="Base de datos no conectada.")
    
    with engine.connect() as connection:
        query = text("""
            SELECT id, nombre, username, password_hash, numero_cuenta, saldo_disponible 
            FROM usuarios 
            WHERE username = :username
        """)
        result = connection.execute(query, {"username": credenciales.username}).fetchone()
        
        if not result:
            raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos.")
        
        user_dict = dict(result._mapping)
        
        if not verify_password(credenciales.password, user_dict["password_hash"]):
            raise HTTPException(status_code=400, detail="Usuario o contraseña incorrectos.")
        
        return LoginResponse(
            token="fake-jwt-token-active",
            message="Login exitoso",
            usuario_id=user_dict["id"],
            nombre=user_dict["nombre"],
            numero_cuenta=user_dict.get("numero_cuenta"),
            saldo_disponible=float(user_dict.get("saldo_disponible") or 0.0),
            tarjetas=[]
        )

@app.post("/api/register", response_model=RegisterResponse)
def registrar_usuario_1(user: RegisterRequest):
    return logica_registro(user)

@app.post("/api/auth/register", response_model=RegisterResponse)
def registrar_usuario_2(user: RegisterRequest):
    return logica_registro(user)

@app.post("/api/login", response_model=LoginResponse)
def iniciar_sesion_1(credenciales: LoginRequest):
    return logica_login(credenciales)

@app.post("/api/auth/login", response_model=LoginResponse)
def iniciar_sesion_2(credenciales: LoginRequest):
    return logica_login(credenciales)
@app.post("/api/auth/login", response_model=LoginResponse)
def iniciar_sesion_2(credenciales: LoginRequest):
    return logica_login(credenciales)
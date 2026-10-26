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

# --- MODELOS PYDANTIC ---

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

class TarjetaCreateRequest(BaseModel):
    usuario_id: int
    banco: str
    numero_tarjeta: str
    fecha_exp: str
    cvv: str
    nfc_habilitado: bool = True
    compras_web_habilitadas: bool = True

class TarjetaToggleNfcRequest(BaseModel):
    nfc_habilitado: bool

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

# --- FUNCIONES AUXILIARES ---

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

# Crear la tabla de tarjetas automáticamente al arrancar si no existe
def inicializar_tabla_tarjetas():
    if not engine:
        return
    try:
        with engine.connect() as connection:
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS tarjetas (
                    id SERIAL PRIMARY KEY,
                    usuario_id INT REFERENCES usuarios(id) ON DELETE CASCADE,
                    banco VARCHAR(100),
                    numero_enmascarado VARCHAR(30),
                    fecha_exp VARCHAR(10),
                    cvv_cifrado VARCHAR(255),
                    nfc_habilitado BOOLEAN DEFAULT TRUE,
                    compras_web_habilitadas BOOLEAN DEFAULT TRUE
                );
            """))
            connection.commit()
    except Exception as e:
        print(f"Error al crear tabla tarjetas: {e}")

@app.on_event("startup")
def startup_event():
    inicializar_tabla_tarjetas()

# --- ENDPOINTS BÁSICOS ---

@app.get("/")
def read_root():
    return {"status": "online", "message": "API Fintech operando correctamente"}

@app.get("/api/test-db")
def test_db_connection():
    if not engine:
        return {"status": "error", "message": "Motor de base de datos no inicializado."}
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT id, username, correo FROM usuarios LIMIT 5;"))
            rows = [dict(row._mapping) for row in result]
        return {
            "status": "success",
            "message": "¡Comunicación exitosa con PostgreSQL!",
            "registros_encontrados": rows
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error al comunicarse con la base de datos: {str(e)}"
        }

# --- ENDPOINTS DE AUTENTICACIÓN ---

@app.post("/api/auth/register", response_model=RegisterResponse)
def registrar_usuario(user: RegisterRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="Base de datos no conectada.")

    try:
        username_clean = user.username.strip()
        correo_clean = user.correo.strip().lower()

        partes_cedula = user.cedula.strip().split("-")
        tipo_doc = partes_cedula[0] if len(partes_cedula) > 1 else "V"
        num_doc = partes_cedula[1] if len(partes_cedula) > 1 else user.cedula.strip()

        with engine.connect() as connection:
            check_user = connection.execute(
                text("SELECT id FROM usuarios WHERE LOWER(username) = LOWER(:username)"),
                {"username": username_clean}
            ).fetchone()
            if check_user:
                raise HTTPException(status_code=400, detail="El nombre de usuario ya se encuentra registrado.")

            check_email = connection.execute(
                text("SELECT id FROM usuarios WHERE LOWER(correo) = LOWER(:correo)"),
                {"correo": correo_clean}
            ).fetchone()
            if check_email:
                raise HTTPException(status_code=400, detail="El correo electrónico ya se encuentra registrado.")

            check_cedula = connection.execute(
                text("SELECT id FROM usuarios WHERE numero_documento = :num_doc"),
                {"num_doc": num_doc}
            ).fetchone()
            if check_cedula:
                raise HTTPException(status_code=400, detail="El número de cédula ya se encuentra registrado.")

            nuevo_numero_cuenta = generar_numero_cuenta()
            hashed_pwd = hash_password(user.password)

            insert_query = text("""
                INSERT INTO usuarios (nombre, apellido, correo, tipo_documento, numero_documento, celular, username, password_hash, numero_cuenta, saldo_disponible, verificado)
                VALUES (:nombre, :apellido, :correo, :tipo_documento, :numero_documento, :celular, :username, :password_hash, :numero_cuenta, :saldo_disponible, :verificado)
            """)

            connection.execute(insert_query, {
                "nombre": user.nombre.strip(),
                "apellido": user.apellido.strip(),
                "correo": correo_clean,
                "tipo_documento": tipo_doc,
                "numero_documento": num_doc,
                "celular": user.celular.strip() if user.celular else "",
                "username": username_clean,
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
        user_input = credenciales.username.strip()
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT * FROM usuarios WHERE LOWER(username) = LOWER(:val)"),
                {"val": user_input}
            ).fetchone()

            if not result:
                result = connection.execute(
                    text("SELECT * FROM usuarios WHERE LOWER(correo) = LOWER(:val)"),
                    {"val": user_input}
                ).fetchone()

            if not result:
                raise HTTPException(status_code=401, detail="Credenciales incorrectas.")

            usuario = dict(result._mapping)

        if not verify_password(credenciales.password, usuario.get("password_hash") or ""):
            raise HTTPException(status_code=401, detail="Credenciales incorrectas.")

        usuario_id = usuario.get("id")
        nombre_val = usuario.get("nombre") or ""
        apellido_val = usuario.get("apellido") or ""
        nombre_completo = f"{nombre_val} {apellido_val}".strip()

        saldo_raw = usuario.get("saldo_disponible")
        saldo_num = float(saldo_raw) if saldo_raw is not None else 0.0

        num_cuenta = usuario.get("numero_cuenta") or "0185-0000-0000"

        # Cargar las tarjetas del usuario al iniciar sesión
        tarjetas_list = []
        with engine.connect() as connection:
            t_res = connection.execute(
                text("SELECT id, banco, numero_enmascarado, fecha_exp, nfc_habilitado, compras_web_habilitadas FROM tarjetas WHERE usuario_id = :uid"),
                {"uid": usuario_id}
            ).fetchall()
            tarjetas_list = [dict(row._mapping) for row in t_res]

        return LoginResponse(
            token="bearer_token_simulado",
            message="Inicio de sesión exitoso.",
            usuario_id=usuario_id,
            nombre=nombre_completo if nombre_completo else (usuario.get("username") or "Usuario"),
            numero_cuenta=num_cuenta,
            saldo_disponible=saldo_num,
            tarjetas=tarjetas_list
        )
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ERROR REAL LOGIN: {str(e)}")

# --- ENDPOINTS DE TARJETAS ---

@app.get("/api/tarjetas/{usuario_id}")
def obtener_tarjetas_usuario(usuario_id: int):
    if not engine:
        raise HTTPException(status_code=500, detail="Base de datos no conectada.")
    try:
        with engine.connect() as connection:
            result = connection.execute(
                text("SELECT id, banco, numero_enmascarado, fecha_exp, nfc_habilitado, compras_web_habilitadas FROM tarjetas WHERE usuario_id = :uid"),
                {"uid": usuario_id}
            ).fetchall()
            tarjetas = [dict(row._mapping) for row in result]
        return {"status": "success", "tarjetas": tarjetas}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al obtener tarjetas: {str(e)}")

@app.post("/api/tarjetas/registrar")
def registrar_tarjeta(tarjeta: TarjetaCreateRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="Base de datos no conectada.")
    try:
        num_limpio = tarjeta.numero_tarjeta.strip().replace(" ", "")
        if len(num_limpio) < 12:
            raise HTTPException(status_code=400, detail="Número de tarjeta inválido.")
        
        enmascarado = f"•••• •••• •••• {num_limpio[-4:]}"
        cvv_hash = hash_password(tarjeta.cvv) # CVV cifrado de forma segura

        with engine.connect() as connection:
            query = text("""
                INSERT INTO tarjetas (usuario_id, banco, numero_enmascarado, fecha_exp, cvv_cifrado, nfc_habilitado, compras_web_habilitadas)
                VALUES (:uid, :banco, :num_enm, :f_exp, :cvv, :nfc, :web)
            """)
            connection.execute(query, {
                "uid": tarjeta.usuario_id,
                "banco": tarjeta.banco.strip(),
                "num_enm": enmascarado,
                "f_exp": tarjeta.fecha_exp.strip(),
                "cvv": cvv_hash,
                "nfc": tarjeta.nfc_habilitado,
                "web": tarjeta.compras_web_habilitadas
            })
            connection.commit()
        return {"success": True, "message": "Tarjeta registrada exitosamente."}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al registrar tarjeta: {str(e)}")

@app.put("/api/tarjetas/{tarjeta_id}/nfc")
def actualizar_nfc_tarjeta(tarjeta_id: int, body: TarjetaToggleNfcRequest):
    if not engine:
        raise HTTPException(status_code=500, detail="Base de datos no conectada.")
    try:
        with engine.connect() as connection:
            connection.execute(
                text("UPDATE tarjetas SET nfc_habilitado = :nfc WHERE id = :tid"),
                {"nfc": body.nfc_habilitado, "tid": tarjeta_id}
            )
            connection.commit()
        return {"success": True, "message": "Estado NFC actualizado correctamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al actualizar NFC: {str(e)}")

@app.delete("/api/tarjetas/{tarjeta_id}")
def eliminar_tarjeta(tarjeta_id: int):
    if not engine:
        raise HTTPException(status_code=500, detail="Base de datos no conectada.")
    try:
        with engine.connect() as connection:
            connection.execute(
                text("DELETE FROM tarjetas WHERE id = :tid"),
                {"tid": tarjeta_id}
            )
            connection.commit()
        return {"success": True, "message": "Tarjeta eliminada exitosamente."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error al eliminar tarjeta: {str(e)}")
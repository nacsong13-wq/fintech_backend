from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
import models
import schemas
from database import engine, get_db

# Crea las tablas en la base de datos si no existen
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Fintech NFC Backend", version="1.0.0")

@app.get("/")
def read_root():
    return {"message": "API Backend NFC Fintech funcionando correctamente"}

@app.post("/api/auth/login")
def login_user(request: schemas.LoginRequest, db: Session = Depends(get_db)):
    # Busca al usuario por su 'usuario' (username) o por su 'correo'
    db_user = db.query(models.User).filter(
        (models.User.usuario == request.username) | (models.User.correo == request.username)
    ).first()
    
    # Valida si el usuario existe y si la contraseña coincide
    if not db_user or db_user.password_hash != request.password:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, 
            detail="Credenciales incorrectas"
        )
    
    return {
        "token": "fake-jwt-token-xyz",
        "message": "Inicio de sesión exitoso",
        "nombre": db_user.nombre
    }

@app.post("/api/auth/register", status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    # Verifica si el usuario o correo ya se encuentran registrados
    existing_user = db.query(models.User).filter(
        (models.User.usuario == user.username) | (models.User.correo == user.correo)
    ).first()
    
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="El usuario o el correo ya están registrados"
        )
    
    # Crea el nuevo registro usando los campos exactos de tu tabla en Supabase
    new_user = models.User(
        usuario=user.username,
        password_hash=user.password,  # Nota: Almacena en texto plano tal como lo configuraste en la base de datos
        nombre=user.nombre,
        apellido=user.apellido,
        correo=user.correo,
        tipo_documento="V",          # Valor por defecto o ajústalo según tu UI
        numero_documento=user.cedula,
        celular=""                   # Puedes agregarlo al formulario si lo requieres luego
    )
    
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    return {
        "message": "Usuario registrado exitosamente",
        "success": True
    }
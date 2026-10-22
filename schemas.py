from pydantic import BaseModel
from typing import Optional

# --- Esquemas de Login ---
class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: Optional[str] = None
    message: Optional[str] = None
    nombre: Optional[str] = None

# --- Esquemas de Registro ---
class UserCreate(BaseModel):
    nombre: str
    apellido: str
    correo: str
    cedula: str
    username: str
    password: str

class RegisterResponse(BaseModel):
    message: Optional[str] = None
    success: Optional[bool] = None
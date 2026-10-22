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
class UserCreate(BaseModel.model_config = { "protected_namespaces": () } if hasattr(BaseModel, "model_config") else {}): # type: ignore
    nombre: str
    apellido: str
    correo: str
    cedula: str
    username: str
    password: str

class RegisterResponse(BaseModel):
    message: Optional[str] = None
    success: Optional[bool] = None
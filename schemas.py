from pydantic import BaseModel
from typing import Optional

class LoginRequest(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    nombre: str
    apellido: str
    correo: str
    cedula: str
    celular: Optional[str] = ""

class GenericResponse(BaseModel):
    message: str
    success: bool
from sqlalchemy import Column, Integer, String
from database import Base

class User(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    usuario = Column("user", String, unique=True, index=True)
    password_hash = Column(String)
    nombre = Column(String)
    apellido = Column(String)
    correo = Column(String)
    tipo_documento = Column(String)
    numero_documento = Column(String)
    celular = Column(String)
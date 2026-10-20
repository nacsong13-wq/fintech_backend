from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.orm import Session
import models
import schemas
from database import engine, get_db

models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="Fintech NFC Backend", version="1.0.0")

@app.get("/")
def read_root():
    return {"message": "API Backend NFC Fintech funcionando correctamente"}

@app.post("/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    
    new_user = models.User(
        email=user.email,
        hashed_password=user.password,
        nfc_card_id=user.nfc_card_id,
        balance=0.0
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
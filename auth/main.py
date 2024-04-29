from fastapi import FastAPI, HTTPException, Response, Depends, status, Form
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pymongo import MongoClient
from passlib.context import CryptContext
import jwt, os
from datetime import datetime, timedelta
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional
from fastapi.middleware.cors import CORSMiddleware
 
# Configuration
load_dotenv()
MONGO_DB_URI = os.getenv("MONGODB_URI")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_SECRET_TOKEN = os.getenv("ACCESS_SECRET_TOKEN")
ACCESS_TOKEN_EXPIRE_MINUTES = 10

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
client = MongoClient(MONGO_DB_URI)
db = client['jmsk-hosting-db']
users_collection = db.user_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class UserCreate(BaseModel):
    username: str
    email: str
    password: str
    role: Optional[str] = "user"
    services: Optional[list[str]] = []
    createdAt: Optional[datetime] = datetime.utcnow()

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def authenticate_user(email: str, password: str):
    user = users_collection.find_one({"email": email})
    if not user:
        return False
    if not verify_password(password, user['password']):
        return False
    return user

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, ACCESS_SECRET_TOKEN, algorithm=ALGORITHM)
    return encoded_jwt

#form req
@app.post("/login", response_model=str)
async def login_for_access_token(username:str=Form(...), password:str=Form(...)):
    user = authenticate_user(username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": str(user["_id"])}, expires_delta=access_token_expires
    )
    response = Response(content="Login successful", media_type="application/json")
    response.set_cookie(key="accessToken", value=access_token, httponly=True)
    return response

#raw req
@app.post("/register")
async def register(user: UserCreate):
    existing_user = users_collection.find_one({"$or": [{"email": user.email}, {"username": user.username}]})
    if existing_user:
        raise HTTPException(status_code=400, detail="Username or Email already exists")
    
    hashed_password = get_password_hash(user.password)
    new_user = {
        "username": user.username, 
        "email": user.email,
        "password": hashed_password, 
        "role": user.role,
        "services": user.services,
        "createdAt": user.createdAt}
    users_collection.insert_one(new_user)
    return {"message": "User created successfully", "user": {"username": user.username, "email": user.email}}

@app.post("/logout")
async def logout():
    response = Response(content="Logout successful", media_type="application/json")
    response.delete_cookie(key="accessToken")
    return response

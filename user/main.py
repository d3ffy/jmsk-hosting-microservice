from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer
from fastapi.middleware.cors import CORSMiddleware
import jwt
from jwt import PyJWTError
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
import os
from dotenv import load_dotenv
from typing import Optional
from datetime import datetime, timedelta

load_dotenv()
MONGODB_URI = os.getenv('MONGODB_URI')
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_SECRET_TOKEN = os.getenv("ACCESS_SECRET_TOKEN")
client = AsyncIOMotorClient(MONGODB_URI)
db = client['jmsk-hosting-db']

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

class ServiceCart(BaseModel):
    serviceId: str
    price: float
    duration: Optional[int] = 30

class Service(BaseModel):
    serviceId: str
    duration: Optional[datetime] = datetime.utcnow() + timedelta(days=30)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(ftoken, ACCESS_SECRET_TOKEN, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")
        return user_id
    except PyJWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials")

@app.post("/users/services/", response_model=Service)
async def add_service_to_user(service: Service, user_id: str = Depends(get_current_user)):
    user_oid = ObjectId(user_id)
    service_dict = service.dict(by_alias=True)
    service_dict['_id'] = ObjectId()
    updated_user = await db.user_db.update_one(
        {"_id": user_oid},
        {"$push": {"services": service_dict},
         "$set": {"duration": service.duration}}  # Set the duration in the document
    )
    if updated_user.modified_count == 1:
        return service
    raise HTTPException(status_code=500, detail="Failed to add service to user")

@app.get("/users/services/")
async def get_services_from_user(user_id: str = Depends(get_current_user)):
    user_oid = ObjectId(user_id)
    user = await db.user_db.find_one({"_id": user_oid})
    services = user.get("services", [])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return [{"serviceId": service["serviceId"], "duration": service["duration"]} for service in services]

@app.delete("/users/services/{service_id}")
async def remove_service_from_user(service_id: str, user_id: str = Depends(get_current_user)):
    user_oid = ObjectId(user_id)
    service_oid = ObjectId(service_id)
    result = await db.user_db.update_one(
        {"_id": user_oid},
        {"$pull": {"services": {"_id": service_oid}}}
    )
    if result.modified_count == 1:
        return {"message": "Service removed successfully"}
    raise HTTPException(status_code=404, detail="Service not found or already removed")

@app.post("/users/cart/", response_model=ServiceCart)
async def add_item_to_cart(item: ServiceCart, user_id: str = Depends(get_current_user)):
    user_oid = ObjectId(user_id)
    item_dict = item.dict(by_alias=True)
    item_dict['_id'] = ObjectId()  # Ensure the item has a unique MongoDB ObjectId
    updated_user = await db.user_db.update_one(
        {"_id": user_oid},
        {"$push": {"cart": item_dict}}
    )
    if updated_user.modified_count == 1:
        return item
    raise HTTPException(status_code=500, detail="Failed to add item to cart")

@app.get("/users/cart/")
async def get_cart_items(user_id: str = Depends(get_current_user)):
    user_oid = ObjectId(user_id)
    user = await db.user_db.find_one({"_id": user_oid})
    cart_items = user.get("cart", [])
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return [{"_id": str(item["_id"]), "serviceId": item["serviceId"], "price": item["price"]} for item in cart_items]

@app.delete("/users/cart/{item_id}")
async def remove_item_from_cart(item_id: str, user_id: str = Depends(get_current_user)):
    user_oid = ObjectId(user_id)
    result = await db.user_db.update_one(
        {"_id": user_oid},
        {"$pull": {"cart": {"serviceId": item_id}}}
    )
    if result.modified_count == 1:
        return {"message": "Item removed successfully"}
    raise HTTPException(status_code=404, detail="Item not found or already removed")

@app.delete("/users/cart/")
async def remove_all_item_from_cart(user_id: str = Depends(get_current_user)):
    user_oid = ObjectId(user_id)
    result = await db.user_db.update_one(
        {"_id": user_oid},
        {"$set": {"cart": []}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="No items found in cart or user not found")
    
    return {"message": "All items in cart removed successfully"}

@app.get("/getAllUsers")
async def get_all_users():
    users = await db.user_db.find().to_list(None)
    return [{
        "userId": user["_id"].__str__(),
        "username": user["username"],
        "email": user["email"],
        } 
        for user in users
    ]
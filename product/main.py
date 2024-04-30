from fastapi import FastAPI, HTTPException, status
from bson import ObjectId
from pydantic import BaseModel
from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware
import requests
import httpx

class Service(BaseModel):
    serviceId: str
    name: str
    description: str
    price: float
    duration: int

class Review(BaseModel):
    text: str

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

load_dotenv()
MONGODB_URI = os.getenv('MONGODB_URI')
client = AsyncIOMotorClient(MONGODB_URI)
db = client['jmsk-hosting-db']

from typing import Optional

class ServiceModel(BaseModel):
    serviceId: Optional[str] = None
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    duration: Optional[int] = None

@app.post("/product/", response_model=ServiceModel, status_code=status.HTTP_201_CREATED)
async def add_service(service: ServiceModel):
    existing_service = await db.service_db.find_one({"serviceId": service.serviceId})
    if existing_service:
        raise HTTPException(status_code=400, detail="Service already exists")
    await db.service_db.insert_one(service.dict())
    return service

@app.delete("/product/{serviceId}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_service(serviceId: str):
    result = await db.service_db.delete_one({"serviceId": serviceId})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Service not found")
    return {"message": "Service deleted successfully"}

@app.get("/product/", response_model=list[ServiceModel])
async def get_all_services():
    services = await db.service_db.find().to_list(None)
    return services

@app.patch("/product/{serviceId}", response_model=ServiceModel)
async def update_service(serviceId: str, service: ServiceModel):
    existing_service = await db.service_db.find_one({"serviceId": serviceId})
    if not existing_service:
        raise HTTPException(status_code=404, detail="Service not found")
    # Create a dictionary of the fields to update, excluding any that are None
    update_data = {k: v for k, v in service.dict(exclude_unset=True).items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")
    await db.service_db.update_one({"serviceId": serviceId}, {"$set": update_data})
    # Get the updated service data
    updated_service = await db.service_db.find_one({"serviceId": serviceId})
    return updated_service

@app.get("/product/{serviceId}", response_model=ServiceModel)
async def get_product_detail(serviceId: str):
    service = await db.service_db.find_one({"serviceId": serviceId})
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return service

@app.post("/postReview/")
async def post_review(review: Review):
    url = "https://api.aiforthai.in.th/ssense"
    data = {'text': review.text}
    headers = {'Apikey': "3vA3wfXxuLwX9L7vvCluzFViqbiRtErj"}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, data=data, headers=headers)
            response.raise_for_status()
            result_data = response.json()
        except httpx.RequestError as exc:
            print(f"An error occurred while requesting {exc.request.url!r}.")
            raise HTTPException(status_code=400, detail="Error connecting to sentiment analysis service")
        except httpx.HTTPStatusError as exc:
            print(f"Error response {exc.response.status_code} while requesting {exc.request.url!r}.")
            raise HTTPException(status_code=exc.response.status_code, detail="Sentiment analysis service returned an error")

    sentiment = result_data.get('sentiment', {})
    document = {
        'text': review.text,
        'sentiment': sentiment
    }
    insert_result = await db.review_db.insert_one(document)
    return {"mongo_id": str(insert_result.inserted_id), "text": review.text}
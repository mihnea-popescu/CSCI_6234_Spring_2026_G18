from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from database import get_db, create_tables
from routes import auth, auctions, customers, managers, price_predictor

app = FastAPI(title="Auction House API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
create_tables()

# Include routers
app.include_router(auth.router, prefix="/auth", tags=["authentication"])
app.include_router(auctions.router, prefix="/auctions", tags=["auctions"])
app.include_router(customers.router, prefix="/customers", tags=["customers"])
app.include_router(managers.router, prefix="/managers", tags=["managers"])
app.include_router(price_predictor.router, prefix="/price", tags=["price"])

@app.get("/")
async def root():
    return {"message": "Auction House API"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
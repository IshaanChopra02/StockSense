import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from pydantic import BaseModel
from datetime import datetime
from typing import Optional

# 1. Database Setup
if not os.path.exists("static"):
    os.makedirs("static")

SQLALCHEMY_DATABASE_URL = "sqlite:///./stocksense.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. Database Models
class Location(Base):
    __tablename__ = "locations"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    sku = Column(String, unique=True, index=True)
    category = Column(String)
    unit_of_measure = Column(String)
    total_stock = Column(Integer, default=0)

class StockMovement(Base):
    __tablename__ = "stock_movements"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    transaction_type = Column(String) 
    quantity = Column(Integer)
    source_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    destination_location_id = Column(Integer, ForeignKey("locations.id"), nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

# 3. Pydantic Schemas
class LocationCreate(BaseModel):
    name: str

class ProductCreate(BaseModel):
    name: str
    sku: str
    category: str
    unit_of_measure: str
    initial_stock: int = 0

class MovementCreate(BaseModel):
    product_id: int
    transaction_type: str 
    quantity: int
    source_location_id: Optional[int] = None
    destination_location_id: Optional[int] = None

# 4. Initialize App
app = FastAPI(title="StockSense API")

app.mount("/static", StaticFiles(directory="static"), name="static")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- FRONTEND ROUTE (Using Absolute Path to guarantee correct file loading) ---
@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    # Forces FastAPI to look for index.html in the exact same folder as this Python script
    base_dir = os.path.dirname(os.path.abspath(__file__))
    index_path = os.path.join(base_dir, "index.html")
    
    try:
        with open(index_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"<h1>Error: Missing File</h1><p>Expected to find index.html at: <br><b>{index_path}</b></p>"

# --- API Endpoints ---
@app.get("/locations/")
def get_locations(db: Session = Depends(get_db)):
    return db.query(Location).all()

@app.get("/products/")
def get_products(db: Session = Depends(get_db)):
    return db.query(Product).all()

@app.post("/products/")
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    product_data = product.model_dump(exclude={"initial_stock"})
    db_product = Product(**product_data, total_stock=product.initial_stock)
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@app.post("/inventory/move/")
def process_stock_movement(movement: MovementCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == movement.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    actual_quantity = movement.quantity

    if movement.transaction_type == "Receipt":
        product.total_stock += movement.quantity
    elif movement.transaction_type == "Delivery":
        if product.total_stock < movement.quantity:
            raise HTTPException(status_code=400, detail="Not enough stock")
        product.total_stock -= movement.quantity
        actual_quantity = -movement.quantity
    else:
        raise HTTPException(status_code=400, detail="Invalid type")

    ledger_entry = StockMovement(
        product_id=product.id,
        transaction_type=movement.transaction_type,
        quantity=actual_quantity,
        source_location_id=movement.source_location_id,
        destination_location_id=movement.destination_location_id
    )
    db.add(ledger_entry)
    db.commit()
    db.refresh(product)
    
    return {"status": "Success", "product": product.name, "new_total_stock": product.total_stock}

@app.get("/inventory/ledger/")
def get_ledger(db: Session = Depends(get_db)):
    return db.query(StockMovement).order_by(StockMovement.id.desc()).all()

@app.get("/dashboard/")
def get_dashboard(db: Session = Depends(get_db)):
    total_products = db.query(Product).count()
    low_stock_items = db.query(Product).filter(Product.total_stock < 10).all()
    return {
        "Total Products in Stock": total_products,
        "Low Stock Alerts": [p.name for p in low_stock_items]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)
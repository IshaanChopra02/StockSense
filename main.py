import os
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine, Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import sessionmaker, Session, declarative_base
from pydantic import BaseModel
from datetime import datetime
import random

if not os.path.exists("static"):
    os.makedirs("static")

SQLALCHEMY_DATABASE_URL = "sqlite:///./stocksense.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

otp_store = {}
pending_users = {} # Naye users ko OTP verify hone tak hold karne ke liye

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    password = Column(String)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), default=1)
    name = Column(String, index=True)
    sku = Column(String, index=True)
    category = Column(String)
    unit_of_measure = Column(String)
    total_stock = Column(Integer, default=0)

class StockMovement(Base):
    __tablename__ = "stock_movements"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), default=1)
    product_id = Column(Integer, ForeignKey("products.id"))
    transaction_type = Column(String) 
    quantity = Column(Integer)
    timestamp = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(bind=engine)

db_session = SessionLocal()
if not db_session.query(User).filter(User.email == "test@stocksense.com").first():
    default_user = User(email="test@stocksense.com", password="password123")
    db_session.add(default_user)
    db_session.commit()
db_session.close()

class AuthSchema(BaseModel):
    email: str
    password: str

class RegisterSchema(BaseModel):
    name: str
    email: str
    password: str

class OtpVerifySchema(BaseModel):
    email: str
    otp: str

class ProductCreate(BaseModel):
    user_id: int = 1
    name: str
    sku: str
    category: str
    unit_of_measure: str
    initial_stock: int = 0

class MovementCreate(BaseModel):
    user_id: int = 1
    product_id: int
    transaction_type: str 
    quantity: int

app = FastAPI(title="StockSense API")
app.mount("/static", StaticFiles(directory="static"), name="static")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/login", response_class=HTMLResponse)
def serve_login():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "login.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>login.html not found</h1>", 404

@app.get("/app", response_class=HTMLResponse)
def serve_app():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(base_dir, "index.html")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>index.html not found</h1>", 404

@app.get("/", response_class=HTMLResponse)
def serve_root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login")

@app.get("/logout")
def logout():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login")

# --- LOGIN ROUTES ---
@app.post("/api/auth/login")
def login(auth: AuthSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == auth.email).first()
    if not user:
        raise HTTPException(status_code=404, detail="Account not found. Please create an account first.")
    elif user.password != auth.password:
        raise HTTPException(status_code=400, detail="Incorrect password")
    
    otp = str(random.randint(100000, 999999))
    otp_store[auth.email] = otp
    print(f"\n======================")
    print(f"🔑 LOGIN OTP for {auth.email}: {otp}")
    print(f"======================\n")
    return {"requires_otp": True, "message": "OTP sent to terminal"}

@app.post("/api/auth/verify-login-otp")
def verify_login_otp(data: OtpVerifySchema, db: Session = Depends(get_db)):
    if data.email in otp_store and otp_store[data.email] == data.otp:
        user = db.query(User).filter(User.email == data.email).first()
        return {"status": "Success", "user_id": user.id if user else 1}
    raise HTTPException(status_code=400, detail="Invalid OTP")

# --- REGISTRATION ROUTES ---
@app.post("/api/auth/register")
def register(data: RegisterSchema, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == data.email).first()
    if user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    otp = str(random.randint(100000, 999999))
    otp_store[data.email] = otp
    pending_users[data.email] = data
    
    print(f"\n======================")
    print(f"🆕 REGISTRATION OTP for {data.email}: {otp}")
    print(f"======================\n")
    return {"requires_otp": True, "message": "OTP sent to terminal"}

@app.post("/api/auth/verify-register-otp")
def verify_register_otp(data: OtpVerifySchema, db: Session = Depends(get_db)):
    if data.email in otp_store and otp_store[data.email] == data.otp:
        if data.email in pending_users:
            user_data = pending_users[data.email]
            new_user = User(email=user_data.email, password=user_data.password)
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            return {"status": "Success", "user_id": new_user.id}
    raise HTTPException(status_code=400, detail="Invalid Registration OTP")

# --- INVENTORY ROUTES ---
@app.get("/products/")
def get_products(user_id: int = 1, db: Session = Depends(get_db)):
    return db.query(Product).filter(Product.user_id == user_id).all()

@app.post("/products/")
def create_product(product: ProductCreate, db: Session = Depends(get_db)):
    db_product = Product(
        user_id=product.user_id,
        name=product.name,
        sku=product.sku,
        category=product.category,
        unit_of_measure=product.unit_of_measure,
        total_stock=product.initial_stock
    )
    db.add(db_product)
    db.commit()
    db.refresh(db_product)
    return db_product

@app.post("/inventory/move/")
def process_stock_movement(movement: MovementCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == movement.product_id, Product.user_id == movement.user_id).first()
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
    
    ledger_entry = StockMovement(
        user_id=movement.user_id,
        product_id=product.id,
        transaction_type=movement.transaction_type,
        quantity=actual_quantity
    )
    db.add(ledger_entry)
    db.commit()
    db.refresh(product)
    return {"status": "Success", "product": product.name, "new_total_stock": product.total_stock}

@app.get("/inventory/ledger/")
def get_ledger(user_id: int = 1, db: Session = Depends(get_db)):
    return db.query(StockMovement).filter(StockMovement.user_id == user_id).order_by(StockMovement.id.desc()).all()

@app.get("/dashboard/")
def get_dashboard(user_id: int = 1, db: Session = Depends(get_db)):
    total_products = db.query(Product).filter(Product.user_id == user_id).count()
    low_stock_items = db.query(Product).filter(Product.user_id == user_id, Product.total_stock < 10).all()
    return {
        "Total Products in Stock": total_products,
        "Low Stock Alerts": [p.name for p in low_stock_items]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)
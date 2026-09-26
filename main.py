import os
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()

class LoginData(BaseModel):
    email: str
    password: str

@app.get("/login", response_class=HTMLResponse)
def get_login():
    if os.path.exists("login.html"):
        with open("login.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>login.html file missing!</h1>", 404

@app.get("/app", response_class=HTMLResponse)
def get_app():
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>index.html file missing!</h1>", 404

@app.post("/api/auth/login")
def login(data: LoginData):
    # Success mockup for hackathon UI showcase
    return {"status": "Success", "redirect": "/app"}

@app.get("/dashboard/")
def get_dashboard():
    return {"Total Products in Stock": 12, "Low Stock Alerts": []}

@app.get("/")
def read_root():
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url="/login")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8002)
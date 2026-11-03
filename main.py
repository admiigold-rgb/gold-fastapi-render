import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from typing import Optional
from database import supabase

app = FastAPI(title="Gold Branch Management System - Phase 1", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Pydantic Schemas
class NewCustomerKYC(BaseModel):
    name: str = Field(..., description="வாடிக்கையாளர் பெயர்")
    phone: str = Field(..., description="மொபைல் எண்")
    aadhaar_no: Optional[str] = Field(None, description="ஆதார் எண்")
    pan_no: Optional[str] = Field(None, description="பான் எண்")
    address: Optional[str] = Field(None, description="முகவரி")
    branch_name: str = Field(..., description="கிளையின் பெயர்")

class CustomerUpdateRequest(BaseModel):
    customer_id: int = Field(..., description="வாடிக்கையாளர் அடையாள எண்")
    branch_name: str = Field(..., description="கிளை பெயர்")
    requested_changes: dict = Field(..., description="மாற்ற வேண்டிய புதிய தகவல்கள்")

class CustomerVisitEntry(BaseModel):
    customer_id: int = Field(..., description="வாடிக்கையாளர் அடையாள எண்")
    branch_name: str = Field(..., description="கிளை பெயர்")
    purpose: Optional[str] = Field("REGULAR_TRANSACTION", description="வருகையின் நோக்கம்")

@app.get("/")
def serve_ui():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "FastAPI சர்வர் இயங்குகிறது."}

# 1. வாடிக்கையாளர் தேடல் API (மொபைல் எண் அல்லது பெயர் மூலம்)
@app.get("/api/customer/search")
def search_customer(query: str):
    try:
        # எண் எனில் போன் நம்பரிலும், எழுத்து எனில் பெயரிலும் தேடும்
        if query.isdigit():
            res = supabase.table("customers").select("*").ilike("phone", f"%{query}%").limit(5).execute()
        else:
            res = supabase.table("customers").select("*").ilike("name", f"%{query}%").limit(5).execute()
        
        return {"status": "success", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"தேடல் பிழை: {str(e)}")

# 2. மாற்றம் இல்லாத பழைய வாடிக்கையாளருக்கு வருகைப் பதிவு (Visit Entry)
@app.post("/api/customer/visit")
def log_visit(data: CustomerVisitEntry):
    try:
        record = {
            "customer_id": data.customer_id,
            "branch": data.branch_name,
            "purpose": data.purpose
        }
        res = supabase.table("customer_visits").insert(record).execute()
        return {"status": "success", "message": "வருகை வெற்றிகரமாகப் பதிவானது", "visit_id": res.data[0].get("id") if res.data else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"வருகைப் பதிவு பிழை: {str(e)}")

# 3. வாடிக்கையாளர் விபர மாற்றக் கோரிக்கை (Approval Request)
@app.post("/api/customer/request-update")
def request_update(data: CustomerUpdateRequest):
    try:
        record = {
            "customer_id": data.customer_id,
            "branch": data.branch_name,
            "changes": data.requested_changes,
            "status": "PENDING"
        }
        res = supabase.table("customer_update_requests").insert(record).execute()
        return {"status": "success", "message": "மாற்றக் கோரிக்கை தலைமை அலுவலக ஒப்புதலுக்கு அனுப்பப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"கோரிக்கை பதிவு பிழை: {str(e)}")

# 4. புதிய வாடிக்கையாளர் KYC பதிவு
@app.post("/api/customer/new-kyc")
def create_kyc(data: NewCustomerKYC):
    try:
        # ஏற்கனவே உள்ளாரா எனச் சரிபார்த்தல்
        existing = supabase.table("customers").select("id").eq("phone", data.phone).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail="இந்த மொபைல் எண் ஏற்கனவே பயன்பாட்டில் உள்ளது.")

        record = {
            "name": data.name,
            "phone": data.phone,
            "aadhaar_no": data.aadhaar_no,
            "pan_no": data.pan_no,
            "address": data.address,
            "branch": data.branch_name,
            "status": "PENDING_APPROVAL"
        }
        res = supabase.table("customers").insert(record).execute()
        return {"status": "success", "message": "புதிய KYC பதிவு சேமிக்கப்பட்டது. தலைமை ஒப்புதலுக்குக் காத்திருக்கிறது.", "customer_id": res.data[0].get("id") if res.data else None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KYC பதிவு பிழை: {str(e)}")

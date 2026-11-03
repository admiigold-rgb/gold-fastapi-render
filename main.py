import os
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from database import supabase

app = FastAPI(
    title="Gold Branch Management - Safe Test Environment",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

# Data Schemas
class NewCustomerKYC(BaseModel):
    name: str = Field(..., description="வாடிக்கையாளர் பெயர்")
    mobile: str = Field(..., description="முதன்மை மொபைல் எண்")
    mobile2: Optional[str] = Field(None, description="இரண்டாவது மொபைல் எண்")
    guardian_name: Optional[str] = Field(None, description="தந்தை / கணவர் பெயர்")
    address: Optional[str] = Field(None, description="முழு முகவரி")
    branch_id: int = Field(default=1, description="கிளை எண்")

class CustomerUpdateRequest(BaseModel):
    customer_id: int = Field(..., description="வாடிக்கையாளர் ஐடி")
    branch_id: int = Field(default=1, description="கிளை ஐடி")
    requested_changes: Dict[str, Any] = Field(..., description="மாற்றப்பட வேண்டிய விபரங்கள்")

class CustomerVisitEntry(BaseModel):
    customer_id: int = Field(..., description="வாடிக்கையாளர் ஐடி")
    branch_id: int = Field(default=1, description="கிளை ஐடி")
    purpose: Optional[str] = Field(default="REGULAR_TRANSACTION", description="வருகையின் நோக்கம்")

@app.get("/")
def serve_ui():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "FastAPI சோதனை சர்வர் இயங்குகிறது."}

# 1. சோதனை வாடிக்கையாளர் தேடல் API (test_customers-ல் மட்டும் தேடும்)
@app.get("/api/customer/search")
def search_customer(query: str = Query(..., min_length=1)):
    try:
        clean_query = query.strip()
        if clean_query.isdigit():
            res = (
                supabase.table("test_customers")
                .select("id, name, mobile, mobile2, guardian_name, address, branch_id, kyc_status, is_active")
                .ilike("mobile", f"%{clean_query}%")
                .limit(10)
                .execute()
            )
        else:
            res = (
                supabase.table("test_customers")
                .select("id, name, mobile, mobile2, guardian_name, address, branch_id, kyc_status, is_active")
                .ilike("name", f"%{clean_query}%")
                .limit(10)
                .execute()
            )
        return {"status": "success", "count": len(res.data), "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"சோதனைத் தேடல் பிழை: {str(e)}")

# 2. சோதனை புதிய KYC பதிவு (test_customers-ல் மட்டும் பதியும்)
@app.post("/api/customer/new-kyc")
def create_kyc(data: NewCustomerKYC):
    try:
        clean_mobile = data.mobile.strip()
        existing = (
            supabase.table("test_customers")
            .select("id, name")
            .eq("mobile", clean_mobile)
            .execute()
        )
        if existing.data:
            raise HTTPException(
                status_code=400,
                detail=f"இந்த மொபைல் எண் ஏற்கனவே சோதனைப் பதிவில் உள்ளது ({existing.data[0]['name']})."
            )

        record = {
            "name": data.name.strip(),
            "mobile": clean_mobile,
            "mobile2": data.mobile2.strip() if data.mobile2 else None,
            "guardian_name": data.guardian_name.strip() if data.guardian_name else None,
            "address": data.address.strip() if data.address else None,
            "branch_id": data.branch_id,
            "kyc_status": "PENDING",
            "is_active": True
        }

        res = supabase.table("test_customers").insert(record).execute()
        return {
            "status": "success",
            "message": "சோதனை KYC வெற்றிகரமாகச் சேமிக்கப்பட்டது.",
            "data": res.data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"சோதனை KYC பிழை: {str(e)}")

# 3. சோதனை வருகைப் பதிவு (test_customer_visits-ல் மட்டும் பதியும்)
@app.post("/api/customer/visit")
def log_customer_visit(data: CustomerVisitEntry):
    try:
        record = {
            "customer_id": data.customer_id,
            "branch_id": data.branch_id,
            "purpose": data.purpose
        }
        res = supabase.table("test_customer_visits").insert(record).execute()
        return {
            "status": "success",
            "message": "சோதனை வருகை வெற்றிகரமாகப் பதிவானது.",
            "data": res.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"சோதனை வருகைப் பதிவு பிழை: {str(e)}")

# 4. சோதனை விபர மாற்றக் கோரிக்கை (test_customer_update_requests-ல் பதியும்)
@app.post("/api/customer/request-update")
def request_customer_update(data: CustomerUpdateRequest):
    try:
        record = {
            "customer_id": data.customer_id,
            "branch_id": data.branch_id,
            "requested_changes": data.requested_changes,
            "status": "PENDING"
        }
        res = supabase.table("test_customer_update_requests").insert(record).execute()
        return {
            "status": "success",
            "message": "சோதனை மாற்றக் கோரிக்கை சேமிக்கப்பட்டது.",
            "data": res.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"சோதனை மாற்றக் கோரிக்கை பிழை: {str(e)}")

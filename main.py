import os
from typing import Optional, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from database import supabase

app = FastAPI(
    title="Gold Branch Management System - Phase 1",
    version="1.0.0",
    description="Branch Customer Visit, KYC, and Profile Verification API"
)

# CORS அனுமதி
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static கோப்புறையை இணைத்தல் (Frontend UI)
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")


# --- Pydantic Data Schemas ---

class NewCustomerKYC(BaseModel):
    name: str = Field(..., description="வாடிக்கையாளர் பெயர்")
    mobile: str = Field(..., description="முதன்மை மொபைல் எண்")
    mobile2: Optional[str] = Field(None, description="இரண்டாவது மொபைல் எண்")
    guardian_name: Optional[str] = Field(None, description="தந்தை / கணவர் பெயர்")
    address: Optional[str] = Field(None, description="முழு முகவரி")
    branch_id: int = Field(default=1, description="கிளை அடையாள எண் (integer)")


class CustomerUpdateRequest(BaseModel):
    customer_id: int = Field(..., description="வாடிக்கையாளர் ஐடி")
    branch_id: int = Field(default=1, description="கிளை ஐடி")
    requested_changes: Dict[str, Any] = Field(..., description="மாற்றப்பட வேண்டிய விபரங்கள்")


class CustomerVisitEntry(BaseModel):
    customer_id: int = Field(..., description="வாடிக்கையாளர் ஐடி")
    branch_id: int = Field(default=1, description="கிளை ஐடி")
    purpose: Optional[str] = Field(default="REGULAR_TRANSACTION", description="வருகையின் நோக்கம்")


# --- Endpoints ---

@app.get("/")
def serve_ui():
    """முகப்புத் திரையைக் காண்பித்தல்"""
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "FastAPI சர்வர் இயங்குகிறது. static/index.html கோப்பு இணைக்கப்படவில்லை."}


@app.get("/health")
def health_check():
    """சர்வர் நிலை சரிபார்ப்பு"""
    return {"status": "active", "service": "Gold Branch API"}


@app.get("/api/customer/search")
def search_customer(query: str = Query(..., min_length=1, description="மொபைல் எண் அல்லது பெயர்")):
    """
    1. வாடிக்கையாளர் தேடல் API:
       எண் எனில் 'mobile'-லும், எழுத்து எனில் 'name'-லும் தேடும்.
    """
    try:
        clean_query = query.strip()
        if clean_query.isdigit():
            res = (
                supabase.table("customers")
                .select("id, customer_code, name, mobile, mobile2, guardian_name, address, branch_id, kyc_status, is_active")
                .ilike("mobile", f"%{clean_query}%")
                .limit(10)
                .execute()
            )
        else:
            res = (
                supabase.table("customers")
                .select("id, customer_code, name, mobile, mobile2, guardian_name, address, branch_id, kyc_status, is_active")
                .ilike("name", f"%{clean_query}%")
                .limit(10)
                .execute()
            )
        
        return {"status": "success", "count": len(res.data), "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"தேடல் பிழை: {str(e)}")


@app.post("/api/customer/new-kyc")
def create_kyc(data: NewCustomerKYC):
    """
    2. புதிய வாடிக்கையாளர் KYC பதிவு:
       'customers' அட்டவணையில் புதிய பதிவைச் சேர்க்கும்.
    """
    try:
        clean_mobile = data.mobile.strip()
        
        # ஏற்கனவே இந்த மொபைல் எண் உள்ளதா எனச் சரிபார்த்தல்
        existing = (
            supabase.table("customers")
            .select("id, name")
            .eq("mobile", clean_mobile)
            .execute()
        )
        if existing.data:
            raise HTTPException(
                status_code=400,
                detail=f"இந்த மொபைல் எண் ஏற்கனவே '{existing.data[0]['name']}' என்ற பெயரில் பதிவாகியுள்ளது."
            )

        # அசல் காலம்களின் பெயர்களுக்கு ஏற்ப தரவை அமைத்தல்
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

        res = supabase.table("customers").insert(record).execute()

        return {
            "status": "success",
            "message": "புதிய வாடிக்கையாளர் KYC வெற்றிகரமாகச் சேமிக்கப்பட்டது. தலைமையக ஒப்புதலுக்குக் காத்திருக்கிறது.",
            "data": res.data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KYC பதிவு பிழை: {str(e)}")


@app.post("/api/customer/visit")
def log_customer_visit(data: CustomerVisitEntry):
    """
    3. வாடிக்கையாளர் வருகைப் பதிவு:
       'customer_visits' அட்டவணையில் பதிவை உருவாக்கும்.
    """
    try:
        record = {
            "customer_id": data.customer_id,
            "branch_id": data.branch_id,
            "purpose": data.purpose
        }
        res = supabase.table("customer_visits").insert(record).execute()
        return {
            "status": "success",
            "message": "வாடிக்கையாளர் வருகை வெற்றிகரமாகப் பதிவானது.",
            "data": res.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"வருகைப் பதிவு பிழை: {str(e)}")


@app.post("/api/customer/request-update")
def request_customer_update(data: CustomerUpdateRequest):
    """
    4. விபர மாற்றக் கோரிக்கை:
       'customer_update_requests' அட்டவணையில் சேமிக்கும்.
    """
    try:
        record = {
            "customer_id": data.customer_id,
            "branch_id": data.branch_id,
            "requested_changes": data.requested_changes,
            "status": "PENDING"
        }
        res = supabase.table("customer_update_requests").insert(record).execute()
        return {
            "status": "success",
            "message": "விபர மாற்றக் கோரிக்கை தலைமையக ஒப்புதலுக்கு அனுப்பப்பட்டது.",
            "data": res.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"மாற்றக் கோரிக்கை பிழை: {str(e)}")

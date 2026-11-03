import os
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from database import supabase

app = FastAPI(
    title="Gold Branch Management - Safe Test Environment",
    version="1.1.0"
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

# Schemas
class NewCustomerKYC(BaseModel):
    name: str = Field(...)
    mobile: str = Field(...)
    mobile2: Optional[str] = None
    guardian_name: Optional[str] = None
    address: Optional[str] = None
    branch_id: int = 1

class CustomerVisitEntry(BaseModel):
    customer_id: int
    branch_id: int = 1
    purpose: Optional[str] = "REGULAR_TRANSACTION"

class OrnamentItem(BaseModel):
    item_type: str
    item_count: int
    gross_weight: float
    net_weight: float
    purity: str

class NewGoldLoanEntry(BaseModel):
    customer_id: int
    branch_id: int = 1
    loan_no: str
    scheme_name: str
    loan_amount: float
    charges_amount: float = 0.0
    photo_url: Optional[str] = None
    items: List[OrnamentItem]

@app.get("/")
def serve_ui():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "FastAPI சர்வர் இயங்குகிறது."}

@app.get("/health")
def health_check():
    return {"status": "active", "service": "Gold Branch API"}

# வாடிக்கையாளர் தேடல்
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
        raise HTTPException(status_code=500, detail=f"தேடல் பிழை: {str(e)}")

# வருகைப் பதிவு
@app.post("/api/customer/visit")
def log_customer_visit(data: CustomerVisitEntry):
    try:
        record = {
            "customer_id": data.customer_id,
            "branch_id": data.branch_id,
            "purpose": data.purpose
        }
        res = supabase.table("test_customer_visits").insert(record).execute()
        return {"status": "success", "message": "வருகை பதிவானது", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"வருகைப் பதிவு பிழை: {str(e)}")

# புதிய KYC பதிவு
@app.post("/api/customer/new-kyc")
def create_kyc(data: NewCustomerKYC):
    try:
        clean_mobile = data.mobile.strip()
        existing = supabase.table("test_customers").select("id, name").eq("mobile", clean_mobile).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail=f"இந்த மொபைல் எண் ஏற்கனவே உள்ளது ({existing.data[0]['name']}).")

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
        return {"status": "success", "message": "KYC வெற்றிகரமாகச் சேமிக்கப்பட்டது.", "data": res.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KYC பதிவு பிழை: {str(e)}")

# நகைக்கடன் புதிய அடகு பதிவு API
@app.post("/api/loan/new-pawn")
def create_new_pawn(data: NewGoldLoanEntry):
    try:
        if not data.items:
            raise HTTPException(status_code=400, detail="குறைந்தது ஒரு நகையாவது பட்டியலில் சேர்க்கப்பட வேண்டும்.")

        total_gross = sum(i.gross_weight for i in data.items)
        total_net = sum(i.net_weight for i in data.items)
        net_payable = data.loan_amount - data.charges_amount

        loan_record = {
            "loan_no": data.loan_no,
            "customer_id": data.customer_id,
            "scheme_name": data.scheme_name,
            "total_gross_weight": round(total_gross, 3),
            "total_net_weight": round(total_net, 3),
            "loan_amount": data.loan_amount,
            "charges_amount": data.charges_amount,
            "net_payable_amount": net_payable,
            "photo_url": data.photo_url,
            "branch_id": data.branch_id,
            "status": "ACTIVE"
        }
        res_loan = supabase.table("test_gold_loans").insert(loan_record).execute()
        new_loan_id = res_loan.data[0]["id"]

        items_payload = []
        for i in data.items:
            items_payload.append({
                "loan_id": new_loan_id,
                "item_type": i.item_type,
                "item_count": i.item_count,
                "gross_weight": i.gross_weight,
                "net_weight": i.net_weight,
                "purity": i.purity
            })
        supabase.table("test_gold_loan_items").insert(items_payload).execute()

        return {
            "status": "success",
            "message": "நகைக்கடன் புதிய அடகு வெற்றிகரமாகச் சேமிக்கப்பட்டது.",
            "loan_id": new_loan_id,
            "net_payable": net_payable
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"அடகுப் பதிவு பிழை: {str(e)}")

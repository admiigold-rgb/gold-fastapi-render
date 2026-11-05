import os
import random
import requests
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from database import supabase

app = FastAPI(
    title="Gold Branch Management - Complete System with Auto Loan No & Cart Controls",
    version="5.0.0"
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

# Fast2SMS OTP Helper
def send_fast2sms_otp(mobile_no: str, otp_code: str, customer_name: str, amount: float, txn_type: str = "receive"):
    try:
        api_key = os.getenv("FAST2SMS_API_KEY", "eBGQYanRZNKVCpMSg3KB5kUxY2QhDnOjxesh3Hqr7FOG792XV9wut4TPhQia")
        clean_mobile = "".join(filter(str.isdigit, str(mobile_no)))[-10:]
        url = "https://www.fast2sms.com/dev/bulkV2"
        headers = {
            "authorization": api_key.strip(),
            "Content-Type": "application/x-www-form-urlencoded",
            "accept": "application/json",
        }
        var_values = f"{customer_name}|{abs(amount):,.2f}|{otp_code}"
        dlt_msg_id = "229683" if txn_type == "receive" else "229682"
        payload = {
            "route": "dlt",
            "sender_id": "MUTUSI",
            "message": dlt_msg_id,
            "variables_values": var_values,
            "numbers": clean_mobile,
            "flash": "0"
        }
        resp = requests.post(url, headers=headers, data=payload, timeout=10)
        res_json = resp.json()
        if res_json.get("return") is True:
            return True, "SMS அனுப்பப்பட்டது!"
        return False, str(res_json.get("message") or res_json)
    except Exception as e:
        return False, f"SMS இணைப்புப் பிழை: {str(e)}"

# Schemas
class LoginRequest(BaseModel):
    username: str
    password: str

class BranchPayload(BaseModel):
    branch_code: str
    branch_name: str
    city: str
    phone: Optional[str] = None

class StaffPayload(BaseModel):
    username: str
    password: Optional[str] = None
    full_name: str
    mobile: str
    role_key: str = "BRANCH_STAFF"
    branch_id: int
    can_access_counter: bool = True
    can_approve_kyc: bool = False
    can_approve_updates: bool = False
    can_manage_users: bool = False
    can_approve_otp_exempt: bool = False

class CompanyBankPayload(BaseModel):
    bank_name: str
    branch_name: str
    account_type: str = "CURRENT"
    account_no: str
    ifsc_code: str
    upi_id: Optional[str] = None

class InterestSlab(BaseModel):
    from_days: int
    to_days: int
    rate_percent: float

class LoanSchemePayload(BaseModel):
    scheme_code: str
    scheme_name: str
    min_loan_amount: float = 1000.00
    max_loan_amount: float = 1500000.00
    tenure_months: int = 12
    min_interest_days: int = 7
    auction_grace_days: int = 30
    auction_charge_amount: float = 500.00
    processing_charge_type: str = "PLEDGE"  # PLEDGE / RELEASE
    processing_charge_calc: str = "AMOUNT"  # AMOUNT / PERCENTAGE
    processing_charge_value: float = 0.00
    max_ltv_percentage: float = 75.00
    interest_slabs: List[InterestSlab]
    purity_rate_multipliers: Optional[Dict[str, float]] = {
        "916": 0.75, "22CT": 0.75, "18CT": 0.60, "999": 0.85
    }

class DailyGoldRatePayload(BaseModel):
    rate_24k_per_gram: float
    rate_22k_per_gram: float
    rate_18k_per_gram: float

class FullCustomerKYCPayload(BaseModel):
    name: str
    mobile: str
    alt_mobile: Optional[str] = None
    guardian_name: Optional[str] = None
    relation_type: Optional[str] = "தந்தை"
    address: Optional[str] = None
    id_proof_type: Optional[str] = "Aadhaar Card"
    id_proof_no: Optional[str] = None
    nominee_name: Optional[str] = None
    nominee_relation: Optional[str] = None
    nominee_mobile: Optional[str] = None
    ref1_name: Optional[str] = None
    ref1_mobile: Optional[str] = None
    ref1_address: Optional[str] = None
    ref2_name: Optional[str] = None
    ref2_mobile: Optional[str] = None
    ref2_address: Optional[str] = None
    customer_photo: Optional[str] = None
    signature_photo: Optional[str] = None
    id_proof_photo: Optional[str] = None
    branch_id: int = 1

class CustomerVisitEntry(BaseModel):
    customer_id: int
    branch_id: int = 1
    purpose: Optional[str] = "REGULAR_TRANSACTION"

class CustomerUpdateRequest(BaseModel):
    customer_id: int
    branch_id: int = 1
    requested_changes: Dict[str, Any]

class ApprovalActionPayload(BaseModel):
    request_id: int
    action: str
    admin_id: int

class BankTransferPayload(BaseModel):
    customer_id: int
    branch_id: int = 1
    settlement_id: Optional[int] = None
    direction: str  # PAYOUT / RECEIPT
    amount: float
    pay_mode: str  # BANK_TRANSFER / UPI
    beneficiary_name: Optional[str] = None
    account_no: Optional[str] = None
    ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None
    upi_id: Optional[str] = None
    is_third_party: bool = False
    passbook_photo: Optional[str] = None
    consent_doc_photo: Optional[str] = None
    company_bank_name: Optional[str] = None
    receipt_ref_no: Optional[str] = None
    receipt_screenshot: Optional[str] = None

class BankApprovalPayload(BaseModel):
    transfer_id: int
    action: str  # APPROVE / REJECT
    admin_id: int
    notes: Optional[str] = None

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

class DenominationCounts(BaseModel):
    c_500: int = 0
    c_200: int = 0
    c_100: int = 0
    c_50: int = 0
    c_20: int = 0
    c_10: int = 0
    c_coins: int = 0

class SendOtpPayload(BaseModel):
    customer_id: int
    mobile: str
    customer_name: str
    net_amount: float
    direction: str

class SettleWithOtpPayload(BaseModel):
    customer_id: int
    branch_id: int = 1
    otp_code: str
    net_amount: float
    direction: str
    settlement_type: str
    cash_amount: float = 0.0
    bank_amount: float = 0.0
    bank_ref_no: Optional[str] = None
    bank_name: Optional[str] = None
    denominations: Optional[DenominationCounts] = None
    transaction_date: Optional[str] = None

# --- Cash Day Schemas ---
class CashDayOpenPayload(BaseModel):
    branch_id: int
    business_date: str
    opening_balance: float
    denominations: Dict[str, int]
    staff_id: int

class CashDayClosePayload(BaseModel):
    cash_day_id: int
    closing_balance: float
    denominations: Dict[str, int]
    calculated_system_cash: float
    staff_id: int

# --- API Endpoints ---

@app.get("/")
def serve_ui():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "FastAPI Server Running"}

@app.get("/health")
def health_check():
    return {"status": "active", "service": "Enterprise API v5"}

# 1. பணியாளர் உள்நுழைவு (Login API with Role-Based Access Override)
@app.post("/api/auth/staff-login")
def staff_unified_login(data: LoginRequest):
    try:
        res = (
            supabase.table("test_staff_users")
            .select("*, test_branches(branch_name, branch_code)")
            .eq("username", data.username.strip())
            .eq("password", data.password.strip())
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=401, detail="பயனர் பெயர் அல்லது கடவுச்சொல் தவறானது!")

        user = res.data[0]
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="இந்தக் கணக்கு முடக்கப்பட்டுள்ளது.")

        branch_info = user.get("test_branches") or {}
        role = user.get("role_key", "BRANCH_STAFF")
        is_admin_role = (role in ["HQ_ADMIN", "ADMIN"])

        user_profile = {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role_key": role,
            "branch_id": user.get("branch_id") or 1,
            "branch_code": branch_info.get("branch_code", "BR"),
            "branch_name": branch_info.get("branch_name", "Branch"),
            "permissions": {
                "can_access_counter": True if is_admin_role else bool(user.get("can_access_counter", True)),
                "can_approve_kyc": True if is_admin_role else bool(user.get("can_approve_kyc", False)),
                "can_approve_updates": True if is_admin_role else bool(user.get("can_approve_updates", False)),
                "can_manage_users": True if is_admin_role else bool(user.get("can_manage_users", False)),
                "can_approve_otp_exempt": True if is_admin_role else bool(user.get("can_approve_otp_exempt", False)) # 👈 உரிமை சரிபார்த்தல்
            }
        }
        return {"status": "success", "message": "உள்நுழைவு முடிந்தது!", "user": user_profile}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"உள்நுழைவு பிழை: {str(e)}")

# 2. கிளை வாரியான வாடிக்கையாளர் தேடல் API
@app.get("/api/customer/search")
def search_customer(query: str = Query(..., min_length=1), branch_id: int = Query(...)):
    try:
        clean_query = query.strip()
        db_query = supabase.table("test_customers").select("*").eq("branch_id", branch_id)
        if clean_query.isdigit():
            res = db_query.ilike("mobile", f"%{clean_query}%").limit(10).execute()
        else:
            res = db_query.ilike("name", f"%{clean_query}%").limit(10).execute()
        return {"status": "success", "count": len(res.data), "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"தேடல் பிழை: {str(e)}")

# 3. தொடர் ஆட்டோமேட்டிக் நகைக்கடன் எண் வழங்கும் API (Auto Loan No)
@app.get("/api/loan/next-loan-no")
def get_next_loan_no(branch_id: int = Query(...)):
    try:
        branch_res = supabase.table("test_branches").select("branch_code").eq("id", branch_id).execute()
        if not branch_res.data:
            raise HTTPException(status_code=404, detail="கிளை விபரம் கிடைக்கவில்லை.")
        branch_code = branch_res.data[0]["branch_code"].strip().upper()
        count_res = supabase.table("test_gold_loans").select("id", count="exact").eq("branch_id", branch_id).execute()
        next_count = (count_res.count or 0) + 1
        formatted_loan_no = f"{branch_code}/{next_count:04d}"
        return {
            "status": "success",
            "branch_code": branch_code,
            "next_loan_no": formatted_loan_no,
            "count": next_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"கடன் எண் பிழை: {str(e)}")

# 4. நகைக்கடன் பதிவு & நீக்கம்
# 1. B: புதிய அடகு பதிவின் போது நாள் பூட்டப்பட்டுள்ளதா எனச் சரிபார்த்தல்
@app.post("/api/loan/new-pawn")
def create_new_pawn(data: NewGoldLoanEntry):
    check_day = (
        supabase.table("test_branch_cash_days")
        .select("status")
        .eq("branch_id", data.branch_id)
        .order("business_date", desc=True)
        .limit(1)
        .execute()
    )
    if check_day.data and check_day.data[0].get("status") == "CLOSED":
        raise HTTPException(
            status_code=400, 
            detail="இந்த நாளுக்கான கணக்கு ஏற்கனவே பூட்டப்பட்டுவிட்டது (CLOSED). புதிய அடகு வைக்க முடியாது!"
        )

    if not data.items:
        raise HTTPException(status_code=400, detail="நகைகளைச் சேர்க்கவும்.")

    total_gross = sum(i.gross_weight for i in data.items)
    total_net = sum(i.net_weight for i in data.items)
    net_payable = data.loan_amount - data.charges_amount

    loan_record = {
        "loan_no": data.loan_no.strip(),
        "customer_id": data.customer_id,
        "scheme_name": data.scheme_name,
        "total_gross_weight": round(total_gross, 3),
        "total_net_weight": round(total_net, 3),
        "loan_amount": data.loan_amount,
        "charges_amount": data.charges_amount,
        "net_payable_amount": net_payable,
        "photo_url": data.photo_url,
        "ornament_photo": data.photo_url,
        "branch_id": data.branch_id,
        "status": "ACTIVE"
    }
    res_loan = supabase.table("test_gold_loans").insert(loan_record).execute()
    new_loan_id = res_loan.data[0]["id"]

    items_payload = [{
        "loan_id": new_loan_id,
        "item_type": i.item_type.strip(),
        "item_count": i.item_count,
        "gross_weight": i.gross_weight,
        "net_weight": i.net_weight,
        "purity": i.purity
    } for i in data.items]
    supabase.table("test_gold_loan_items").insert(items_payload).execute()

    return {
        "status": "success", 
        "message": "நகைக்கடன் கார்ட்டில் சேர்க்கப்பட்டது.", 
        "loan_id": new_loan_id, 
        "net_payable": net_payable
    }

@app.delete("/api/loan/{loan_id}")
def delete_cart_loan(loan_id: int):
    try:
        supabase.table("test_gold_loans").delete().eq("id", loan_id).execute()
        return {"status": "success", "message": "கடன் கார்ட்டில் இருந்து நீக்கப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"கடன் நீக்கல் பிழை: {str(e)}")

# 5. திட்டங்கள், வங்கிக் கணக்குகள் & தங்க விலை மேலாண்மை
@app.get("/api/admin/schemes")
def get_loan_schemes():
    res = supabase.table("test_loan_schemes").select("*").eq("is_active", True).order("id", desc=True).execute()
    return {"status": "success", "data": res.data}

@app.post("/api/admin/scheme/create")
def create_loan_scheme(data: LoanSchemePayload):
    check = supabase.table("test_loan_schemes").select("id").eq("scheme_code", data.scheme_code.strip()).execute()
    if check.data:
        raise HTTPException(status_code=400, detail="திட்டக் குறியீடு ஏற்கனவே உள்ளது.")
    res = supabase.table("test_loan_schemes").insert(data.model_dump()).execute()
    return {"status": "success", "message": "புதிய நகைக்கடன் திட்டம் உருவாக்கப்பட்டது.", "data": res.data}

@app.delete("/api/admin/scheme/{scheme_id}")
def delete_loan_scheme(scheme_id: int):
    supabase.table("test_loan_schemes").delete().eq("id", scheme_id).execute()
    return {"status": "success", "message": "திட்டம் நீக்கப்பட்டது."}

@app.get("/api/admin/company-banks")
def get_company_banks():
    res = supabase.table("test_company_banks").select("*").eq("is_active", True).order("id", desc=True).execute()
    return {"status": "success", "data": res.data}

@app.post("/api/admin/company-bank/create")
def create_company_bank(data: CompanyBankPayload):
    res = supabase.table("test_company_banks").insert(data.model_dump()).execute()
    return {"status": "success", "message": "நிறுவன வங்கி கணக்கு சேர்க்கப்பட்டது.", "data": res.data}

@app.delete("/api/admin/company-bank/{bank_id}")
def delete_company_bank(bank_id: int):
    supabase.table("test_company_banks").delete().eq("id", bank_id).execute()
    return {"status": "success", "message": "வங்கி கணக்கு நீக்கப்பட்டது."}

@app.get("/api/admin/gold-rate/today")
def get_today_gold_rate():
    res = supabase.table("test_daily_gold_rates").select("*").order("rate_date", desc=True).limit(1).execute()
    return {"status": "success", "data": res.data[0] if res.data else None}

@app.post("/api/admin/gold-rate/update")
def update_today_gold_rate(data: DailyGoldRatePayload):
    record = data.model_dump()
    record["rate_date"] = "now()"
    res = supabase.table("test_daily_gold_rates").upsert(record, on_conflict="rate_date").execute()
    return {"status": "success", "message": "அன்றைய தங்க விலை நிர்ணயிக்கப்பட்டது.", "data": res.data}

# 6. கிளைகள் & பணியாளர்கள் மேலாண்மை
@app.get("/api/admin/branches")
def get_branches():
    res = supabase.table("test_branches").select("*").order("id", desc=True).execute()
    return {"status": "success", "data": res.data}

@app.post("/api/admin/branch/create")
def create_branch(data: BranchPayload):
    res = supabase.table("test_branches").insert(data.model_dump()).execute()
    return {"status": "success", "message": "கிளை உருவாக்கப்பட்டது.", "data": res.data}

@app.put("/api/admin/branch/{branch_id}")
def update_branch(branch_id: int, data: BranchPayload):
    supabase.table("test_branches").update(data.model_dump()).eq("id", branch_id).execute()
    return {"status": "success", "message": "கிளை விபரங்கள் புதுப்பிக்கப்பட்டன."}

@app.delete("/api/admin/branch/{branch_id}")
def delete_branch(branch_id: int):
    supabase.table("test_branches").delete().eq("id", branch_id).execute()
    return {"status": "success", "message": "கிளை நீக்கப்பட்டது."}

@app.get("/api/admin/staff")
def get_staff_list():
    res = supabase.table("test_staff_users").select("*, test_branches(branch_name)").order("id", desc=True).execute()
    return {"status": "success", "data": res.data}

@app.post("/api/admin/staff/create")
def create_staff(data: StaffPayload):
    check = supabase.table("test_staff_users").select("id").eq("username", data.username.strip()).execute()
    if check.data:
        raise HTTPException(status_code=400, detail="இந்தப் பயனர் பெயர் ஏற்கனவே உள்ளது.")
    res = supabase.table("test_staff_users").insert(data.model_dump()).execute()
    return {"status": "success", "message": "பணியாளர் கணக்கு உருவாக்கப்பட்டது.", "data": res.data}

@app.put("/api/admin/staff/{staff_id}")
def update_staff(staff_id: int, data: StaffPayload):
    update_dict = {
        "full_name": data.full_name,
        "mobile": data.mobile,
        "role_key": data.role_key,
        "branch_id": data.branch_id,
        "can_access_counter": data.can_access_counter,
        "can_approve_kyc": data.can_approve_kyc,
        "can_approve_updates": data.can_approve_updates,
        "can_manage_users": data.can_manage_users
        "can_approve_otp_exempt": data.can_approve_otp_exempt
    }
    if data.password:
        update_dict["password"] = data.password
    supabase.table("test_staff_users").update(update_dict).eq("id", staff_id).execute()
    return {"status": "success", "message": "பணியாளர் விபரங்கள் புதுப்பிக்கப்பட்டன."}

@app.delete("/api/admin/staff/{staff_id}")
def delete_staff(staff_id: int):
    supabase.table("test_staff_users").delete().eq("id", staff_id).execute()
    return {"status": "success", "message": "பணியாளர் நீக்கப்பட்டது."}

# 7. வங்கி பரிவர்த்தனை வேண்டுகோள் & நிலை
@app.post("/api/bank/request-transfer")
def create_bank_transfer(data: BankTransferPayload):
    record = data.model_dump()
    record["status"] = "PENDING"
    res = supabase.table("test_bank_transfers").insert(record).execute()
    return {"status": "success", "message": "வங்கி பரிவர்த்தனை வேண்டுகோள் தலைமையகத்திற்கு அனுப்பப்பட்டது.", "data": res.data}

@app.get("/api/bank/branch-status")
def get_branch_bank_status(branch_id: int = Query(...)):
    cust_res = supabase.table("test_customers").select("id, name, mobile").execute()
    cust_map = {c["id"]: c for c in (cust_res.data or [])}
    trans_res = supabase.table("test_bank_transfers").select("*").eq("branch_id", branch_id).order("id", desc=True).limit(20).execute()
    data = trans_res.data or []
    for t in data:
        c = cust_map.get(t.get("customer_id"), {})
        t["test_customers"] = {"name": c.get("name", "வாடிக்கையாளர்"), "mobile": c.get("mobile", "-")}
    return {"status": "success", "data": data}

@app.post("/api/hq/process-bank-transfer")
def process_bank_transfer_hq(data: BankApprovalPayload):
    status = "APPROVED" if data.action == "APPROVE" else "REJECTED"
    supabase.table("test_bank_transfers").update({
        "status": status,
        "approved_by": data.admin_id,
        "hq_notes": data.notes,
        "approved_at": "now()"
    }).eq("id", data.transfer_id).execute()
    return {"status": "success", "message": f"வங்கிப் பரிவர்த்தனை '{status}' செய்யப்பட்டது."}

# 8. தலைமையக ஒருங்கிணைந்த நிலுவைகள்
@app.get("/api/hq/all-pending-approvals")
def get_all_pending_approvals():
    cust_res = supabase.table("test_customers").select("id, name, mobile").execute()
    cust_map = {c["id"]: c for c in (cust_res.data or [])}

    payouts_res = supabase.table("test_bank_transfers").select("*").eq("direction", "PAYOUT").eq("status", "PENDING").order("id", desc=True).execute()
    payouts_data = payouts_res.data or []
    for p in payouts_data:
        c = cust_map.get(p.get("customer_id"), {})
        p["test_customers"] = {"name": c.get("name", f"வாடிக்கையாளர் #{p.get('customer_id')}"), "mobile": c.get("mobile", "-")}

    receipts_res = supabase.table("test_bank_transfers").select("*").eq("direction", "RECEIPT").eq("status", "PENDING").order("id", desc=True).execute()
    receipts_data = receipts_res.data or []
    for r in receipts_data:
        c = cust_map.get(r.get("customer_id"), {})
        r["test_customers"] = {"name": c.get("name", f"வாடிக்கையாளர் #{r.get('customer_id')}"), "mobile": c.get("mobile", "-")}

    visits_res = supabase.table("test_customer_visits").select("*").eq("visit_status", "PENDING").order("id", desc=True).limit(20).execute()
    visits_data = visits_res.data or []
    for v in visits_data:
        c = cust_map.get(v.get("customer_id"), {})
        v["test_customers"] = {"name": c.get("name", f"வாடிக்கையாளர் #{v.get('customer_id')}"), "mobile": c.get("mobile", "-")}

    kyc_res = supabase.table("test_customers").select("*").eq("kyc_status", "PENDING").order("id", desc=True).execute()
    updates_res = supabase.table("test_customer_update_requests").select("*").eq("status", "PENDING").order("id", desc=True).execute()
    updates_data = updates_res.data or []
    for u in updates_data:
        c = cust_map.get(u.get("customer_id"), {})
        u["test_customers"] = {"name": c.get("name", f"வாடிக்கையாளர் #{u.get('customer_id')}"), "mobile": c.get("mobile", "-")}

    return {
        "status": "success",
        "pending_kyc": kyc_res.data or [],
        "pending_updates": updates_data,
        "pending_visits": visits_data,
        "pending_payouts": payouts_data,
        "pending_receipts": receipts_data
    }

@app.post("/api/hq/approve-visit")
def process_visit_approval(data: ApprovalActionPayload):
    status = "VERIFIED" if data.action == "APPROVE" else "REJECTED"
    supabase.table("test_customer_visits").update({
        "visit_status": status,
        "approved_by": data.admin_id,
        "approved_at": "now()"
    }).eq("id", data.request_id).execute()
    return {"status": "success", "message": f"வருகை நிலை '{status}' என மாற்றப்பட்டது."}

@app.post("/api/hq/approve-kyc")
def process_kyc_approval(data: ApprovalActionPayload):
    status = "VERIFIED" if data.action == "APPROVE" else "REJECTED"
    supabase.table("test_customers").update({"kyc_status": status}).eq("id", data.request_id).execute()
    return {"status": "success", "message": f"KYC நிலை '{status}' என மாற்றப்பட்டது."}

@app.post("/api/hq/approve-update")
def process_update_approval(data: ApprovalActionPayload):
    req_res = supabase.table("test_customer_update_requests").select("*").eq("id", data.request_id).execute()
    if not req_res.data:
        raise HTTPException(status_code=404, detail="கோரிக்கை கிடைக்கவில்லை.")
    req = req_res.data[0]
    if data.action == "APPROVE":
        changes = req.get("requested_changes", {})
        if changes:
            supabase.table("test_customers").update(changes).eq("id", req["customer_id"]).execute()
        supabase.table("test_customer_update_requests").update({"status": "APPROVED"}).eq("id", data.request_id).execute()
        return {"status": "success", "message": "சுயவிவர மாற்றம் அங்கீகரிக்கப்பட்டது."}
    else:
        supabase.table("test_customer_update_requests").update({"status": "REJECTED"}).eq("id", data.request_id).execute()
        return {"status": "success", "message": "சுயவிவர மாற்றக் கோரிக்கை நிராகரிக்கப்பட்டது."}

# 9. வருகைப் பதிவு & முழு KYC & சுயவிவர மாற்றம்
@app.post("/api/customer/visit")
def log_customer_visit(data: CustomerVisitEntry):
    record = {"customer_id": data.customer_id, "branch_id": data.branch_id, "purpose": data.purpose, "visit_status": "PENDING"}
    res = supabase.table("test_customer_visits").insert(record).execute()
    return {"status": "success", "message": "வருகை தலைமை ஒப்புதலுக்கு அனுப்பப்பட்டது.", "data": res.data}

@app.post("/api/customer/new-full-kyc")
def create_full_kyc(data: FullCustomerKYCPayload):
    clean_mobile = data.mobile.strip()
    existing = supabase.table("test_customers").select("id, name").eq("mobile", clean_mobile).execute()
    if existing.data:
        raise HTTPException(status_code=400, detail=f"இந்த மொபைல் எண் ஏற்கனவே உள்ளது ({existing.data[0]['name']}).")
    record = data.model_dump()
    record["kyc_status"] = "PENDING"
    record["is_active"] = True
    res = supabase.table("test_customers").insert(record).execute()
    return {"status": "success", "message": "முழு KYC சமர்ப்பிக்கப்பட்டது! தலைமை ஒப்புதலுக்குக் காத்திருக்கிறது.", "data": res.data}

@app.post("/api/customer/request-update")
def request_customer_update(data: CustomerUpdateRequest):
    record = {
        "customer_id": data.customer_id,
        "branch_id": data.branch_id,
        "requested_changes": data.requested_changes,
        "status": "PENDING"
    }
    supabase.table("test_customer_update_requests").insert(record).execute()
    return {"status": "success", "message": "விபர மாற்றக் கோரிக்கை தலைமையக ஒப்புதலுக்கு அனுப்பப்பட்டது."}

# 10. OTP & இறுதி செட்டில்மென்ட்
@app.post("/api/otp/send")
def trigger_otp_sms(payload: SendOtpPayload):
    otp_code = str(random.randint(100000, 999999))
    txn_type = "receive" if payload.direction == "COMPANY_PAYABLE" else "pay"
    success, msg = send_fast2sms_otp(payload.mobile, otp_code, payload.customer_name, payload.net_amount, txn_type)
    if not success:
        raise HTTPException(status_code=502, detail=f"SMS பிழை: {msg}")
    supabase.table("test_transaction_otps").insert({
        "customer_id": payload.customer_id,
        "mobile": payload.mobile,
        "otp_code": otp_code,
        "net_amount": payload.net_amount,
        "txn_type": txn_type,
        "is_verified": False
    }).execute()
    return {"status": "success", "message": "OTP SMS அனுப்பப்பட்டது."}

# 1. C: செட்டில்மென்ட்டின் போது நாள் பூட்டப்பட்டுள்ளதா எனச் சரிபார்த்தல்
@app.post("/api/transaction/settle-with-otp")
def settle_with_otp(data: SettleWithOtpPayload):
    txn_date = data.transaction_date or "now()"
    
    day_status_res = (
        supabase.table("test_branch_cash_days")
        .select("status")
        .eq("branch_id", data.branch_id)
        .eq("business_date", txn_date)
        .execute()
    )
    if day_status_res.data and day_status_res.data[0].get("status") == "CLOSED":
        raise HTTPException(
            status_code=400, 
            detail="தேர்வு செய்யப்பட்ட நாள் ஏற்கனவே பூட்டப்பட்டுவிட்டது (CLOSED). இதில் பணப் பரிவர்த்தனை செய்ய முடியாது!"
        )

    if not data.is_exempted:
        otp_query = (
            supabase.table("test_transaction_otps")
            .select("id, otp_code, is_verified")
            .eq("customer_id", data.customer_id)
            .eq("is_verified", False)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not otp_query.data or otp_query.data[0]["otp_code"] != (data.otp_code or "").strip():
            raise HTTPException(status_code=400, detail="OTP தவறானது அல்லது காலாவதியானது.")
        supabase.table("test_transaction_otps").update({"is_verified": True}).eq("id", otp_query.data[0]["id"]).execute()

    settle_record = {
        "customer_id": data.customer_id,
        "branch_id": data.branch_id,
        "net_amount": data.net_amount,
        "settlement_type": data.settlement_type,
        "cash_amount": data.cash_amount,
        "bank_amount": data.bank_amount,
        "bank_ref_no": data.bank_ref_no,
        "bank_name": data.bank_name,
        "direction": data.direction,
        "transaction_date": txn_date
    }
    res_settle = supabase.table("test_transaction_settlements").insert(settle_record).execute()
    new_settle_id = res_settle.data[0]["id"]

    if data.cash_amount > 0 and data.denominations:
        supabase.table("test_cash_denominations").insert({
            "settlement_id": new_settle_id,
            "c_500": data.denominations.c_500,
            "c_200": data.denominations.c_200,
            "c_100": data.denominations.c_100,
            "c_50": data.denominations.c_50,
            "c_20": data.denominations.c_20,
            "c_10": data.denominations.c_10,
            "c_coins": data.denominations.c_coins,
            "total_calculated_cash": data.cash_amount
        }).execute()

    if data.visit_id:
        supabase.table("test_customer_visits").update({
            "status": "PENDING_HQ",
            "net_amount": data.net_amount,
            "cash_amount": data.cash_amount,
            "bank_amount": data.bank_amount,
            "direction": data.direction,
            "actions_summary": data.actions_summary or "நகைக்கடன் பரிவர்த்தனை"
        }).eq("id", data.visit_id).execute()

    return {
        "status": "success", 
        "message": "பரிவர்த்தனை முடிந்தது!", 
        "settlement_id": new_settle_id
    }

# ==================== கிளை நாள் திறப்பு, அறிக்கை & நாள் பூட்டுதல் API ====================

# 1. குறிப்பிட்ட நாளின் நிலையை அறிதல் (Check Cash Day Status)
# 1. A: நாள் நிலை அறிதல் மற்றும் முந்தைய நாளின் இருப்பைத் தானாகக் கொண்டுவருதல்
@app.get("/api/cash-day/status")
def get_cash_day_status(branch_id: int = Query(...), date: str = Query(...)):
    try:
        res = supabase.table("test_branch_cash_days").select("*").eq("branch_id", branch_id).eq("business_date", date).execute()
        if res.data:
            return {"status": "success", "data": res.data[0]}

        prev_res = (
            supabase.table("test_branch_cash_days")
            .select("closing_balance")
            .eq("branch_id", branch_id)
            .lt("business_date", date)
            .order("business_date", desc=True)
            .limit(1)
            .execute()
        )
        
        carried_opening = 0.0
        if prev_res.data and prev_res.data[0].get("closing_balance") is not None:
            carried_opening = float(prev_res.data[0]["closing_balance"])

        new_day = {
            "branch_id": branch_id,
            "business_date": date,
            "opening_balance": carried_opening,
            "status": "OPEN"
        }
        ins_res = supabase.table("test_branch_cash_days").insert(new_day).execute()
        return {"status": "success", "data": ins_res.data[0]}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"நாள் இருப்பு பிழை: {str(e)}")

# 2. நாள் திறப்பு (Open Cash Day)
@app.post("/api/cash-day/open")
def open_cash_day(data: CashDayOpenPayload):
    try:
        check = supabase.table("test_branch_cash_days").select("id").eq("branch_id", data.branch_id).eq("business_date", data.business_date).execute()
        if check.data:
            raise HTTPException(status_code=400, detail="இந்த நாளுக்கான தொடக்க இருப்பு ஏற்கனவே திறக்கப்பட்டுள்ளது.")
        
        record = {
            "branch_id": data.branch_id,
            "business_date": data.business_date,
            "opening_balance": data.opening_balance,
            "opening_denominations": data.denominations,
            "opened_by": data.staff_id,
            "status": "OPEN"
        }
        res = supabase.table("test_branch_cash_days").insert(record).execute()
        return {"status": "success", "message": "நாள் வெற்றிகரமாகத் திறக்கப்பட்டது!", "data": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 3. குறிப்பிட்ட நாளுக்கான அனைத்து நடவடிக்கைகள் & கணக்கீடுகள் (Day Summary Report)
# ==================== 1. அன்றைய நடவடிக்கைகள் அறிக்கை API ====================
@app.get("/api/cash-day/report")
def get_day_cash_report(branch_id: int = Query(...), date: str = Query(...)):
    try:
        clean_date = date.strip()

        # 1. அன்றைய நாள் இருப்பு விவரம்
        day_res = (
            supabase.table("test_branch_cash_days")
            .select("*")
            .eq("branch_id", branch_id)
            .eq("business_date", clean_date)
            .execute()
        )
        day_info = day_res.data[0] if day_res.data else None

        # 2. வாடிக்கையாளர் விபரங்களை விரைவாக எடுக்க மேப்பிங் செய்தல்
        cust_res = supabase.table("test_customers").select("id, name, mobile").execute()
        cust_map = {c["id"]: c for c in (cust_res.data or [])}

        # 3. குறிப்பிட்ட நாளின் அனைத்து செட்டில்மென்ட்களையும் எடுத்தல்
        settle_res = (
            supabase.table("test_transaction_settlements")
            .select("*")
            .eq("branch_id", branch_id)
            .eq("transaction_date", clean_date)
            .order("id", desc=True)
            .execute()
        )
        raw_settlements = settle_res.data or []

        total_cash_in = 0.0   # வாடிக்கையாளர் நிறுவனத்திற்கு செலுத்திய ரொக்கம்
        total_cash_out = 0.0  # நிறுவனம் வாடிக்கையாளருக்கு வழங்கிய ரொக்கம்
        formatted_settlements = []

        for s in raw_settlements:
            cash = float(s.get("cash_amount") or 0.0)
            bank = float(s.get("bank_amount") or 0.0)
            direction = s.get("direction", "COMPANY_PAYABLE")

            if direction == "CUSTOMER_PAYABLE":
                total_cash_in += cash
            elif direction == "COMPANY_PAYABLE":
                total_cash_out += cash

            c_info = cust_map.get(s.get("customer_id"), {})
            formatted_settlements.append({
                "id": s.get("id"),
                "customer_name": c_info.get("name", f"வாடிக்கையாளர் #{s.get('customer_id')}"),
                "mobile": c_info.get("mobile", "-"),
                "direction": direction,
                "settlement_type": s.get("settlement_type", "CASH"),
                "cash_amount": cash,
                "bank_amount": bank,
                "net_amount": float(s.get("net_amount") or (cash + bank)),
                "created_at": s.get("created_at")
            })

        opening = float(day_info.get("opening_balance") or 0.0) if day_info else 0.0
        calculated_closing = opening + total_cash_in - total_cash_out

        return {
            "status": "success",
            "business_date": clean_date,
            "opening_balance": opening,
            "total_cash_in": total_cash_in,
            "total_cash_out": total_cash_out,
            "calculated_closing": calculated_closing,
            "settlements_count": len(formatted_settlements),
            "settlements": formatted_settlements
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"அறிக்கை எடுப்பதில் பிழை: {str(e)}")

# OTP விலக்குக் கோரிக்கை
@app.post("/api/otp/request-exemption")
def request_otp_exemption(data: OtpExemptRequestPayload):
    supabase.table("test_customer_visits").update({
        "otp_exemption_status": "REQUESTED",
        "purpose": f"OTP விலக்குக் கோரிக்கை: {data.reason}"
    }).eq("id", data.visit_id).execute()
    return {"status": "success", "message": "OTP விலக்குக் கோரிக்கை தலைமையகத்திற்கு அனுப்பப்பட்டது."}

# நிலுவையில் உள்ள OTP விலக்குக் கோரிக்கைகள் பட்டியல்
@app.get("/api/hq/pending-otp-exemptions")
def get_pending_otp_exemptions():
    res = (
        supabase.table("test_customer_visits")
        .select("*, test_customers(name, mobile)")
        .eq("otp_exemption_status", "REQUESTED")
        .order("id", desc=True)
        .execute()
    )
    return {"status": "success", "data": res.data or []}

# தலைமையகம் ஒப்புதல் அளித்தல்
@app.post("/api/hq/approve-otp-exemption")
def approve_otp_exemption(data: OtpExemptApprovalPayload):
    status = "APPROVED" if data.action == "APPROVE" else "REJECTED"
    supabase.table("test_customer_visits").update({
        "otp_exemption_status": status,
        "otp_exempted": (status == "APPROVED")
    }).eq("id", data.visit_id).execute()
    return {"status": "success", "message": f"OTP விலக்கு '{status}' செய்யப்பட்டது."}

# கிளை கவுண்ட்டரில் நிலை அறியும் API
@app.get("/api/otp/exemption-status")
def check_otp_exemption_status(visit_id: int = Query(...)):
    res = supabase.table("test_customer_visits").select("otp_exemption_status, otp_exempted").eq("id", visit_id).execute()
    if res.data:
        return {"status": "success", "data": res.data[0]}
    return {"status": "success", "data": {"otp_exemption_status": "NONE", "otp_exempted": False}}

# 4. மாலை நாள் முடிப்பு & பூட்டுதல் (Close Cash Day)
# 1. D: மாலை நாள் பூட்டுதல்
@app.post("/api/cash-day/close")
def close_cash_day(data: CashDayClosePayload):
    try:
        day_res = (
            supabase.table("test_branch_cash_days")
            .select("id, status")
            .eq("branch_id", data.branch_id)
            .eq("business_date", data.business_date)
            .execute()
        )
        if not day_res.data:
            raise HTTPException(status_code=404, detail="இந்த நாளின் இருப்புப் பதிவு கிடைக்கவில்லை.")

        if day_res.data[0].get("status") == "CLOSED":
            raise HTTPException(status_code=400, detail="இந்த நாள் ஏற்கனவே பூட்டப்பட்டுவிட்டது.")

        day_id = day_res.data[0]["id"]
        diff = data.closing_balance - data.calculated_system_cash

        update_data = {
            "closing_balance": data.closing_balance,
            "closing_denominations": data.denominations,
            "calculated_system_cash": data.calculated_system_cash,
            "cash_difference": diff,
            "closed_by": data.staff_id,
            "closed_at": "now()",
            "status": "CLOSED"
        }
        supabase.table("test_branch_cash_days").update(update_data).eq("id", day_id).execute()
        return {
            "status": "success", 
            "message": "நாள் வெற்றிகரமாகப் பூட்டப்பட்டது! இனி புதிய பரிவர்த்தனைகள் செய்ய முடியாது.", 
            "difference": diff
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

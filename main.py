import os
import random
import requests
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from database import supabase

# இந்திய நேர மண்டலம் (IST = UTC + 5 மணி 30 நிமிடங்கள்)
IST = timezone(timedelta(hours=5, minutes=30))

app = FastAPI(
    title="Muthusise Gold Loan Management - Enterprise Core",
    version="6.2.0"
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
        try:
            res_json = resp.json()
        except Exception:
            return False, f"SMS சர்வர் பிழை (Status {resp.status_code})"

        if res_json.get("return") is True:
            return True, "SMS அனுப்பப்பட்டது!"
        return False, str(res_json.get("message") or res_json)
    except Exception as e:
        return False, f"SMS இணைப்புப் பிழை: {str(e)}"

# Pydantic Schemas
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
    can_approve_expenses: bool = False  
    can_manage_treasury: bool = False
    can_approve_rebate: bool = False

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
    processing_charge_type: str = "PLEDGE"
    processing_charge_calc: str = "AMOUNT"
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
    transaction_date: Optional[str] = None

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
    direction: str
    amount: float
    pay_mode: str
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
    action: str
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
    branch_id: int
    loan_no: str
    scheme_name: str
    loan_amount: float
    charges_amount: float = 0.0
    photo_url: Optional[str] = None
    items: List[Any] = []
    transaction_date: Optional[str] = None  # 👈 இந்த வரியைச் சேர்த்துக் கொள்ளவும்
    visit_id: Optional[int] = None

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
    visit_id: Optional[int] = None
    otp_code: Optional[str] = None
    is_exempted: bool = False
    net_amount: float
    direction: str
    settlement_type: str
    cash_amount: float = 0.0
    bank_amount: float = 0.0
    bank_ref_no: Optional[str] = None
    bank_name: Optional[str] = None
    denominations: Optional[DenominationCounts] = None
    transaction_date: Optional[str] = None
    actions_summary: Optional[str] = None
    cart_items: Optional[List[Dict[str, Any]]] = []

class OtpExemptRequestPayload(BaseModel):
    visit_id: int
    branch_id: int
    reason: str
    staff_id: int

class OtpExemptApprovalPayload(BaseModel):
    visit_id: int
    action: str
    admin_id: int

class CashDayClosePayload(BaseModel):
    branch_id: int
    business_date: str
    closing_balance: float
    denominations: Dict[str, int]
    calculated_system_cash: float
    staff_id: int
# ==========================================
# 🧾 கிளை தினசரி செலவு மேலாண்மை (Branch Expenses)
# ==========================================

# 1. Pydantic Model
class BranchExpenseRequest(BaseModel):
    branch_id: int
    category: str
    amount: float
    payment_mode: str = "CASH"
    reason: Optional[str] = None
    bill_photo: Optional[str] = None
    staff_id: int

class ExpenseApprovalPayload(BaseModel):
    expense_id: int
    action: str  # APPROVE / REJECT
    admin_id: int


# 2. கிளை செலவுக் கோரிக்கை  அனுப்பும் API
@app.post("/api/expense/request")
def create_branch_expense(data: dict):
    try:
        # 1. கிளை எண் மற்றும் கவுண்ட்டரில் இருந்து வரும் பரிவர்த்தனை தேதியை முதலில் எடுத்தல்
        branch_id = data.get("branch_id") or 1
        trans_date = data.get("transaction_date") or datetime.now(IST).strftime("%Y-%m-%d")

        # 2. நாள் பூட்டப்பட்டுள்ளதா (CLOSED) எனச் சரிபார்த்தல்
        day_chk = (
            supabase.table("test_branch_cash_days")
            .select("status")
            .eq("branch_id", branch_id)
            .eq("business_date", trans_date)
            .execute()
        )
        if day_chk.data and day_chk.data[0].get("status") == "CLOSED":
            raise HTTPException(
                status_code=400, 
                detail=f"⚠️ {trans_date} நாளுக்கான மாலை கணக்கு ஏற்கனவே பூட்டப்பட்டுவிட்டது! இந்தப் பழைய தேதியில் புதிய செலவுகளைப் பதிவு செய்ய முடியாது."
            )

        # 3. செலவுப் பதிவு விவரங்கள்
        record = {
            "branch_id": branch_id,
            "category": data.get("category"),
            "amount": float(data.get("amount") or 0.0),
            "payment_mode": data.get("payment_mode", "CASH"),
            "reason": data.get("reason"),
            "bill_photo": data.get("bill_photo"),
            "status": "PENDING",
            "created_by": data.get("staff_id"),
            "transaction_date": trans_date,
            "created_at": datetime.now(IST).isoformat()
        }
        res = supabase.table("test_branch_expenses").insert(record).execute()
        return {"status": "success", "message": "செலவுக் கோரிக்கை தலைமையக ஒப்புதலுக்கு அனுப்பப்பட்டது.", "data": res.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"செலவு பதிவு பிழை: {str(e)}")

# 3. தலைமையகத்தில் நிலுவையில் உள்ள செலவுகளை எடுக்கும் API
@app.get("/api/hq/pending-expenses")
def get_pending_expenses():
    try:
        branch_res = supabase.table("test_branches").select("id, branch_name, branch_code").execute()
        b_map = {b["id"]: b for b in (branch_res.data or [])}

        exp_res = (
            supabase.table("test_branch_expenses")
            .select("*")
            .eq("status", "PENDING")
            .order("id", desc=True)
            .execute()
        )
        data = exp_res.data or []
        for x in data:
            b = b_map.get(x.get("branch_id"), {})
            x["branch_name"] = b.get("branch_name", f"கிளை #{x.get('branch_id')}")

        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# 4. தலைமையகம் செலவுக்கு ஒப்புதல் அளிக்கும் API
@app.post("/api/hq/approve-expense")
def approve_branch_expense(data: ExpenseApprovalPayload):
    try:
        status = "APPROVED" if data.action == "APPROVE" else "REJECTED"
        supabase.table("test_branch_expenses").update({
            "status": status,
            "approved_by": data.admin_id,
            "approved_at": "now()"
        }).eq("id", data.expense_id).execute()

        return {"status": "success", "message": f"செலவு வெற்றிகரமாக '{status}' செய்யப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# API Endpoints
@app.get("/")
def serve_ui():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "FastAPI Server Running"}

@app.get("/health")
def health_check():
    return {"status": "active", "service": "Enterprise API v6.2"}

# 1. Staff Login
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
                "can_approve_otp_exempt": True if is_admin_role else bool(user.get("can_approve_otp_exempt", False)),
                "can_approve_expenses": True if is_admin_role else bool(user.get("can_approve_expenses", False)),
                "can_manage_treasury": True if is_admin_role else bool(user.get("can_manage_treasury", False)),
                "can_approve_rebate": True if is_admin_role else bool(user.get("can_approve_rebate", False))
            }
        }
        return {"status": "success", "message": "உள்நுழைவு முடிந்தது!", "user": user_profile}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"உள்நுழைவு பிழை: {str(e)}")

# 2. Customer Search
@app.get("/api/customer/search")
def search_customer(query: str = Query(..., min_length=1), branch_id: int = Query(...)):
    try:
        clean_query = query.strip()
        db_query = supabase.table("test_customers").select("*").eq("branch_id", branch_id)
        if clean_query.isdigit():
            res = db_query.ilike("mobile", f"%{clean_query}%").limit(10).execute()
        else:
            res = db_query.ilike("name", f"%{clean_query}%").limit(10).execute()
        return {"status": "success", "count": len(res.data or []), "data": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"தேடல் பிழை: {str(e)}")

# 3. Next Loan Number
@app.get("/api/loan/next-loan-no")
def get_next_loan_no(branch_id: int = Query(...)):
    try:
        branch_res = supabase.table("test_branches").select("branch_code").eq("id", branch_id).execute()
        if not branch_res.data:
            raise HTTPException(status_code=404, detail="கிளை விபரம் கிடைக்கவில்லை.")
        branch_code = branch_res.data[0]["branch_code"].strip().upper()
        count_res = supabase.table("test_gold_loans").select("id", count="exact").eq("branch_id", branch_id).execute()
        next_count = (count_res.count or len(count_res.data or [])) + 1
        formatted_loan_no = f"{branch_code}/{next_count:04d}"
        return {
            "status": "success",
            "branch_code": branch_code,
            "next_loan_no": formatted_loan_no,
            "count": next_count
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"கடன் எண் பிழை: {str(e)}")
        
# வாடிக்கையாளரின் நடப்பு நகைக்கடன்களை எடுக்கும் API
@app.get("/api/customer/{customer_id}/active-loans")
def get_customer_active_loans(customer_id: int):
    try:
        res = supabase.table("test_gold_loans") \
            .select("*, test_gold_loan_items(*)") \
            .eq("customer_id", customer_id) \
            .eq("status", "ACTIVE") \
            .order("id", desc=False) \
            .execute()
        
        loans = res.data or []
        
        # ஒவ்வொரு கடனுக்கும் முந்தைய வட்டி / பகுதி அசல் வரலாற்றை இணைத்தல்
        for loan in loans:
            history = []
            for tbl_name in ["test_gold_loan_repayments", "test_gold_loan_transactions", "test_loan_repayments"]:
                try:
                    h_res = supabase.table(tbl_name) \
                        .select("*") \
                        .eq("loan_id", loan["id"]) \
                        .order("id", desc=False) \
                        .execute()
                    if h_res.data:
                        history = h_res.data
                        break
                except Exception:
                    continue
            loan["repayment_history"] = history

        return {"status": "success", "data": loans}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 4. New Gold Loan
@app.post("/api/loan/new-pawn")
def create_new_pawn(data: dict):
    try:
        branch_id = data.get("branch_id") or 1
        trans_date = data.get("transaction_date") or datetime.now(IST).strftime("%Y-%m-%d")

        # அன்றைய நாள் லாக் செய்யப்பட்டுள்ளதா எனச் சரிபார்த்தல்
        check_day = (
            supabase.table("test_branch_cash_days")
            .select("status")
            .eq("branch_id", branch_id)
            .eq("business_date", trans_date)
            .execute()
        )
        if check_day.data and check_day.data[0].get("status") == "CLOSED":
            raise HTTPException(status_code=400, detail="இந்த நாளுக்கான கணக்கு ஏற்கனவே பூட்டப்பட்டுவிட்டது (CLOSED). புதிய அடகு வைக்க முடியாது!")

        items = data.get("items") or []
        if not items:
            raise HTTPException(status_code=400, detail="நகைகளைச் சேர்க்கவும்.")

        # Dictionary-யில் இருந்து எடையைக் கணக்கிடும் சரியான முறை:
        total_gross = sum(float(i.get("gross_weight") if isinstance(i, dict) else getattr(i, "gross_weight", 0) or 0) for i in items)
        total_net = sum(float(i.get("net_weight") if isinstance(i, dict) else getattr(i, "net_weight", 0) or 0) for i in items)
        
        loan_amt = float(data.get("loan_amount") or 0.0)
        charges_amt = float(data.get("charges_amount") or 0.0)
        net_payable = loan_amt - charges_amt

        # நகைப் படம் எடுத்தல்
        ornament_img = data.get("ornament_photo") or data.get("photo_url")

        loan_record = {
            "loan_no": str(data.get("loan_no") or "").strip(),
            "customer_id": data.get("customer_id"),
            "scheme_name": data.get("scheme_name"),
            "total_gross_weight": round(total_gross, 3),
            "total_net_weight": round(total_net, 3),
            "loan_amount": loan_amt,
            "charges_amount": charges_amt,
            "net_payable_amount": net_payable,
            "photo_url": ornament_img,
            "ornament_photo": ornament_img,
            "branch_id": branch_id,
            "status": "ACTIVE",
            "visit_id": data.get("visit_id"),
            "transaction_date": trans_date,
            "outstanding_principal": loan_amt,
            "last_interest_paid_date": trans_date,
            "created_at": datetime.now(IST).isoformat()
        }
        res_loan = supabase.table("test_gold_loans").insert(loan_record).execute()
        if not res_loan.data:
            raise HTTPException(status_code=500, detail="கடன் பதிவு தோல்வியடைந்தது.")
        new_loan_id = res_loan.data[0]["id"]

        # நகை உருப்படிகள் ஒவ்வொன்றையும் Dictionary முறையில் சேர்த்தல்:
        items_payload = []
        for i in items:
            if isinstance(i, dict):
                items_payload.append({
                    "loan_id": new_loan_id,
                    "item_type": str(i.get("item_type") or "").strip(),
                    "item_count": int(i.get("item_count") or 1),
                    "gross_weight": float(i.get("gross_weight") or 0.0),
                    "net_weight": float(i.get("net_weight") or 0.0),
                    "purity": i.get("purity")
                })
            else:
                items_payload.append({
                    "loan_id": new_loan_id,
                    "item_type": str(getattr(i, "item_type", "")).strip(),
                    "item_count": int(getattr(i, "item_count", 1)),
                    "gross_weight": float(getattr(i, "gross_weight", 0.0)),
                    "net_weight": float(getattr(i, "net_weight", 0.0)),
                    "purity": getattr(i, "purity", None)
                })

        supabase.table("test_gold_loan_items").insert(items_payload).execute()
        return {"status": "success", "message": "நகைக்கடன் கார்ட்டில் சேர்க்கப்பட்டது.", "loan_id": new_loan_id, "net_payable": net_payable}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"கடன் உருவாக்கம் பிழை: {str(e)}")

# 5. Cash Day Status (Auto Roll-forward)
@app.get("/api/cash-day/status")
def get_cash_day_status(branch_id: int, date: Optional[str] = None, date_str: Optional[str] = None):
    try:
        # date அல்லது date_str இரண்டில் எதில் தேதி வந்தாலும் எடுத்தல்
        target_date = date or date_str or datetime.now(IST).strftime("%Y-%m-%d")

        res = (
            supabase.table("test_branch_cash_days")
            .select("*")
            .eq("branch_id", branch_id)
            .eq("business_date", target_date)
            .execute()
        )

        if res.data and len(res.data) > 0:
            row = res.data[0]
            is_closed = (row.get("status") == "CLOSED")
            return {
                "status": "success",
                "is_closed": is_closed,
                "data": row
            }
        else:
            return {
                "status": "success",
                "is_closed": False,
                "data": None
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"நாள் நிலை அறியும் பிழை: {str(e)}")

# 6. Day Report
@app.get("/api/cash-day/report")
def get_cash_day_report(branch_id: int, date_str: str):
    try:
        # 0. கிளை பெயர் எடுத்தல்
        branch_name = "Aundivilai"
        try:
            br_res = supabase.table("test_branches").select("name").eq("id", branch_id).execute()
            if br_res.data and br_res.data[0].get("name"):
                branch_name = br_res.data[0].get("name")
        except Exception:
            pass

        # 1. தொடக்க இருப்பு எடுத்தல்
        opening_bal = 0.0
        try:
            prev_closed = (
                supabase.table("test_branch_cash_days")
                .select("closing_balance")
                .eq("branch_id", branch_id)
                .lt("business_date", date_str)
                .eq("status", "CLOSED")
                .order("business_date", desc=True)
                .limit(1)
                .execute()
            )
            if prev_closed.data:
                opening_bal = float(prev_closed.data[0].get("closing_balance") or 0.0)
        except Exception as e:
            print("Opening balance fetch err:", e)

        unified_entries = []
        tot_cash_in = 0.0
        tot_cash_out = 0.0
        tot_bank_in = 0.0
        tot_bank_out = 0.0

        # 2. test_customer_visits அட்டவணையில் இருந்து முழுமையாக எடுத்தல்
        # தேதி வடிகட்டுதலை மிகவும் நம்பகமான முறையில் செய்தல்
        all_visits = []
        try:
            # விசிட்களை branch_id மற்றும் transaction_date மூலம் எடுத்தல்
            v_res = supabase.table("test_customer_visits").select("*").eq("branch_id", branch_id).execute()
            
            for row in (v_res.data or []):
                # தேதி பொருத்தம் பார்த்தல் (transaction_date அல்லது created_at தொடக்கம்)
                r_date = str(row.get("transaction_date") or "")
                c_date = str(row.get("created_at") or "")[:10]
                
                if r_date == date_str or c_date == date_str:
                    all_visits.append(row)
        except Exception as v_err:
            print("Visits fetch error:", v_err)

        # வாடிக்கையாளர் பெயர்களை எடுத்தல்
        cust_ids = [v["customer_id"] for v in all_visits if v.get("customer_id")]
        cust_map = {}
        if cust_ids:
            try:
                c_res = supabase.table("test_customers").select("id, name, mobile").in_("id", cust_ids).execute()
                for c in (c_res.data or []):
                    cust_map[c["id"]] = c
            except Exception:
                pass

        for v in all_visits:
            cid = v.get("customer_id")
            cust_info = cust_map.get(cid, {})
            c_name = cust_info.get("name") or "வாடிக்கையாளர்"
            
            # வருகை எண் வடிவம் (எ.கா: VST-AUN-0012)
            v_id_val = v.get("id")
            v_code = f"VST-AUN-{int(v_id_val):04d}" if str(v_id_val).isdigit() else f"VST-{v_id_val}"

            # தொகைகள்
            net_amt = float(v.get("net_amount") or 0.0)
            cash_val = float(v.get("cash_amount") or 0.0)
            bank_val = float(v.get("bank_amount") or 0.0)
            direction = str(v.get("direction") or "OUTWARD").upper()

            # cash_amount / bank_amount தனித்துக் குறிப்பிடப்படவில்லை எனில்
            if cash_val == 0.0 and bank_val == 0.0 and net_amt > 0.0:
                cash_val = net_amt

            c_in = 0.0
            c_out = 0.0
            b_in = 0.0
            b_out = 0.0

            if direction in ["OUTWARD", "COMPANY_PAYABLE"]:
                c_out = cash_val
                b_out = bank_val
                tot_cash_out += cash_val
                tot_bank_out += bank_val
            else:
                c_in = cash_val
                b_in = bank_val
                tot_cash_in += cash_val
                tot_bank_in += bank_val

            created_t = str(v.get("created_at") or "")
            t_str = created_t[11:16] if len(created_t) >= 16 else "--:--"

            unified_entries.append({
                "time": t_str,
                "visit_no": v_code,
                "entry_type": "வணிக வருகை",
                "party_name": c_name,
                "activity": v.get("actions_summary") or "Pledge (புதிய நகைக் கடன்)",
                "gross_in": (c_in + b_in) if (c_in + b_in) > 0 else 0.0,
                "gross_out": (c_out + b_out) if (c_out + b_out) > 0 else 0.0,
                "cash_change": (-c_out) if c_out > 0 else (c_in if c_in > 0 else 0.0),
                "bank_change": (-b_out) if b_out > 0 else (b_in if b_in > 0 else 0.0),
                "raw_time": created_t or str(v_id_val)
            })

        # 3. கிளை செலவுகள்
        try:
            exp_res = supabase.table("test_branch_expenses").select("*").eq("branch_id", branch_id).eq("status", "APPROVED").execute()
            for e in (exp_res.data or []):
                e_date = str(e.get("transaction_date") or "")
                e_created = str(e.get("created_at") or "")[:10]
                if e_date == date_str or e_created == date_str:
                    amt = float(e.get("amount") or 0.0)
                    e_mode = str(e.get("payment_mode") or "CASH").upper()
                    e_time = str(e.get("created_at") or "")
                    t_str = e_time[11:16] if len(e_time) >= 16 else "--:--"
                    
                    if e_mode == "CASH":
                        tot_cash_out += amt
                        c_chg = -amt
                        b_chg = 0.0
                    else:
                        tot_bank_out += amt
                        b_chg = -amt
                        c_chg = 0.0

                    unified_entries.append({
                        "time": t_str,
                        "visit_no": "-",
                        "entry_type": "கிளை செலவு",
                        "party_name": e.get("category", "செலவு"),
                        "activity": e.get("reason") or "அங்கீகரிக்கப்பட்ட செலவு",
                        "gross_in": 0.0,
                        "gross_out": amt,
                        "cash_change": c_chg,
                        "bank_change": b_chg,
                        "raw_time": e_time
                    })
        except Exception as e_err:
            print("Expenses report err:", e_err)

        # 4. கருவூலப் பரிமாற்றங்கள்
        try:
            tr_res = supabase.table("test_treasury_transfers").select("*").eq("branch_id", branch_id).eq("status", "APPROVED").execute()
            type_names = {
                'BRANCH_TO_HQ': ('HQ பணப் பட்டுவாடா', 'கிளை ➔ தலைமை அலுவலகம்'),
                'HQ_TO_BRANCH': ('HQ நிதி ஒதுக்கீடு', 'தலைமையக நிதி வரவு'),
                'CASH_TO_BANK': ('வங்கி டெபாசிட்', 'ரொக்கம் ➔ வங்கி'),
                'BANK_TO_CASH': ('வங்கி வித்ராயல்', 'வங்கி ➔ கிளை ரொக்கம்')
            }
            for t in (tr_res.data or []):
                t_date = str(t.get("transaction_date") or "")
                t_created = str(t.get("created_at") or "")[:10]
                if t_date == date_str or t_created == date_str:
                    amt = float(t.get("amount") or 0.0)
                    ttype = t.get("transfer_type")
                    t_time = str(t.get("created_at") or "")
                    t_str = t_time[11:16] if len(t_time) >= 16 else "--:--"
                    t_title, t_desc = type_names.get(ttype, ('பணப் பரிமாற்றம்', ttype))

                    c_chg = 0.0
                    g_in = 0.0
                    g_out = 0.0

                    if ttype in ['HQ_TO_BRANCH', 'BANK_TO_CASH']:
                        tot_cash_in += amt
                        c_chg = amt
                        g_in = amt
                    else:
                        tot_cash_out += amt
                        c_chg = -amt
                        g_out = amt

                    unified_entries.append({
                        "time": t_str,
                        "visit_no": "-",
                        "entry_type": t_title,
                        "party_name": t.get("carrier_person") or "பணப் பரிமாற்றம்",
                        "activity": t_desc,
                        "gross_in": g_in,
                        "gross_out": g_out,
                        "cash_change": c_chg,
                        "bank_change": 0.0,
                        "raw_time": t_time
                    })
        except Exception as t_err:
            print("Treasury report err:", t_err)

        unified_entries.sort(key=lambda x: str(x.get("raw_time") or ""))
        calc_closing = opening_bal + tot_cash_in - tot_cash_out

        return {
            "status": "success",
            "branch_name": branch_name,
            "opening_balance": opening_bal,
            "total_cash_in": tot_cash_in,
            "total_cash_out": tot_cash_out,
            "total_bank_in": tot_bank_in,
            "total_bank_out": tot_bank_out,
            "calculated_closing": calc_closing,
            "entries": unified_entries
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"அறிக்கை கணக்கீட்டுப் பிழை: {str(e)}")

@app.get("/api/cash-day/next-business-date")
def get_next_business_date(branch_id: int):
    try:
        # கடைசியாகப் பூட்டப்பட்ட (CLOSED) நாளை எடுத்தல்
        last_closed = (
            supabase.table("test_branch_cash_days")
            .select("business_date")
            .eq("branch_id", branch_id)
            .eq("status", "CLOSED")
            .order("business_date", desc=True)
            .limit(1)
            .execute()
        )
        if last_closed.data:
            last_date_str = last_closed.data[0]["business_date"]
            last_dt = datetime.strptime(last_date_str, "%Y-%m-%d")
            next_date = (last_dt + timedelta(days=1)).strftime("%Y-%m-%d")
            return {"status": "success", "suggested_date": next_date, "last_closed_date": last_date_str}
        else:
            # இதுவரை எந்த நாளும் பூட்டப்படவில்லை எனில் மிகப்பழைய பரிவர்த்தனை நாள் அல்லது இன்றைய நாள்
            today_str = datetime.now(IST).strftime("%Y-%m-%d")
            return {"status": "success", "suggested_date": today_str, "last_closed_date": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"தேதி அறிவதில் பிழை: {str(e)}")

@app.get("/api/cash-day/validate-date-sequence")
def validate_date_sequence(branch_id: int, selected_date: str):
    try:
        # கடைசியாகப் பூட்டப்பட்ட நாள்
        last_closed = (
            supabase.table("test_branch_cash_days")
            .select("business_date")
            .eq("branch_id", branch_id)
            .eq("status", "CLOSED")
            .order("business_date", desc=True)
            .limit(1)
            .execute()
        )
        
        if last_closed.data:
            last_date_str = last_closed.data[0]["business_date"]
            last_dt = datetime.strptime(last_date_str, "%Y-%m-%d")
            allowed_dt = last_dt + timedelta(days=1)
            allowed_date_str = allowed_dt.strftime("%Y-%m-%d")
            
            sel_dt = datetime.strptime(selected_date, "%Y-%m-%d")

            # பூட்டப்பட்ட நாளுக்கு அடுத்த நாளைத் தவிர எதிர்காலத் தேதிகளுக்குத் தாவினால் தடுத்தல்
            if sel_dt > allowed_dt:
                return {
                    "is_valid": False,
                    "allowed_date": allowed_date_str,
                    "message": f"⚠️ தொடர் நாள் விதிமீறல்: {last_date_str} நாளுக்குப் பிறகு அடுத்த வேலை நாளான {allowed_date_str}-ஐ மட்டுமே முடிக்க முடியும். தாவிச் சென்று {selected_date}-ல் பணியாற்ற முடியாது!"
                }
        
        return {"is_valid": True, "message": "அனுமதிக்கப்பட்டது"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 1. மாலை கணக்கு முடித்தல் (Day Close)
@app.post("/api/cash-day/close")
def close_cash_day(data: dict):
    try:
        branch_id = data.get("branch_id") or 1
        business_date = data.get("business_date") or datetime.now(IST).strftime("%Y-%m-%d")
        closing_balance = float(data.get("closing_balance") or 0.0)
        calc_sys_cash = float(data.get("calculated_system_cash") or 0.0)
        staff_id = data.get("staff_id") or 1
        denoms = data.get("denominations") or {}

        # 👈 தாள்கள் தொகை கணினியின்படி சரியாக இல்லையெனில் நிராகரித்தல் (Strict Zero Difference Rule)
        diff = round(closing_balance - calc_sys_cash, 2)
        if diff != 0.0:
            raise HTTPException(
                status_code=400, 
                detail=f"கணினியின்படி இருக்க வேண்டிய ரொக்கமும் (₹{calc_sys_cash:,.2f}) தாள்களின் தொகையும் (₹{closing_balance:,.2f}) சமமாக இல்லை! வேறுபாடு: ₹{diff:,.2f}. சமமாக இருந்தால் மட்டுமே நாளைப் பூட்ட முடியும்."
            )

        # 1. முந்தைய நாளின் இறுதி இருப்பை (Closing Balance) எடுத்தல்
        opening = 0.0
        try:
            prev_day_res = (
                supabase.table("test_branch_cash_days")
                .select("closing_balance, opening_balance")
                .eq("branch_id", branch_id)
                .lt("business_date", business_date)
                .order("business_date", desc=True)
                .limit(1)
                .execute()
            )
            if prev_day_res.data:
                opening = float(prev_day_res.data[0].get("closing_balance") or prev_day_res.data[0].get("opening_balance") or 0.0)
        except Exception as pe:
            print("Previous closing balance fetch error:", pe)

        # 2. அன்றைய நாள் பதிவு ஏற்கனவே உள்ளதா எனப் பார்த்தல்
        day_res = (
            supabase.table("test_branch_cash_days")
            .select("id, status")
            .eq("branch_id", branch_id)
            .eq("business_date", business_date)
            .execute()
        )

        if day_res.data and day_res.data[0].get("status") == "CLOSED":
            raise HTTPException(status_code=400, detail=f"{business_date} நாளுக்கான கணக்கு ஏற்கனவே பூட்டப்பட்டுவிட்டது (CLOSED).")

        now_time = datetime.now(IST).isoformat()

        if day_res.data:
            # ஏற்கனவே வரிசை இருந்தால் update செய்தல்
            day_id = day_res.data[0]["id"]
            update_data = {
                "closing_balance": closing_balance,
                "calculated_system_cash": calc_sys_cash,
                "status": "CLOSED",
                "closed_by": staff_id,
                "closed_at": now_time
            }
            supabase.table("test_branch_cash_days").update(update_data).eq("id", day_id).execute()
        else:
            # காலை பதிவு இல்லையென்றாலும், புதிய பதிவை உருவாக்கி உடனே பூட்டுதல்
            new_record = {
                "branch_id": branch_id,
                "business_date": business_date,
                "opening_balance": opening,
                "closing_balance": closing_balance,
                "calculated_system_cash": calc_sys_cash,
                "status": "CLOSED",
                "opened_by": staff_id,
                "closed_by": staff_id,
                "created_at": now_time,
                "closed_at": now_time
            }
            supabase.table("test_branch_cash_days").insert(new_record).execute()

        # 3. தாள்கள் டினாமினேஷன் இருப்பின் சேமித்தல்
        if denoms:
            denom_record = {
                "branch_id": branch_id,
                "business_date": business_date,
                "record_type": "DAY_CLOSE",
                "c_500": denoms.get("c_500", 0),
                "c_200": denoms.get("c_200", 0),
                "c_100": denoms.get("c_100", 0),
                "c_50": denoms.get("c_50", 0),
                "c_20": denoms.get("c_20", 0),
                "c_10": denoms.get("c_10", 0),
                "c_coins": denoms.get("c_coins", 0),
                "total_amount": closing_balance
            }
            try:
                supabase.table("test_cash_denominations").insert(denom_record).execute()
            except Exception as de:
                print("Denominations save note:", de)

        return {
            "status": "success",
            "message": f"{business_date} மாலை கணக்கு வெற்றிகரமாக முடிக்கப்பட்டு லாக் செய்யப்பட்டது!",
            "closing_balance": closing_balance,
            "difference": 0.0
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"மாலை கணக்கு முடிப்பதில் பிழை: {str(e)}")


# 2. நாள் நிலையைச் சரிபார்த்தல் & தொடக்க இருப்பை முந்தைய நாளிலிருந்து தானாக எடுத்தல் (Auto Rollover)
@app.get("/api/cash-day/status")
def get_cash_day_status(branch_id: int, date_str: str):
    try:
        cur_day = (
            supabase.table("test_branch_cash_days")
            .select("*")
            .eq("branch_id", branch_id)
            .eq("business_date", date_str)
            .execute()
        )

        if cur_day.data:
            day_rec = cur_day.data[0]
            return {
                "business_date": date_str,
                "status": day_rec.get("status", "OPEN"),
                "opening_balance": float(day_rec.get("opening_balance") or 0.0),
                "is_closed": day_rec.get("status") == "CLOSED"
            }
        
        prev_day = (
            supabase.table("test_branch_cash_days")
            .select("*")
            .eq("branch_id", branch_id)
            .lt("business_date", date_str)
            .order("business_date", desc=True)
            .limit(1)
            .execute()
        )

        auto_opening = 0.0
        if prev_day.data:
            auto_opening = float(prev_day.data[0].get("closing_balance") or prev_day.data[0].get("opening_balance") or 0.0)

        supabase.table("test_branch_cash_days").insert({
            "branch_id": branch_id,
            "business_date": date_str,
            "opening_balance": auto_opening,
            "status": "OPEN",
            "created_at": datetime.now().isoformat()
        }).execute()

        return {
            "business_date": date_str,
            "status": "OPEN",
            "opening_balance": auto_opening,
            "is_closed": False
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"நாள் நிலையை அறிவதில் பிழை: {str(e)}")

# 7. நாள் நிலையைச் சரிபார்த்தல் & தொடக்க இருப்பை முந்தைய நாளிலிருந்து தானாக எடுத்தல் (Auto Rollover)
@app.get("/api/cash-day/status")
def get_cash_day_status(branch_id: int, date_str: str):
    try:
        # தற்போதைய தேதிக்கான பதிவு உள்ளதா எனப் பார்த்தல்
        cur_day = (
            supabase.table("test_branch_cash_days")
            .select("*")
            .eq("branch_id", branch_id)
            .eq("business_date", date_str)
            .execute()
        )

        if cur_day.data:
            day_rec = cur_day.data[0]
            return {
                "business_date": date_str,
                "status": day_rec.get("status", "OPEN"),
                "opening_balance": float(day_rec.get("opening_balance") or 0.0),
                "is_closed": day_rec.get("status") == "CLOSED"
            }
        
        # தற்போதைய தேதிக்கு இன்னும் பதிவு இல்லை என்றால்:
        # முந்தைய நாளின் கடைசிப் பதிவை எடுத்து அதிலுள்ள closing_balance-ஐ தொடக்க இருப்பாக மாற்றுதல்
        prev_day = (
            supabase.table("test_branch_cash_days")
            .select("*")
            .eq("branch_id", branch_id)
            .lt("business_date", date_str)
            .order("business_date", desc=True)
            .limit(1)
            .execute()
        )

        auto_opening = 0.0
        if prev_day.data:
            # முந்தைய நாள் மாலை முடிவு இருப்பை அடுத்த நாளின் தொடக்க இருப்பாக எடுத்தல்
            auto_opening = float(prev_day.data[0].get("closing_balance") or prev_day.data[0].get("opening_balance") or 0.0)

        # புதிய நாளுக்குத் தானாகவே OPEN நிலையில் பதிவு உருவாக்குதல்
        supabase.table("test_branch_cash_days").insert({
            "branch_id": branch_id,
            "business_date": date_str,
            "opening_balance": auto_opening,
            "status": "OPEN",
            "created_at": datetime.now().isoformat()
        }).execute()

        return {
            "business_date": date_str,
            "status": "OPEN",
            "opening_balance": auto_opening,
            "is_closed": False
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"நாள் நிலையை அறிவதில் பிழை: {str(e)}")

# 8. Counter Live Visits Table
@app.get("/api/customer/branch-visits")
def get_branch_visits(branch_id: int = Query(...), date: str = Query(...)):
    try:
        visits_res = (
            supabase.table("test_customer_visits")
            .select("*, test_customers(name, mobile)")
            .eq("branch_id", branch_id)
            .order("id", desc=True)
            .limit(30)
            .execute()
        )
        return {"status": "success", "data": visits_res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/customer/visit")
def log_customer_visit(data: CustomerVisitEntry):
    try:
        # கவுண்ட்டரில் இருந்து வரும் தேதி அல்லது தற்போதைய இந்தியத் தேதி
        selected_date = getattr(data, 'transaction_date', None) or datetime.now(IST).strftime("%Y-%m-%d")
        now_ist = datetime.now(IST).isoformat()

        # நாள் லாக் செய்யப்பட்டுள்ளதா எனப் பார்த்தல்
        day_check = (
            supabase.table("test_branch_cash_days")
            .select("status")
            .eq("branch_id", data.branch_id)
            .eq("business_date", selected_date)
            .execute()
        )
        if day_check.data and day_check.data[0].get("status") == "CLOSED":
            raise HTTPException(
                status_code=400, 
                detail=f"தேதி {selected_date}-க்கான மாலை கணக்கு முடிக்கப்பட்டுவிட்டது (Day Closed). புதிய பரிவர்த்தனைகள் செய்ய முடியாது!"
            )

        record = {
            "customer_id": data.customer_id,
            "branch_id": data.branch_id,
            "purpose": data.purpose,
            "transaction_date": selected_date,
            "created_at": now_ist,
            "status": "IN_PROGRESS",
            "audit_status": "PENDING",
            "otp_exemption_status": "NONE",
            "otp_exempted": False
        }
        res = supabase.table("test_customer_visits").insert(record).execute()
        if not res.data:
            raise HTTPException(status_code=500, detail="வருகைப் பதிவு தோல்வியடைந்தது.")
        return {"status": "success", "message": "வருகை துவங்கியது.", "data": res.data[0]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"வருகைப் பதிவு பிழை: {str(e)}")

# 9. OTP Exemption System
@app.post("/api/otp/request-exemption")
def request_otp_exemption(data: OtpExemptRequestPayload):
    try:
        supabase.table("test_customer_visits").update({
            "otp_exemption_status": "REQUESTED",
            "purpose": f"OTP விலக்குக் கோரிக்கை: {data.reason}"
        }).eq("id", data.visit_id).execute()
        return {"status": "success", "message": "OTP விலக்குக் கோரிக்கை தலைமையகத்திற்கு அனுப்பப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"விலக்குக் கோரிக்கை பிழை: {str(e)}")


@app.get("/api/hq/pending-otp-exemptions")
def get_pending_otp_exemptions():
    try:
        # வாடிக்கையாளர் விவரங்களை தனியாக எடுத்தல்
        cust_res = supabase.table("test_customers").select("id, name, mobile").execute()
        cust_map = {c["id"]: c for c in (cust_res.data or [])}

        # கோரிக்கைகளை எடுத்தல்
        res = (
            supabase.table("test_customer_visits")
            .select("*")
            .eq("otp_exemption_status", "REQUESTED")
            .order("id", desc=True)
            .execute()
        )
        visits_data = res.data or []

        # வாடிக்கையாளர் பெயரை இணைத்தல்
        for v in visits_data:
            c = cust_map.get(v.get("customer_id"), {})
            v["test_customers"] = {
                "name": c.get("name", f"வாடிக்கையாளர் #{v.get('customer_id')}"),
                "mobile": c.get("mobile", "-")
            }

        return {"status": "success", "data": visits_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OTP விலக்கு பட்டியல் பிழை: {str(e)}")

@app.get("/api/hq/visit-details/{visit_id}")
def get_visit_details_for_hq(visit_id: int):
    try:
        # 1. வருகை விபரம் எடுத்தல்
        visit_res = supabase.table("test_customer_visits").select("*").eq("id", visit_id).execute()
        if not visit_res.data:
            raise HTTPException(status_code=404, detail="வருகை விபரம் கிடைக்கவில்லை")
        visit = visit_res.data[0]

        # 2. வாடிக்கையாளர் விபரம்
        cust_res = supabase.table("test_customers").select("*").eq("id", visit["customer_id"]).execute()
        customer = cust_res.data[0] if cust_res.data else {}

        # 3. கிளை விபரம்
        branch_res = supabase.table("test_branches").select("branch_name, branch_code").eq("id", visit.get("branch_id", 1)).execute()
        branch = branch_res.data[0] if branch_res.data else {}

        # 4. அந்த குறிப்பிட்ட வருகையில் மட்டும் மேற்கொள்ளப்பட்ட கடன் விபரம் (சரியான தொகையுடன் பொருத்துதல்)
        v_net_amt = float(visit.get("net_amount") or 0.0)
        
        loans_query = (
            supabase.table("test_gold_loans")
            .select("*, test_gold_loan_items(*)")
            .eq("customer_id", visit["customer_id"])
        )
        
        # வருகை நேரம் அல்லது அதற்குப் பின் உருவான கடன்களை எடுத்தல்
        if visit.get("created_at"):
            loans_query = loans_query.gte("created_at", visit["created_at"])
            
        raw_loans = loans_query.order("id", desc=True).limit(5).execute().data or []

        # வருகைத் தொகையுடன் (net_amount) கச்சிதமாகப் பொருந்தும் கடனை மட்டும் தேர்வு செய்தல்
        matched_loans = []
        if raw_loans:
            for l in raw_loans:
                # கடன் தொகையோ அல்லது கழிவுகள் போக உள்ள தொகையோ வருகைத் தொகையுடன் ஒத்துப்போகிறதா எனப் பார்த்தல்
                l_amt = float(l.get("loan_amount") or 0.0)
                l_net = float(l.get("net_payable_amount") or 0.0)
                
                if v_net_amt > 0 and (abs(l_amt - v_net_amt) < 1000 or abs(l_net - v_net_amt) < 1000):
                    matched_loans = [l]
                    break
            
            # பொருந்தும் கடன் இல்லை எனில், அந்த வருகை நேரத்தில் உருவான கடைசி 1 கடனை மட்டும் எடுத்தல்
            if not matched_loans:
                matched_loans = [raw_loans[0]]

        # 5. பணத் தீர்வு மற்றும் ரொக்கத் தாள்கள் விபரம்
        settle_res = (
            supabase.table("test_transaction_settlements")
            .select("*, test_cash_denominations(*)")
            .eq("customer_id", visit["customer_id"])
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        settlement = settle_res.data[0] if settle_res.data else {}

        # 6. அனுப்பப்பட்ட OTP விபரம்
        otp_res = (
            supabase.table("test_transaction_otps")
            .select("*")
            .eq("customer_id", visit["customer_id"])
            .order("id", desc=True)
            .limit(1)
            .execute()
        )
        otp_info = otp_res.data[0] if otp_res.data else {}

        return {
            "status": "success",
            "visit": visit,
            "customer": customer,
            "branch": branch,
            "loans": matched_loans,
            "settlement": settlement,
            "otp_info": otp_info
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
@app.post("/api/hq/approve-otp-exemption")
def approve_otp_exemption(data: OtpExemptApprovalPayload):
    try:
        status = "APPROVED" if data.action == "APPROVE" else "REJECTED"
        supabase.table("test_customer_visits").update({
            "otp_exemption_status": status,
            "otp_exempted": (status == "APPROVED")
        }).eq("id", data.visit_id).execute()
        return {"status": "success", "message": f"OTP விலக்கு '{status}' செய்யப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/otp/exemption-status")
def check_otp_exemption_status(visit_id: int = Query(...)):
    try:
        res = supabase.table("test_customer_visits").select("otp_exemption_status, otp_exempted").eq("id", visit_id).execute()
        if res.data:
            return {"status": "success", "data": res.data[0]}
        return {"status": "success", "data": {"otp_exemption_status": "NONE", "otp_exempted": False}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 10. Settle with OTP
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

@app.post("/api/transaction/settle-with-otp")
def settle_with_otp(data: SettleWithOtpPayload):
    try:
        txn_date = data.transaction_date or datetime.now(IST).strftime("%Y-%m-%d")
        day_status_res = supabase.table("test_branch_cash_days").select("status").eq("branch_id", data.branch_id).eq("business_date", txn_date).execute()
        if day_status_res.data and day_status_res.data[0]["status"] == "CLOSED":
            raise HTTPException(status_code=400, detail="தேர்வு செய்யப்பட்ட நாள் ஏற்கனவே பூட்டப்பட்டுவிட்டது (CLOSED). இதில் பணப் பரிவர்த்தனை செய்ய முடியாது!")

        # 🔒 தீவிரமான சர்வர் பக்க வட்டி தள்ளுபடி ஒப்புதல் சரிபார்ப்பு
        for item in (data.cart_items or []):
            if item.get("is_repayment") is True:
                meta = item.get("repayment_meta") or {}
                disc_amt = float(meta.get("discount_amount", 0))
                req_id = item.get("rebate_req_id")
                
                # தள்ளுபடி தொகை கொடுக்கப்பட்டிருந்தால் கோரிக்கை ஐடி கட்டாயம் இருக்க வேண்டும் மற்றும் HQ Approved ஆக இருக்க வேண்டும்
                if disc_amt > 0:
                    if not req_id:
                        raise HTTPException(status_code=400, detail="பாதுகாப்புப் பிழை: வட்டி தள்ளுபடி கோரிக்கை எண் (Rebate ID) காணப்படவில்லை!")
                    
                    rebate_check = supabase.table("test_rebate_approvals").select("status").eq("id", req_id).execute()
                    if not rebate_check.data:
                        raise HTTPException(status_code=400, detail="பாதுகாப்புப் பிழை: முறையான வட்டி தள்ளுபடி கோரிக்கை தரவுத்தளத்தில் இல்லை.")
                    
                    status = rebate_check.data[0].get("status")
                    if status != "APPROVED":
                        raise HTTPException(
                            status_code=400, 
                            detail=f"❌ பரிவர்த்தனை நிராகரிக்கப்பட்டது: இந்த வட்டி தள்ளுபடிக்குத் தலைமையக ஒப்புதல் கிடைக்கவில்லை! (தற்போதைய நிலை: {status})"
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
        if not res_settle.data:
            raise HTTPException(status_code=500, detail="பரிவர்த்தனை பதிவு தோல்வியடைந்தது.")
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

        # visit_id இருந்தால் அதை நேரடியாக மாற்றுதல், இல்லாவிட்டால் வாடிக்கையாளரின் நடப்பு வருகையைத் தேடி மாற்றுதல்
        target_visit_id = data.visit_id
        if not target_visit_id:
            last_visit = (
                supabase.table("test_customer_visits")
                .select("id")
                .eq("customer_id", data.customer_id)
                .eq("branch_id", data.branch_id)
                .order("id", desc=True)
                .limit(1)
                .execute()
            )
            if last_visit.data:
                target_visit_id = last_visit.data[0]["id"]

        if target_visit_id:
            supabase.table("test_customer_visits").update({
                "status": "PENDING_HQ",
                "net_amount": data.net_amount,
                "cash_amount": data.cash_amount,
                "bank_amount": data.bank_amount,
                "direction": data.direction,
                "actions_summary": data.actions_summary or "நகைக்கடன் பரிவர்த்தனை நிறைவுற்றது"
            }).eq("id", target_visit_id).execute()

        # கூடையில் உள்ள வட்டி, பகுதி அசல் மற்றும் கடன் முடிப்பு நடவடிக்கைகளைச் செயல்படுத்துதல்
        for item in (data.cart_items or []):
            if item.get("is_repayment") is True:
                loan_id = item.get("loan_id")
                action_type = item.get("action_type")
                meta = item.get("repayment_meta") or {}

                int_paid = float(meta.get("interest_paid", 0))
                prin_paid = float(meta.get("principal_paid", 0))
                disc_amt = float(meta.get("discount_amount", 0))

                # 1. பரிவர்த்தனை வரலாற்றில் பதிவு செய்தல்
                supabase.table("test_loan_repayments").insert({
                    "visit_id": target_visit_id,
                    "loan_id": loan_id,
                    "customer_id": data.customer_id,
                    "branch_id": data.branch_id,
                    "action_type": action_type,
                    "interest_paid": int_paid,
                    "principal_paid": prin_paid,
                    "discount_amount": disc_amt,
                    "other_charges": float(meta.get("other_charges", 0)),
                    "auction_notice_charges": float(meta.get("auction_charges", 0)),
                    "days_calculated": meta.get("days_calculated", 0),
                    "rate_applied": meta.get("rate_applied", 0),
                    "transaction_date": txn_date
                }).execute()

                # 2. கடனின் தற்போதைய நிலுவை & நிலையைப் புதுப்பித்தல்
                loan_res = supabase.table("test_gold_loans").select("*").eq("id", loan_id).execute()
                if loan_res.data:
                    loan_row = loan_res.data[0]
                    curr_prin = float(loan_row.get("outstanding_principal") or loan_row.get("loan_amount") or 0)
                    new_prin = max(0.0, curr_prin - prin_paid)

                    update_fields = {
                        "outstanding_principal": new_prin,
                        "last_interest_paid_date": txn_date
                    }
                    if action_type == "FULL_CLOSURE" or new_prin <= 0:
                        update_fields["status"] = "CLOSED"
                        update_fields["closed_date"] = txn_date

                    supabase.table("test_gold_loans").update(update_fields).eq("id", loan_id).execute()

        return {"status": "success", "message": "பரிவர்த்தனை முடிந்தது!", "settlement_id": new_settle_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"தீர்வுப் பிழை: {str(e)}")
        
# Schemes, Banks, Gold Rate, Branches, Staff
@app.get("/api/admin/schemes")
def get_loan_schemes():
    res = supabase.table("test_loan_schemes").select("*").eq("is_active", True).order("id", desc=True).execute()
    return {"status": "success", "data": res.data or []}

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

@app.put("/api/admin/scheme/{scheme_id}")
def update_loan_scheme(scheme_id: int, data: LoanSchemePayload):
    check = supabase.table("test_loan_schemes").select("id").eq("scheme_code", data.scheme_code.strip()).neq("id", scheme_id).execute()
    if check.data:
        raise HTTPException(status_code=400, detail="இந்தத் திட்டக் குறியீடு ஏற்கனவே வேறொரு திட்டத்தில் உள்ளது.")
    res = supabase.table("test_loan_schemes").update(data.model_dump()).eq("id", scheme_id).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="திட்டம் கண்டறியப்படவில்லை.")
    return {"status": "success", "message": "திட்ட விவரங்கள் வெற்றிகரமாகப் புதுப்பிக்கப்பட்டன!", "data": res.data}

@app.patch("/api/admin/scheme/{scheme_id}/toggle-active")
def toggle_loan_scheme_active(scheme_id: int):
    curr = supabase.table("test_loan_schemes").select("is_active").eq("id", scheme_id).execute()
    if not curr.data:
        raise HTTPException(status_code=404, detail="திட்டம் கண்டறியப்படவில்லை.")
    current_status = curr.data[0].get("is_active")
    new_status = False if current_status is not False else True
    res = supabase.table("test_loan_schemes").update({"is_active": new_status}).eq("id", scheme_id).execute()
    status_text = "Active (செயலில்)" if new_status else "Deactive (நிறுத்தப்பட்டது)"
    return {"status": "success", "message": f"திட்டத்தின் நிலை '{status_text}' என மாற்றப்பட்டது!", "is_active": new_status}

@app.get("/api/admin/company-banks")
def get_company_banks():
    res = supabase.table("test_company_banks").select("*").eq("is_active", True).order("id", desc=True).execute()
    return {"status": "success", "data": res.data or []}

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

@app.get("/api/admin/branches")
def get_branches():
    res = supabase.table("test_branches").select("*").order("id", desc=True).execute()
    return {"status": "success", "data": res.data or []}

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
    return {"status": "success", "data": res.data or []}

@app.post("/api/admin/staff/create")
def create_staff(data: StaffPayload):
    check = supabase.table("test_staff_users").select("id").eq("username", data.username.strip()).execute()
    if check.data:
        raise HTTPException(status_code=400, detail="இந்தப் பயனர் பெயர் ஏற்கனவே உள்ளது.")
    
    staff_record = data.model_dump()
    if not staff_record.get("password"):
        staff_record["password"] = "gold123"
        
    res = supabase.table("test_staff_users").insert(staff_record).execute()
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
        "can_manage_users": data.can_manage_users,
        "can_approve_otp_exempt": data.can_approve_otp_exempt,
        "can_approve_expenses": data.can_approve_expenses,
        "can_manage_treasury": data.can_manage_treasury,
        "can_approve_rebate": data.can_approve_rebate
    }
    if data.password:
        update_dict["password"] = data.password
    supabase.table("test_staff_users").update(update_dict).eq("id", staff_id).execute()
    return {"status": "success", "message": "பணியாளர் விபரங்கள் புதுப்பிக்கப்பட்டன."}

@app.delete("/api/admin/staff/{staff_id}")
def delete_staff(staff_id: int):
    supabase.table("test_staff_users").delete().eq("id", staff_id).execute()
    return {"status": "success", "message": "பணியாளர் நீக்கப்பட்டது."}

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

class HQBankPayoutApprovalPayload(BaseModel):
    transfer_id: int
    action: str
    admin_id: int
    company_bank_id: Optional[int] = None
    utr_ref_no: Optional[str] = None
    payment_mode_used: Optional[str] = "IMPS"
    notes: Optional[str] = None

@app.post("/api/hq/process-bank-transfer")
def process_hq_bank_transfer(data: dict):
    try:
        transfer_id = data.get("transfer_id")
        action = data.get("action")  # 'APPROVE' or 'REJECT'
        admin_id = data.get("admin_id") or 1
        company_bank_id = data.get("company_bank_id")
        utr_ref_no = data.get("utr_ref_no")
        notes = data.get("notes") or ""

        # 1. நிறுவன வங்கியின் பெயரை எடுத்தல் (ID-யிலிருந்து bank_name பெறுதல்)
        company_bank_name = None
        if company_bank_id:
            try:
                b_res = supabase.table("test_company_banks").select("bank_name, account_no").eq("id", company_bank_id).execute()
                if b_res.data:
                    b_row = b_res.data[0]
                    company_bank_name = f"{b_row.get('bank_name', '')} ({b_row.get('account_no', '')})"
            except Exception as be:
                print("Bank name fetch error:", be)

        now_time = datetime.now(IST).isoformat()

        # 2. நிராகரிப்பு (REJECT)
        if action == "REJECT":
            supabase.table("test_bank_transfers").update({
                "status": "REJECTED",
                "hq_notes": notes,
                "approved_by": admin_id,
                "approved_at": now_time
            }).eq("id", transfer_id).execute()
            return {"status": "success", "message": "வங்கிப் பரிவர்த்தனை நிராகரிக்கப்பட்டது."}

        # 3. ஒப்புதல் (APPROVE) - அட்டவணையின் சரியான பத்திகளுக்கு மட்டும் சேமித்தல்
        update_payload = {
            "status": "APPROVED",
            "company_bank_name": company_bank_name,
            "receipt_ref_no": utr_ref_no,
            "hq_notes": notes,
            "approved_by": admin_id,
            "approved_at": now_time
        }
        supabase.table("test_bank_transfers").update(update_payload).eq("id", transfer_id).execute()

        # 4. நிறுவன வங்கிக் கணக்கு இருப்பைக் குறைத்தல் (பட்டுவாடா தொகை)
        if company_bank_id:
            try:
                tr_chk = supabase.table("test_bank_transfers").select("amount, direction").eq("id", transfer_id).execute()
                if tr_chk.data:
                    amount = float(tr_chk.data[0].get("amount") or 0.0)
                    direction = tr_chk.data[0].get("direction")
                    
                    cb_res = supabase.table("test_company_banks").select("*").eq("id", company_bank_id).execute()
                    if cb_res.data:
                        cb_row = cb_res.data[0]
                        for bal_col in ["current_balance", "balance", "opening_balance"]:
                            if bal_col in cb_row:
                                old_bal = float(cb_row.get(bal_col) or 0.0)
                                new_bal = (old_bal - amount) if direction == "PAYOUT" else (old_bal + amount)
                                supabase.table("test_company_banks").update({bal_col: new_bal}).eq("id", company_bank_id).execute()
                                break
            except Exception as b_err:
                print("Company bank balance note (ignored):", b_err)

        return {"status": "success", "message": "வங்கிப் பட்டுவாடா வெற்றிகரமாக உறுதி செய்யப்பட்டு ஒப்புதல் அளிக்கப்பட்டது!"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"வங்கி ஒப்புதல் பிழை: {str(e)}")

@app.get("/api/hq/all-pending-approvals")
def get_all_pending_approvals():
    try:
        cust_res = supabase.table("test_customers").select("id, name, mobile").execute()
        cust_map = {c["id"]: c for c in (cust_res.data or [])}

        branch_res = supabase.table("test_branches").select("id, branch_name, branch_code").execute()
        branch_map = {b["id"]: b for b in (branch_res.data or [])}

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

        visits_res = supabase.table("test_customer_visits").select("*").eq("status", "PENDING_HQ").order("id", desc=True).limit(20).execute()
        visits_data = visits_res.data or []
        for v in visits_data:
            c = cust_map.get(v.get("customer_id"), {})
            v["test_customers"] = {"name": c.get("name", f"வாடிக்கையாளர் #{v.get('customer_id')}"), "mobile": c.get("mobile", "-")}

        kyc_res = supabase.table("test_customers").select("*").eq("kyc_status", "PENDING").order("id", desc=True).execute()

        updates_res = supabase.table("test_customer_update_requests").select("*").eq("status", "PENDING").order("id", desc=True).execute()
        updates_data = updates_res.data or []
        for u in updates_data:
            c = cust_map.get(u.get("customer_id"), {})
            b = branch_map.get(u.get("branch_id"), {})
            u["test_customers"] = {"name": c.get("name", f"வாடிக்கையாளர் #{u.get('customer_id')}"), "mobile": c.get("mobile", "-")}
            u["test_branches"] = {"branch_name": b.get("branch_name", f"கிளை #{u.get('branch_id')}"), "branch_code": b.get("branch_code", "BR")}

        return {
            "status": "success",
            "pending_kyc": kyc_res.data or [],
            "pending_updates": updates_data,
            "pending_visits": visits_data,
            "pending_payouts": payouts_data,
            "pending_receipts": receipts_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"தலைமையக நிலுவைகள் பிழை: {str(e)}")

@app.post("/api/hq/approve-visit")
def process_visit_approval(data: ApprovalActionPayload):
    try:
        status = "VERIFIED" if data.action == "APPROVE" else "REJECTED"
        supabase.table("test_customer_visits").update({
            "status": status,
            "audit_status": "AUDITED" if status == "VERIFIED" else "REJECTED"
        }).eq("id", data.request_id).execute()
        return {"status": "success", "message": f"வருகை நிலை '{status}' என மாற்றப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/approve-kyc")
def process_kyc_approval(data: ApprovalActionPayload):
    try:
        status = "VERIFIED" if data.action == "APPROVE" else "REJECTED"
        supabase.table("test_customers").update({"kyc_status": status}).eq("id", data.request_id).execute()
        return {"status": "success", "message": f"KYC நிலை '{status}' என மாற்றப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/approve-update")
def process_update_approval(data: ApprovalActionPayload):
    try:
        req_res = supabase.table("test_customer_update_requests").select("*").eq("id", data.request_id).execute()
        if not req_res.data:
            raise HTTPException(status_code=404, detail="கோரிக்கை கிடைக்கவில்லை.")
        req = req_res.data[0]

        new_status = "APPROVED" if data.action == "APPROVE" else "REJECTED"

        if data.action == "APPROVE":
            changes = req.get("requested_changes", {})
            if changes:
                supabase.table("test_customers").update(changes).eq("id", req["customer_id"]).execute()

        # Schema cache பிழையைத் தவிர்க்கும் தற்காப்பு அணுகுமுறை
        try:
            supabase.table("test_customer_update_requests").update({
                "status": new_status,
                "approved_by": data.admin_id,
                "approved_at": "now()"
            }).eq("id", data.request_id).execute()
        except Exception:
            # காலம்கள் இல்லையென்றால் நிலையை மட்டும் மாற்றும் Fallback
            supabase.table("test_customer_update_requests").update({
                "status": new_status
            }).eq("id", data.request_id).execute()

        msg = "சுயவிவர மாற்றம் வெற்றிகரமாக அங்கீகரிக்கப்பட்டது!" if new_status == "APPROVED" else "சுயவிவர மாற்றக் கோரிக்கை நிராகரிக்கப்பட்டது."
        return {"status": "success", "message": msg}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"சுயவிவர ஒப்புதல் பிழை: {str(e)}")

@app.post("/api/customer/new-full-kyc")
def create_full_kyc(data: FullCustomerKYCPayload):
    try:
        clean_mobile = data.mobile.strip()
        existing = supabase.table("test_customers").select("id, name").eq("mobile", clean_mobile).execute()
        if existing.data:
            raise HTTPException(status_code=400, detail=f"இந்த மொபைல் எண் ஏற்கனவே உள்ளது ({existing.data[0]['name']}).")
        record = data.model_dump()
        record["kyc_status"] = "PENDING"
        record["is_active"] = True
        res = supabase.table("test_customers").insert(record).execute()
        return {"status": "success", "message": "முழு KYC சமர்ப்பிக்கப்பட்டது! தலைமை ஒப்புதலுக்குக் காத்திருக்கிறது.", "data": res.data or []}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KYC பதிவு பிழை: {str(e)}")

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
        return {"status": "success", "message": "விபர மாற்றக் கோரிக்கை தலைமையக ஒப்புதலுக்கு அனுப்பப்பட்டது.", "data": res.data or []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"கோரிக்கை பதிவு பிழை: {str(e)}")

# ==========================================
# 🔄 உள்-பணப் பரிமாற்றம் & கருவூல மேலாண்மை (Treasury Transfers)
# ==========================================

class TreasuryTransferRequest(BaseModel):
    transfer_type: str  # BRANCH_TO_HQ, HQ_TO_BRANCH, CASH_TO_BANK, BANK_TO_CASH
    branch_id: int
    company_bank_id: Optional[int] = None
    amount: float
    carrier_person: Optional[str] = None
    reference_no: Optional[str] = None
    proof_doc: Optional[str] = None
    notes: Optional[str] = None
    staff_id: int

class TreasuryApprovalPayload(BaseModel):
    transfer_id: int
    action: str  # APPROVE / REJECT
    admin_id: int

@app.post("/api/treasury/transfer-request")
def create_treasury_transfer(data: dict):
    try:
        branch_id = data.get("branch_id") or 1
        trans_date = data.get("transaction_date") or datetime.now(IST).strftime("%Y-%m-%d")

        # நாள் பூட்டப்பட்டுள்ளதா எனச் சரிபார்த்தல்
        day_chk = (
            supabase.table("test_branch_cash_days")
            .select("status")
            .eq("branch_id", branch_id)
            .eq("business_date", trans_date)
            .execute()
        )
        if day_chk.data and day_chk.data[0].get("status") == "CLOSED":
            raise HTTPException(
                status_code=400, 
                detail=f"⚠️ {trans_date} நாளுக்கான மாலை கணக்கு ஏற்கனவே பூட்டப்பட்டுவிட்டது! இந்தப் பழைய தேதியில் புதிய பணப் பரிமாற்றம் செய்ய முடியாது."
            )

        from_src = "BRANCH_CASH"
        to_dest = "HQ_VAULT"
        transfer_type = data.get("transfer_type")

        if transfer_type == "HQ_TO_BRANCH":
            from_src = "HQ_VAULT"
            to_dest = "BRANCH_CASH"
        elif transfer_type == "CASH_TO_BANK":
            from_src = "BRANCH_CASH"
            to_dest = "COMPANY_BANK"
        elif transfer_type == "BANK_TO_CASH":
            from_src = "COMPANY_BANK"
            to_dest = "BRANCH_CASH"

        rec = {
            "transfer_type": transfer_type,
            "from_source": from_src,
            "to_destination": to_dest,
            "branch_id": branch_id,
            "company_bank_id": data.get("company_bank_id"),
            "amount": float(data.get("amount") or 0.0),
            "carrier_person": data.get("carrier_person"),
            "reference_no": data.get("reference_no"),
            "proof_doc": data.get("proof_doc"),
            "notes": data.get("notes"),
            "status": "PENDING",
            "created_by": data.get("staff_id"),
            "transaction_date": trans_date,
            "created_at": datetime.now(IST).isoformat()
        }
        res = supabase.table("test_treasury_transfers").insert(rec).execute()
        return {"status": "success", "message": "பணப் பரிமாற்றக் கோரிக்கை தலைமையக ஒப்புதலுக்கு அனுப்பப்பட்டது.", "data": res.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"பரிமாற்றப் பதிவு பிழை: {str(e)}")

@app.get("/api/hq/pending-treasury-transfers")
def get_pending_treasury_transfers():
    try:
        branch_res = supabase.table("test_branches").select("id, branch_name").execute()
        b_map = {b["id"]: b.get("branch_name") for b in (branch_res.data or [])}

        bank_res = supabase.table("test_company_banks").select("id, bank_name, account_no").execute()
        bk_map = {b["id"]: f"{b['bank_name']} ({b['account_no']})" for b in (bank_res.data or [])}

        res = (
            supabase.table("test_treasury_transfers")
            .select("*")
            .eq("status", "PENDING")
            .order("id", desc=True)
            .execute()
        )
        data = res.data or []
        for x in data:
            x["branch_name"] = b_map.get(x.get("branch_id"), f"கிளை #{x.get('branch_id')}")
            if x.get("company_bank_id"):
                x["company_bank_label"] = bk_map.get(x.get("company_bank_id"), "-")

        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/approve-treasury-transfer")
def approve_treasury_transfer(data: TreasuryApprovalPayload):
    try:
        status = "APPROVED" if data.action == "APPROVE" else "REJECTED"
        
        t_res = supabase.table("test_treasury_transfers").select("*").eq("id", data.transfer_id).execute()
        if not t_res.data:
            raise HTTPException(status_code=404, detail="பரிமாற்ற விபரம் கிடைக்கவில்லை")
        transfer = t_res.data[0]

        # வங்கி சம்பந்தப்பட்டிருந்தால் நிறுவன வங்கி இருப்பைப் புதுப்பித்தல்
        if status == "APPROVED" and transfer.get("company_bank_id"):
            amt = float(transfer.get("amount") or 0.0)
            bk_res = supabase.table("test_company_banks").select("*").eq("id", transfer["company_bank_id"]).execute()
            if bk_res.data:
                comp_bank = bk_res.data[0]
                cur_bal = float(comp_bank.get("current_balance") or comp_bank.get("opening_balance") or 0.0)
                
                if transfer.get("transfer_type") == "CASH_TO_BANK":
                    new_bal = cur_bal + amt  # வங்கியில் ரொக்கம் சேர்ந்தது
                elif transfer.get("transfer_type") == "BANK_TO_CASH":
                    new_bal = cur_bal - amt  # வங்கியிலிருந்து ரொக்கம் எடுக்கப்பட்டது
                else:
                    new_bal = cur_bal

                supabase.table("test_company_banks").update({"current_balance": new_bal}).eq("id", transfer["company_bank_id"]).execute()

        supabase.table("test_treasury_transfers").update({
            "status": status,
            "approved_by": data.admin_id,
            "approved_at": "now()"
        }).eq("id", data.transfer_id).execute()

        return {"status": "success", "message": f"பரிமாற்றம் வெற்றிகரமாக '{status}' செய்யப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ==========================================
# 🏷️ வட்டி தள்ளுபடி (Interest Rebate) ஒப்புதல் மையம்
# ==========================================

@app.post("/api/rebate/request")
def request_interest_rebate(data: dict):
    try:
        rec = {
            "visit_id": data.get("visit_id"),
            "loan_id": data.get("loan_id"),
            "loan_no": data.get("loan_no"),
            "customer_id": data.get("customer_id"),
            "branch_id": data.get("branch_id") or 1,
            "calculated_interest": float(data.get("calculated_interest") or 0),
            "requested_rebate": float(data.get("requested_rebate") or 0),
            "reason": data.get("reason") or "வட்டி தள்ளுபடி கோரிக்கை",
            "status": "PENDING",
            "requested_by": data.get("staff_id") or 1
        }
        res = supabase.table("test_rebate_approvals").insert(rec).execute()
        req_id = res.data[0]["id"] if res.data else None
        return {"status": "success", "request_id": req_id, "message": "வட்டி தள்ளுபடி ஒப்புதலுக்கு அனுப்பப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/rebate/status/{req_id}")
def check_rebate_status(req_id: int):
    try:
        res = supabase.table("test_rebate_approvals").select("status").eq("id", req_id).execute()
        status = res.data[0]["status"] if res.data else "PENDING"
        return {"status": "success", "approval_status": status}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/hq/pending-rebates")
def get_pending_rebates():
    try:
        cust_res = supabase.table("test_customers").select("id, name, mobile").execute()
        c_map = {c["id"]: c for c in (cust_res.data or [])}

        br_res = supabase.table("test_branches").select("id, branch_name").execute()
        b_map = {b["id"]: b.get("branch_name") for b in (br_res.data or [])}

        res = supabase.table("test_rebate_approvals").select("*").eq("status", "PENDING").order("id", desc=True).execute()
        data = res.data or []
        for r in data:
            c = c_map.get(r.get("customer_id"), {})
            r["customer_name"] = c.get("name", "-")
            r["customer_mobile"] = c.get("mobile", "-")
            r["branch_name"] = b_map.get(r.get("branch_id"), f"கிளை #{r.get('branch_id')}")
        return {"status": "success", "data": data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/hq/approve-rebate")
def approve_rebate_request(data: dict):
    try:
        req_id = data.get("request_id")
        action = data.get("action") # APPROVE / REJECT
        admin_id = data.get("admin_id") or 1
        new_status = "APPROVED" if action == "APPROVE" else "REJECTED"

        supabase.table("test_rebate_approvals").update({
            "status": new_status,
            "approved_by": admin_id,
            "approved_at": datetime.now(IST).isoformat()
        }).eq("id", req_id).execute()

        return {"status": "success", "message": f"வட்டி தள்ளுபடி கோரிக்கை '{new_status}' செய்யப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

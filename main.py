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
    title="Gold Branch Management - Strict RBAC & CRUD",
    version="2.2.0"
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
        formatted_amount = f"{abs(amount):,.2f}"
        var_values = f"{customer_name}|{formatted_amount}|{otp_code}"
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
            return True, "SMS வெற்றிகரமாக அனுப்பப்பட்டது!"
        err_msg = res_json.get("message") or str(res_json)
        return False, str(err_msg)
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

class NewCustomerKYC(BaseModel):
    name: str
    mobile: str
    mobile2: Optional[str] = None
    guardian_name: Optional[str] = None
    address: Optional[str] = None
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

class DirectSettlementPayload(BaseModel):
    customer_id: int
    branch_id: int = 1
    net_amount: float
    direction: str
    settlement_type: str
    cash_amount: float = 0.0
    bank_amount: float = 0.0
    bank_ref_no: Optional[str] = None
    bank_name: Optional[str] = None
    denominations: Optional[DenominationCounts] = None

# --- Endpoints ---

@app.get("/")
def serve_ui():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return {"message": "FastAPI சர்வர் இயங்குகிறது."}

@app.get("/health")
def health_check():
    return {"status": "active", "service": "Enterprise API"}

# 1. Login API (துல்லியமான பூலியன் பாதுகாப்போடு)
@app.post("/api/auth/staff-login")
def staff_unified_login(data: LoginRequest):
    try:
        res = (
            supabase.table("test_staff_users")
            .select("*, test_branches(branch_name)")
            .eq("username", data.username.strip())
            .eq("password", data.password.strip())
            .execute()
        )

        if not res.data:
            # Fallback for older demo accounts
            f_res = supabase.table("test_users").select("*").eq("username", data.username.strip()).eq("password", data.password.strip()).execute()
            if not f_res.data:
                raise HTTPException(status_code=401, detail="பயனர் பெயர் அல்லது கடவுச்சொல் தவறானது!")
            u = f_res.data[0]
            is_adm = (u.get("role") == "ADMIN")
            return {
                "status": "success",
                "user": {
                    "id": u["id"],
                    "username": u["username"],
                    "full_name": u["full_name"],
                    "role_key": u.get("role", "BRANCH_STAFF"),
                    "branch_id": u.get("branch_id", 1),
                    "branch_name": u.get("branch_name", "Thingalnagar"),
                    "permissions": {
                        "can_access_counter": True,
                        "can_approve_kyc": is_adm,
                        "can_approve_updates": is_adm,
                        "can_manage_users": is_adm
                    }
                }
            }

        user = res.data[0]
        if not user.get("is_active", True):
            raise HTTPException(status_code=403, detail="இந்தக் கணக்கு முடக்கப்பட்டுள்ளது.")

        branch_info = user.get("test_branches") or {}
        user_profile = {
            "id": user["id"],
            "username": user["username"],
            "full_name": user["full_name"],
            "role_key": user.get("role_key", "BRANCH_STAFF"),
            "branch_id": user.get("branch_id") or 1,
            "branch_name": branch_info.get("branch_name", "Branch"),
            "permissions": {
                "can_access_counter": bool(user.get("can_access_counter", True)),
                "can_approve_kyc": bool(user.get("can_approve_kyc", False)),
                "can_approve_updates": bool(user.get("can_approve_updates", False)),
                "can_manage_users": bool(user.get("can_manage_users", False))
            }
        }
        return {"status": "success", "message": "உள்நுழைவு முடிந்தது!", "user": user_profile}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"உள்நுழைவு பிழை: {str(e)}")

# 2. கிளைகள் மேலாண்மை (CRUD: Read, Create, Update, Delete)
@app.get("/api/admin/branches")
def get_branches():
    try:
        res = supabase.table("test_branches").select("*").order("id", desc=True).execute()
        return {"status": "success", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"கிளைகள் பட்டியல் பிழை: {str(e)}")

@app.post("/api/admin/branch/create")
def create_branch(data: BranchPayload):
    try:
        res = supabase.table("test_branches").insert(data.model_dump()).execute()
        return {"status": "success", "message": "புதிய கிளை உருவாக்கப்பட்டது.", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"கிளை உருவாக்கம் பிழை: {str(e)}")

@app.put("/api/admin/branch/{branch_id}")
def update_branch(branch_id: int, data: BranchPayload):
    try:
        res = supabase.table("test_branches").update(data.model_dump()).eq("id", branch_id).execute()
        return {"status": "success", "message": "கிளை விபரங்கள் புதுப்பிக்கப்பட்டன."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"கிளை திருத்தம் பிழை: {str(e)}")

@app.delete("/api/admin/branch/{branch_id}")
def delete_branch(branch_id: int):
    try:
        supabase.table("test_branches").delete().eq("id", branch_id).execute()
        return {"status": "success", "message": "கிளை நீக்கப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"கிளை நீக்கல் பிழை: {str(e)}")

# 3. பணியாளர் மேலாண்மை (CRUD: Read, Create, Update, Delete)
@app.get("/api/admin/staff")
def get_staff_list():
    try:
        res = supabase.table("test_staff_users").select("*, test_branches(branch_name)").order("id", desc=True).execute()
        return {"status": "success", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"பணியாளர் பட்டியல் பிழை: {str(e)}")

@app.post("/api/admin/staff/create")
def create_staff(data: StaffPayload):
    try:
        check = supabase.table("test_staff_users").select("id").eq("username", data.username.strip()).execute()
        if check.data:
            raise HTTPException(status_code=400, detail="இந்தப் பயனர் பெயர் ஏற்கனவே உள்ளது.")

        res = supabase.table("test_staff_users").insert(data.model_dump()).execute()
        return {"status": "success", "message": "புதிய பணியாளர் கணக்கு உருவாக்கப்பட்டது.", "data": res.data}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"பணியாளர் உருவாக்கம் பிழை: {str(e)}")

@app.put("/api/admin/staff/{staff_id}")
def update_staff(staff_id: int, data: StaffPayload):
    try:
        update_dict = {
            "full_name": data.full_name,
            "mobile": data.mobile,
            "role_key": data.role_key,
            "branch_id": data.branch_id,
            "can_access_counter": data.can_access_counter,
            "can_approve_kyc": data.can_approve_kyc,
            "can_approve_updates": data.can_approve_updates,
            "can_manage_users": data.can_manage_users
        }
        if data.password:
            update_dict["password"] = data.password

        supabase.table("test_staff_users").update(update_dict).eq("id", staff_id).execute()
        return {"status": "success", "message": "பணியாளர் விபரங்கள் புதுப்பிக்கப்பட்டன."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"பணியாளர் திருத்தம் பிழை: {str(e)}")

@app.delete("/api/admin/staff/{staff_id}")
def delete_staff(staff_id: int):
    try:
        supabase.table("test_staff_users").delete().eq("id", staff_id).execute()
        return {"status": "success", "message": "பணியாளர் கணக்கு நீக்கப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"பணியாளர் நீக்கல் பிழை: {str(e)}")

# 4. தலைமையக ஒப்புதல்கள்
@app.get("/api/hq/pending-approvals")
def get_pending_approvals():
    try:
        kyc_pending = supabase.table("test_customers").select("*").eq("kyc_status", "PENDING").execute()
        updates_pending = supabase.table("test_customer_update_requests").select("*, test_customers(name, mobile)").eq("status", "PENDING").execute()
        return {
            "status": "success",
            "pending_kyc": kyc_pending.data,
            "pending_updates": updates_pending.data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"ஒப்புதல் பட்டியல் பிழை: {str(e)}")

@app.post("/api/hq/approve-kyc")
def process_kyc_approval(data: ApprovalActionPayload):
    try:
        status = "VERIFIED" if data.action == "APPROVE" else "REJECTED"
        supabase.table("test_customers").update({"kyc_status": status}).eq("id", data.request_id).execute()
        return {"status": "success", "message": f"KYC நிலை '{status}' என மாற்றப்பட்டது."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"KYC ஒப்புதல் பிழை: {str(e)}")

@app.post("/api/hq/approve-update")
def process_update_approval(data: ApprovalActionPayload):
    try:
        req_res = supabase.table("test_customer_update_requests").select("*").eq("id", data.request_id).execute()
        if not req_res.data:
            raise HTTPException(status_code=404, detail="கோரிக்கை கிடைக்கவில்லை.")

        req = req_res.data[0]
        if data.action == "APPROVE":
            changes = req.get("requested_changes", {})
            update_data = {}
            if "mobile" in changes and changes["mobile"]:
                update_data["mobile"] = changes["mobile"]
            if "address" in changes and changes["address"]:
                update_data["address"] = changes["address"]

            if update_data:
                supabase.table("test_customers").update(update_data).eq("id", req["customer_id"]).execute()

            supabase.table("test_customer_update_requests").update({"status": "APPROVED"}).eq("id", data.request_id).execute()
            return {"status": "success", "message": "விபர மாற்றம் புதுப்பிக்கப்பட்டது."}
        else:
            supabase.table("test_customer_update_requests").update({"status": "REJECTED"}).eq("id", data.request_id).execute()
            return {"status": "success", "message": "விபர மாற்றம் நிராகரிக்கப்பட்டது."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"மாற்ற ஒப்புதல் பிழை: {str(e)}")

# 5. வாடிக்கையாளர் தேடல் & வருகை
@app.get("/api/customer/search")
def search_customer(query: str = Query(..., min_length=1)):
    try:
        clean_query = query.strip()
        if clean_query.isdigit():
            res = supabase.table("test_customers").select("id, name, mobile, mobile2, guardian_name, address, branch_id, kyc_status, is_active").ilike("mobile", f"%{clean_query}%").limit(10).execute()
        else:
            res = supabase.table("test_customers").select("id, name, mobile, mobile2, guardian_name, address, branch_id, kyc_status, is_active").ilike("name", f"%{clean_query}%").limit(10).execute()
        return {"status": "success", "count": len(res.data), "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"தேடல் பிழை: {str(e)}")

@app.post("/api/customer/visit")
def log_customer_visit(data: CustomerVisitEntry):
    try:
        record = {"customer_id": data.customer_id, "branch_id": data.branch_id, "purpose": data.purpose}
        res = supabase.table("test_customer_visits").insert(record).execute()
        return {"status": "success", "message": "வருகை பதிவானது", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"வருகைப் பதிவு பிழை: {str(e)}")

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
        return {"status": "success", "message": "KYC சமர்ப்பிக்கப்பட்டது. தலைமை ஒப்புதலுக்குக் காத்திருக்கிறது.", "data": res.data}
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
        return {"status": "success", "message": "விபர மாற்றக் கோரிக்கை அனுப்பப்பட்டது.", "data": res.data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"மாற்றக் கோரிக்கை பிழை: {str(e)}")

# 6. நகைக்கடன் பதிவு
@app.post("/api/loan/new-pawn")
def create_new_pawn(data: NewGoldLoanEntry):
    try:
        if not data.items:
            raise HTTPException(status_code=400, detail="குறைந்தது ஒரு நகையாவது சேர்க்கப்பட வேண்டும்.")

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
            "branch_id": data.branch_id,
            "status": "ACTIVE"
        }
        res_loan = supabase.table("test_gold_loans").insert(loan_record).execute()
        new_loan_id = res_loan.data[0]["id"]

        items_payload = []
        for i in data.items:
            items_payload.append({
                "loan_id": new_loan_id,
                "item_type": i.item_type.strip(),
                "item_count": i.item_count,
                "gross_weight": i.gross_weight,
                "net_weight": i.net_weight,
                "purity": i.purity
            })
        supabase.table("test_gold_loan_items").insert(items_payload).execute()

        return {"status": "success", "message": "நகைக்கடன் வெற்றிகரமாகச் சேமிக்கப்பட்டது.", "loan_id": new_loan_id, "net_payable": net_payable}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"அடகுப் பதிவு பிழை: {str(e)}")

# 7. OTP & Settle
@app.post("/api/otp/send")
def trigger_otp_sms(payload: SendOtpPayload):
    try:
        otp_code = str(random.randint(100000, 999999))
        txn_type = "receive" if payload.direction == "COMPANY_PAYABLE" else "pay"

        success, msg = send_fast2sms_otp(
            mobile_no=payload.mobile,
            otp_code=otp_code,
            customer_name=payload.customer_name,
            amount=payload.net_amount,
            txn_type=txn_type
        )

        if not success:
            raise HTTPException(status_code=502, detail=f"SMS அனுப்புவதில் தோல்வி: {msg}")

        supabase.table("test_transaction_otps").insert({
            "customer_id": payload.customer_id,
            "mobile": payload.mobile,
            "otp_code": otp_code,
            "net_amount": payload.net_amount,
            "txn_type": txn_type,
            "is_verified": False
        }).execute()

        return {"status": "success", "message": "OTP வாடிக்கையாளர் மொபைலுக்கு SMS மூலம் அனுப்பப்பட்டது."}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OTP பிழை: {str(e)}")

@app.post("/api/transaction/settle-with-otp")
def settle_with_otp(data: SettleWithOtpPayload):
    try:
        otp_query = (
            supabase.table("test_transaction_otps")
            .select("id, otp_code, is_verified")
            .eq("customer_id", data.customer_id)
            .eq("is_verified", False)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )

        if not otp_query.data:
            raise HTTPException(status_code=400, detail="செல்லுபடியாகும் OTP கோரிக்கை எதுவும் இல்லை.")

        latest_otp = otp_query.data[0]
        if latest_otp["otp_code"] != data.otp_code.strip():
            raise HTTPException(status_code=400, detail="உள்ளிட்ட OTP தவறானது. மீண்டும் முயற்சிக்கவும்.")

        if data.cash_amount > 0 and data.denominations:
            calc_cash = (
                data.denominations.c_500 * 500 +
                data.denominations.c_200 * 200 +
                data.denominations.c_100 * 100 +
                data.denominations.c_50 * 50 +
                data.denominations.c_20 * 20 +
                data.denominations.c_10 * 10 +
                data.denominations.c_coins
            )
            if round(calc_cash, 2) != round(data.cash_amount, 2):
                raise HTTPException(status_code=400, detail=f"தாள்களின் கூட்டுத்தொகை (₹{calc_cash}) பொருந்தவில்லை.")

        settle_record = {
            "customer_id": data.customer_id,
            "branch_id": data.branch_id,
            "net_amount": data.net_amount,
            "settlement_type": data.settlement_type,
            "cash_amount": data.cash_amount,
            "bank_amount": data.bank_amount,
            "bank_ref_no": data.bank_ref_no,
            "bank_name": data.bank_name,
            "direction": data.direction
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

        supabase.table("test_transaction_otps").update({"is_verified": True}).eq("id", latest_otp["id"]).execute()

        return {"status": "success", "message": "🎉 பரிவர்த்தனை முடிவடைந்தது! வருகை நிறைவு செய்யப்பட்டது.", "settlement_id": new_settle_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"செட்டில்மென்ட் பிழை: {str(e)}")

@app.post("/api/transaction/settle")
def direct_settle_transaction(data: DirectSettlementPayload):
    try:
        if data.cash_amount > 0 and data.denominations:
            calc_cash = (
                data.denominations.c_500 * 500 +
                data.denominations.c_200 * 200 +
                data.denominations.c_100 * 100 +
                data.denominations.c_50 * 50 +
                data.denominations.c_20 * 20 +
                data.denominations.c_10 * 10 +
                data.denominations.c_coins
            )
            if round(calc_cash, 2) != round(data.cash_amount, 2):
                raise HTTPException(status_code=400, detail=f"தாள்களின் கூட்டுத்தொகை பொருந்தவில்லை.")

        settle_record = {
            "customer_id": data.customer_id,
            "branch_id": data.branch_id,
            "net_amount": data.net_amount,
            "settlement_type": data.settlement_type,
            "cash_amount": data.cash_amount,
            "bank_amount": data.bank_amount,
            "bank_ref_no": data.bank_ref_no,
            "bank_name": data.bank_name,
            "direction": data.direction
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

        return {"status": "success", "message": "✅ பரிவர்த்தனை வெற்றிகரமாகச் சேமிக்கப்பட்டது!", "settlement_id": new_settle_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"செட்டில்மென்ட் பிழை: {str(e)}")

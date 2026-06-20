from flask import Blueprint, request, jsonify
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    jwt_required,
    get_jwt_identity,
    get_jwt
)
from werkzeug.security import check_password_hash
from datetime import datetime, timezone, timedelta
import logging

from models import Admin, LoginLog, db
from extensions import limiter, redis_client

auth_bp = Blueprint("auth", __name__)

# إعداد السجلات لمراقبة الأخطاء (Loggers)
logger = logging.getLogger(__name__)

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION_MINUTES = 15


# ==========================================
# دالة مساعدة لضمان استمرارية الريديس (Ensure Redis Reliability)
# ==========================================
def safe_redis_execute(func, *args, **kwargs):
    """
    دالة دفاعية لتشغيل أوامر الريديس.
    إذا تشنج خادم الريديس أو سقط، لا ينهار السيرفر بالكامل، بل يسجل الخطأ ويستمر العمل.
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"Redis Connection Error: {str(e)}")
        return None


# ==========================================
# 1. LOGIN
# ==========================================
@auth_bp.route("/api/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    user_ip = request.remote_addr or "0.0.0.0"
    user_agent = request.user_agent.string if request.user_agent else "Unknown"

    # 1. المعالجة الآمنة لحالات الـ None (Handle None Cases)
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"success": False, "message": "Invalid or missing JSON payload"}), 400

    username = data.get("username")
    password = data.get("password")

    # التحقق الصارم من المدخلات الفارغة أو الأنواع غير النصية
    if not isinstance(username, str) or not isinstance(password, str):
        return jsonify({"success": False, "message": "Username and password must be valid strings"}), 400

    username = username.strip()
    if not username or not password:
        return jsonify({"success": False, "message": "Username and password cannot be empty"}), 400

    # 2. الاستعلام الآمن من قاعدة البيانات
    try:
        admin = Admin.query.filter_by(username=username).first()
    except Exception as e:
        logger.critical(f"Database error during login: {str(e)}")
        return jsonify({"success": False, "message": "Internal service disruption"}), 500

    if not admin:
        return jsonify({"success": False, "message": "Invalid credentials"}), 401

    # 3. فحص الحساب المقفل (Account Lock) مع معالجة الـ None في التواريخ
    if admin.is_locked:
        lockout_time = admin.lockout_until.replace(tzinfo=timezone.utc) if admin.lockout_until else datetime.now(
            timezone.utc)
        if datetime.now(timezone.utc) > lockout_time:
            admin.is_locked = False
            admin.failed_attempts = 0
            db.session.commit()
        else:
            time_left = max(0, (lockout_time - datetime.now(timezone.utc)).seconds // 60)
            return jsonify({"success": False, "message": f"Account is locked. Try again in {time_left} minutes."}), 403

    # 4. التحقق من كلمة المرور ومعالجة الفشل
    if admin.password is None or not check_password_hash(admin.password, password):
        admin.failed_attempts = (admin.failed_attempts or 0) + 1

        if admin.failed_attempts >= MAX_FAILED_ATTEMPTS:
            admin.is_locked = True
            admin.lockout_until = datetime.now(timezone.utc) + timedelta(minutes=LOCKOUT_DURATION_MINUTES)
            message = f"Invalid credentials. Account locked for {LOCKOUT_DURATION_MINUTES} minutes."
        else:
            message = f"Invalid credentials. Attempts left: {MAX_FAILED_ATTEMPTS - admin.failed_attempts}"

        log = LoginLog(admin_id=admin.id, ip_address=user_ip, user_agent=user_agent, status="failed")
        db.session.add(log)
        db.session.commit()
        return jsonify({"success": False, "message": message}), 401

    # 5. نجاح تسجيل الدخول
    admin.failed_attempts = 0
    admin.is_locked = False
    admin.lockout_until = None

    log = LoginLog(admin_id=admin.id, ip_address=user_ip, user_agent=user_agent, status="success")
    db.session.add(log)
    db.session.commit()

    # نظام صلاحيات مرن مبني على معالجة الـ None
    user_role = admin.role if admin.role else "user"
    additional_claims = {
        "role": user_role,
        "username": admin.username,
        "type": "access"  # تتبع دورة حياة التوكن (Token Lifecycle)
    }

    access = create_access_token(identity=str(admin.id), additional_claims=additional_claims)

    # وسم توكن التحديث بشكل صريح لمنع استخدامه في مسارات الـ Access
    refresh_claims = {"role": user_role, "type": "refresh"}
    refresh = create_refresh_token(identity=str(admin.id), additional_claims=refresh_claims)

    return jsonify({
        "success": True,
        "access_token": access,
        "refresh_token": refresh,
        "user": {
            "id": admin.id,
            "username": admin.username,
            "role": user_role
        }
    })


# ==========================================
# 2. PROTECTED REFRESH ENDPOINT (WITH ROTATION)
# ==========================================
@auth_bp.route("/api/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """
    مسار التحديث المحمي بالكامل (Protect Refresh Endpoint):
    يفحص جودة التوكن، يمنع هجمات التبديل، ويضمن سلامة تتبع دورة الحياة.
    """
    user_id = get_jwt_identity()
    refresh_jwt = get_jwt()

    # 1. تتبع دورة الحياة ومنع التلاعب (Token Lifecycle & Type Check)
    if refresh_jwt.get("type") != "refresh":
        return jsonify({"success": False, "message": "Invalid token type for this endpoint"}), 400

    refresh_jti = refresh_jwt.get("jti")
    user_role = refresh_jwt.get("role", "user")

    if not refresh_jti:
        return jsonify({"success": False, "message": "Malformed token payload"}), 400

    # 2. فحص القائمة السوداء مع ضمان موثوقية الريديس (Redis Reliability)
    is_blacklisted = safe_redis_execute(redis_client.get, f"bl_{refresh_jti}")
    if is_blacklisted:
        # ثغرة خرق أمني (Token Reuse): تم إعادة استخدام توكن مستهلك!
        safe_redis_execute(redis_client.set, f"user_block_{user_id}", "true", ex=3600)
        return jsonify({"success": False, "message": "Security Alert: Session hijacked. Please re-login."}), 401

    is_user_blocked = safe_redis_execute(redis_client.get, f"user_block_{user_id}")
    if is_user_blocked:
        return jsonify({"success": False, "message": "Access denied due to previous security incident."}), 401

    # 3. إدراج التوكن القديم في القائمة السوداء فوراً (Rotation)
    exp_timestamp = refresh_jwt.get("exp")
    if exp_timestamp:
        rem_time = datetime.fromtimestamp(exp_timestamp, timezone.utc) - datetime.now(timezone.utc)
        ex_seconds = max(1, int(rem_time.total_seconds()))
        safe_redis_execute(redis_client.set, f"bl_{refresh_jti}", "used", ex=ex_seconds)

    # 4. توليد زوج توكنز جديد آمن مع وسم دورة الحياة
    new_access_claims = {"role": user_role, "type": "access"}
    new_refresh_claims = {"role": user_role, "type": "refresh"}

    new_access = create_access_token(identity=str(user_id), additional_claims=new_access_claims)
    new_refresh = create_refresh_token(identity=str(user_id), additional_claims=new_refresh_claims)

    return jsonify({
        "access_token": new_access,
        "refresh_token": new_refresh
    })


# ==========================================
# 3. LOGOUT
# ==========================================
@auth_bp.route("/api/logout", methods=["POST"])
@jwt_required()
def logout():
    access_jwt = get_jwt()
    access_jti = access_jwt.get("jti")
    exp_timestamp = access_jwt.get("exp")

    if access_jti and exp_timestamp:
        rem_time = datetime.fromtimestamp(exp_timestamp, timezone.utc) - datetime.now(timezone.utc)
        ex_seconds = max(1, int(rem_time.total_seconds()))
        safe_redis_execute(redis_client.set, f"bl_{access_jti}", "revoked", ex=ex_seconds)

    return jsonify({"success": True, "message": "Successfully logged out"})

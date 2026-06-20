from functools import wraps
from flask import jsonify
from flask_jwt_extended import verify_jwt_in_request, get_jwt
from flask_jwt_extended.exceptions import JWTExtendedException


def admin_required(fn):
    """
    مزخرف صارم لحماية مسارات لوحة التحكم:
    1. يتحقق من وجود توكن عبور (Access Token) صالح.
    2. يمنع استخدام توكن التحديث (Refresh Token) لدخول المسارات الحساسة.
    3. يتأكد من أن دور المستخدم هو "admin" حصراً.
    """

    @wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            # 1. التحقق من وجود توكن صالح في الطلب
            verify_jwt_in_request()
            claims = get_jwt()

            # 2. حماية استباقية: منع استخدام Refresh Token في مسارات الـ Access
            if claims.get("type") != "access":
                return jsonify({
                    "success": False,
                    "message": "Invalid token type. Access token required."
                }), 401

            # 3. التحقق من الصلاحيات (Role System)
            if claims.get("role") != "admin":
                return jsonify({
                    "success": False,
                    "message": "Access denied. Administrators only."
                }), 403

        # نلتقط فقط أخطاء الـ JWT المحددة لكي نترك الأخطاء الأخرى تذهب لمعالج الأخطاء العام
        except (JWTExtendedException, Exception) as e:
            # إذا كان الخطأ قادم من انتهاء صلاحية أو تلاعب بالتوكن، نتركه يمر لـ register_jwt_handlers
            # أما إذا أردنا معالجته هنا محلياً، نرد بـ jsonify لتوحيد هيكل البيانات للفرونت اند
            return jsonify({
                "success": False,
                "message": "Authentication required or token invalid"
            }), 401

        return fn(*args, **kwargs)

    return wrapper
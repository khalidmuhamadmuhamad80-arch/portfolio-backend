import re
import bleach
from flask import Blueprint, request, jsonify
from extensions import db, limiter  # استيراد الـ limiter المركزي
from models import Contact

contact_bp = Blueprint("contact", __name__)

# تعبير نمطي معتمد للتحقق من صحة البريد الإلكتروني (Email Regex)
EMAIL_REGEX = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"


@contact_bp.route("/api/contact", methods=["POST"])
# 1. Rate Limiting: حد أقصى 3 رسائل في الدقيقة و 10 في الساعة لكل IP لمنع الإغراق
@limiter.limit("3 per minute; 10 per hour")
def contact():
    # المعالجة الآمنة لحالات الـ JSON الفارغ
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"success": False, "message": "Invalid or missing JSON payload"}), 400

    # 2. Spam Protection: تقنية الـ Honeypot
    # الفرونت اند يصمم حقل اسمه "website" ويكون مخفي تماماً بالـ CSS عن المستخدم
    # البوتات (Bots) ستقوم بملئه تلقائياً، فإذا وجدنا فيه نصاً، نعلم أنه سبام ونرفضه!
    honeypot = data.get("website")
    if honeypot:
        # نرد بـ 200 نجاح وهمي (Fake Success) لخداع البوت وجعله يظن أنه نجح فلا يحاول مجدداً
        return jsonify({"success": True, "message": "Message sent successfully (Spam Filtered)"}), 200

    raw_name = data.get("name")
    raw_email = data.get("email")
    raw_message = data.get("message")

    # التحقق من وجود الحقول وأنها نصوص وليست أنواعاً أخرى
    if not isinstance(raw_name, str) or not isinstance(raw_email, str) or not isinstance(raw_message, str):
        return jsonify({"success": False, "message": "All fields must be valid strings"}), 400

    # إزالة المسافات الزائدة من الأطراف
    name = raw_name.strip()
    email = raw_email.strip().lower()
    message = raw_message.strip()

    # التحقق من الحقول الفارغة بعد الفلترة
    if not name or not email or not message:
        return jsonify({"success": False, "message": "All fields are required"}), 400

    # التحقق من أطوال المدخلات (حماية حجم البيانات)
    if len(name) < 2 or len(name) > 100:
        return jsonify({"success": False, "message": "Name must be between 2 and 100 characters"}), 400

    if len(message) > 1000:
        return jsonify({"success": False, "message": "Message cannot exceed 1000 characters"}), 400

    # 3. Email Validation: التحقق الصارم من هيكل البريد الإلكتروني
    if not re.match(EMAIL_REGEX, email):
        return jsonify({"success": False, "message": "Invalid email address format"}), 400

    # 4. Sanitization: تنظيف النصوص تماماً من أي وسوم HTML أو سكريبتات خبيثة
    # مكتبة bleach تقوم بتجريد النص وتحويل الأكواد مثل <script> إلى نصوص آمنة تماماً
    clean_name = bleach.clean(name, tags=[], strip=True)
    clean_message = bleach.clean(message, tags=[], strip=True)

    try:
        new_msg = Contact(
            name=clean_name,
            email=email,  # الإيميل مفحوص مسبقاً بالـ Regex ولا يحتاج bleach
            message=clean_message
        )

        db.session.add(new_msg)
        db.session.commit()

        return jsonify({"success": True, "message": "Your message has been sent successfully"}), 201

    except Exception:
        db.session.rollback()  # التراجع لحماية جلسة قاعدة البيانات من التعليق
        return jsonify({"success": False, "message": "An internal error occurred. Please try again later."}), 500
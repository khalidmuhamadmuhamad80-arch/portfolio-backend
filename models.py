from extensions import db
from datetime import datetime, timezone


# ==========================================
# 1. MODEL: CONTACT (نظام رسائل التواصل)
# ==========================================
class Contact(db.Model):
    __tablename__ = "contacts"  # تحديد اسم الجدول صراحة (Clean Code)

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    message = db.Column(db.Text, nullable=False)

    # استخدام الطريقة الحديثة والآمنة للمناطق الزمنية
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


# ==========================================
# 2. MODEL: PROJECT (معرض الأعمال والمشاريع)
# ==========================================
class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(150), nullable=False)  # رفعنا الطول لـ 150 ليتوافق مع الـ Validation
    description = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(500))  # زيادة الطول لاستيعاب روابط الـ GitHub الطويلة
    image_url = db.Column(db.String(500))  # زيادة الطول لروابط الصور السحابية
    video_url = db.Column(db.String(500))  # زيادة الطول لروابط اليوتيوب

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


# ==========================================
# 3. MODEL: ADMIN (إدارة المستخدمين والصلاحيات)
# ==========================================
class Admin(db.Model):
    __tablename__ = "admins"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)  # رفع الطول لـ 255 لأن الهاش الحديث يكون طويلاً جداً

    # 🔐 إضافة ميزة: الـ Role System كامل
    role = db.Column(db.String(20), default="admin", nullable=False)

    # 🔐 إضافة ميزة: الحماية الصارمة وقفل الحساب (Account Lock)
    failed_attempts = db.Column(db.Integer, default=0, nullable=False)
    is_locked = db.Column(db.Boolean, default=False, nullable=False)
    lockout_until = db.Column(db.DateTime, nullable=True)  # يمكن أن يكون فارغاً إذا كان الحساب نشطاً

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # ربط علاقة وراثية لجلب سجلات تسجيل الدخول الخاصة بهذا الأدمن بسهولة (Relationship)
    login_logs = db.relationship('LoginLog', backref='admin', lazy=True, cascade="all, delete-orphan")


# ==========================================
# 4. MODEL: LOGIN LOG (📈 تتبع محاولات الدخول الخبيثة والصحيحة)
# ==========================================
class LoginLog(db.Model):
    __tablename__ = "login_logs"

    id = db.Column(db.Integer, primary_key=True)
    admin_id = db.Column(db.Integer, db.ForeignKey('admins.id', ondelete="CASCADE"), nullable=False)

    ip_address = db.Column(db.String(50), nullable=False, default="0.0.0.0")
    user_agent = db.Column(db.String(255), nullable=False, default="Unknown")
    status = db.Column(db.String(20), nullable=False)  # نجاح (success) أو فشل (failed)

    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
import os
from app import create_app
from extensions import db
from models import Admin
from utils.security import hash_password

app = create_app()


def seed_admin():
    """سكريبت آمن وذكي لإنشاء حساب المشرف الافتراضي"""
    with app.app_context():
        print("\n" + "=" * 50)
        print("🚀 STARTING ADMIN CREATION SEEDER...")
        print("=" * 50)

        # 🔐 جلب البيانات من متغيرات البيئة لتأمينها، مع توفير قيم افتراضية للتطوير المحلي
        username = os.environ.get("DEFAULT_ADMIN_USER", "moko")
        raw_password = os.environ.get("DEFAULT_ADMIN_PASS", "100300")
        admin_role = "admin"  # تعيين الصلاحية الافتراضية

        try:
            # 🔍 الفحص الاستباقي: التحقق من وجود الحساب مسبقاً لمنع انهيار الكود
            existing_admin = Admin.query.filter_by(username=username).first()

            if existing_admin:
                print(f"ℹ️  Admin with username '{username}' already exists.")
                # اختياري: يمكنك تحديث كلمة المرور هنا إن أردت، أو تخطي العملية
                print("⏭️  Skipping creation to avoid duplicate entries.")
                print("=" * 50 + "\n")
                return

            # 🛠️ إنشاء كائن المشرف الجديد بأمان
            new_admin = Admin(
                username=username,
                password=hash_password(raw_password),
                role=admin_role  # تأكيد تمرير الـ role المتوافق مع باقى المسارات
            )

            db.session.add(new_admin)
            db.session.commit()

            print(f"✅ Admin '{username}' created successfully!")
            print(f"📝 Credentials used -> User: {username} | Pass: {raw_password}")
            print("⚠️  REMEMBER: Change these credentials in production environment variables!")

        except Exception as e:
            db.session.rollback()  # تراجع عن العمليات في حال حدوث أي خطأ في قاعدة البيانات
            print(f"❌ CRITICAL ERROR: Could not create admin. Reason: {str(e)}")

        print("=" * 50 + "\n")


if __name__ == "__main__":
    seed_admin()
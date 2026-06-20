from app import create_app  # استخدام الـ Application Factory الذي قمنا بتطويره
from extensions import db
from models import Admin


def check_all_admins():
    """سكريبت فحص وطباعة المشرفين المسجلين في النظام"""
    app = create_app()

    with app.app_context():
        print("\n" + "=" * 50)
        print("🔍 STARTING DATABASE ADMIN CHECK...")
        print("=" * 50)

        try:
            # جلب جميع المشرفين
            admins = Admin.query.all()

            if not admins:
                print("⚠️  No administrators found in the database.")
                return

            print(f"📊 Total Admins Found: {len(admins)}\n")
            print(f"{'ID':<5} | {'Username':<20} | {'Role':<15}")
            print("-" * 50)

            for admin in admins:
                # 🛠️ تم إصلاح الخطأ هنا من admins.role إلى admin.role
                print(f"{admin.id:<5} | {admin.username:<20} | {admin.role:<15}")

        except Exception as e:
            print(f"❌ CRITICAL ERROR DURING CHECK: {str(e)}")

        print("=" * 50 + "\n")


if __name__ == "__main__":
    check_all_admins()

import os
import secrets
import logging
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from sqlalchemy import or_

from extensions import db
from models import Project
from utils.decorators import admin_required

projects_bp = Blueprint("projects", __name__)

# إعداد السجلات (Clean Code & Diagnostics)
logger = logging.getLogger(__name__)

# إعدادات الميديا والملفات
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 ميجابايت


def allowed_file(filename):
    """فحص امتداد الملف أمنياً"""
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


# 8. 📊 دالة معيارية لتوحيد شكل الاستجابة (Response Standard)
def make_api_response(success, message, data=None, meta=None, status_code=200):
    response = {"success": success, "message": message}
    if data is not None:
        response["data"] = data
    if meta is not None:
        response["meta"] = meta
    return jsonify(response), status_code


# ==========================================
# 1. READ ALL (With Search, Pagination, Sorting, Performance)
# ==========================================
@projects_bp.route("/api/projects", methods=["GET"])
def get_projects():
    # 7. ⚠️ Error Handling العام للمسار
    try:
        # 3. 🔍 Search
        search_query = request.args.get("q", "").strip()

        # 5. 📉 Sorting (الافتراضي: الأحدث أولاً)
        sort_by = request.args.get("sort_by", "created_at").strip()
        sort_order = request.args.get("order", "desc").strip()

        # 2. 📄 Pagination
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 6, type=int)

        # بناء الاستعلام الأساسي (Query Optimization)
        query = Project.query

        # تطبيق البحث إن وجد
        if search_query:
            query = query.filter(
                or_(
                    Project.title.ilike(f"%{search_query}%"),
                    Project.description.ilike(f"%{search_query}%")
                )
            )

        # تطبيق الترتيب ديناميكياً بأمان لمنع الـ SQL Injection
        if sort_by == "title":
            sort_column = Project.title
        else:
            sort_column = Project.id  # ترتيب افتراضي آمن بالـ ID

        if sort_order == "asc":
            query = query.order_by(sort_column.asc())
        else:
            query = query.order_by(sort_column.desc())

        # 9. ⚡ Performance: جلب البيانات مجزأة ومقيدة من قاعدة البيانات مباشرة
        paginated_projects = query.paginate(page=page, per_page=per_page, error_out=False)

        # تجهيز البيانات
        projects_list = [
            {
                "id": p.id,
                "title": p.title,
                "description": p.description,
                "link": p.link or "",
                "image_url": p.image_url or "",
                "video_url": p.video_url or "",
            }
            for p in paginated_projects.items
        ]

        meta_data = {
            "total_items": paginated_projects.total,
            "pages": paginated_projects.pages,
            "current_page": paginated_projects.page,
            "per_page": paginated_projects.per_page
        }

        return make_api_response(True, "Projects retrieved successfully", data=projects_list, meta=meta_data)

    except Exception as e:
        logger.error(f"Error in get_projects: {str(e)}")
        return make_api_response(False, "Failed to retrieve projects due to an internal error", status_code=500)


# ==========================================
# 2. READ SINGLE (Handle None Cases)
# ==========================================
@projects_bp.route("/api/projects/<int:project_id>", methods=["GET"])
def get_project_by_id(project_id):
    try:
        project = Project.query.get(project_id)
        if not project:
            return make_api_response(False, "Project not found", status_code=404)

        data = {
            "id": project.id,
            "title": project.title,
            "description": project.description,
            "link": project.link or "",
            "image_url": project.image_url or "",
            "video_url": project.video_url or ""
        }
        return make_api_response(True, "Project retrieved successfully", data=data)

    except Exception as e:
        logger.error(f"Error in get_project_by_id: {str(e)}")
        return make_api_response(False, "Internal server error", status_code=500)


# ==========================================
# 3. CREATE (1. 🔐 Authentication CRUD + 4. 🧼 Validation)
# ==========================================
@projects_bp.route("/api/projects", methods=["POST"])
@admin_required  # حماية الدخول للأدمن فقط
def create_project():
    try:
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        link = request.form.get("link", "").strip()
        video_url = request.form.get("video_url", "").strip()

        # 4. 🧼 Validation الصارم للمدخلات
        if not title or not description:
            return make_api_response(False, "Title and description are required fields", status_code=400)

        if len(title) < 3 or len(title) > 150:
            return make_api_response(False, "Title must be between 3 and 150 characters", status_code=400)

        image_url = ""

        # التعامل الآمن مع رفع الملفات
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename != "":
                if not allowed_file(file.filename):
                    return make_api_response(False, "Invalid image format. Allowed: PNG, JPG, JPEG, WEBP",
                                             status_code=400)

                # فحص حجم الملف (Performance & Protection)
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)  # إعادة المؤشر لأول الملف لقراءته

                if file_size > MAX_FILE_SIZE_BYTES:
                    return make_api_response(False, "Image size exceeds the 5MB limit", status_code=400)

                filename = secure_filename(file.filename)
                unique_filename = f"proj_{secrets.token_hex(8)}_{filename}"

                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                image_url = f"/uploads/{unique_filename}"

        new_project = Project(
            title=title,
            description=description,
            link=link,
            image_url=image_url,
            video_url=video_url
        )
        db.session.add(new_project)
        db.session.commit()

        return make_api_response(True, "Project created successfully", data={"id": new_project.id}, status_code=201)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in create_project: {str(e)}")
        return make_api_response(False, "Failed to create project", status_code=500)


# ==========================================
# 4. UPDATE (Partial Validation & Asset Management)
# ==========================================
@projects_bp.route("/api/projects/<int:project_id>", methods=["PUT"])
@admin_required
def update_project(project_id):
    try:
        project = Project.query.get(project_id)
        if not project:
            return make_api_response(False, "Project not found", status_code=404)

        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        link = request.form.get("link", "").strip()
        video_url = request.form.get("video_url", "").strip()

        # تحديث الحقول النصية إذا تم إرسالها فقط (Flexibility)
        if title:
            if len(title) < 3 or len(title) > 150:
                return make_api_response(False, "Title must be between 3 and 150 characters", status_code=400)
            project.title = title

        if description:
            project.description = description

        if link:
            project.link = link
        if video_url:
            project.video_url = video_url

        # معالجة رفع صورة جديدة وحذف القديمة لعدم هدر المساحة
        if "image" in request.files:
            file = request.files["image"]
            if file and file.filename != "":
                if not allowed_file(file.filename):
                    return make_api_response(False, "Invalid image format", status_code=400)

                # حذف الصورة القديمة من السيرفر فوراً
                if project.image_url:
                    old_path = os.path.join(UPLOAD_FOLDER, project.image_url.split("/uploads/")[-1])
                    if os.path.exists(old_path):
                        os.remove(old_path)

                filename = secure_filename(file.filename)
                unique_filename = f"proj_{secrets.token_hex(8)}_{filename}"
                file.save(os.path.join(UPLOAD_FOLDER, unique_filename))
                project.image_url = f"/uploads/{unique_filename}"

        db.session.commit()
        return make_api_response(True, "Project updated successfully")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in update_project: {str(e)}")
        return make_api_response(False, "Failed to update project", status_code=500)


# ==========================================
# 5. DELETE (With Auto Purge)
# ==========================================
@projects_bp.route("/api/projects/<int:project_id>", methods=["DELETE"])
@admin_required
def delete_project(project_id):
    try:
        project = Project.query.get(project_id)
        if not project:
            return make_api_response(False, "Project not found", status_code=404)

        # حذف الملف الفيزيائي من نظام التشغيل
        if project.image_url:
            file_path = os.path.join(UPLOAD_FOLDER, project.image_url.split("/uploads/")[-1])
            if os.path.exists(file_path):
                os.remove(file_path)

        db.session.delete(project)
        db.session.commit()

        return make_api_response(True, "Project and assets deleted successfully")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in delete_project: {str(e)}")
        return make_api_response(False, "Failed to delete project", status_code=500)
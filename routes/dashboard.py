from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/api/dashboard", methods=["GET"])
@jwt_required()
def dashboard():
    claims = get_jwt()

    if claims.get("role") != "admin":
        return {"message": "Forbidden"}, 403

    return jsonify({
        "message": "dashboard works"
    })
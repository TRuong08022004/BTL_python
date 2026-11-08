from flask import Blueprint, abort, jsonify, render_template, request
from sqlalchemy import Integer, cast, select

from ..helpers import action_response, amount, login_required, record_id, text_field
from ..models import ROOM_CLASSES, ROOM_STATUSES, Room, db

rooms = Blueprint("rooms", __name__)


@rooms.route("/rooms", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "create":
            status = request.form.get("status", "empty")
            if status not in ("empty", "repair"):
                raise ValueError("Trạng thái phòng mới không hợp lệ.")
            room = Room(
                room_number=text_field("room_number", 30),
                area=amount("area", positive=True, maximum=999999.99, optional=True),
                monthly_price=amount("monthly_price", positive=True),
                electricity_price=amount("electricity_price", maximum=9999999999),
                water_price=amount("water_price", maximum=9999999999),
                status=status,
                description=text_field("description", 5000, required=False),
            )
            db.session.add(room)
            db.session.commit()
            return action_response("Đã thêm phòng mới.", "rooms.index")
        if action == "delete":
            room = db.get_or_404(Room, record_id("id"))
            if room.contracts:
                raise ValueError("Phòng đã có hợp đồng nên không thể xóa.")
            db.session.delete(room)
            db.session.commit()
            return action_response("Đã xóa phòng.", "rooms.index")
        raise ValueError("Thao tác không hợp lệ.")
    query = select(Room).order_by(cast(Room.room_number, Integer), Room.room_number)
    return render_template(
        "rooms.html",
        rooms=db.session.scalars(query).all(),
        page_title="Quản lý phòng",
        active_page="rooms",
    )


@rooms.post("/api/rooms/update-status")
@login_required
def update_status():
    room_id = record_id("id")
    status = request.form.get("status", "")
    if status not in ROOM_STATUSES:
        raise ValueError("Dữ liệu trạng thái không hợp lệ.")
    room = db.session.scalar(select(Room).where(Room.id == room_id).with_for_update())
    if room is None:
        abort(404, "Không tìm thấy phòng.")
    if room.active_contract and status == "empty":
        raise ValueError(
            "Phòng đang có hợp đồng hiệu lực nên không thể chuyển thành còn trống."
        )
    if not room.active_contract and status == "rented":
        raise ValueError(
            "Cần tạo hợp đồng trước khi chuyển phòng sang trạng thái đang thuê."
        )
    room.status = status
    db.session.commit()
    return jsonify(
        success=True,
        message="Đã cập nhật trạng thái phòng.",
        data=dict(
            room_id=room.id,
            status=status,
            status_label=ROOM_STATUSES[status],
            status_class=ROOM_CLASSES[status],
        ),
    )

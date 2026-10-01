"""
YANGI OPERATSION MODULLAR — DB testlari (v4)

Qamrov:
- Yoqilg'i nazorati: quyish qaydi, prev_odometer avtomatik, 100km sarf hisobi, me'yordan oshish
- Avans hisoboti: yaratish (raqam avtomatik), tasdiqlash/rad etish, jami summalar
- Yig'ish varaqasi: yaratish, holat yangilash
- Shubhali harakat: log qo'shish, ro'yxat va holat
- Sotuvchilar reytingi: eng yaxshi sotuvchi taxtasi
"""
from datetime import datetime, timedelta

from database import models, crud


class TestFuelLogs:
    def test_create_fuel_log_generates_cost(self, db_session):
        entry = crud.create_fuel_log(db_session, {
            "driver_name": "Ali", "vehicle": "01A123BB",
            "odometer_km": 12000, "liters": 45.0,
            "price_per_liter": 6800, "created_by": "Haydovchi",
        })
        assert entry.id is not None
        assert entry.total_cost == 45.0 * 6800
        assert entry.prev_odometer_km is None

    def test_prev_odometer_auto_filled(self, db_session):
        crud.create_fuel_log(db_session, {"driver_id": 1, "driver_name": "Ali",
                                          "odometer_km": 10000, "liters": 40.0})
        second = crud.create_fuel_log(db_session, {"driver_id": 1, "driver_name": "Ali",
                                                   "odometer_km": 10500, "liters": 50.0})
        assert second.prev_odometer_km == 10000

    def test_fuel_efficiency_norm(self, db_session):
        """500 km masofa, 50 litr -> 10 L/100km (me'yor 15 dan past -> yaxshi)"""
        crud.create_fuel_log(db_session, {"driver_id": 1, "driver_name": "Ali",
                                          "odometer_km": 10000, "liters": 40.0})
        crud.create_fuel_log(db_session, {"driver_id": 1, "driver_name": "Ali",
                                          "odometer_km": 10500, "liters": 50.0})
        stats = crud.get_fuel_efficiency(db_session, driver_id=1, norm_liters_per_100km=15)
        assert stats["avg_liters_per_100km"] == 10.0
        assert stats["over_norm"] is False

    def test_fuel_efficiency_over_norm(self, db_session):
        """100 km, 40 litr -> 40 L/100km (me'yordan 2.6x oshgan)"""
        crud.create_fuel_log(db_session, {"driver_id": 1, "driver_name": "Ali",
                                          "odometer_km": 10000, "liters": 40.0})
        crud.create_fuel_log(db_session, {"driver_id": 1, "driver_name": "Ali",
                                          "odometer_km": 10100, "liters": 40.0})
        stats = crud.get_fuel_efficiency(db_session, driver_id=1, norm_liters_per_100km=15)
        assert stats["over_norm"] is True
        assert stats["avg_liters_per_100km"] == 40.0

    def test_fuel_no_odometer_no_efficiency(self, db_session):
        crud.create_fuel_log(db_session, {"driver_name": "Ali", "liters": 25.0})
        stats = crud.get_fuel_efficiency(db_session, days=30)
        assert stats["avg_liters_per_100km"] is None
        assert stats["logs_count"] == 1

    def test_list_fuel_logs_ordered(self, db_session):
        crud.create_fuel_log(db_session, {"driver_name": "Ali", "liters": 25.0})
        crud.create_fuel_log(db_session, {"driver_name": "Vali", "liters": 30.0})
        logs = crud.list_fuel_logs(db_session)
        assert len(logs) == 2


class TestExpenseReports:
    def test_create_auto_number(self, db_session):
        r1 = crud.create_expense_report(db_session, {
            "employee_name": "Xodim", "category": "yoqilgi", "amount": 150_000,
            "created_by": "Xodim",
        })
        r2 = crud.create_expense_report(db_session, {
            "employee_name": "Xodim", "category": "ovqat", "amount": 50_000,
            "created_by": "Xodim",
        })
        assert r1.report_number.startswith("EXP-")
        assert r2.report_number != r1.report_number
        assert r1.status == "kutilmoqda"

    def test_approve_and_reject(self, db_session):
        r = crud.create_expense_report(db_session, {
            "employee_name": "Xodim", "category": "yol_hagi", "amount": 200_000,
            "created_by": "Xodim",
        })
        approved = crud.review_expense_report(db_session, r.id, "tasdiqlangan",
                                              reviewed_by="Direktor", note="OK")
        assert approved.status == "tasdiqlangan"
        assert approved.reviewed_by == "Direktor"
        assert approved.reviewed_at is not None

        rejected = crud.review_expense_report(db_session, r.id, "rad_etilgan",
                                              reviewed_by="Direktor")
        assert rejected.status == "rad_etilgan"

    def test_review_unknown_returns_none(self, db_session):
        assert crud.review_expense_report(db_session, 999999, "tasdiqlangan") is None

    def test_totals_only_approved(self, db_session):
        crud.create_expense_report(db_session, {"employee_name": "A", "category": "a",
                                                "amount": 100_000, "created_by": "A"})
        r2 = crud.create_expense_report(db_session, {"employee_name": "A", "category": "a",
                                                     "amount": 300_000, "created_by": "A"})
        crud.review_expense_report(db_session, r2.id, "tasdiqlangan", reviewed_by="D")
        totals = crud.get_expense_totals(db_session, days=30)
        assert totals["approved_total"] == 300_000
        assert totals["by_status"]["kutilmoqda"] == 100_000

    def test_list_by_status(self, db_session):
        crud.create_expense_report(db_session, {"employee_name": "A", "category": "a",
                                                "amount": 100_000, "created_by": "A"})
        r2 = crud.create_expense_report(db_session, {"employee_name": "A", "category": "a",
                                                     "amount": 100_000, "created_by": "A"})
        crud.review_expense_report(db_session, r2.id, "tasdiqlangan", reviewed_by="D")
        pending = crud.list_expense_reports(db_session, status="kutilmoqda")
        approved = crud.list_expense_reports(db_session, status="tasdiqlangan")
        assert len(pending) == 1
        assert len(approved) == 1


class TestPickingList:
    def test_create_auto_number(self, db_session):
        item = crud.create_picking_list(db_session, {
            "product_id": 1, "product_name": "G'isht", "quantity": 500,
            "sector": "A1", "created_by": "Omborchi",
        })
        assert item.picking_number.startswith("PKG-")
        assert item.status == "yangi"

    def test_status_transition(self, db_session):
        item = crud.create_picking_list(db_session, {
            "product_id": 1, "product_name": "G'isht", "quantity": 500, "created_by": "Omborchi",
        })
        updated = crud.update_picking_status(db_session, item.id, "tayyor", picked_by="Omborchi")
        assert updated.status == "tayyor"
        assert updated.picked_by == "Omborchi"
        assert updated.picked_at is not None

        sent = crud.update_picking_status(db_session, item.id, "yuborilgan")
        assert sent.status == "yuborilgan"

    def test_update_unknown_returns_none(self, db_session):
        assert crud.update_picking_status(db_session, 999999, "tayyor") is None

    def test_list_by_status(self, db_session):
        crud.create_picking_list(db_session, {"product_id": 1, "product_name": "A",
                                              "quantity": 10, "created_by": "O"})
        crud.create_picking_list(db_session, {"product_id": 2, "product_name": "B",
                                              "quantity": 20, "created_by": "O"})
        items = crud.list_picking_lists(db_session, status="yangi")
        assert len(items) == 2


class TestSuspiciousActivity:
    def test_log_and_list(self, db_session):
        crud.log_suspicious_activity(
            db_session, "big_discount", severity="high",
            description="5% limitdan oshish", user_name="Sotuvchi", user_id=42,
        )
        acts = crud.list_suspicious_activities(db_session)
        assert len(acts) == 1
        assert acts[0].activity_type == "big_discount"
        assert acts[0].severity == "high"
        assert acts[0].user_id == 42

    def test_update_status(self, db_session):
        act = crud.log_suspicious_activity(db_session, "night_sale", severity="medium",
                                            description="Tungi sotuv", user_name="Kassir")
        updated = crud.update_suspicious_status(db_session, act.id, "hal_qilingan")
        assert updated.status == "hal_qilingan"

    def test_update_unknown_returns_none(self, db_session):
        assert crud.update_suspicious_status(db_session, 999999, "hal_qilingan") is None

    def test_filter_by_status(self, db_session):
        crud.log_suspicious_activity(db_session, "a", description="x")
        act = crud.log_suspicious_activity(db_session, "b", description="y")
        crud.update_suspicious_status(db_session, act.id, "ko'rib_chiqilgan")
        pending = crud.list_suspicious_activities(db_session, status="yangi")
        reviewed = crud.list_suspicious_activities(db_session, status="ko'rib_chiqilgan")
        assert len(pending) == 1
        assert len(reviewed) == 1


class TestSellerRatings:
    def test_ratings_ordered_by_score(self, db_session):
        from database import crud as c
        db_session.add(models.Product(name="R G'isht", category="g'isht", unit="dona",
                                      selling_price=1000, production_cost=500, is_active=True))
        db_session.commit()
        product = db_session.query(models.Product).first()
        # Ikkita sotuvchi turli hajmda sotadi
        c.create_sale_record(db_session, product_id=product.id, quantity=10, unit_price=1000,
                             total_amount=10_000, payment_method="cash",
                             customer_name="A", user_id=1, user_name="Sotuvchi A")
        c.create_sale_record(db_session, product_id=product.id, quantity=10, unit_price=1000,
                             total_amount=10_000, payment_method="cash",
                             customer_name="A", user_id=1, user_name="Sotuvchi A")
        c.create_sale_record(db_session, product_id=product.id, quantity=10, unit_price=1000,
                             total_amount=10_000, payment_method="cash",
                             customer_name="B", user_id=2, user_name="Sotuvchi B")

        ratings = crud.get_seller_ratings(db_session, days=30)
        assert len(ratings) == 2
        # Eng ko'p sotgan birinchi o'rinda
        assert ratings[0]["seller"] == "Sotuvchi A"
        assert ratings[0]["rank"] == 1
        assert ratings[0]["sales_count"] == 2
        assert ratings[1]["rank"] == 2

    def test_ratings_empty(self, db_session):
        assert crud.get_seller_ratings(db_session) == []
from utils.auth_db import (
    create_user,
    delete_user_data,
    get_conn,
    get_user_by_email,
    init_db,
    purge_expired_data,
    save_analysis_log,
    save_chat_log,
    save_weather_log,
)


def test_delete_user_removes_associated_personal_data():
    init_db()
    assert create_user("Delete Me", "delete@example.com", "StrongPass1!")[0]
    user = get_user_by_email("delete@example.com")
    user_id = int(user["id"])
    save_analysis_log(user_id, "leaf.jpg", "Healthy", 0.9, "N/A", "None")
    save_chat_log(user_id, "user", "Private farm question")
    save_weather_log(user_id, "Farm", 30, 70, 2, "Clear", "live")

    delete_user_data(user_id)

    assert get_user_by_email("delete@example.com") is None
    with get_conn() as connection:
        assert connection.execute(
            "SELECT COUNT(*) AS c FROM analysis_logs WHERE user_id = ?", (user_id,)
        ).fetchone()["c"] == 0
        assert connection.execute(
            "SELECT COUNT(*) AS c FROM chat_logs WHERE user_id = ?", (user_id,)
        ).fetchone()["c"] == 0


def test_retention_purge_removes_old_records_only():
    init_db()
    assert create_user("Retention", "retention@example.com", "StrongPass1!")[0]
    user_id = int(get_user_by_email("retention@example.com")["id"])
    save_analysis_log(user_id, "old.jpg", "Healthy", 0.9, "N/A", "None")
    save_chat_log(user_id, "user", "Old message")
    with get_conn() as connection:
        connection.execute(
            "UPDATE analysis_logs SET created_at = ? WHERE user_id = ?",
            ("2000-01-01T00:00:00+00:00", user_id),
        )
        connection.execute(
            "UPDATE chat_logs SET created_at = ? WHERE user_id = ?",
            ("2000-01-01T00:00:00+00:00", user_id),
        )

    deleted = purge_expired_data(analysis_retention_days=30, weather_retention_days=30, chat_retention_days=30)

    assert deleted["analysis_logs"] == 1
    assert deleted["chat_logs"] == 1

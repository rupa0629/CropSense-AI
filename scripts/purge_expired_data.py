"""Apply configured personal-data retention windows."""

from config.settings import get_settings
from utils.auth_db import purge_expired_data


def main() -> None:
    settings = get_settings()
    deleted = purge_expired_data(
        analysis_retention_days=settings.analysis_retention_days,
        weather_retention_days=settings.weather_retention_days,
        chat_retention_days=settings.chat_retention_days,
    )
    print("Retention purge completed:", deleted)


if __name__ == "__main__":
    main()

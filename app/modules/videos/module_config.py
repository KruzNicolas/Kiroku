from app.shared.config.settings import get_settings


def get_videos_database_id() -> str:
    database_id = get_settings().notion_database_id_videos
    if not database_id:
        raise ValueError(
            "NOTION_DATABASE_ID_VIDEOS (or legacy NOTION_DATABASE_ID) is required"
        )
    return database_id

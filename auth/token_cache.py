import stat
import msal
from config import TOKEN_PATH


def load_cache() -> msal.SerializableTokenCache:
    cache = msal.SerializableTokenCache()
    if TOKEN_PATH.exists():
        cache.deserialize(TOKEN_PATH.read_text(encoding="utf-8"))
    return cache


def save_cache(cache: msal.SerializableTokenCache) -> None:
    if cache.has_state_changed:
        TOKEN_PATH.write_text(cache.serialize(), encoding="utf-8")
        try:
            TOKEN_PATH.chmod(stat.S_IRUSR | stat.S_IWUSR)
        except Exception:
            pass

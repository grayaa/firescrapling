"""Compatibility shim — re-exports split modules so `import main as core` keeps working.

New code should import from db / auth_service / keys_service / jobs_service /
crawl_runner / admin_service / extraction directly. This module stays thin for one
milestone, then imports can be updated and this file removed.
"""
from __future__ import annotations

from db import (  # noqa: F401
    CACHE_DIR,
    DATA_DIR,
    DB_PATH,
    _BACKEND_ROOT,
    _REPO_ROOT,
    _connect,
    _get_db,
    _migrate_api_key_hashing,
    _migrate_jobs_and_idempotency,
    configure_logging,
    default_database_url,
    get_engine,
    init_db,
    metadata,
    reset_engine,
)
from auth_service import (  # noqa: F401
    count_users,
    create_session_token,
    hash_password,
    login_user,
    register_user,
    registration_is_open,
    resolve_session_token,
    revoke_session_token,
    verify_password,
)
from keys_service import (  # noqa: F401
    create_api_key,
    delete_api_key,
    get_api_keys,
    get_api_usage,
    get_usage_summary,
    hash_api_key,
    key_hint_from_value,
    list_api_keys_masked,
    mask_key_value,
    record_api_usage,
    resolve_api_key,
    touch_api_key_last_used,
)
from jobs_service import (  # noqa: F401
    _add_log,
    _notify_job_webhook,
    _update_job_progress,
    count_job_results,
    create_job_with_idempotency,
    delete_job,
    delete_job_for_user,
    get_job_by_id,
    get_job_for_user,
    get_job_history,
    get_job_logs,
    get_job_logs_after,
    get_job_results,
    get_job_results_for_user,
)
from extraction import (  # noqa: F401
    _extract_structured_via_openrouter,
    extract_structured_via_openrouter,
)
from crawl_runner import (  # noqa: F401
    crawl_site_streaming,
    map_domain,
    run_crawl_background,
    run_scrape_background,
    scrape_page_streaming,
    spawn_crawl_thread,
    spawn_crawl_thread_local,
    spawn_scrape_thread,
    spawn_scrape_thread_local,
)
from admin_service import (  # noqa: F401
    admin_delete_job,
    admin_delete_user,
    admin_get_health,
    admin_get_stats,
    admin_list_jobs,
    admin_list_users,
)

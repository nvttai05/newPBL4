import structlog, sys, logging

def setup_logging():
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    structlog.configure(
        processors=[structlog.processors.add_log_level, structlog.processors.JSONRenderer()],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger()

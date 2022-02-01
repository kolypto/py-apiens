import logging.config


LOGGING_CONFIG_DICT = {
    'version': 1,
    'disable_existing_loggers': False,

    # Config for logging.root - the special Logger() object that by default collects all
    # messages from all modules in the system. All messages from child loggers are
    # propagated (redirected) to this logger (unless propagate=False is set).
    'root': {
        'level': logging.INFO,
        'handlers': [
            'console',
        ],
    },
    'formatters': {
        'standard': {
            # 'format': "%(asctime)s - %(levelname)s - %(message)s",
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'standard',
            'level': logging.INFO,
            'stream': 'ext://sys.stdout',
        },
    },
}


def basicConfig():
    """ Do basic logging configuration that most apps will be happy with """
    logging.basicConfig()
    logging.config.dictConfig(LOGGING_CONFIG_DICT)

    logging.root.setLevel(logging.INFO)

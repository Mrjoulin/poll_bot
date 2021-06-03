import coloredlogs
import logging

field_styles = coloredlogs.DEFAULT_FIELD_STYLES
field_styles["levelname"] = dict(color='green', bold=True)

coloredlogs.install(
    fmt='[%(asctime)s: %(filename)s:%(lineno)s - %(funcName)10s()] %(levelname)s:%(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    field_styles=field_styles,
    level=logging.INFO
)

logging.info(f'Logging level has been set to {logging.getLogger().getEffectiveLevel()}')

# Remove telegram updating logging warnings
logging.getLogger("telegram.vendor.ptb_urllib3.urllib3.connectionpool").setLevel(logging.ERROR)

from .bot import start_bot

start_bot()

import os
import logging
logging.basicConfig(level=logging.INFO)
logging.info('[TEST] os imported')
logging.info('[TEST] PATH: %s', os.getenv('PATH'))

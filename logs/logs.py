import logging

class CustomFormatter(logging.Formatter):
    #These are the sequences need to get colored ouput
    RESET_SEQ = "\033[0m"
    COLOR_SEQ = "\033[1;%dm"
    BOLD_SEQ = "\033[1m"
    blue = "\x1b[33;94m"
    green = "\x1b[33;92m"
    white = "\x1b[33;97m"
    grey = "\x1b[38;20m"
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    reset = "\x1b[0m"
    format = "%(asctime)s [%(threadName)s] [%(name)s] [%(levelname)s]"+" %(message)s " +" (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.DEBUG: blue + format + reset,
        logging.INFO: green + format + reset,
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: bold_red + format + reset
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def setUpLog():
    # Create and configure logger
    logger = logging.getLogger('trakr-ai')
    # fileHandler = logging.FileHandler("{0}/{1}.log".format("./Logs","main"))
    # fileHandler.setFormatter(CustomFormatter())
    # logger.addHandler(fileHandler)
    consoleHandler = logging.StreamHandler()
    consoleHandler.setFormatter(CustomFormatter())
    logger.addHandler(consoleHandler)

    # Setting the threshold of logger to DEBUG
    logger.setLevel(logging.INFO)
    return logger



logger = setUpLog()
from os import get_terminal_size
from itertools import cycle
from time import sleep
from threading import Thread
from traceback import TracebackException
from enum import Enum
from tqdm import tqdm

from zotify.config import *
from zotify.zotify import Zotify

UP_ONE_LINE = "\033[A"
DOWN_ONE_LINE = "\033[B"
START_OF_PREV_LINE = "\033[F"
CLEAR_LINE = "\033[K"


class PrintChannel(Enum):
    MANDATORY = "MANDATORY"
    
    SPLASH = PRINT_SPLASH
    
    WARNINGS = PRINT_WARNINGS
    ERRORS = PRINT_ERRORS
    API_ERRORS = PRINT_API_ERRORS
    
    PROGRESS_INFO = PRINT_PROGRESS_INFO
    SKIPS = PRINT_SKIPS
    DOWNLOADS = PRINT_DOWNLOADS


ERROR_CHANNELS = [PrintChannel.WARNINGS, PrintChannel.ERRORS, PrintChannel.API_ERRORS]
EVENT_CHANNELS = [PrintChannel.PROGRESS_INFO, PrintChannel.SKIPS, PrintChannel.DOWNLOADS]


class Printer:
    @staticmethod
    def print(channel: PrintChannel, msg: str) -> None:
        if channel == PrintChannel.MANDATORY or Zotify.CONFIG.get(channel.value):
            try:
                columns, _ = get_terminal_size()
            except OSError:
                columns = 80
            for line in msg.splitlines():
                tqdm.write(line.ljust(columns))
    
    @staticmethod
    def print_loader(channel: PrintChannel, msg: str) -> None:
        if channel == PrintChannel.MANDATORY or Zotify.CONFIG.get(channel.value):
            Printer.print(channel, START_OF_PREV_LINE*2 + msg)
    
    @staticmethod
    def progress(iterable=None, desc=None, total=None, unit='it', disable=False, unit_scale=False, unit_divisor=1000, pos=1):
        return tqdm(iterable=iterable, desc=desc, total=total, disable=disable, leave=False, position=pos, 
                    unit=unit, unit_scale=unit_scale, unit_divisor=unit_divisor)
    
    @staticmethod
    def json_dump_printer(obj: dict) -> None:
        try:
            columns, _ = get_terminal_size()
        except OSError:
            columns = 80
        Printer.print(PrintChannel.ERRORS, "#" * columns)
        Printer.print(PrintChannel.ERRORS, json.dumps(obj, indent=2))
        Printer.print(PrintChannel.ERRORS, "#" * columns + "\n")
    
    @staticmethod
    def traceback_printer(e: Exception) -> None:
        Printer.print(PrintChannel.ERRORS, "\n")
        Printer.print(PrintChannel.ERRORS, "".join(TracebackException.from_exception(e).format()))
        Printer.print(PrintChannel.ERRORS, "\n\n")


# load symbol from:
# https://stackoverflow.com/questions/22029562/python-how-to-make-simple-animated-loading-while-process-is-running


class Loader:
    """Busy symbol.
    
    Can be called inside a context:
    
    with Loader("This take some Time..."):
        # do something
        pass
    """
    def __init__(self, chan, desc="Loading...", end='', timeout=0.1, mode='prog'):
        """
        A loader-like context manager
        
        Args:
            desc (str, optional): The loader's description. Defaults to "Loading...".
            end (str, optional): Final print. Defaults to "".
            timeout (float, optional): Sleep time between prints. Defaults to 0.1.
        """
        self.desc = desc
        self.end = end
        self.timeout = timeout
        self.channel = chan
        
        self._thread = Thread(target=self._animate, daemon=True)
        if mode == 'std1':
            self.steps = ["⢿", "⣻", "⣽", "⣾", "⣷", "⣯", "⣟", "⡿"]
        elif mode == 'std2':
            self.steps = ["◜","◝","◞","◟"]
        elif mode == 'std3':
            self.steps = ["😐 ","😐 ","😮 ","😮 ","😦 ","😦 ","😧 ","😧 ","🤯 ","💥 ","✨ ","\u3000 ","\u3000 ","\u3000 "]
        elif mode == 'prog':
            self.steps = ["[∙∙∙]","[●∙∙]","[∙●∙]","[∙∙●]","[∙∙∙]"]
        
        self.done = False
    
    def start(self):
        Printer.print(self.channel, "\n")
        self._thread.start()
        return self
    
    def _animate(self):
        for c in cycle(self.steps):
            if self.done:
                break
            Printer.print_loader(self.channel, f"\t{c} {self.desc}")
            sleep(self.timeout)
    
    def __enter__(self):
        self.start()
    
    def stop(self):
        self.done = True
        if self.end != "":
            Printer.print(self.channel, self.end)
    
    def __exit__(self, exc_type, exc_value, tb):
        # handle exceptions with those variables ^
        self.stop()

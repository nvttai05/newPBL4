from pathlib import Path
from .base import Runner

class PythonRunner(Runner):
    def command(self, entry: Path):
        return ["/usr/bin/python3", str(entry)]

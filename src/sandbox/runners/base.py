from pathlib import Path
from typing import List

class Runner:
    def command(self, entry: Path) -> List[str]:
        raise NotImplementedError

from ccdexplorer_fundamentals.tooter import Tooter, TooterChannel, TooterType
from rich.console import Console

from env import ADMIN_CHAT_ID

console = Console()


class Utils:
    def send_to_tooter(self, msg: str):
        self.tooter: Tooter
        self.tooter.relay(
            channel=TooterChannel.NOTIFIER,
            title="",
            chat_id=ADMIN_CHAT_ID,
            body=msg,
            notifier_type=TooterType.INFO,
        )

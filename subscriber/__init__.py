from ccdexplorer_fundamentals.GRPCClient import GRPCClient
from ccdexplorer_fundamentals.mongodb import (
    Collections,
    CollectionsUtilities,
    MongoMotor,
)
from ccdexplorer_fundamentals.tooter import Tooter
from pymongo.collection import Collection
from rich.console import Console

from .module import Module as _module
from .utils import Utils as _utils

console = Console()


class Subscriber(_module, _utils):
    def __init__(
        self,
        grpcclient: GRPCClient,
        tooter: Tooter,
        motormongo: MongoMotor,
    ):
        self.grpcclient = grpcclient
        self.tooter = tooter
        self.motormongo = motormongo

        self.motor_mainnet: dict[Collections, Collection] = self.motormongo.mainnet
        self.motor_testnet: dict[Collections, Collection] = self.motormongo.testnet
        self.motor_utilities: dict[CollectionsUtilities, Collection] = (
            self.motormongo.utilities
        )

    def exit(self):
        pass

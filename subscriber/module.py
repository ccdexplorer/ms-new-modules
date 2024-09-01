import io

import ccdexplorer_fundamentals.GRPCClient.wadze as wadze
from ccdexplorer_fundamentals.enums import NET
from ccdexplorer_fundamentals.GRPCClient import GRPCClient
from ccdexplorer_fundamentals.mongodb import (
    Collections,
)
from ccdexplorer_fundamentals.tooter import Tooter
from pymongo import DeleteOne, ReplaceOne
from pymongo.collection import Collection
from rich.console import Console

from .utils import Utils as _utils

console = Console()


class Module(_utils):
    def get_module_metadata(
        self, net: NET, block_hash: str, module_ref: str
    ) -> dict[str, str]:
        self.grpcclient: GRPCClient
        ms = self.grpcclient.get_module_source(module_ref, block_hash, net)

        if ms.v0:
            bs = io.BytesIO(bytes.fromhex(ms.v0))
        else:
            bs = io.BytesIO(bytes.fromhex(ms.v1))

        try:
            module = wadze.parse_module(bs.read())
        except Exception as e:
            tooter_message = (
                f"{net}: New module get_module_metadata failed with error  {e}."
            )
            self.send_to_tooter(tooter_message)
            return {}

        results = {}
        if "export" in module.keys():
            for line in module["export"]:
                split_line = str(line).split("(")
                if split_line[0] == "ExportFunction":
                    split_line = str(line).split("'")
                    name = split_line[1]

                    if name[:5] == "init_":
                        results["module_name"] = name[5:]
                    else:
                        method_name = name.split(".")[1] if "." in name else name
                        if "methods" in results:
                            results["methods"].append(method_name)
                        else:
                            results["methods"] = [method_name]

        return results

    async def cleanup(self):

        for net in NET:
            console.log(f"Running cleanup for {net}")
            db: dict[Collections, Collection] = (
                self.motor_mainnet if net.value == "mainnet" else self.motor_testnet
            )

            todo_modules = (
                await db[Collections.queue_todo]
                .find({"type": "module"})
                .to_list(length=None)
            )
            for msg in todo_modules:
                await self.process_new_module(net, msg)
                await self.remove_todo_from_queue(net, msg)

    async def remove_todo_from_queue(self, net: str, msg: dict):
        db: dict[Collections, Collection] = (
            self.motor_mainnet if net.value == "mainnet" else self.motor_testnet
        )

        _ = await db[Collections.queue_todo].bulk_write(
            [DeleteOne({"_id": msg["_id"]})]
        )

    async def process_new_module(self, net: str, msg: dict):
        self.motor_mainnet: dict[Collections, Collection]
        self.motor_testnet: dict[Collections, Collection]
        self.grpcclient: GRPCClient
        self.tooter: Tooter

        db_to_use = self.motor_testnet if net == "testnet" else self.motor_mainnet
        module_ref = msg["module_ref"]
        try:
            results = self.get_module_metadata(NET(net), "last_final", module_ref)
        except Exception as e:
            tooter_message = f"{net}: New module failed with error  {e}."
            self.send_to_tooter(tooter_message)
            return

        module = {
            "_id": module_ref,
            "module_name": (
                results["module_name"] if "module_name" in results.keys() else None
            ),
            "methods": results["methods"] if "methods" in results.keys() else [],
        }

        _ = await db_to_use[Collections.modules].bulk_write(
            [ReplaceOne({"_id": module_ref}, module, upsert=True)]
        )
        tooter_message = f"{net}: New module processed {module_ref} with name {module['module_name']}."
        self.send_to_tooter(tooter_message)

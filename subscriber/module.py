import io

import ccdexplorer_fundamentals.GRPCClient.wadze as wadze
from ccdexplorer_fundamentals.enums import NET
from ccdexplorer_fundamentals.GRPCClient import GRPCClient
import re
from ccdexplorer_fundamentals.mongodb import (
    Collections,
)
from ccdexplorer_fundamentals.tooter import Tooter
from ccdexplorer_fundamentals.mongodb import MongoTypeModule, ModuleVerification
from pymongo import DeleteOne, ReplaceOne
from pymongo.collection import Collection
from concordium_client import ConcordiumClient
from rich.console import Console
import subprocess
import httpx
import os
import shutil
import datetime as dt
import tarfile
from pathlib import Path

from .utils import Utils as _utils

console = Console()


class Module(_utils):
    # Add this helper at class level
    def get_project_root(self):
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

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
                f"{net.value}: New module get_module_metadata failed with error  {e}."
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

    async def cleanup(self, from_: str):

        for net in NET:
            console.log(f"Running cleanup for {net} from {from_}.")
            db: dict[Collections, Collection] = (
                self.motor_mainnet if net == NET.MAINNET else self.motor_testnet
            )

            todo_modules = (
                await db[Collections.queue_todo]
                .find({"type": "module"})
                .to_list(length=None)
            )
            for msg in todo_modules:
                await self.process_new_module(net, msg)
                await self.remove_todo_from_queue(net, msg)

    async def remove_todo_from_queue(self, net: NET, msg: dict):
        db: dict[Collections, Collection] = (
            self.motor_mainnet if net == NET.MAINNET else self.motor_testnet
        )

        _ = await db[Collections.queue_todo].bulk_write(
            [DeleteOne({"_id": msg["_id"]})]
        )

    async def process_new_module(self, net: NET, msg: dict):
        self.motor_mainnet: dict[Collections, Collection]
        self.motor_testnet: dict[Collections, Collection]
        self.grpcclient: GRPCClient
        self.tooter: Tooter

        db_to_use = self.motor_mainnet if net == NET.MAINNET else self.motor_testnet
        module_ref = msg["module_ref"]
        try:
            results = self.get_module_metadata(net, "last_final", module_ref)
        except Exception as e:
            tooter_message = f"{net.value}: New module failed with error  {e}."
            self.send_to_tooter(tooter_message)
            return

        module = {
            "_id": module_ref,
            "module_name": (
                results["module_name"] if "module_name" in results.keys() else None
            ),
            "methods": results["methods"] if "methods" in results.keys() else [],
            "verification": None,
        }

        _ = await db_to_use[Collections.modules].bulk_write(
            [ReplaceOne({"_id": module_ref}, module, upsert=True)]
        )
        tooter_message = f"{net.value}: New module processed {module_ref} with name {module['module_name']}."
        self.send_to_tooter(tooter_message)

    # Add build verification before verify-build
    def verify_rust_setup(self):
        # Check Rust installation
        rust_check = subprocess.run(
            ["rustc", "--version"], capture_output=True, text=True
        )
        # print(f"Rust version: {rust_check.stdout}")

        # Check wasm target
        wasm_check = subprocess.run(
            ["rustc", "--print", "target-list"], capture_output=True, text=True
        )
        # print(f"WASM target available: {'wasm32-unknown-unknown' in wasm_check.stdout}")

        # Check cargo-concordium
        concordium_check = subprocess.run(
            ["cargo", "concordium", "--version"], capture_output=True, text=True
        )
        # print(f"Cargo concordium: {concordium_check.stdout}")

    async def verify_module(
        self, net: NET, concordium_client: ConcordiumClient, msg: dict
    ):
        self.motor_mainnet: dict[Collections, Collection]
        self.motor_testnet: dict[Collections, Collection]
        self.tooter: Tooter
        # Add verification steps
        self.verify_rust_setup()

        module_ref = msg["module_ref"]

        file_path = Path(f"tmp/{module_ref}.out")
        if file_path.exists():
            file_path.unlink()

        db_to_use = self.motor_mainnet if net == NET.MAINNET else self.motor_testnet

        concordium_client.save_module(net, module_ref)

        # print(f"Current working directory: {os.getcwd()}")
        # print(f"Module path exists: {os.path.exists(f'tmp/{module_ref}.out')}")
        # print(
        #     f"Cargo version: {subprocess.run(['cargo', '--version'], capture_output=True, text=True).stdout}"
        # )

        # # Before the subprocess.run call, add:
        # tmp_dir = "tmp"
        # if not os.path.exists(tmp_dir):
        #     os.makedirs(tmp_dir)

        cargo_run = subprocess.run(
            [
                "cargo",
                "concordium",
                "print-build-info",
                "--module",
                f"tmp/{module_ref}.out",
            ],
            capture_output=True,
            text=True,
        )
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        result = ansi_escape.sub("", cargo_run.stderr)
        output_list = result.splitlines()
        verification = None

        if len(output_list) == 4:
            build_image_used = output_list[0].split("used: ")[1].strip()
            build_command_used = output_list[1].split("used: ")[1].strip()
            archive_hash = output_list[2].split("archive: ")[1].strip()
            link_to_source_code = output_list[3].split("source code: ")[1].strip()
            source_code_at_verification_time = ""

            response = await httpx.AsyncClient().get(
                url=link_to_source_code, follow_redirects=True
            )
            try:
                source_code_at_verification_time = response.content
                module_folder = tarfile.open(
                    fileobj=io.BytesIO(source_code_at_verification_time), mode="r:*"
                )
                print(f"{link_to_source_code=} retrieved.")
                module_folder.extractall(path=f"tmp/source_{module_ref}")
                module_name_on_disk = next(os.walk(f"tmp/source_{module_ref}"))[1][0]
                with open(
                    f"tmp/source_{module_ref}/{module_name_on_disk}/src/lib.rs", "r"
                ) as file:
                    source_code_at_verification_time = file.read()

            except Exception as e:  # noqa: E722
                print(f"EXCEPTION: {e}")
                source_code_at_verification_time = ""
                pass
            print(f"{dt.datetime.now()}: Starting subprocess.run for verify-build...")
            # Add before cargo_run:
            module_path = f"tmp/{module_ref}.out"
            # print(f"File exists check: {os.path.exists(module_path)}")
            # print(f"Absolute path: {os.path.abspath(module_path)}")
            # print(f"Current directory contents: {os.listdir('.')}")
            # print(f"Tmp directory contents: {os.listdir('tmp')}")
            # Replace cargo_run section with:
            project_root = self.get_project_root()
            module_path = os.path.join(project_root, "tmp", f"{module_ref}.out")
            # Extract and build
            # Extract to specific directory and use it for build
            source_dir = f"tmp/source_{module_ref}"
            if os.path.exists(source_dir):
                shutil.rmtree(source_dir)
            os.makedirs(source_dir, exist_ok=True)

            try:
                module_folder.extractall(path=source_dir)
                module_name_on_disk = next(os.walk(source_dir))[1][0]
                build_dir = os.path.join(source_dir, module_name_on_disk)

                # Run verify-build from source directory
                cargo_run = subprocess.run(
                    ["cargo", "concordium", "verify-build", "--module", module_path],
                    capture_output=True,
                    text=True,
                    cwd=build_dir,  # Run from source directory
                )

                # print(f"Build directory contents: {os.listdir(build_dir)}")
                # print(
                #     f"Cargo.toml exists: {os.path.exists(os.path.join(build_dir, 'Cargo.toml'))}"
                # )

            except Exception as e:
                print(f"Build error: {str(e)}")
                raise

            if cargo_run.returncode != 0:
                print(f"Error: {cargo_run.stderr}")
                raise Exception(
                    f"cargo-concordium verify-build failed: {cargo_run.stderr}"
                )
            print(f"{dt.datetime.now()}: Subprocess.run for verify-build done.")
            result = ansi_escape.sub("", cargo_run.stderr)
            output_list = result.splitlines()
            verified = output_list[-1] == "Source and module match."

            # if verified:
            #     response = await httpx.AsyncClient().get(url=link_to_source_code)
            #     try:
            #         source_code_at_verification_time = response.json()
            #     except Exception as e:  # noqa: E722
            #         print(e)
            #         source_code_at_verification_time = ""
            #         pass

            # else:
            #     source_code_at_verification_time = ""
            verification = ModuleVerification(
                verified=verified,
                build_image_used=build_image_used,
                build_command_used=build_command_used,
                archive_hash=archive_hash,
                link_to_source_code=link_to_source_code,
                source_code_at_verification_time=source_code_at_verification_time,
            )
            print(f"{module_ref=}: verified status {verification.verified=}")
            module_from_collection = await db_to_use[Collections.modules].find_one(
                {"_id": module_ref}
            )

            module_from_collection.update({"verification": verification.model_dump()})

            _ = await db_to_use[Collections.modules].bulk_write(
                [ReplaceOne({"_id": module_ref}, module_from_collection, upsert=True)]
            )
            tooter_message = f"{net.value}: Module {module_ref} with name {module_from_collection['module_name']} added verification with status {verified}."
            self.send_to_tooter(tooter_message)
        else:
            print(f"No build info found.")
            # print(output_list[0])

from __future__ import annotations
import os
import asyncio
import atexit
import json
import subprocess
import aiomqtt
from aiomqtt.client import Message
from ccdexplorer_fundamentals.GRPCClient import GRPCClient
from ccdexplorer_fundamentals.mongodb import MongoMotor, Collections, ModuleVerification
from ccdexplorer_fundamentals.tooter import Tooter
from pymongo import DeleteOne, ReplaceOne
from rich.progress import track
from ccdexplorer_fundamentals.enums import NET
from concordium_client import ConcordiumClient
from env import (
    MQTT_PASSWORD,
    MQTT_QOS,
    MQTT_SERVER,
    MQTT_USER,
    RUN_LOCAL,
    ADMIN_CHAT_ID,
)
from subscriber import Subscriber
from subprocess import STDOUT, check_output

tooter = Tooter()
motormongo = MongoMotor(tooter, nearest=True)
concordium_client = ConcordiumClient(tooter=tooter)
# Suppress logging warnings
os.environ["GRPC_VERBOSITY"] = "ERROR"


def decode_to_json(msg: Message):
    m_decode = str(msg.payload.decode("utf-8", "ignore"))
    if len(m_decode) > 0:
        m_in = json.loads(m_decode)  # decode json data
    else:
        m_in = ""
    return m_in


def filter_net(msg: Message) -> NET:
    try:
        return NET(msg.topic.value.split("/")[1])
    except:  # noqa: E722
        return NET.MAINNET


async def run(cmd: str):
    proc = await asyncio.create_subprocess_shell(
        cmd, stderr=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE
    )

    stdout, stderr = await proc.communicate()

    print(f"[{cmd!r} exited with {proc.returncode}]")
    if stdout:
        print(f"[stdout]\n{stdout.decode()}")
    if stderr:
        print(f"[stderr]\n{stderr.decode()}")


def call_cmd(cmd):
    try:
        check_output(cmd, stderr=STDOUT, timeout=1, shell=True)
    except subprocess.CalledProcessError:
        print("Exit status 1")


async def main():
    grpcclient = GRPCClient()
    subscriber = Subscriber(grpcclient, tooter, motormongo, concordium_client)
    atexit.register(subscriber.exit)

    interval = 3
    client = aiomqtt.Client(
        MQTT_SERVER,
        1883,
        username=MQTT_USER,
        password=MQTT_PASSWORD,
        clean_session=False,
        identifier=f"{RUN_LOCAL}module-mqtt-listener",
    )

    # for net in NET:
    #     db_to_use = motormongo.mainnet if net == NET.MAINNET else motormongo.testnet
    #     result = await db_to_use[Collections.modules].find({}).to_list(length=None)
    #     for module in track(result):
    #         if "verification" in module:
    #             if module["verification"] is not None:
    #                 if module["verification"]["verified"] is False:
    #                     module["verification"].update(
    #                         {"verification_status": "verified_failed"}
    #                     )
    #                 else:
    #                     module["verification"].update(
    #                         {"verification_status": "verified_success"}
    #                     )
    #             else:
    #                 module.update(
    #                     {
    #                         "verification": ModuleVerification(
    #                             verification_status="not_started"
    #                         ).model_dump(exclude_none=True),
    #                     }
    #                 )
    #         else:
    #             module.update(
    #                 {
    #                     "verification": ModuleVerification(
    #                         verification_status="not_started"
    #                     ).model_dump(exclude_none=True),
    #                 }
    #             )

    #         _ = await db_to_use[Collections.modules].bulk_write(
    #             [ReplaceOne({"_id": module["_id"]}, module, upsert=True)]
    #         )

    # exit()
    # msg = {
    #     "module_ref": "98c0395109389123ea2f9370482ed8654487402f290361d2cf86a87d2065820f"
    # }

    # await subscriber.process_new_module(NET.TESTNET, msg)
    # await subscriber.verify_module(NET.TESTNET, subscriber.concordium_client, msg)
    await subscriber.cleanup("topic")
    while True:
        try:
            async with client:
                await client.subscribe("ccdexplorer/+/heartbeat/#", qos=MQTT_QOS)
                await client.subscribe("ccdexplorer/services/#", qos=MQTT_QOS)
                async for message in client.messages:
                    net = filter_net(message)
                    msg = decode_to_json(message)
                    if message.topic.matches("ccdexplorer/services/module/restart"):
                        exit()
                    if message.topic.matches("ccdexplorer/services/cleanup"):
                        await subscriber.cleanup("topic")
                    if message.topic.matches("ccdexplorer/+/heartbeat/module/new"):
                        await subscriber.process_new_module(net, msg)
                        await subscriber.verify_module(
                            net, subscriber.concordium_client, msg
                        )
                    if message.topic.matches("ccdexplorer/services/info"):
                        await grpcclient.aconnection_info(
                            "MS Modules", tooter, ADMIN_CHAT_ID
                        )
        except aiomqtt.MqttError:
            print(f"Connection lost; Reconnecting in {interval} seconds ...")
            await asyncio.sleep(interval)


asyncio.run(main())

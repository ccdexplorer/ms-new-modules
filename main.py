from __future__ import annotations
import os
import asyncio
import atexit
import json
import subprocess
import aiomqtt
from aiomqtt.client import Message
from ccdexplorer_fundamentals.GRPCClient import GRPCClient
from ccdexplorer_fundamentals.mongodb import MongoMotor, Collections
from ccdexplorer_fundamentals.tooter import Tooter
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
    # print("Starting docker")
    # docker_run = subprocess.run(
    #     [
    #         "docker",
    #         "run",
    #         "-v",
    #         "/var/run/docker.sock:/var/run/docker.sock",
    #         "-i",
    #         "docker",
    #     ],
    #     capture_output=True,
    #     text=True,
    # )
    # # if docker_run.returncode != 0:
    # #     print(f"Docker error: {docker_run.stderr}")
    # #     raise Exception("Failed to start docker container")

    # print(f"Docker output: {docker_run.stdout}")
    # print(f"Docker error(s): {docker_run.stderr}")
    # print("Docker started")
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

    msg = {
        "module_ref": "3617bc04a686f020c1b21fd508c65ee6a9b94cb71aaf7959006207ff5f80d623"
    }
    # msg = {
    #     "module_ref": "f7d13649702c6d24ebd784631beceea79773b10f16f99e21cf81ef8f755b5d44"
    # }
    for net in NET:
        db_to_use = motormongo.mainnet if net == NET.MAINNET else motormongo.testnet
        result = await db_to_use[Collections.modules].find({})
        for module in result:
            msg = {"module_ref": module["_id"]}
            print(f"Working on {net.value} - module: {module['_id']}.........")
            await subscriber.verify_module(net, subscriber.concordium_client, msg)
    exit()
    # await subscriber.cleanup("startup")
    # while True:
    #     try:
    #         async with client:
    #             await client.subscribe("ccdexplorer/+/heartbeat/#", qos=MQTT_QOS)
    #             await client.subscribe("ccdexplorer/services/#", qos=MQTT_QOS)
    #             async for message in client.messages:
    #                 net = filter_net(message)
    #                 msg = decode_to_json(message)
    #                 if message.topic.matches("ccdexplorer/services/module/restart"):
    #                     exit()
    #                 if message.topic.matches("ccdexplorer/services/cleanup"):
    #                     await subscriber.cleanup("topic")
    #                 if message.topic.matches("ccdexplorer/+/heartbeat/module/new"):
    #                     await subscriber.process_new_module(net, msg)
    #                     await subscriber.verify_module(
    #                         net, subscriber.concordium_client, msg
    #                     )
    #                 if message.topic.matches("ccdexplorer/services/info"):
    #                     await grpcclient.aconnection_info(
    #                         "MS Modules", tooter, ADMIN_CHAT_ID
    #                     )
    #     except aiomqtt.MqttError:
    #         print(f"Connection lost; Reconnecting in {interval} seconds ...")
    #         await asyncio.sleep(interval)


asyncio.run(main())

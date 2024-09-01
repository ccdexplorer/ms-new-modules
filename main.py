from __future__ import annotations

import asyncio
import atexit
import json

import aiomqtt
from aiomqtt.client import Message
from ccdexplorer_fundamentals.GRPCClient import GRPCClient
from ccdexplorer_fundamentals.mongodb import MongoMotor
from ccdexplorer_fundamentals.tooter import Tooter

from env import MQTT_PASSWORD, MQTT_QOS, MQTT_SERVER, MQTT_USER
from subscriber import Subscriber

grpcclient = GRPCClient()
tooter = Tooter()
motormongo = MongoMotor(tooter, nearest=True)


def decode_to_json(msg: Message):
    m_decode = str(msg.payload.decode("utf-8", "ignore"))
    if len(m_decode) > 0:
        m_in = json.loads(m_decode)  # decode json data
    else:
        m_in = ""
    return m_in


def filter_net(msg: Message):
    return msg.topic.value.split("/")[1]


async def main():
    subscriber = Subscriber(grpcclient, tooter, motormongo)
    atexit.register(subscriber.exit)

    interval = 3
    client = aiomqtt.Client(
        MQTT_SERVER,
        1883,
        username=MQTT_USER,
        password=MQTT_PASSWORD,
        clean_session=False,
        identifier="module-mqtt-listener",
    )
    await subscriber.cleanup()
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
                        await subscriber.cleanup()
                    if message.topic.matches("ccdexplorer/+/heartbeat/module/new"):
                        await subscriber.process_new_module(net, msg)

        except aiomqtt.MqttError:
            print(f"Connection lost; Reconnecting in {interval} seconds ...")
            await asyncio.sleep(interval)


asyncio.run(main())

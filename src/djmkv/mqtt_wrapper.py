import asyncio
import pathlib

import aiomqtt


class MQTTWrapper:
    def __init__(self, mqtt_client: aiomqtt.Client):
        self.mqtt_client = mqtt_client
        self.message_queue = asyncio.Queue()

    async def enqueue_message(
        self, topic: str | pathlib.Path, payload: str | bytes, **kwargs
    ) -> None:
        await self.message_queue.put(
            (
                str(topic),
                payload,
                kwargs,
            )
        )

    async def send_loop(self, retries=10, retry_delay=0.1) -> None:
        topic, payload, kwargs = await self.message_queue.get()
        remaining_retries = retries
        while True:
            try:
                async with self.mqtt_client as client:
                    while True:
                        await client.publish(topic, payload, **kwargs)
                        remaining_retries = retries
                        topic, payload, kwargs = await self.message_queue.get()
            except aiomqtt.MqttError:
                print("Failed to connect to MQTT broker.")
                remaining_retries -= 1
                if remaining_retries <= 0:
                    # get a new message, as this one is having problems
                    topic, payload, kwargs = await self.message_queue.get()
                await asyncio.sleep(retry_delay)
                pass

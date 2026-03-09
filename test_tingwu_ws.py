import asyncio
from dotenv import load_dotenv

load_dotenv()
from server.asr import TingwuProvider


async def test_tingwu():
    print("Testing TingwuProvider...")
    p = TingwuProvider()

    # 构造事件监听测试
    async def dummy_update(text, is_end):
        print(f"Update: {text} | is_end: {is_end}")

    loop = asyncio.get_event_loop()
    p.set_callback(dummy_update, loop)

    print("Starting provider...")
    p.start()

    print("Sending dummy audio...")
    # 给一点假的PCM数据(16k 16bit 单声道)看能否推成功
    dummy_audio = b"\x00" * 3200
    for _ in range(10):
        p.add_audio(dummy_audio)
        await asyncio.sleep(0.1)

    print("Stopping provider...")
    p.stop()
    print("Done.")


if __name__ == "__main__":
    asyncio.run(test_tingwu())

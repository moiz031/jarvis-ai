import asyncio
import websockets
import json
import time

async def test_mic_toggle():
    uri = "ws://localhost:8080/ws"
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            # 1. Test Mic Toggle ON
            print("\n[Test 1] Testing Mic Toggle ON...")
            await websocket.send(json.dumps({"type": "mic_toggle", "data": True}))
            
            # Wait for status response
            start_time = time.time()
            found_listening = False
            while time.time() - start_time < 5:
                response = await websocket.recv()
                msg = json.loads(response)
                print(f"Received: {msg}")
                if msg.get("type") == "status" and "listening" in msg.get("data").lower():
                    found_listening = True
                    print("SUCCESS: Received 'Listening' status from backend.")
                    break
            
            if not found_listening:
                print("FAILURE: Did not receive 'Listening' status within 5 seconds.")

            # 2. Test Mic Toggle OFF
            print("\n[Test 2] Testing Mic Toggle OFF...")
            await websocket.send(json.dumps({"type": "mic_toggle", "data": False}))
            
            start_time = time.time()
            found_idle = False
            while time.time() - start_time < 5:
                response = await websocket.recv()
                msg = json.loads(response)
                print(f"Received: {msg}")
                if msg.get("type") == "status" and "idle" in msg.get("data").lower():
                    found_idle = True
                    print("SUCCESS: Received 'Idle' status from backend.")
                    break
            
            if not found_idle:
                print("FAILURE: Did not receive 'Idle' status within 5 seconds.")

    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_mic_toggle())

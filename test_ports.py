import serial.tools.list_ports
import time
print("Checking COM ports...")
try:
    start = time.time()
    ports = serial.tools.list_ports.comports()
    print(f"Detected {len(ports)} ports in {time.time()-start:.2f}s.")
    for p in ports:
        print(f"- {p.device}: {p.description}")
except Exception as e:
    print(f"COM PORT CHECK FAILED: {e}")

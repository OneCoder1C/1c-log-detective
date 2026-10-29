from pathlib import Path

LOG_FILE = Path("1c_logs/1cv8c_29332/26102717.log")

with LOG_FILE.open("rb") as file:
    for line in file:
        if b"ACTIVEUSERS" in line:
            text = line.decode("utf-8")
            print(text[:500])
            break
    else:
        print("Строка ACTIVEUSERS не найдена.")

from pathlib import Path

from techlog import iter_techlog_events, parse_event


LOG_FILE = Path("1c_logs/1cv8c_29332/26102717.log")


def main():
    with LOG_FILE.open("r", encoding="utf-8", errors="replace") as file:
        for raw_event in iter_techlog_events(file):
            event = parse_event(raw_event)

            if event is None or event.event_type != "TLOCK":
                continue

            if "Reference69.REFLOCK" not in raw_event:
                continue

            print(raw_event.splitlines()[0][:1500])
            break


if __name__ == "__main__":
    main()

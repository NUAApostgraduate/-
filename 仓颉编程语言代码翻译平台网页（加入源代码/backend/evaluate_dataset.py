import argparse
import json
from pathlib import Path

import server


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate local Java/Cangjie parallel dataset.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    payload = server.evaluate_dataset_payload({"limit": args.limit, "use_model": True})
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()

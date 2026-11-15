import argparse
import json
import logging

from agent.orchestrator import Orchestrator


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("message", nargs="?")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    agent = Orchestrator()
    if args.message:
        print(agent.chat(args.message).model_dump_json(indent=2))
        return
    print("MLOps agent. Type exit to quit. Confirmations run only after you type confirm.")
    token = None
    while True:
        message = input("You> ").strip()
        if message == "exit":
            break
        try:
            response = agent.chat(message, token if message.lower() == "confirm" else None)
            print(json.dumps(response.model_dump(), indent=2))
            token = response.confirmation_token
        except (ValueError, PermissionError) as exc:
            print(str(exc))


if __name__ == "__main__":
    main()

"""Admin command line for the server.

    python -m app.manage create-agent OFFICE-PC-01
    python -m app.manage list-agents
"""
import argparse
import sys

from sqlalchemy import select

from .database import SessionLocal, init_db
from .models import Agent
from .security import generate_api_key, hash_api_key


def create_agent(name: str) -> int:
    with SessionLocal() as db:
        if db.scalar(select(Agent).where(Agent.name == name)):
            print(f"An agent named '{name}' already exists.", file=sys.stderr)
            return 1
        api_key = generate_api_key()
        db.add(Agent(name=name, api_key_hash=hash_api_key(api_key)))
        db.commit()
    print(f"Created agent '{name}'.")
    print(f"API key: {api_key}")
    print("Copy this key into the agent's config.json now. It cannot be shown again.")
    return 0


def list_agents() -> int:
    with SessionLocal() as db:
        agents = db.scalars(select(Agent).order_by(Agent.name)).all()
    if not agents:
        print("No agents yet. Create one with: python -m app.manage create-agent NAME")
    for a in agents:
        seen = a.last_seen.isoformat(timespec="seconds") + "Z" if a.last_seen else "never"
        print(f"{a.id:>3}  {a.name:<25} host={a.hostname or '-':<20} last_seen={seen}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.manage")
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create-agent", help="register a monitored computer and print its API key")
    create.add_argument("name")
    sub.add_parser("list-agents", help="show registered agents")
    args = parser.parse_args()

    init_db()
    if args.command == "create-agent":
        return create_agent(args.name)
    return list_agents()


if __name__ == "__main__":
    sys.exit(main())

"""Admin command line for the server.

    python -m app.manage create-user alice --role admin
    python -m app.manage reset-password alice
    python -m app.manage list-users
    python -m app.manage create-agent OFFICE-PC-01
    python -m app.manage list-agents

Passwords are asked for interactively (or read from standard input when piped).
Computers can also be added from the dashboard's Computers page.
"""
import argparse
import getpass
import re
import sys

from sqlalchemy import func, select

from .database import SessionLocal, init_db
from .models import Agent, User
from .passwords import hash_password, password_problem
from .schemas import USERNAME_PATTERN
from .security import generate_api_key, hash_api_key


def read_password() -> str | None:
    if not sys.stdin.isatty():
        password = sys.stdin.readline().rstrip("\r\n")
    else:
        password = getpass.getpass("Password: ")
        if getpass.getpass("Repeat password: ") != password:
            print("Passwords do not match.", file=sys.stderr)
            return None
    if problem := password_problem(password):
        print(problem, file=sys.stderr)
        return None
    return password


def create_user(name: str | None, role: str) -> int:
    if not name:
        # Piped input from PowerShell can start with a byte-order mark.
        name = (input("Username: ") if sys.stdin.isatty() else sys.stdin.readline()).lstrip("﻿").strip()
    if not re.fullmatch(USERNAME_PATTERN, name) or not 3 <= len(name) <= 50:
        print("Username must be 3-50 letters, numbers, dots, dashes, or underscores.", file=sys.stderr)
        return 1
    with SessionLocal() as db:
        if db.scalar(select(User).where(func.lower(User.username) == name.lower())):
            print(f"A user named '{name}' already exists.", file=sys.stderr)
            return 1
        password = read_password()
        if password is None:
            return 1
        db.add(User(username=name, password_hash=hash_password(password), role=role))
        db.commit()
    print(f"Created {role} user '{name}'. They can now sign in to the dashboard.")
    return 0


def reset_password(name: str) -> int:
    with SessionLocal() as db:
        user = db.scalar(select(User).where(func.lower(User.username) == name.lower()))
        if user is None:
            print(f"No user named '{name}'.", file=sys.stderr)
            return 1
        password = read_password()
        if password is None:
            return 1
        user.password_hash = hash_password(password)
        user.is_active = True
        db.commit()
    print(f"Password for '{name}' changed.")
    return 0


def list_users() -> int:
    with SessionLocal() as db:
        users = db.scalars(select(User).order_by(User.username)).all()
    if not users:
        print("No users yet. Create one with: python -m app.manage create-user NAME --role admin")
    for u in users:
        state = "" if u.is_active else "  (disabled)"
        print(f"{u.id:>3}  {u.username:<25} {u.role:<7}{state}")
    return 0


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
        revoked = "  (revoked)" if a.revoked_at else ""
        print(f"{a.id:>3}  {a.name:<25} host={a.hostname or '-':<20} last_seen={seen}{revoked}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m app.manage")
    sub = parser.add_subparsers(dest="command", required=True)
    cu = sub.add_parser("create-user", help="add a dashboard user")
    cu.add_argument("name", nargs="?", help="asked for if left out")
    cu.add_argument("--role", choices=["admin", "viewer"], default="viewer")
    rp = sub.add_parser("reset-password", help="set a new password for a user (and re-enable them)")
    rp.add_argument("name")
    sub.add_parser("list-users", help="show dashboard users")
    ca = sub.add_parser("create-agent", help="register a monitored computer and print its API key")
    ca.add_argument("name")
    sub.add_parser("list-agents", help="show registered computers")
    args = parser.parse_args()

    init_db()
    if args.command == "create-user":
        return create_user(args.name, args.role)
    if args.command == "reset-password":
        return reset_password(args.name)
    if args.command == "list-users":
        return list_users()
    if args.command == "create-agent":
        return create_agent(args.name)
    return list_agents()


if __name__ == "__main__":
    sys.exit(main())

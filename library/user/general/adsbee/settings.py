"""Validate picker values without evaluating user input as shell code."""
import ipaddress
import sys
from model import coordinates


def validate(args):
    if args[0] == "center":
        return len(args) == 3 and coordinates(args[1], args[2]) is not None
    if args[0] == "port":
        return len(args) == 2 and args[1].isdigit() and 1 <= int(args[1]) <= 65535
    if args[0] == "host":
        return len(args) == 3 and bool(ipaddress.IPv4Address(args[1])) and validate(["port", args[2]])
    return False


if __name__ == "__main__":
    try:
        sys.exit(0 if validate(sys.argv[1:]) else 1)
    except (ValueError, IndexError):
        sys.exit(1)

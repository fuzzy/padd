#!/usr/bin/env python3

import os
import sys
import time
import urllib.request as request


START_T = time.time()


def convert_size(s):
    key = {"k": 1, "m": 2, "g": 3}
    if s[-1].isalpha() and s[-1].lower() in key.keys() and s[:-1].isnumeric():
        return int(s[:-1]) * (1024 ** key[s[-1].lower()])
    elif not s[-1].isalpha() and s.isnumeric():
        return int(s)
    else:
        raise Exception(f"convert_size: Invalid value passed in: {s}")


def humanize_size(n):
    suffixes = ("B", "K", "M", "G", "T")
    for x in reversed(range(1, 6)):
        if n >= 1024**x:
            return f"{float(n) / (1024 ** x):7.2f}{suffixes[x]}"
    return f"{n}{suffixes[1]}"


def humanize_seconds(n):
    h, m, s = 0, 0, 0
    if n < 60:
        s = n
    elif n >= 60 and n < 60**2:
        m = int(n / 60)
        s = int(n % 60)
    elif n >= 60**2:
        h = int(n / (60**2))
        m = int((n % (60**2)) / 60)
        s = int((n % (60**2)) % 60)
    sepr = "\033[33m:\033[0m"
    retv = f"{h:02d}{sepr}{m:02d}{sepr}{s:02d}"
    return retv


def apply_defaults(d):
    defaults = {
        "bs": "5M",
        "if": sys.stdin,
        "of": sys.stdout,
        "status": "progress",
        "oflags": "",
        "oftype": None,
        "iflags": "",
        "iftype": None,
    }
    for k, v in defaults.items():
        if k not in d.keys():
            d[k] = v
    return d


def sanitize_args(d):
    for k, v in apply_defaults(d).items():
        if k == "bs" and k.isalpha():
            d[k] = convert_size(v)
        elif k in ("if", "of"):
            if v[0:4] == "/dev" and not os.path.isdir(v):
                if k == "if":
                    d[k] = open(v, "rb")
                    d["iftype"] = "\033[34mD\033[0m"
                elif k == "of":
                    d[k] = open(v, "wb+")
                    d["oftype"] = "\033[32mD\033[0m"
            elif v[0:4] not in ("http", "ftp:") and not os.path.isdir(v):
                if k == "if":
                    d[k] = open(v, "rb")
                    d["iftype"] = "\033[34mF\033[0m"
                elif k == "of":
                    d[k] = open(v, "wb+")
                    d["oftype"] = "\033[32mF\033[0m"
            elif k == "if" and v.find(":") != -1 and v[0:4] in ("http", "ftp:"):
                d["iftype"] = "\033[34mN\033[0m"
                d[k] = request.urlopen(v)
            else:
                raise Exception(f"sanitize_args: Invalid value for `of` given: {v}")
        elif k in ("iflags", "oflags"):
            d[k] = v.split(",")
    return d


def transfer(d):
    data = {
        "total": False,  # This signals no progress bar
        "read": 0,
        "write": 0,
    }
    art = f"{d['iftype']}\033[33m<->\033[0m{d['oftype']}"

    try:
        # Get length if input is a download
        data["total"] = d["if"].length
    except Exception:
        if os.path.isfile(d["if"].name):
            data["total"] = os.path.getsize(d["if"].name)

    # And set these outside the loop for status
    wrote = None
    rate = None
    bars = None
    # Fill our buffer before the loop
    buff = d["if"].read(d["bs"])
    while buff:
        # Record our read in size
        data["read"] += len(buff)
        # drain the buffer into the destination
        d["of"].write(buff)
        if "sync" in d["oflags"]:
            try:
                d["of"].sync()
            except AttributeError:
                pass
        # TODO: support sync on the output (from oflags)
        data["write"] += len(buff)

        # Handle any status output
        if d["status"] == "progress":
            wrote = humanize_size(data["write"])
            srate = data["write"] / (time.time() - START_T)
            rate = humanize_size(srate)

            if data["total"]:
                perc = float(data["write"]) / float(data["total"]) * 100.0
                sleft = int((data["total"] - data["write"]) / srate)
                tleft = humanize_seconds(sleft)
                bars = f"\033[33m{'-' * 20}\033[0m"
                if int(perc) >= 5:
                    nbars = int(int(perc) / 5)
                    nspce = 20 - nbars
                    xbars = f'\033[32m{"#" * nbars}\033[0m'
                    xspce = f'\033[33m{"-" * nspce}\033[0m'
                    bars = f"{xbars}{xspce}"
                sys.stderr.write(
                    f"{art} {wrote} @ {rate}/s [eta: {tleft}] [{bars}] ({perc:6.2f}%)\r"
                )
                sys.stderr.flush()
            elif not data["total"]:
                htime = humanize_seconds(int(time.time() - START_T))
                sys.stderr.write(f"{art} {wrote} @ {rate}/s in {htime}\r")
                sys.stderr.flush()
        # refill the buffer
        buff = d["if"].read(d["bs"])
    try:
        d["of"].close()
        d["if"].close()
    except Exception:
        pass
    # Final status message
    if d["status"] == "progress" and data["total"]:
        time_s = humanize_seconds(int(time.time() - START_T))
        sys.stderr.write(
            f"{art} {wrote} @ {rate}/s [run: {time_s}] [{bars}] (100.00%)\n"
        )
        sys.stderr.flush()


def parse_args():
    retv = {}
    for arg in sys.argv[1:]:
        if arg.find("=") != -1:
            _key, val = arg.split("=")
            if _key[0] == "-":
                key = _key[1:]
            else:
                key = _key
            retv[key] = val
    return sanitize_args(retv)


def main():
    try:
        data = parse_args()
        transfer(data)
    except KeyboardInterrupt:
        sys.exit(1)
    except Exception as error:
        print(f"ERROR: {error}")
        raise


if __name__ == "__main__":
    main()

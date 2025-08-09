#!/usr/bin/env python3
"""
child_runner.py
Runs the target script in a heavily restricted environment.
- Enforces RLIMIT_CPU and RLIMIT_AS
- Sets a wall-clock alarm
- Replaces builtins to disable file I/O and restrict imports
- Disables networking while keeping socket/ssl attributes
- Loads injected_dfs.json (if present) and injects as variable `dfs`
"""

import sys
import os
import signal
import resource
import types
import json
import pandas as pd

# Child tunables
CPU_TIME_SECONDS = 3
MEMORY_BYTES = 200 * 1024 * 1024  # ~200MB
ALARM_SECONDS = 10

# Allowed top-level modules (whitelist)
ALLOWED_MODULES = {
    "math", "json", "re", "itertools", "functools", "random", "statistics",
    "string", "collections", "heapq", "bisect", "datetime",
    "pandas", "numpy", "matplotlib","openai"
}

def hard_limits():
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (CPU_TIME_SECONDS, CPU_TIME_SECONDS + 1))
    except Exception:
        pass
    try:
        resource.setrlimit(resource.RLIMIT_AS, (MEMORY_BYTES, MEMORY_BYTES))
    except Exception:
        pass

def alarm_handler(signum, frame):
    raise TimeoutError("child: wall timeout reached")

def disable_networking():
    """
    Replace socket and ssl in sys.modules with wrappers that preserve
    constants/classes but raise on operations that would perform networking.
    """
    import socket as real_socket
    import ssl as real_ssl
    import sys as _sys

    def _raise(*a, **k):
        raise RuntimeError("networking disabled in sandbox")

    # --- fake socket: copy attributes but block connect/socket creation ---
    fake_socket = types.ModuleType("socket")
    for attr in dir(real_socket):
        try:
            setattr(fake_socket, attr, getattr(real_socket, attr))
        except Exception:
            pass
    for func in ("socket", "create_connection", "getaddrinfo", "gethostbyname", "gethostbyaddr", "getnameinfo"):
        try:
            setattr(fake_socket, func, _raise)
        except Exception:
            pass
    _sys.modules["socket"] = fake_socket

    # --- fake ssl: copy attributes; block wrap_socket and network-y methods ---
    fake_ssl = types.ModuleType("ssl")
    for attr in dir(real_ssl):
        try:
            setattr(fake_ssl, attr, getattr(real_ssl, attr))
        except Exception:
            pass
    try:
        # make wrap_socket raise
        fake_ssl.wrap_socket = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("ssl disabled"))
        # keep create_default_context but make context not open sockets
        def _create_default_context(*a, **k):
            # return a real SSLContext but network ops are blocked by socket replacement
            return real_ssl.SSLContext(real_ssl.PROTOCOL_TLS_CLIENT)
        fake_ssl.create_default_context = _create_default_context
    except Exception:
        pass
    _sys.modules["ssl"] = fake_ssl

def make_safe_builtins():
    import builtins as _builtins
    allowed = [
        # safe builtins list (no file/network execution)
        "abs","all","any","ascii","bin","bool","bytearray","bytes",
        "chr","complex","dict","divmod","enumerate","filter","float","format",
        "frozenset","hash","hex","id","int","isinstance","issubclass","iter",
        "len","list","map","max","min","next","object","oct","ord","pow",
        "print","range","repr","reversed","round","set","slice","sorted",
        "str","sum","tuple","zip",
        # exceptions
        "BaseException","Exception","StopIteration","ArithmeticError","LookupError",
    ]
    safe = {name: getattr(_builtins, name) for name in allowed if hasattr(_builtins, name)}

    def blocked_open(*args, **kwargs):
        raise PermissionError("file IO is disabled in sandbox")

    def restricted_import(name, globals=None, locals=None, fromlist=(), level=0):
        root = name.split(".")[0]
        if root in ALLOWED_MODULES:
            return __import__(name, globals or {}, locals or {}, fromlist, level)
        raise ImportError(f"import of '{name}' not allowed in sandbox")

    safe["open"] = blocked_open
    safe["__import__"] = restricted_import
    return safe

def clear_environment():
    for k in list(os.environ.keys()):
        if k.startswith("LD_") or k in ("PYTHONPATH","PYTHONHOME"):
            del os.environ[k]

def run_target(target_path):
    # read source
    with open(target_path, "r", encoding="utf-8") as f:
        source = f.read()

    # attempt to load injected dfs (while file I/O still allowed)
    injected_dfs = None
    try:
        inject_path = os.path.join(os.path.dirname(target_path), "injected_dfs.json")
        if os.path.exists(inject_path):
            with open(inject_path, "r", encoding="utf-8") as f:
                json_dfs = json.load(f)
            injected_dfs = [
                (name, pd.DataFrame(data["data"], columns=data["columns"]))
                for name, data in json_dfs
            ]
    except Exception:
        injected_dfs = None

    # build restricted globals and inject dfs
    safe_builtins = make_safe_builtins()
    restricted_globals = {
        "__builtins__": safe_builtins,
        "__name__": "__main__",
        "__file__": target_path,
        "__package__": None,
    }
    if injected_dfs is not None:
        restricted_globals["dfs"] = injected_dfs

    code = compile(source, target_path, "exec")
    exec(code, restricted_globals, restricted_globals)

def main():
    if len(sys.argv) != 2:
        print("child_runner.py <script.py>", file=sys.stderr)
        sys.exit(2)

    target = sys.argv[1]
    hard_limits()

    # set an alarm (wall-clock) too
    signal.signal(signal.SIGALRM, alarm_handler)
    signal.alarm(ALARM_SECONDS)

    clear_environment()
    disable_networking()

    # change to minimal tmp dir
    try:
        tmp = os.path.abspath(os.path.join("/tmp", "sandbox_child"))
        os.makedirs(tmp, exist_ok=True)
        os.chdir(tmp)
    except Exception:
        pass

    try:
        run_target(target)
    except MemoryError:
        print("child: killed (memory limit reached)", file=sys.stderr)
        sys.exit(137)
    except TimeoutError:
        print("child: killed (timeout)", file=sys.stderr)
        sys.exit(124)
    except SystemExit:
        raise
    except BaseException as e:
        print("child: runtime error:", repr(e), file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()

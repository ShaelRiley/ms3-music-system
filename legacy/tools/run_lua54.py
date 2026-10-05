#!/usr/bin/env python3
"""Run a Lua file through the system Lua 5.4 shared library.

The CI/work container ships liblua without the command-line interpreter. This
small runner keeps finite headless validators executable without vendoring Lua.
"""

import ctypes
import ctypes.util
import pathlib
import sys


def main() -> int:
    syntax_only = len(sys.argv) >= 3 and sys.argv[1] == "--syntax"
    if len(sys.argv) < 2:
        print("usage: tools/run_lua54.py [--syntax] <script.lua> [args...]", file=sys.stderr)
        return 2
    if syntax_only:
        scripts = [pathlib.Path(s).resolve() for s in sys.argv[2:]]
        script_args = []
    else:
        scripts = [pathlib.Path(sys.argv[1]).resolve()]
        script_args = sys.argv[2:]

    library = ctypes.util.find_library("lua5.4") or "liblua5.4.so.0"
    lua = ctypes.CDLL(library)
    lua.luaL_newstate.restype = ctypes.c_void_p
    lua.luaL_openlibs.argtypes = [ctypes.c_void_p]
    lua.luaL_loadfilex.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_char_p]
    lua.luaL_loadfilex.restype = ctypes.c_int
    lua.lua_pcallk.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_longlong,
        ctypes.c_void_p,
    ]
    lua.lua_pcallk.restype = ctypes.c_int
    lua.lua_tolstring.argtypes = [
        ctypes.c_void_p,
        ctypes.c_int,
        ctypes.POINTER(ctypes.c_size_t),
    ]
    lua.lua_tolstring.restype = ctypes.c_char_p
    lua.lua_close.argtypes = [ctypes.c_void_p]

    lua.luaL_loadbufferx.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_char_p, ctypes.c_char_p]
    lua.luaL_loadbufferx.restype = ctypes.c_int

    state = lua.luaL_newstate()
    lua.luaL_openlibs(state)
    try:
        for script in scripts:
            arg_map = f"[0] = {repr(str(script))}"
            for i, a in enumerate(script_args, 1):
                arg_map += f", [{i}] = {repr(a)}"
            init_code = f"arg = {{{arg_map}}}".encode()
            if lua.luaL_loadbufferx(state, init_code, len(init_code), b"=init_arg", None) == 0:
                lua.lua_pcallk(state, 0, 0, 0, 0, None)
            status = lua.luaL_loadfilex(state, str(script).encode(), None)
            if status == 0 and not syntax_only:
                status = lua.lua_pcallk(state, 0, -1, 0, 0, None)
            if status != 0:
                size = ctypes.c_size_t()
                message = lua.lua_tolstring(state, -1, ctypes.byref(size))
                print(f"{script}: " + message[: size.value].decode(errors="replace"), file=sys.stderr)
                return 1
            if syntax_only:
                print(f"PASS {script}")
        return 0
    finally:
        lua.lua_close(state)


if __name__ == "__main__":
    raise SystemExit(main())

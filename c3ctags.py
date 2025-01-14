#!/bin/python3
import json
import subprocess
import re
import sys
import os

__version__ = (0, 0, 2)
all = ["c3ctags"]

c3c = "c3c"
params = ["compile", "-P", "--use-stdlib=no"]

def get_json(path):
    assert(path.endswith(".c3") or path.endswith(".c3i"))
    return json.loads(subprocess.check_output((c3c, *params, path)))

def format_type(Type):
    Type = Type.replace("[", r"\[")
    Type = Type.replace("]", r"\]")
    Type = Type.replace("*", r"\s*\*\s*")
    return Type

def unnamespace(namespaced):
    last = namespaced.rfind("::")
    if last < 0:
        return namespaced
    return namespaced[2 + last:]

def add_regex(text, result, regex, name) ->int:
    Match = regex.search(text)
    if Match is None:
        print(regex)
        print(f"ERROR: Failed to find {name}")
        raise ValueError
    offset = Match.start()
    text_up_to = text[:offset]
    line = 1 + text_up_to.count("\n")
    line_start = text_up_to.rfind("\n") + 1
    end = Match.end()
    result.append(b"%b\x7f%b\x01%d,%d" % (text[line_start:end].encode(), name.encode(), line, line_start))
    return end

def parse(item, text, result, prefix) -> int:
    name = unnamespace(item["name"])
    if not prefix:
        regex = re.compile(rf"{name}")
    else:
        regex = re.compile(rf"{prefix}.*?{name}")
    try:
        return add_regex(text, result,regex, name)
    except:
        print(item)
        raise

def parse_with_type(item, text, result, T, prefix) -> int:
    try:
        Type = format_type(item[T])
    except:
        Type = ""
    if Type == "":
        parse(item, text, result, prefix)
    else:
        if not prefix:
            parse(item, text, result, Type)
        else:
            parse(item, text, result, f"{prefix}.*?{Type}")

def _parse_types(ast, text, result, T):
    start = 0
    for Type in ast[T]:
        kind = Type["kind"]
        name = Type["name"]
        t_name = unnamespace(name)
        
        if kind in ("struct", "enum", "distinct", "bitstruct", "union"):
            start = parse(Type, text[start:], result, kind)
            continue
        
        if kind == "typedef":
            start = parse(Type, text[start:], result, "def")
            continue
        
        print(Type)
        raise NotImplementedError
    del ast[T]

def parse_types(ast, text, result):
    _parse_types(ast, text, result, "types")
    _parse_types(ast, text, result, "generic_types")

def parse_functions(ast, text, result):
    start = 0
    for fn in ast["functions"]:
        start = parse_with_type(fn, text[start:], result, "rtype", "fn")
    del ast["functions"]
    
    start = 0
    for fn in ast["generic_functions"]:
        start = parse_with_type(fn, text[start:], result, "rtype", "fn")
    del ast["generic_functions"]

def parse_macros(ast, text, result):
    start = 0
    for macro in ast["macros"]:
        start = parse_with_type(macro, text[start:], result, "rtype", "macro")
    del ast["macros"]

    start = 0
    for macro in ast["generic_macros"]:
        start = parse_with_type(macro, text[start:], result, "rtype", "macro")
    del ast["generic_macros"]

def parse_constants(ast, text, result):
    start = 0
    for constant in ast["constants"]:
        start = parse_with_type(constant, text[start:], result, "type", "const")
    del ast["constants"]

def parse_modules(ast, text, result):
    start = 0
    for module in ast["modules"]:
        if module == "std::core":
            continue
        start = parse({"name": module}, text[start:], result, "module")
    del ast["modules"]

    start = 0
    for module in ast["generic_modules"]:
        start = parse({"name": module}, text[start:], result, "module")
    del ast["generic_modules"]

def parse_globals(ast, text, result):
    start = 0
    for Global in ast["globals"]:
        start = parse_with_type({"name": Global, **ast["globals"][Global]}, text[start:], result, "type", None)
    del ast["globals"]

def c3ctags(paths: list, output_file: str="TAGS", append=False, no_globals=False):
    for path in paths:
        ast = get_json(path)
        text = open(path, "rt").read()
        result = []

        try:
            parse_types(ast, text, result)
            parse_functions(ast, text, result)
            parse_macros(ast, text, result)
            parse_constants(ast, text, result)
            parse_modules(ast, text, result)
            if not no_globals:
                parse_globals(ast, text, result)
        except:
            print(f"in file: {path}")
            raise
    
        result = b"\n".join(result)
        if not append and os.path.exists(output_file):
            if "y" != input(f"file {output_file} already exists. overwrite? (y) "):
                print("Aborted.")
                raise SystemExit(1)
        with open(output_file, "ab" if append else "wb") as out:
            out.write(b"\x0c\n%b,%d\n" % (path.encode(), len(result)))
            out.write(result)
            out.write(b"\n")
        append = True
    print(f"wrote tags to {output_file}")

if "__main__" == __name__:
    paths = []
    append = False
    no_globals = False
    output_file = "TAGS"
    args = list(reversed(sys.argv))
    me = args.pop()
    while len(args):
        arg = args.pop()
        
        if arg == "-V" or arg == "--version":
            print(f"{me} {'.'.join(str(i) for i in __version)}")
            raise SystemExit(0)

        if arg == "-h" or arg == "--help":
            paths.clear()
            break
        
        if arg == "-a" or arg == "--append":
            append = True
            continue

        if arg == "-o":
            if len(args) == 0:
                raise ValueError("expected argument")
            output_file = args.pop()
            continue

        if arg == "--no-globals":
            no_globals = True
            continue
        
        paths.append(arg)
    
    if len(paths) == 0:
        print(f"usage: {me} [options] [file-name] ...")
        print("\n-a, --append\n    Append tag entries to existing tags file.")
        print("--no-globals\n    Do not create tag entries for global variables.")
        print("-o FILE\n    Write the tags to FILE.")
        
        raise SystemExit(1)
    
    c3ctags(paths, output_file=output_file, append=append, no_globals=no_globals)

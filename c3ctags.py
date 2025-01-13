#!/bin/python3
import json
import subprocess
import re
import sys

__version__ = (0, 0, 1)
all = ["c3ctags"]

c3c = "c3c"
params = ["compile", "-P", "--use-stdlib=no"]

def get_json(path):
    assert(path.endswith(".c3") or path.endswith(".c3i"))
    return json.loads(subprocess.check_output((c3c, *params, path)))

def format_type(Type):
    Type = Type.replace("[", r"\[")
    Type = Type.replace("]", r"\]")
    refcount = Type.count("*")
    if 0 == refcount:
        return Type
    return Type.replace("*", "") + r"\s*" + (r"\*" * refcount)

def unnamespace(namespaced):
    last = namespaced.rfind("::")
    if last < 0:
        return namespaced
    return namespaced[2 + last:]

def add_regex(text, result, regex, name):
    Match = regex.search(text)
    if Match is None:
        print(regex)
        print(f"ERROR: Failed to find {name}")
        raise ValueError
    offset = Match.start()
    text_up_to = text[:offset]
    line = 1 + text_up_to.count("\n")
    line_start = text_up_to.rfind("\n") + 1
    result.append(b"%b\x7f%b\x01%d,%d" % (text[line_start:Match.end()].encode(), name.encode(), line, line_start))

def parse(item, text, result, prefix):
    name = unnamespace(item["name"])
    if not prefix:
        regex = re.compile(rf"{name}")
    else:
        regex = re.compile(rf"{prefix}.*?{name}")
    add_regex(text, result,regex, name)

def parse_with_type(item, text, result, T, prefix):
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
    for Type in ast[T]:
        kind = Type["kind"]
        name = Type["name"]
        t_name = unnamespace(name)
        
        if kind in ("struct", "enum", "distinct", "bitstruct", "union"):
            parse(Type, text, result, kind)
            continue
        
        if kind == "typedef":
            parse(Type, text, result, "def")
            continue
        
        print(Type)
        raise NotImplementedError
    del ast[T]

def parse_types(ast, text, result):
    _parse_types(ast, text, result, "types")
    _parse_types(ast, text, result, "generic_types")

def parse_functions(ast, text, result):
    for fn in ast["functions"]:
        parse_with_type(fn, text, result, "rtype", "fn")
    del ast["functions"]
    
    for fn in ast["generic_functions"]:
        parse_with_type(fn, text, result, "rtype", "fn")
    del ast["generic_functions"]

def parse_macros(ast, text, result):
    for macro in ast["macros"]:
        parse_with_type(macro, text, result, "rtype", "macro")
    del ast["macros"]
    
    for macro in ast["generic_macros"]:
        parse_with_type(macro, text, result, "rtype", "macro")
    del ast["generic_macros"]

def parse_constants(ast, text, result):
    for constant in ast["constants"]:
        parse_with_type(constant, text, result, "type", "const")
    del ast["constants"]

def parse_modules(ast, text, result):
    for module in ast["modules"]:
        if module == "std::core":
            continue
        parse({"name": module}, text, result, "module")
    del ast["modules"]
    
    for module in ast["generic_modules"]:
        parse({"name": module}, text, result, "module")
    del ast["generic_modules"]

def parse_globals(ast, text, result):
    for Global in ast["globals"]:
        parse_with_type({"name": Global, **ast["globals"][Global]}, text, result, "type", None)
    del ast["globals"]

def c3ctags(path):
    ast = get_json(path)
    text = open(path, "rt").read()
    result = []
    
    parse_types(ast, text, result)
    parse_functions(ast, text, result)
    parse_macros(ast, text, result)
    parse_constants(ast, text, result)
    parse_modules(ast, text, result)
    parse_globals(ast, text, result)

    for things in ast:
        for item in ast[things]:
            print(f"{things[:-1]}:", item, ast[things][item])
        print(things, "are not handled.\n")
    
    result = b"\n".join(result)
    with open("TAGS", "wb") as out:
        out.write(b"\x0c\n%b,%d\n" % (path.encode(), len(result)))
        out.write(result)
        out.write(b"\n")

if "__main__" == __name__:
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <path to .c3 or .c3i>")
        raise SystemExit(1)
    c3ctags(sys.argv[1])

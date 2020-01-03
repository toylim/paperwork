import importlib
import sys

import openpaperwork_core


# skip some interfaces ; too many plugin depends on it, making the graph
# unreadable
INTERFACES_TO_IGNORE = {
    "chkdeps",
    "pages",
}


def load_plugins(core, arg):
    (module_name, variable) = arg.rsplit(".", 1)
    module = importlib.import_module(module_name)
    plugin_names = getattr(module, variable)
    for name in plugin_names:
        print("Loading {} ...".format(name))
        core.load(name)


g_current_frame = []
g_indent = 0


def print_package(out, plugin_name):
    global g_current_frame
    global g_indent

    pkgs = plugin_name.split(".", 1)
    plugin_name = pkgs[-1]
    pkgs = pkgs[:-1]

    print("Package: {}".format(pkgs))

    idx = 0
    for (idx, (pkg_a, pkg_b)) in enumerate(zip(pkgs, g_current_frame)):
        if pkg_a != pkg_b:
            break
    else:
        if len(g_current_frame) == len(pkgs):
            return plugin_name

    while len(g_current_frame) > idx:
        g_indent -= 1
        out.write('{}}}\n'.format("  " * g_indent))
        g_current_frame = g_current_frame[:-1]

    while len(pkgs) > idx:
        out.write('\n{}package "{}" <<Frame>> {{\n'.format(
            "  " * g_indent, pkgs[idx]
        ))
        g_indent += 1
        if pkgs[idx] == "openpaperwork_core":
            out.write('{}class "Core"\n'.format("  " * g_indent))
        idx += 1

    g_current_frame = pkgs
    return plugin_name


g_interfaces = set()

def dump_plugin(out, long_plugin_name, short_plugin_name, plugin):
    global g_interfaces
    global g_indent

    long_plugin_name = long_plugin_name.split(".", 1)[1].replace(".", "-")

    print("Plugin: {}".format(long_plugin_name))
    interfaces = plugin.get_interfaces()
    for i in INTERFACES_TO_IGNORE:
        if i in interfaces:
            interfaces.remove(i)
    print("Interfaces: {}".format(interfaces))

    out.write('{}class "{}"\n'.format("  " * g_indent, long_plugin_name))

    if len(interfaces) <= 0:
        out.write('{}"Core" o-- "{}"\n'.format(
            "  " * g_indent, long_plugin_name
        ))

    for interface in interfaces:
        if interface not in g_interfaces:
            g_interfaces.add(interface)
            out.write('{}interface "{}"\n'.format(
                "  " * g_indent, interface
            ))
            out.write('{}"Core" o-- "{}"\n'.format(
                "  " * g_indent, interface
            ))
        out.write('{}"{}" <|-- "{}"\n'.format(
            "  " * g_indent, interface, long_plugin_name
        ))

    # Do not show plugin dependencies. It makes the graph too messy

    # deps = plugin.get_deps()
    # print("Dependencies: {}".format(deps))
    # for dep in deps:
    #     interface = dep['interface']
    #     if interface in INTERFACES_TO_IGNORE:
    #         continue
    #     out.write('{}"{}" o-- "{}"\n'.format(
    #         "  " * g_indent, long_plugin_name, interface)
    #    )


def main():
    core = openpaperwork_core.Core()

    if len(sys.argv) <= 1:
        print("Usage: {} [out_file] [plugin list]".format(sys.argv[0]))
        print(
            "Example: {}"
            " out.uml paperwork_shell.main.DEFAULT_CLI_PLUGINS".format(
                sys.argv[0]
            )
        )
        sys.exit(1)

    for arg in sys.argv[2:]:
        load_plugins(core, arg)

    print("{} plugins found".format(len(core.plugins)))

    package_name = None

    with open(sys.argv[1], "w") as out:
        out.write("@startuml\n")
        out.write("left to right direction\n")
        for plugin_name in sorted(core.plugins):
            print("----")
            plugin = core.plugins[plugin_name]
            short_plugin_name = print_package(out, plugin_name)
            short_plugin_name = plugin_name
            dump_plugin(out, plugin_name, short_plugin_name, plugin)
        print("----")
        print_package(out, "")  # closes the current frames
        out.write("@enduml\n")

    print("====")
    print("Plantuml command:")
    print("PLANTUML_LIMIT_SIZE=65536 plantuml {}".format(sys.argv[1]))

if __name__ == "__main__":
    main()

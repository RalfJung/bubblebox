import sys, os, glob, random, string, subprocess
from pprint import pprint

HOME = os.environ["HOME"]
XDG_RUNTIME_DIR = os.environ["XDG_RUNTIME_DIR"]
BUBBLEBOX_DIR = XDG_RUNTIME_DIR + "/bubblebox"
os.makedirs(BUBBLEBOX_DIR, exist_ok=True)

def randname():
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(8))

class BwrapInvocation:
    """Gathered information for a bwrap invocation.
    This will be created empty, and then each directive's `setup` function is called
    with this object, so they can accumulate the bwrap flags and any other relevant state."""
    def __init__(self):
        # The flags to pass to bwrap.
        self.flags = []
        # Functions to call at the end of the setup process.
        # They will receive this object as argument, so they can add further flags.
        self.finalizers = []
        # If this is `None` it means so far no d-bus proxy has been set up.
        self.dbus_proxy_flags = None

class BwrapDirective:
    """Directive that just passes flags to bwrap."""
    def __init__(self, bwrap_flags):
        self.bwrap_flags = bwrap_flags
    def setup(self, bwrap):
        bwrap.flags.extend(self.bwrap_flags)

class GroupDirective:
    """Directive that groups a bunch of directives to be treated as one."""
    def __init__(self, directives):
        self.directives = directives
    def setup(self, bwrap):
        for directive in self.directives:
            directive.setup(bwrap)

class DbusProxyDirective:
    """Directive that sets up a d-bus proxy and adds flags to it.
    If the directive is used multiple times, the flags accumulate."""
    def __init__(self, dbus_proxy_flags):
        self.dbus_proxy_flags = dbus_proxy_flags
    def setup(self, bwrap):
        if bwrap.dbus_proxy_flags is None:
            # We are the first d-bus proxy directive. Set up the flags and the finalizer.
            bwrap.dbus_proxy_flags = []
            bwrap.finalizers.append(DbusProxyDirective.launch_dbus_proxy)
        # Always add the flags.
        bwrap.dbus_proxy_flags.extend(self.dbus_proxy_flags)
    def launch_dbus_proxy(bwrap):
        """Finalizer that launches a d-bus proxy with the flags accumulated in `bwrap`."""
        # For the system bus, we assume it to be at a fixed location and provide it to the sandbox at that same location.
        # For the session bus, we tell the proxy to talk to DBUS_SESSION_BUS_ADDRESS on the host, but we always put it
        # at `$XDG_RUNTIME_DIR/bus` in the sandbox.
        session_bus = XDG_RUNTIME_DIR + "/bus" # how the sandbox will see the bus
        system_bus = "/run/dbus/system_bus_socket"
        session_bus_proxy = BUBBLEBOX_DIR + "/bus-" + randname()
        system_bus_proxy = BUBBLEBOX_DIR + "/bus-system-" + randname()
        # Prepare a pipe to coordinate shutdown of bwrap and the proxy
        bwrap_end, other_end = os.pipe() # both FDs are "non-inheritable" now
        # Invoke the debus-proxy
        args = ["/usr/bin/xdg-dbus-proxy", "--fd="+str(other_end)]
        args += ["unix:path="+system_bus, system_bus_proxy, "--filter"] # just block everything for the system bus
        args += [os.environ["DBUS_SESSION_BUS_ADDRESS"], session_bus_proxy, "--filter"] + bwrap.dbus_proxy_flags
        #pprint(args)
        subprocess.Popen(
            args,
            pass_fds = [other_end], # default is to pass only the std FDs!
        )
        # Wait until the proxy is ready
        os.read(bwrap_end, 1)
        assert os.path.exists(session_bus_proxy)
        # Make sure bwrap can access the other end of the pipe
        os.set_inheritable(bwrap_end, True)
        # Put this at the usual location for the bus insode the sandbox.
        # TODO: What if DBUS_SESSION_BUS_ADDRESS says something else?
        bwrap.flags.extend((
            "--setenv", "DBUS_SESSION_BUS_ADDRESS", "unix:path="+session_bus,
            "--bind", session_bus_proxy, session_bus,
            "--bind", system_bus_proxy, system_bus,
            "--sync-fd", str(bwrap_end),
        ))

# Constructors that should be used instead of directly mentioning the class above.
def bwrap_flags(*flags):
    return BwrapDirective(flags)
def dbus_proxy_flags(*flags):
    return DbusProxyDirective(flags)
def group(*directives):
    return GroupDirective(directives)

# Run the application in the bubblebox with the given flags.
def bubblebox(*directives):
    if len(sys.argv) <= 1:
        print(f"USAGE: {sys.argv[0]} <program name> <program arguments>")
        sys.exit(1)
    # Make sure `--die-with-parent` is always set.
    directives = group(bwrap_flags("--die-with-parent"), *directives)
    # Compute the bwrap invocation by running all the directives.
    bwrap = BwrapInvocation()
    directives.setup(bwrap)
    for finalizer in bwrap.finalizers:
        finalizer(bwrap)
    # Run bwrap
    args = ["/usr/bin/bwrap"] + bwrap.flags + ["--"] + sys.argv[1:]
    #pprint(args)
    os.execvp(args[0], args)

# Give all instances of the same box a shared XDG_RUNTIME_DIR
def shared_runtime_dir(boxname):
    dirname = BUBBLEBOX_DIR + "/" + boxname
    os.makedirs(dirname, exist_ok=True)
    return bwrap_flags("--bind", dirname, XDG_RUNTIME_DIR)

# Convenient way to declare host access
class Access:
    Read = 0
    Write = 1
    Device = 2

    def flag(val):
        if val == Access.Read:
            return "--ro-bind"
        elif val == Access.Write:
            return "--bind"
        elif val == Access.Device:
            return "--dev-bind"
        else:
            raise Exception(f"invalid access value: {val}")
def host_access(dirs):
    def expand(root, names):
        """`names` is one or more strings that can contain globs. Expand them all relative to `root`."""
        if isinstance(names, str):
            names = (names,)
        assert isinstance(names, tuple)
        for name in names:
            assert not (name.startswith("../") or name.__contains__("/../") or name.endswith("../"))
            path = root + "/" + name
            # prettification
            path = path.replace("//", "/")
            path = path.removesuffix("/.")
            # glob expansion
            globbed = glob.glob(path)
            if len(globbed) == 0:
                raise Exception(f"Path does not exist: {path}")
            yield from globbed
    def recursive_host_access(root, dirs, out):
        for names, desc in dirs.items():
            for path in expand(root, names):
                if isinstance(desc, dict):
                    # Recurse into children
                    recursive_host_access(path, desc, out)
                else:
                    # Allow access to this path
                    out.extend((Access.flag(desc), path, path))
    # Start the recursive traversal
    out = []
    recursive_host_access("", dirs, out)
    #pprint(out)
    return bwrap_flags(*out)
def home_access(dirs):
    return host_access({ HOME: dirs })

# Profile the profiles when importing bubblebox.
import profiles

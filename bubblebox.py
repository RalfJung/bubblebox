import sys, os, glob, random, string, subprocess
from pprint import pprint

HOME = os.environ["HOME"]
XDG_RUNTIME_DIR = os.environ["XDG_RUNTIME_DIR"]
BUBBLEBOX_DIR = XDG_RUNTIME_DIR + "/bubblebox"
os.makedirs(BUBBLEBOX_DIR, exist_ok=True)

def flat_map(f, xs):
    """Concatenate the result of applying `f` to each element of `xs` to a list.
    `None` is treated like the empty list."""
    ys = []
    for x in xs:
        x_mapped = f(x)
        if x_mapped is not None:
            ys.extend(x_mapped)
    return ys

def randname():
    # choose from all lowercase letter
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for i in range(8))

class BoxFlags:
    """Flags that configure the bubblebox"""
    def __init__(self, bwrap_flags = None, dbus_proxy_flags = None):
        self.bwrap_flags = bwrap_flags
        self.dbus_proxy_flags = dbus_proxy_flags

def launch_dbus_proxy(flags):
    """Launches the dbus proxy and returns the bwrap flags to be used to talk to it."""
    # Prepare a pipe to coordinate shutdown of bwrap and the proxy
    bwrap_end, other_end = os.pipe() # both FDs are "non-inheritable" now
    # Invoke the debus-proxy
    filename = BUBBLEBOX_DIR + "/bus-" + randname()
    args = ["/usr/bin/xdg-dbus-proxy", "--fd="+str(other_end)]
    args += [os.environ["DBUS_SESSION_BUS_ADDRESS"], filename, "--filter"] + flags
    #pprint(args)
    subprocess.Popen(
        args,
        pass_fds = [other_end], # default is to pass only the std FDs!
    )
    # Wait until the proxy is ready
    os.read(bwrap_end, 1)
    assert os.path.exists(filename)
    # Make sure bwrap can access the other end of the pipe
    os.set_inheritable(bwrap_end, True)
    # Put this at the usual location for the bus insode the sandbox.
    # TODO: What if DBUS_SESSION_BUS_ADDRESS says something else?
    return ["--bind", filename, XDG_RUNTIME_DIR + "/bus", "--sync-fd", str(bwrap_end)]

# Constructors that should be used instead of directly mentioning the class above.
def bwrap_flags(*flags):
    return BoxFlags(bwrap_flags=flags)
def dbus_proxy_flags(*flags):
    return BoxFlags(dbus_proxy_flags=flags)
def collect_flags(*flags):
    bwrap_flags = flat_map(lambda x: x.bwrap_flags, flags)
    dbus_proxy_flags = flat_map(lambda x: x.dbus_proxy_flags, flags)
    return BoxFlags(bwrap_flags, dbus_proxy_flags)

# Run the application in the bubblebox with the given flags.
def bubblebox(*flags):
    flags = collect_flags(*flags)
    bwrap = "/usr/bin/bwrap"
    extraflags = []
    if flags.dbus_proxy_flags:
        extraflags += launch_dbus_proxy(flags.dbus_proxy_flags)
    args = [bwrap] + flags.bwrap_flags + extraflags + ["--"] + sys.argv[1:]
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
            yield from glob.glob(path)
    def recursive_host_access(root, dirs, out):
        for names, desc in dirs.items():
            for path in expand(root, names):
                if isinstance(desc, dict):
                    # Recurse into children
                    recursive_host_access(path, desc, out)
                else:
                    # Allow access to this path
                    out.extend([Access.flag(desc), path, path])
    # Start the recursive traversal
    out = []
    recursive_host_access("", dirs, out)
    #pprint(out)
    return bwrap_flags(*out)
def home_access(dirs):
    return host_access({ HOME: dirs })

# Profile the profiles when importing bubblebox.
import profiles

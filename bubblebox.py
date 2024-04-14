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

def globexpand(base, names):
    return flat_map(lambda x: glob.glob(base + "/" + x), names)

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

# Convenient methods to give access to the host file system
def ro_host_access(*names):
    return bwrap_flags(*flat_map(lambda x: ["--ro-bind", x, x], names))
def rw_host_access(*names):
    return bwrap_flags(*flat_map(lambda x: ["--bind", x, x], names))
def dev_host_access(*names):
    return bwrap_flags(*flat_map(lambda x: ["--dev-bind", x, x], names))

# Give all instances of the same box a shared XDG_RUNTIME_DIR
def shared_runtime_dir(boxname):
    dirname = BUBBLEBOX_DIR + "/" + boxname
    os.makedirs(dirname, exist_ok=True)
    return bwrap_flags("--bind", dirname, XDG_RUNTIME_DIR)

# Profile the profiles when importing bubblebox.
import profiles

from bubblebox import *

# Various default sandbox settings
DEFAULT = collect_flags(
  # namespace unsharing
  # cannot unshare IPC as that breaks some wine applications
  bwrap_flags("--unshare-user", "--unshare-pid", "--unshare-cgroup"),
  # A different hostname is useful to be able to see when we are inside the sandbox.
  # However, some applications will not like this unless the hostname also exists in `/etc/hosts`!
  bwrap_flags("--unshare-uts", "--hostname", "bubblebox"),
  # basic directories
  bwrap_flags("--proc", "/proc", "--dev", "/dev", "--dir", "/tmp", "--dir", "/var", "--dir", "/run", "--symlink", "../run", "/var/run"),
  # an empty XDG_RUNTIME_DIR
  bwrap_flags("--perms", "0700", "--dir", XDG_RUNTIME_DIR),
  # merged-usr symlinks
  bwrap_flags("--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64", "--symlink", "usr/bin", "/bin", "--symlink", "usr/sbin", "/sbin"),
  # folders we always need access to
  host_access({ ("/usr", "/sys", "/etc"): Access.Read }),
  # make a basic shell work
  home_access({
    (".bashrc", ".bash_aliases", ".profile"): Access.Read,
    "bin": Access.Read,
  }),
)

# https://github.com/igo95862/bubblejail is a good source of paths that need allowing.
# We do not give access to pipewire, that needs a portal (https://docs.pipewire.org/page_portal.html).
def DESKTOP(name):
  return collect_flags(
    DEFAULT,
    # Share XDG_RUNTIME_DIR among all instances of this sandbox
    shared_runtime_dir(name),
    # Access to screen and audio
    host_access({
      "dev": {
        ("dri", "snd"): Access.Device,
      },
      "/tmp/.X11-unix/": Access.Read,
      os.environ["XAUTHORITY"]: Access.Read,
      XDG_RUNTIME_DIR: {
        ("wayland*", "pulse"): Access.Read,
      },
    }),
    # Access to some key user configuration
    home_access({
      (".config/fontconfig", ".XCompose", ".local/share/applications"): Access.Read,
    }),
    # Access to basic d-bus services (that are hopefully safe to expose...)
    dbus_proxy_flags("--talk=org.kde.StatusNotifierWatcher.*", "--talk=org.freedesktop.Notifications.*", "--talk=org.freedesktop.ScreenSaver.*", "--talk=org.freedesktop.portal.*"),
    # Make it possible to open websites in Firefox
    home_access({ ".mozilla/firefox/profiles.ini": Access.Read }),
    dbus_proxy_flags("--talk=org.mozilla.firefox.*"),
  )

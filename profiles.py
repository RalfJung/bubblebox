from bubblebox import *

# Various default sandbox settings
DEFAULT = group(
  # namespace unsharing
  # cannot unshare IPC as that breaks some wine applications
  bwrap_flags("--unshare-user", "--unshare-pid", "--unshare-cgroup"),
  # A different hostname is useful to be able to see when we are inside the sandbox.
  # However, some applications will not like this unless the hostname also exists in `/etc/hosts`!
  # Also, gnome-shell doesn't display window icons properly when this is set.
  #bwrap_flags("--unshare-uts", "--hostname", "bubblebox"),
  # Make sure the sandbox cannot inject commands into the host terminal.
  # TODO: This flag breaks some CLI applications, like job control in shells.
  # Consider using SECCOMP instead.
  # Possible code to use for that: <https://gist.github.com/sloonz/4b7f5f575a96b6fe338534dbc2480a5d#file-sandbox-py-L129>
  # There is also a good list of possible-syscalls-to-block at
  # <https://github.com/flatpak/flatpak/blob/f16e064fd9454fb8f754b769ad1ffce0e42b51db/common/flatpak-run.c#L1791>.
  bwrap_flags("--new-session"),
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

def X11():
  display = os.environ["DISPLAY"].removeprefix(":").split('.')[0]
  return host_access({
      "/tmp/.X11-unix/": {
        "X"+display: Access.Read,
      },
      os.environ["XAUTHORITY"]: Access.Read,
  })

# https://github.com/igo95862/bubblejail/blob/master/src/bubblejail/services.py is a good source of paths that need allowing.
# We do not give access to pipewire, that needs a portal (https://docs.pipewire.org/page_portal.html).
def DESKTOP(name):
  return group(
    DEFAULT,
    # Share XDG_RUNTIME_DIR among all instances of this sandbox
    shared_runtime_dir(name),
    # Access to display servers, hardware acceleration, and audio
    host_access({
      "dev": {
        ("dri", "snd"): Access.Device,
      },
      XDG_RUNTIME_DIR: {
        (os.environ["WAYLAND_DISPLAY"], "pulse"): Access.Read,
      },
    }),
    X11(),
    # Access to some key user configuration.
    # We set GSETTINGS_BACKEND to make GTK3 apps use the config file in ~/.config/glib-2.0.
    # (The "right" solution here is probably the settings portal...)
    home_access({
      (".config/fontconfig", ".config/glib-2.0", ".XCompose", ".local/share/applications"): Access.Read,
    }),
    bwrap_flags("--setenv", "GSETTINGS_BACKEND", "keyfile"),
    # Access to basic d-bus services (that are hopefully safe to expose...)
    dbus_proxy_flags(
      "--call=org.kde.StatusNotifierWatcher=@/StatusNotifierWatcher",
      "--call=org.freedesktop.Notifications=@/org/freedesktop/Notifications",
      "--call=org.freedesktop.ScreenSaver=@/org/freedesktop/ScreenSaver",
      "--call=org.freedesktop.ScreenSaver=@/ScreenSaver",
      "--talk=org.freedesktop.portal.*",
    ),
    # Make it possible to open websites in Firefox
    home_access({ ".mozilla/firefox/profiles.ini": Access.Read }),
    dbus_proxy_flags("--call=org.mozilla.firefox.*=@/org/mozilla/firefox/Remote"),
  )

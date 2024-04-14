from bubblebox import *

# Various default sandbox settings
DEFAULT = collect_flags(
  # general flags
  bwrap_flags("--die-with-parent"),
  # namespace unsharing
  bwrap_flags("--unshare-all", "--share-net", "--hostname", "bwrapped"),
  # basic directories
  bwrap_flags("--proc", "/proc", "--dev", "/dev", "--dir", "/tmp", "--dir", "/var", "--dir", "/run", "--symlink", "../run", "/var/run"),
  # an empty XDG_RUNTIME_DIR
  bwrap_flags("--perms", "0700", "--dir", XDG_RUNTIME_DIR),
  # merged-usr symlinks
  bwrap_flags("--symlink", "usr/lib", "/lib", "--symlink", "usr/lib64", "/lib64", "--symlink", "usr/bin", "/bin", "--symlink", "usr/sbin", "/sbin"),
  # folders we always need access to
  ro_host_access("/usr", "/sys", "/etc"),
  # make a basic shell work
  ro_host_access(*globexpand(HOME, [".bashrc", ".bash_aliases", ".profile", "bin"])),
)

# https://github.com/igo95862/bubblejail is a good source of paths that need allowing.
# We do not give access to pipewire, that needs a portal (https://docs.pipewire.org/page_portal.html).
DESKTOP = collect_flags(
  # Access to screen and audio
  dev_host_access("/dev/dri", "/dev/snd"),
  ro_host_access("/tmp/.X11-unix/", os.environ["XAUTHORITY"]),
  ro_host_access(*globexpand(XDG_RUNTIME_DIR, ["wayland*", "pulse"])),
  # Access to some key global configuration
  ro_host_access(*globexpand(HOME, [".config/fontconfig", ".XCompose"])),
  # Access to basic d-bus services (that are hopefully safe to expose...)
  dbus_proxy_flags("--talk=org.kde.StatusNotifierWatcher.*", "--talk=org.freedesktop.Notifications.*", "--talk=org.freedesktop.ScreenSaver.*", "--talk=org.freedesktop.portal.*"),
  # Make it possible to open websites in Firefox
  ro_host_access(*globexpand(HOME, [".mozilla/firefox/profiles.ini", ".local/share/applications"])),
  dbus_proxy_flags("--talk=org.mozilla.firefox.*"),
)

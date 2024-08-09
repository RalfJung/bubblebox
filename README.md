# BubbleBox: Simple Application Sandboxing

## Introduction

This is the documentation of [BubbleBox](https://www.ralfj.de/projects/bubblebox), a
tool to easily sandbox Linux applications.

The primary use-case for BubbleBox is running applications that you do not trust enough
to give them full access to your home directory, and in particular the secret keys stored there.
BubbleBox is based on [bubblewrap] and [xdg-dbus-proxy] which do all of the heavy lifting.

The goals of this project are similar to [firejail], but I found firejail's configuration to be extremely hard to maintain and debug.
BubbleBox is meant for people that are comfortable editing its Python source code to adjust it to their needs;
if you are looking for something with a more out-of-the-box experience, try [bubblejail].

[firejail]: https://firejail.wordpress.com/
[bubblejail]: https://github.com/igo95862/bubblejail
[bubblewrap]: https://github.com/containers/bubblewrap
[xdg-dbus-proxy]: https://github.com/flatpak/xdg-dbus-proxy

## Usage

The typical way to use BubbleBox is to create a new "jail" script in the BubbleBox source folder.
For instance, if you want a "gamejail" that you can use to run games, create a file `gamejail`
in a BubbleBox checkout with contents like this:

```python
#!/bin/python3
from bubblebox import *

bubblebox(
  profiles.DESKTOP("gamejail"),
  dbus_proxy_flags("--own=com.steampowered.*"),

  home_access({
    ".steam": Access.Write,
  }),
)
```

Then add a symlink to this file somewhere to your PATH, and now you can use `gamejail <application>`
to run arbitrary games inside the BubbleBox.

### Configuration directives

A BubbleBox sandbox is configured by passing a list of directives to the
`bubblebox` functions that declare things the sandbox has access to. Everything
else is blocked by default.

These directives are basically lists of bubblewrap and xdg-dbus-proxy flags,
but BubbleBox provides some convenience functions
to allow higher-level configuration and to share common patterns.

The `profiles.py` file contains some useful directives that are needed by most applications:
- `profiles.DEFAULT` adds the basic flags to isolate the sandbox from the environment
  by unsharing all namespaces except for the network.
  This profile gives access to `/usr`, `/sys`, and `/etc` and also creates a
  stub file system inside the sandbox that is basically always required, such as
  an empty folder to serve as XDG_RUNTIME_DIR. It assumes a merged-usr setup,
  e.g. it will add `/bin` as a symlink to `/usr/bin`. It also gives read-only
  access to some files in the home directory that are often needed to make a
  basic shell work: `.bashrc`, `.bash_aliases`, `.profile` and the `bin`
  directory.
- `profiles.DESKTOP("name")` is intended to make GUI applications work. It
  extends `DEFAULT` by providing access to DRI, X11, ALSA, Wayland, and
  PulseAudio. Furthermore, some GUI configuration files (`.XCompose`,
  fontconfig, and default mime-type associations) are made available to the
  sandbox. The `"name"` is used to create an XDG_RUNTIME_DIR that will be shared
  among all instances of this sandbox. This also sets up the D-Bus proxy and
  gives the application access to notifications, screen saver control, status
  icons, and the flatpak portals (however, actually using these portals is
  untested and would likely require further integration). Finally, it makes
  clicking on links inside the sandbox work properly if your default browser is
  Firefox.

I recommend looking at the sources in `default.py` to learn how to configure your
own sandboxes. Here are the key directives to use:
- `host_access` gives the sandbox read-only or read-write access to some part
  of the host file system. This is declared via nested Python dicts and supports
  glob expressions.
- `home_access` works the same as `host_access` except all paths are relative
  to the home directory.
- `bwrap_flags` allows passing flags directly to `bwrap`. This is rarely needed.
- `dbus_proxy_flags` allows passing flags directly to `xdg-dbus-proxy`.
  This is the typical way to provide access to additional D-Bus names.

## Source, License

You can find the sources in the
[git repository](https://git.ralfj.de/bubblebox.git) (also available
[on GitHub](https://github.com/RalfJung/bubblebox)). They are provided under the
[GPLv2](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html) or (at your
option) any later version of the GPL.  See the file `LICENSE-GPL2` for more
details.

## Contact

If you found a bug, or want to leave a comment, please
[send me a mail](mailto:post-AT-ralfj-DOT-de).  I'm also happy about pull
requests :)

unreleased
==========

* Cross-distribution support: openSUSE Leap 15.6/16.0, SLES 15, Debian 13,
  Ubuntu 24.04/26.04, RHEL 10. Distribution is detected at runtime from
  ``/etc/os-release`` and all operations dispatch to the right backend.
* New ``cui.distro`` module abstracts package manager, network backend,
  repository file layout and key import per family.
* yast2 dependency dropped on every distribution, openSUSE included.
* Built-in network configuration dialog reads the on-disk config of the
  active backend (``systemd-networkd`` ``.network``/``.netdev``,
  ``wicked`` ``ifcfg-`` files plus ``routes``/``config``,
  ``NetworkManager`` via ``nmcli``) and edits multiple IPv4/IPv6
  addresses, separate v4/v6 default gateways, static routes, DNS servers
  and bond devices (mode, MIIMON, members). Changes are written in the
  backend's native format and applied live.
* New language, keyboard layout and timezone dialogs backed by
  ``localectl`` and ``timedatectl``.
* ``zypper`` calls in "Update the system" and "Select software repositories"
  are routed through the platform's package manager.
* The ``install.sh`` helper now detects the package manager and installs the
  matching system packages.
* Bug fixes: invalid escape ``\\s`` regex, ``cffi.FFI.NULL`` (use ``bld.NULL``),
  tab/space mixing in ``get_last_login_time``, format-string-in-translation
  patterns that prevented gettext extraction.

1.1 (2025-02-06)
================

* Remove extraneous lineboxes from within a dialog
* Support Y2038-capable libwtmpdb interface for determining
  last login timestamp

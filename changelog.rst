unreleased
==========

* Cross-distribution support: openSUSE Leap 15.6/16.0, Debian 13,
  Ubuntu 24.04/26.04, RHEL 10. Distribution is detected at runtime from
  ``/etc/os-release`` and all operations dispatch to the right backend.
* New ``cui.distro`` module abstracts package manager, network backend,
  repository file layout and key import per family.
* New built-in network configuration dialog with ``systemd-networkd``,
  ``NetworkManager`` and ``wicked`` backends. Replaces ``yast2 lan`` on
  non-SUSE systems while keeping yast2 as the path on openSUSE.
* New language and timezone dialogs backed by ``localectl`` and
  ``timedatectl``. ``yast2 language`` / ``yast2 timezone`` are still used on
  openSUSE when present.
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

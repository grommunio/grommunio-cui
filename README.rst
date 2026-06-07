grommunio CUI
=============

grommunio CUI (console user interface) is a textgraphical interface for
managing the basic grommunio Appliance configuration.
It is localized, with selectable keyboard layouts and languages.

|shield-agpl|_ |shield-release|_ |shield-loc|

.. |shield-agpl| image:: https://img.shields.io/badge/license-AGPL--3.0-green
.. _shield-agpl: LICENSE.txt
.. |shield-release| image:: https://shields.io/github/v/tag/grommunio/grommunio-cui
.. _shield-release: https://github.com/grommunio/grommunio-cui/tags
.. |shield-loc| image:: https://img.shields.io/github/languages/code-size/grommunio/grommunio-cui

Supported platforms
===================

grommunio-cui targets server appliances and has been verified on:

* openSUSE Leap 15.6 and 16.0
* Debian 13
* Ubuntu 24.04 LTS and 26.04 LTS
* RHEL 10 (and rebuilds: Rocky, AlmaLinux, Oracle Linux)

Distribution detection is done at runtime via ``/etc/os-release``. Operations
that touch the host (package install, network config, locale, timezone) are
dispatched to the right backend automatically:

* **Package manager** — ``zypper`` (SUSE), ``dnf``/``yum`` (RHEL/Fedora),
  ``apt-get`` (Debian/Ubuntu). The "Update the system" and "Select software
  repositories" menu items pick the right tool.
* **Network configuration** — ``systemd-networkd`` (openSUSE 16.0,
  Debian/Ubuntu Server, RHEL when configured that way), ``NetworkManager``
  (RHEL/Fedora default), ``wicked`` (openSUSE Leap 15.6 / SLES 15). The CUI
  auto-detects the active backend, reads the existing config, lets you edit
  IPv4/IPv6 addresses, default gateway and static routes, DNS, and (for
  systemd-networkd / wicked) bond devices, then writes the result back in
  the backend's native format and applies it live.
* **Language / Timezone / Keymap** — ``localectl`` and ``timedatectl``
  (systemd-native, works on all supported distros).

grommunio-cui does not depend on yast2 on any distribution.

Getting Started
===============

Prerequisites
-------------

For CUI to work properly, the Python modules from `<requirements.txt>`_ need to
be present. The ``install.sh`` script installs them from the system package
manager when possible, falling back to ``pip`` otherwise.

Installation
------------

Make sure the path is correctly set:

.. code-block:: sh

	export PYTHONPATH="$PYTHONPATH:<cui_source_dir>"

or let the install script set up the dependencies and copy a wrapper script
to ``/usr/local/bin``:

.. code-block:: sh

	sudo ./install.sh

Support
=======

Support is available through grommunio GmbH and its partners. See
https://grommunio.com/ for details. A community forum is at
`<https://community.grommunio.com/>`_.

For direct contact and supplying information about a security-related
responsible disclosure, contact `dev@grommunio.com <dev@grommunio.com>`_.

Contributing
============

* https://docs.github.com/en/get-started/quickstart/contributing-to-projects
* Alternatively, upload commits to a git store of your choosing, or export the
  series as a patchset using `git format-patch
  <https://git-scm.com/docs/git-format-patch>`_, then convey the git
  link/patches through our direct contact address (above).

Translations
============

First, use xgettext from the package ``gettext-tools`` and run it to search for
``T_`` function calls to generate the template .pot file via:

.. code-block:: sh

	xgettext -kT_ -d cui -o locale/cui.pot cui/*.py

Then use ``msgmerge`` to merge the new or changed keys into the corresponding
language file.

.. code-block:: sh

	for lang in $(cd locale && echo */); do \
		msgmerge --update locale/$lang/LC_MESSAGES/cui.po locale/cui.pot; \
	done

The translations are managed through a `Weblate project
<https://hosted.weblate.org/projects/grommunio/grommunio-cui/>`_. Contributions
are regularly monitored and integrated in the release cycles of grommunio CUI.

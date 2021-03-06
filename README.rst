The Console User Interface (CUI)
================================

The Console User Interface is a text-based interface for managing the
basic grammm Appliance configuration.

1) Installation
---------------

To get the CUI running, you have to install the Python urwid library,
possibly the urwid Git project, and the CUI source itself.
In this guide, it is assumed that you have already installed:

 - gcc
 - python3-devel

These will be used for the build and install process.

1.1) Installation of the urwid module for Python
------------------------------------------------

To get the newest version of urwid, do not use zypper.
Instead, use git:

.. code-block::

    cd /opt/
    git clone https://github.com/urwid/urwid.git

1.2) Installation of the Git source (optional)
----------------------------------------------

For further development, it is recommended to install the git branch 
of the urwid project.

.. code-block::

    git clone ...

1.3) Source file copy
---------------------

Similarly to urwid, also use git to fetch the current CUI version:

.. code-block::

    git clone https://vcs.grammm.com/grammm/cui.git

In the cui directory, you can find requirements.txt and can install them via

.. code-block::

    pip install -r requirements.txt

2) Configuration
----------------

Make sure the path is correctly set:

.. code-block::

    export PYTHONPATH="$PYTHONPATH:/opt/urwid:<cui_source_dir>"

or let the install script copy cui.sh to the system:

.. code-block::

    ./install.sh


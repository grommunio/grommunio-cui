The Console User Interface (CUI)
================================

The Console User Interface is a text-based interface for managing the
basic grommunio Appliance configuration.

1) Installation
---------------

To get the CUI running, the Python modules from requirements.txt
need to be installed.

2) Configuration
----------------

Make sure the path is correctly set:

.. code-block::

    export PYTHONPATH="$PYTHONPATH:<cui_source_dir>"

or let the install script copy cui.sh to the system:

.. code-block::

    ./install.sh

3) Localisation
---------------

First use xgettext from the package `gettext-tools` and use it to search
for `T_`-function calls and generate the template pot file via:

.. code-block::

    cd grommunio-cui
    xgettext -kT_ -d cui -o locale/cui.pot cui/*.py

and then use `msgmerge` to merge the new or changed keys into the
corresponding language file.

.. code-block::

    for lang in $(cd locale && echo */); do \
        msgmerge --update locale/$lang/LC_MESSAGES/cui.po locale/cui.pot; \
    done

Now give the corresponding po-files to the right translator for translating
the added and modified keys. If you get the files back returned from your local
translator, you will have to reformat the binary mo-files with the assist of
the translated po-files.

.. code-block::

    for lang in $(cd locale && echo */); do \
        msgfmt -o locale/$lang/LC_MESSAGES/cui.mo locale/$lang/LC_MESSAGES/cui.po; \
    done

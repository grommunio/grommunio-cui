The Console User Interface, (CUI)
=================================

The Console User Interface is a text based interface for managing the 
grammm basic configurations.

1 ) Installing
--------------

To get the CUI running you have to install the Python Urwid library,
the Urwid GIT Project (Optional) and the CUI source itself.

1.1) Installing the Urwid Module for Python
-------------------------------------------

To get the newest version of urwid do not use zypper!
Instead use git:

... bash

    cd /opt/
    git clone https://github.com/urwid/urwid.git

1.2) Installing the GIT resources (Optional)
--------------------------------------------

For further developing it is recommended to install also the git branch 
of the urwid project.

... bash

    git clone ...

1.3) Copy the source files
--------------------------

Untar the source files via tar:

... bash

    tar xvzf cui.tgz

In the cui folder you can find the requirements.txt and can install it via

... bash

    pip3 install -r requirements.txt

2 ) Configuration
-----------------

The only hing you have to be sure is that the path is set correct to:

... bash

    export PYTHONPATH="$PYTHONPATH:/opt/urwid:<to_where_the_cui.py_is_lying>"
    
or let the install script copy the cui.sh to your path:

... bash

    ./install.sh
   

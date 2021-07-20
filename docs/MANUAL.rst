The Console User Interface (CUI)
================================

This manual describes how to work with the grommunio console user interface.

1 Mainscreen
------------
.. container:: floatpic

    .. image:: pics/pic001.png
        :width: 50%
        :alt: Main Screen
        :align: right

    After starting the console user interface you are in the main screen.
    Here you just can login or shutdown/reboot the system or, (most important)
    you can switch between light and dark mode.

------------------------

.. container:: floatpic

    .. image:: pics/pic002.png
        :width: 50%
        :alt: Main Screen dark
        :align: left

    Because light mode is hurting some people's eyes a bit, you can hit <F1>
    to switch between dark and light mode.

--------

.. container:: floatpic

    .. image:: pics/pic003.png
        :width: 50%
        :alt: Main Screen
        :align: right

    At first the only senseful option is to use <F2> to log in.
    You should use a superuser account if you want to change system configuration.

--------

.. container:: floatpic

    .. image:: pics/pic004.png
        :width: 50%
        :alt: Main Screen
        :align: left

    After successful login you are in the main menu where you can change a few
    system settings.

    The menu contains the ability to change password, manage network and other
    system settings or use a plain text terminal, who knows what else in future
    will come up?

------------------------

.. container:: floatpic

    .. image:: pics/pic005.png
        :width: 50%
        :alt: Main Screen
        :align: right

    In the first menu you can change your password. At the moment it is
    just a simple subshell with passwd called.

------------------------

.. container:: floatpic

    .. image:: pics/pic006.png
        :width: 50%
        :alt: Main Screen
        :align: left

    The next menu "Network Configuration" leads into the standard yast2 
    lan setup.

------------------------

.. container:: floatpic

    .. image:: pics/pic007.png
        :width: 50%
        :alt: Main Screen
        :align: right

    Here everything that has to do with network you will find here.

------------------------

.. container:: floatpic

    .. image:: pics/pic008.png
        :width: 50%
        :alt: Main Screen
        :align: left

    The most important thing to run grommunio properly is to give the 
    machine any other name than `localhost`.

------------------------

.. container:: floatpic

    .. image:: pics/pic009.png
        :width: 50%
        :alt: Main Screen
        :align: right

    If you have set up your correct network settings the next thing you
    should do is configuring the timezone information.

--------

.. container:: floatpic

    .. image:: pics/pic010.png
        :width: 50%
        :alt: Main Screen
        :align: right

    At this moment we also simple use the standard yast2 timezone configuration
    module. This is important if you are a global player or if you just wanna 
    see the correct local time.

------------------------

.. container:: floatpic

    .. image:: pics/pic011.png
        :width: 50%
        :alt: Main Screen
        :align: left

    After returning to the menu you can now choose the grommunio-setup.

------------------------

.. container:: floatpic

    .. image:: pics/pic012.png
        :width: 50%
        :alt: Main Screen
        :align: right

    The grommunio-setup is greeting you with an explaining welcome screen. Here 
    the only thing to do is not to cancel.

------------------------

.. container:: floatpic

    .. image:: pics/pic013.png
        :width: 50%
        :alt: Main Screen
        :align: left

    The grommunio-setup first asks for a subscription. If you have a subscription,
    now is the right time to use it. Just type in the correct username and password
    you got for your subscription contract.

    If you have no subscription, just leave this empty!

------------------------

.. container:: floatpic

    .. image:: pics/pic014.png
        :width: 50%
        :alt: Main Screen
        :align: right

    If you have an existing database management system and want or must to use this
    system, you can choose the second option for advanced users.

    Everyone else should be fine with the first option, which is creating a local
    DBMS which is the preferred way.

------------------------

.. container:: floatpic

    .. image:: pics/pic015.png
        :width: 50%
        :alt: Main Screen
        :align: left

    To set up the database you have to give the correct host, user, password and 
    database name. Normally grommunio-setup detects all these informations 
    automatically.

------------------------

.. container:: floatpic

    .. image:: pics/pic016.png
        :width: 50%
        :alt: Main Screen
        :align: right

    On the next screen you can set the password for the Admin UI. You can leave
    the random generated password in here. It will be displayed at the end of setup
    and you also can reset it at any time with this CUI.

------------------------

.. container:: floatpic

    .. image:: pics/pic017.png
        :width: 50%
        :alt: Main Screen
        :align: left

    Now we need to now the full qulified domain name (short: FQDN) to generate the
    for the autodiscover outlook connection and therefore at the certificate creation.

------------------------

.. container:: floatpic

    .. image:: pics/pic018.png
        :width: 50%
        :alt: Main Screen
        :align: right

    The last thing grommunio-setup wants to now the name of your mail domain which 
    you are configuring at the moment.

------------------------

.. container:: floatpic

    .. image:: pics/pic019.png
        :width: 50%
        :alt: Main Screen
        :align: left

    Some companies are using relayhosts. To relay the mails over such a server you
    can give its name here. 

------------------------

.. container:: floatpic

    .. image:: pics/pic020.png
        :width: 50%
        :alt: Main Screen
        :align: right

    Now it's the time to choose your wanted certificate type. You can create a poor,
    but fast and with no cost to create, self-signed certificate. It is enough to encrypt
    your traffic, but you have to accept a warning message that informs you about 
    that case.

    You can create or import an already existent official CA authorized certificate or
    last but not least you can automatically generate a "Let's Encrypt" certificate.

------------------------

.. container:: floatpic

    .. image:: pics/pic021.png
        :width: 50%
        :alt: Main Screen
        :align: left

    If you have chosen a self-signed certificate there will be shown an example of the
    message every user has to accept.

------------------------

.. container:: floatpic

    .. image:: pics/pic022.png
        :width: 50%
        :alt: Main Screen
        :align: right

    Congratulation! The grommunio-setup is now finished and you the an overview of your
    chosen settings. Please check everything carefully before you accept and all the 
    minimum needed work is now done.

------------------------

.. container:: floatpic

    .. image:: pics/pic023.png
        :width: 50%
        :alt: Main Screen
        :align: left

    As mentioned before you can set the Admin UI password at any time with this menu point.

------------------------

.. container:: floatpic

    .. image:: pics/pic024.png
        :width: 50%
        :alt: Main Screen
        :align: right

    You do not have to retype the password because you can change it so ro so at any time here.
    Please check it after setting.

------------------------

.. container:: floatpic

    .. image:: pics/pic025.png
        :width: 50%
        :alt: Main Screen
        :align: left

    A message will inform you about the result. You will be noticed if something went wrong while
    the password reset.

------------------------

.. container:: floatpic

    .. image:: pics/pic026.png
        :width: 50%
        :alt: Main Screen
        :align: right

    Every time a database is involved in a process environment like grommunio it is essential that
    all clocks involved are synced in a proper way!

------------------------

.. container:: floatpic

    .. image:: pics/pic027.png
        :width: 50%
        :alt: Main Screen
        :align: left

    You can use the default time servers or you can add your own NTP servers.

------------------------

.. container:: floatpic

    .. image:: pics/pic028.png
        :width: 50%
        :alt: Main Screen
        :align: right

    After pressing OK a message will inform you if something went wrongong while writing the
    timsyncd configuration.

------------------------

.. container:: floatpic

    .. image:: pics/pic029.png
        :width: 50%
        :alt: Main Screen
        :align: left

    Sometimes you have to do some expert configurations and need a shell. A Terminal is therefore
    accessible from here.

------------------------

.. container:: floatpic

    .. image:: pics/pic030.png
        :width: 50%
        :alt: Main Screen
        :align: right

    You can do nearly everything you can do in a normal shell. Just type `exit` to return to the
    CUI.

------------------------

.. container:: floatpic

    .. image:: pics/pic031.png
        :width: 50%
        :alt: Main Screen
        :align: left

    Some configuration changes or updates or similar things can lead into the need of rebooting the
    system. You have to enter the root password to do so.

------------------------

.. container:: floatpic

    .. image:: pics/pic032.png
        :width: 70%
        :alt: Main Screen
        :align: center

    If everything has been set up correctly, all the red warnings have to be gone. Instead you should
    see now in the bottom area of the main screen the URL to the Admin API UI to configure your grommunio
    groupware and much, much, more ...



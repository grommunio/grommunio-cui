#!/bin/bash

if [ -z "$(which xgettext)" ]; then
    echo "No xgettext here! Please install it: sudo zypper install gettext-tools"
    exit 1
fi

xgettext -kT_ -d cui -o locale/cui.pot cui/*.py

for lang in $(cd locale && echo */); do
    msgmerge --update locale/$lang/LC_MESSAGES/cui.po locale/cui.pot
done

echo "The po files has been generated in $(cd locale && echo */) languages."
echo "Please translate them and run 'make'"

# old stuff, better use make
exit 0
for lang in $(cd locale && echo */); do
    msgfmt -o locale/$lang/LC_MESSAGES/cui.mo locale/$lang/LC_MESSAGES/cui.po 
done

# vim: et sw=4 ts=4 sta

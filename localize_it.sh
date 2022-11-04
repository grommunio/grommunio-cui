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
echo "You can use '/^msgstr \"\"\\n\\n' in vi to find all new empty strings"
echo 'and you can use `:%s#^msgid "\(.*\)"\nmsgstr ""\n\n#msgid ""\r"\1"\rmsgstr ""\r"\1"\r\r#` to translate the english file automatically by keys.'
echo 'Use `:%s#^msgid ""\n"\(.*\)"\nmsgstr ""\n\n#msgid ""\r"\1"\rmsgstr ""\r"\1"\r\r#` to translate keys longer than two lines.'
echo 'Use `:%s#^msgid ""\n"\(.*"\n".*\)"\nmsgstr ""\n\n#msgid ""\r"\1"\rmsgstr ""\r"\1"\r\r#` to translate keys longer than three lines.'
echo 'Use `:%s#^msgid ""\n"\(.*"\n".*"\n".*\)"\nmsgstr ""\n\n#msgid ""\r"\1"\rmsgstr ""\r"\1"\r\r#` to translate keys longer than four lines.'

# old stuff, better use make
exit 0
for lang in $(cd locale && echo */); do
    msgfmt -o locale/$lang/LC_MESSAGES/cui.mo locale/$lang/LC_MESSAGES/cui.po 
done

# vim: et sw=4 ts=4 sta


# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2022 grommunio GmbH
"""The module containing the parser classes"""
import configparser
import io
from typing import Iterable, Tuple, List
import configobj


class SectionlessConfigParser(configparser.RawConfigParser):
    """
    Extends ConfigParser to allow files without sections.

    This is done by wrapping read files and prepending them with a placeholder
    section, which defaults to '__config__'
    """

    def __init__(self, *args, **kwargs):
        default_section = kwargs.pop('default_section', None)
        configparser.RawConfigParser.__init__(self, *args, **kwargs)

        self._default_section = None
        self.set_default_section(default_section or '__config__')

    def get_default_section(self):
        """Return the default section of the configfile"""
        return self._default_section

    def set_default_section(self, section):
        """Set the default section of the configfile"""
        self.add_section(section)

        # move all values from the previous default section to the new one
        try:
            default_section_items = self.items(self._default_section)
            self.remove_section(self._default_section)
        except configparser.NoSectionError:
            pass
        else:
            for (key, value) in default_section_items:
                self.set(section, key, value)

        self._default_section = section

    def read(self, filenames, encoding=None):
        if isinstance(filenames, str):
            filenames = [filenames]

        read_ok = []
        for filename in filenames:
            try:
                with open(filename, "r", encoding='utf-8') as file_handle:
                    self.readfp(file_handle)
            except IOError:
                continue
            else:
                read_ok.append(filename)

        return read_ok

    def readfp(self, fp, filename=None):
        if isinstance(fp, io.TextIOWrapper):
            local_fp: io.TextIOWrapper = fp
        else:
            local_fp: Iterable[str] = fp
        stream = io.StringIO()

        try:
            stream.name = local_fp.name
        except AttributeError:
            pass

        stream.write('[' + self._default_section + ']\n')
        stream.write(local_fp.read())
        stream.seek(0, 0)

        return configparser.RawConfigParser.read_file(self, stream, source=filename)

    def write(self, fp, space_around_delimiters=True):
        # Write the items from the default section manually and then remove them
        # from the data. They'll be re-added later.
        default_section_items: List[Tuple[str, str]] = []
        try:
            default_section_items = self.items(self._default_section)
            self.remove_section(self._default_section)

            for (key, value) in default_section_items:
                fp.write(f"{key} = {value}\n")

            fp.write("\n")
        except configparser.NoSectionError:
            pass

        configparser.RawConfigParser.write(self, fp)

        self.add_section(self._default_section)
        for (key, value) in default_section_items:
            self.set(self._default_section, key, value)


class ConfigParser(configobj.ConfigObj):
    """Config file parser class to read and write config files"""
    space_around_delimiters = None
    _delimiters = "=:"

    def __init__(self, *args, delimiters='=:', space_around_delimiter=None, **kwargs):
        kwargs["infile"] = kwargs.pop('infile', args[0] if len(args) > 0 else None)

        # configobj.ConfigObj(self, *args, **kwargs)
        super().__init__(*args, **kwargs)
        self.space_around_delimiters = space_around_delimiter
        self._delimiters = delimiters

    def _write_line(self, indent_string, entry, this_entry, comment):
        """Write an individual line, for the write method"""
        # NOTE: the calls to self._quote here handles non-StringType values.
        if not self.unrepr:
            val = self._decode_element(self._quote(this_entry))
        else:
            val = repr(this_entry)
        if self.space_around_delimiters:
            delim = f" {self._delimiters[0]} "
        else:
            delim = self._delimiters[0]
        return f"{indent_string}{self._decode_element(self._quote(entry, multiline=False))}" \
               f"{self._a_to_u(delim)}{val}{self._decode_element(comment)}"

    def _unquote(self, value):
        """Disable unquoting of " chars"""
        return value

    def _quote(self, value, multiline=True):
        return value


if __name__ == '__main__':
    TESTFILE = '/etc/sysconfig/language'
    testfile_out = f'{TESTFILE}.out'
    c_old = SectionlessConfigParser(allow_no_value=True)
    c_old.read(TESTFILE)
    v_old = c_old.get(c_old.get_default_section(), 'ROOT_USES_LANG')
    print(f"v_old = {v_old}")
    c_old.set(c_old.get_default_section(), 'ROOT_USES_LANG', '"yes"')
    with open(testfile_out, 'w', encoding='utf-8') as test_fh:
        c_old.write(test_fh)
    print('now use ConfigParser instead of config')
    c = ConfigParser(infile=TESTFILE)
    v = c.get('ROOT_USES_LANG')
    print(f"v = {v}")
    c['ROOT_USES_LANG'] = '"yes"'
    # c.walk()
    c.write()
    # c.write(open(testfile_out, 'w'))

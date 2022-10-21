import configparser
import io
from typing import Iterable


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
        return self._default_section

    def set_default_section(self, section):
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
                with open(filename) as fp:
                    self.readfp(fp)
            except IOError:
                continue
            else:
                read_ok.append(filename)

        return read_ok

    def readfp(self, fp, filename=None, *args, **kwargs):
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
        try:
            default_section_items = self.items(self._default_section)
            self.remove_section(self._default_section)

            for (key, value) in default_section_items:
                fp.write("{0} = {1}\n".format(key, value))

            fp.write("\n")
        except configparser.NoSectionError:
            pass

        configparser.RawConfigParser.write(self, fp)

        self.add_section(self._default_section)
        for (key, value) in default_section_items:
            self.set(self._default_section, key, value)


if __name__ == '__main__':
    testfile = '/etc/sysconfig/language'
    c = SectionlessConfigParser(allow_no_value=True)
    c.read(testfile)
    v = c.get(c.get_default_section(), 'ROOT_USES_LANG')
    print(f"v = {v}")
    c.set(c.get_default_section(), 'ROOT_USES_LANG', '"yes"')
    c.write(open(testfile, 'w'))

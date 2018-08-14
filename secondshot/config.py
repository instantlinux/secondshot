"""config

Configuration-file parsing

created 11-aug-2018 by richb@instantlinux.net

license: gplv2
"""


class ReadConfig(object):
    def __init__(self, filename=None):
        self.multiple_allowed = ['backup', 'backup_script', 'exclude',
                                 'include', 'include_conf', 'interval',
                                 'retain']

    def rsnapshot_cfg(self, filename):
        """Parse the rsnapshot config file into a dictionary
        Keywords in this config file can have up to two parameters;
        for those which allow multiple statements of the same keyword,
        return a 2-level sub-dictionary or a single-level list

        Args:
            filename (str): name of config file
        Returns:
            dict:  parsed contents
        Raises:
            SyntaxError: if unexpected syntax
        """

        self.filename = filename
        contents = {}
        fp = open(filename, 'r')
        linenum = 1
        for line in fp:
            if '#' in line:
                line, comment = line.split('#', 1)
            tokens = line.strip().split(None, 2)
            if (len(tokens) == 0):
                continue
            elif (len(tokens) < 2):
                raise SyntaxError('file=%s at line %d\n%s' % (
                    filename, linenum, line))
            key = tokens[0]
            if (key in self.multiple_allowed):
                if (len(tokens) == 2):
                    if (key not in contents):
                        contents[key] = []
                    contents[key].append(tokens[1])
                else:
                    if (key not in contents):
                        contents[key] = {}
                    contents[key][tokens[1]] = tokens[2]
            elif (key not in contents):
                contents[key] = ' '.join(tokens[1:])
            else:
                raise SyntaxError('file=%s (%d): duplicate keyword %s' % (
                    filename, linenum, key))
            linenum += 1
        fp.close()
        return contents

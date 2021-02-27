#!/usr/bin/env python
# SPDX-License-Identifier: AGPL-3.0-or-later
# SPDX-FileCopyrightText: 2021 grammm GmbH

import sys, re
from typing import List, Tuple

CLUT = [  # color look-up table
    #    8-bit, RGB hex
    # Primary 3-bit (8 colors). Unique representation!
    ('00',  '000000', 'black'),
    ('01',  '800000', 'dark red'),
    ('02',  '008000', 'light green'),
    ('03',  '808000', 'brown'),
    ('04',  '000080', 'dark blue'),
    ('05',  '800080', 'dark magenta'),
    ('06',  '008080', 'dark cyan'),
    ('07',  'c0c0c0', 'light gray'),

    # Equivalent "bright" versions of original 8 colors.
    ('08',  '808080', 'dark gray'),
    ('09',  'ff0000', 'light red'),
    ('10',  '00ff00', 'dark green'),
    ('11',  'ffff00', 'yellow'),
    ('12',  '0000ff', 'light blue'),
    ('13',  'ff00ff', 'light magenta'),
    ('14',  '00ffff', 'light cyan'),
    ('15',  'ffffff', 'white'),

    # Strictly ascending.
    ('16',  '000000',  '000000'),
    ('17',  '00005f',  '00005f'),
    ('18',  '000087',  '000087'),
    ('19',  '0000af',  '0000af'),
    ('20',  '0000d7', '0000d7'),
    ('21',  '0000ff', '0000ff'),
    ('22',  '005f00', '005f00'),
    ('23',  '005f5f', '005f5f'),
    ('24',  '005f87', '005f87'),
    ('25',  '005faf', '005faf'),
    ('26',  '005fd7', '005fd7'),
    ('27',  '005fff', '005fff'),
    ('28',  '008700', '008700'),
    ('29',  '00875f', '00875f'),
    ('30',  '008787', '008787'),
    ('31',  '0087af', '0087af'),
    ('32',  '0087d7', '0087d7'),
    ('33',  '0087ff', '0087ff'),
    ('34',  '00af00', '00af00'),
    ('35',  '00af5f', '00af5f'),
    ('36',  '00af87', '00af87'),
    ('37',  '00afaf', '00afaf'),
    ('38',  '00afd7', '00afd7'),
    ('39',  '00afff', '00afff'),
    ('40',  '00d700', '00d700'),
    ('41',  '00d75f', '00d75f'),
    ('42',  '00d787', '00d787'),
    ('43',  '00d7af', '00d7af'),
    ('44',  '00d7d7', '00d7d7'),
    ('45',  '00d7ff', '00d7ff'),
    ('46',  '00ff00', '00ff00'),
    ('47',  '00ff5f', '00ff5f'),
    ('48',  '00ff87', '00ff87'),
    ('49',  '00ffaf', '00ffaf'),
    ('50',  '00ffd7', '00ffd7'),
    ('51',  '00ffff', '00ffff'),
    ('52',  '5f0000', '5f0000'),
    ('53',  '5f005f', '5f005f'),
    ('54',  '5f0087', '5f0087'),
    ('55',  '5f00af', '5f00af'),
    ('56',  '5f00d7', '5f00d7'),
    ('57',  '5f00ff', '5f00ff'),
    ('58',  '5f5f00', '5f5f00'),
    ('59',  '5f5f5f', '5f5f5f'),
    ('60',  '5f5f87', '5f5f87'),
    ('61',  '5f5faf', '5f5faf'),
    ('62',  '5f5fd7', '5f5fd7'),
    ('63',  '5f5fff', '5f5fff'),
    ('64',  '5f8700', '5f8700'),
    ('65',  '5f875f', '5f875f'),
    ('66',  '5f8787', '5f8787'),
    ('67',  '5f87af', '5f87af'),
    ('68',  '5f87d7', '5f87d7'),
    ('69',  '5f87ff', '5f87ff'),
    ('70',  '5faf00', '5faf00'),
    ('71',  '5faf5f', '5faf5f'),
    ('72',  '5faf87', '5faf87'),
    ('73',  '5fafaf', '5fafaf'),
    ('74',  '5fafd7', '5fafd7'),
    ('75',  '5fafff', '5fafff'),
    ('76',  '5fd700', '5fd700'),
    ('77',  '5fd75f', '5fd75f'),
    ('78',  '5fd787', '5fd787'),
    ('79',  '5fd7af', '5fd7af'),
    ('80',  '5fd7d7', '5fd7d7'),
    ('81',  '5fd7ff', '5fd7ff'),
    ('82',  '5fff00', '5fff00'),
    ('83',  '5fff5f', '5fff5f'),
    ('84',  '5fff87', '5fff87'),
    ('85',  '5fffaf', '5fffaf'),
    ('86',  '5fffd7', '5fffd7'),
    ('87',  '5fffff', '5fffff'),
    ('88',  '870000', '870000'),
    ('89',  '87005f', '87005f'),
    ('90',  '870087', '870087'),
    ('91',  '8700af', '8700af'),
    ('92',  '8700d7', '8700d7'),
    ('93',  '8700ff', '8700ff'),
    ('94',  '875f00', '875f00'),
    ('95',  '875f5f', '875f5f'),
    ('96',  '875f87', '875f87'),
    ('97',  '875faf', '875faf'),
    ('98',  '875fd7', '875fd7'),
    ('99',  '875fff', '875fff'),
    ('100', '878700', '878700'),
    ('101', '87875f', '87875f'),
    ('102', '878787', '878787'),
    ('103', '8787af', '8787af'),
    ('104', '8787d7', '8787d7'),
    ('105', '8787ff', '8787ff'),
    ('106', '87af00', '87af00'),
    ('107', '87af5f', '87af5f'),
    ('108', '87af87', '87af87'),
    ('109', '87afaf', '87afaf'),
    ('110', '87afd7', '87afd7'),
    ('111', '87afff', '87afff'),
    ('112', '87d700', '87d700'),
    ('113', '87d75f', '87d75f'),
    ('114', '87d787', '87d787'),
    ('115', '87d7af', '87d7af'),
    ('116', '87d7d7', '87d7d7'),
    ('117', '87d7ff', '87d7ff'),
    ('118', '87ff00', '87ff00'),
    ('119', '87ff5f', '87ff5f'),
    ('120', '87ff87', '87ff87'),
    ('121', '87ffaf', '87ffaf'),
    ('122', '87ffd7', '87ffd7'),
    ('123', '87ffff', '87ffff'),
    ('124', 'af0000', 'af0000'),
    ('125', 'af005f', 'af005f'),
    ('126', 'af0087', 'af0087'),
    ('127', 'af00af', 'af00af'),
    ('128', 'af00d7', 'af00d7'),
    ('129', 'af00ff', 'af00ff'),
    ('130', 'af5f00', 'af5f00'),
    ('131', 'af5f5f', 'af5f5f'),
    ('132', 'af5f87', 'af5f87'),
    ('133', 'af5faf', 'af5faf'),
    ('134', 'af5fd7', 'af5fd7'),
    ('135', 'af5fff', 'af5fff'),
    ('136', 'af8700', 'af8700'),
    ('137', 'af875f', 'af875f'),
    ('138', 'af8787', 'af8787'),
    ('139', 'af87af', 'af87af'),
    ('140', 'af87d7', 'af87d7'),
    ('141', 'af87ff', 'af87ff'),
    ('142', 'afaf00', 'afaf00'),
    ('143', 'afaf5f', 'afaf5f'),
    ('144', 'afaf87', 'afaf87'),
    ('145', 'afafaf', 'afafaf'),
    ('146', 'afafd7', 'afafd7'),
    ('147', 'afafff', 'afafff'),
    ('148', 'afd700', 'afd700'),
    ('149', 'afd75f', 'afd75f'),
    ('150', 'afd787', 'afd787'),
    ('151', 'afd7af', 'afd7af'),
    ('152', 'afd7d7', 'afd7d7'),
    ('153', 'afd7ff', 'afd7ff'),
    ('154', 'afff00', 'afff00'),
    ('155', 'afff5f', 'afff5f'),
    ('156', 'afff87', 'afff87'),
    ('157', 'afffaf', 'afffaf'),
    ('158', 'afffd7', 'afffd7'),
    ('159', 'afffff', 'afffff'),
    ('160', 'd70000', 'd70000'),
    ('161', 'd7005f', 'd7005f'),
    ('162', 'd70087', 'd70087'),
    ('163', 'd700af', 'd700af'),
    ('164', 'd700d7', 'd700d7'),
    ('165', 'd700ff', 'd700ff'),
    ('166', 'd75f00', 'd75f00'),
    ('167', 'd75f5f', 'd75f5f'),
    ('168', 'd75f87', 'd75f87'),
    ('169', 'd75faf', 'd75faf'),
    ('170', 'd75fd7', 'd75fd7'),
    ('171', 'd75fff', 'd75fff'),
    ('172', 'd78700', 'd78700'),
    ('173', 'd7875f', 'd7875f'),
    ('174', 'd78787', 'd78787'),
    ('175', 'd787af', 'd787af'),
    ('176', 'd787d7', 'd787d7'),
    ('177', 'd787ff', 'd787ff'),
    ('178', 'd7af00', 'd7af00'),
    ('179', 'd7af5f', 'd7af5f'),
    ('180', 'd7af87', 'd7af87'),
    ('181', 'd7afaf', 'd7afaf'),
    ('182', 'd7afd7', 'd7afd7'),
    ('183', 'd7afff', 'd7afff'),
    ('184', 'd7d700', 'd7d700'),
    ('185', 'd7d75f', 'd7d75f'),
    ('186', 'd7d787', 'd7d787'),
    ('187', 'd7d7af', 'd7d7af'),
    ('188', 'd7d7d7', 'd7d7d7'),
    ('189', 'd7d7ff', 'd7d7ff'),
    ('190', 'd7ff00', 'd7ff00'),
    ('191', 'd7ff5f', 'd7ff5f'),
    ('192', 'd7ff87', 'd7ff87'),
    ('193', 'd7ffaf', 'd7ffaf'),
    ('194', 'd7ffd7', 'd7ffd7'),
    ('195', 'd7ffff', 'd7ffff'),
    ('196', 'ff0000', 'ff0000'),
    ('197', 'ff005f', 'ff005f'),
    ('198', 'ff0087', 'ff0087'),
    ('199', 'ff00af', 'ff00af'),
    ('200', 'ff00d7', 'ff00d7'),
    ('201', 'ff00ff', 'ff00ff'),
    ('202', 'ff5f00', 'ff5f00'),
    ('203', 'ff5f5f', 'ff5f5f'),
    ('204', 'ff5f87', 'ff5f87'),
    ('205', 'ff5faf', 'ff5faf'),
    ('206', 'ff5fd7', 'ff5fd7'),
    ('207', 'ff5fff', 'ff5fff'),
    ('208', 'ff8700', 'ff8700'),
    ('209', 'ff875f', 'ff875f'),
    ('210', 'ff8787', 'ff8787'),
    ('211', 'ff87af', 'ff87af'),
    ('212', 'ff87d7', 'ff87d7'),
    ('213', 'ff87ff', 'ff87ff'),
    ('214', 'ffaf00', 'ffaf00'),
    ('215', 'ffaf5f', 'ffaf5f'),
    ('216', 'ffaf87', 'ffaf87'),
    ('217', 'ffafaf', 'ffafaf'),
    ('218', 'ffafd7', 'ffafd7'),
    ('219', 'ffafff', 'ffafff'),
    ('220', 'ffd700', 'ffd700'),
    ('221', 'ffd75f', 'ffd75f'),
    ('222', 'ffd787', 'ffd787'),
    ('223', 'ffd7af', 'ffd7af'),
    ('224', 'ffd7d7', 'ffd7d7'),
    ('225', 'ffd7ff', 'ffd7ff'),
    ('226', 'ffff00', 'ffff00'),
    ('227', 'ffff5f', 'ffff5f'),
    ('228', 'ffff87', 'ffff87'),
    ('229', 'ffffaf', 'ffffaf'),
    ('230', 'ffffd7', 'ffffd7'),
    ('231', 'ffffff', 'ffffff'),

    # Gray-scale range.
    ('232', '080808', '080808'),
    ('233', '121212', '121212'),
    ('234', '1c1c1c', '1c1c1c'),
    ('235', '262626', '262626'),
    ('236', '303030', '303030'),
    ('237', '3a3a3a', '3a3a3a'),
    ('238', '444444', '444444'),
    ('239', '4e4e4e', '4e4e4e'),
    ('240', '585858', '585858'),
    ('241', '626262', '626262'),
    ('242', '6c6c6c', '6c6c6c'),
    ('243', '767676', '767676'),
    ('244', '808080', '808080'),
    ('245', '8a8a8a', '8a8a8a'),
    ('246', '949494', '949494'),
    ('247', '9e9e9e', '9e9e9e'),
    ('248', 'a8a8a8', 'a8a8a8'),
    ('249', 'b2b2b2', 'b2b2b2'),
    ('250', 'bcbcbc', 'bcbcbc'),
    ('251', 'c6c6c6', 'c6c6c6'),
    ('252', 'd0d0d0', 'd0d0d0'),
    ('253', 'dadada', 'dadada'),
    ('254', 'e4e4e4', 'e4e4e4'),
    ('255', 'eeeeee', 'eeeeee'),
]

def _str2hex(hexstr):
    return int(hexstr, 16)

def _strip_hash(rgb):
    # Strip leading `#` if exists.
    if rgb.startswith('#'):
        rgb = rgb.lstrip('#')
    return rgb


def _create_dicts():
    clut_copy = [(o[0], o[1]) for o in CLUT]
    short2rgb_dict = dict(clut_copy)
    rgb2short_dict = {}
    for k, v in short2rgb_dict.items():
        rgb2short_dict[v] = k
    return rgb2short_dict, short2rgb_dict

def short2rgb(short):
    return SHORT2RGB_DICT[short]

def print_all(what: str = "all"):
    """ Print all 256 xterm color codes.
    """

    clut_copy: List[Tuple[str, str, str]]
    if what == 'short':
        clut_copy = [(o[0], o[1], o[2]) for o in CLUT if int(o[0]) < 16]
    elif what == 'long':
        clut_copy = [(o[0], o[1], o[2]) for o in CLUT if int(o[0]) > 15]
    else:
        clut_copy = [(o[0], o[1], o[2]) for o in CLUT]
    for short, rgb, name in clut_copy:
        sys.stdout.write('\033[48;5;%sm%s:%s' % (short, short, rgb))
        sys.stdout.write("\033[0m  ")
        sys.stdout.write('\033[38;5;%sm%s:%s' % (short, short, rgb))
        sys.stdout.write("\033[0m  ")
        sys.stdout.write('\033[38;5;%sm%s:%s' % (short, short, name))
        sys.stdout.write("\033[0m\n")
    print( "Printed all codes.")
    print( "You can translate a hex or 0-255 code by providing an argument.")

def rgb2short(rgb):
    """ Find the closest xterm-256 approximation to the given RGB value.
    @param rgb: Hex code representing an RGB value, eg, 'abcdef'
    @returns: String between 0 and 255, compatible with xterm.
    >>> rgb2short('123456')
    ('23', '005f5f')
    >>> rgb2short('ffffff')
    ('231', 'ffffff')
    >>> rgb2short('0DADD6') # vimeo logo
    ('38', '00afd7')
    """
    rgb = _strip_hash(rgb)
    incs = (0x00, 0x5f, 0x87, 0xaf, 0xd7, 0xff)
    # Break 6-char RGB code into 3 integer vals.
    parts = [ int(h, 16) for h in re.split(r'(..)(..)(..)', rgb)[1:4] ]
    res = []
    for part in parts:
        i = 0
        while i < len(incs)-1:
            s, b = incs[i], incs[i+1]  # smaller, bigger
            if s <= part <= b:
                s1 = abs(s - part)
                b1 = abs(b - part)
                if s1 < b1: closest = s
                else: closest = b
                res.append(closest)
                break
            i += 1
    #print '***', res
    res = ''.join([ ('%02.x' % i) for i in res ])
    equiv = RGB2SHORT_DICT[ res ]
    #print '***', res, equiv
    return equiv, res

RGB2SHORT_DICT, SHORT2RGB_DICT = _create_dicts()

#---------------------------------------------------------------------

if __name__ == '__main__' or __name__ == 'color':
    import doctest
    doctest.testmod()
    if len(sys.argv) in [1]:
        print_all()
        raise SystemExit
    arg = sys.argv[1]
    if type(arg) is str and not arg.isnumeric():
        print_all(arg)
        raise SystemExit
    if len(arg) < 4 and int(arg) < 256:
        rgb = short2rgb(arg)
        sys.stdout.write('xterm color \033[38;5;%sm%s\033[0m -> RGB exact \033[38;5;%sm%s\033[0m' % (arg, arg, arg, rgb))
        sys.stdout.write("\033[0m\n")
    else:
        short, rgb = rgb2short(arg)
        sys.stdout.write('RGB %s -> xterm color approx \033[38;5;%sm%s (%s)' % (arg, short, short, rgb))
        sys.stdout.write("\033[0m\n")
#
#  Copyright (c) 2020 by grammm GmbH.
#

import ipaddress
from collections import namedtuple
from os import listdir, remove, access, R_OK, W_OK
from os.path import isfile, join, exists, dirname
from typing import Dict, List

import netifaces
import psutil
import re
from psutil._common import snicstats, snicaddr


# _PRODUCTIVE: bool = False
_PRODUCTIVE: bool = True
path_prefix: str = "/"

# ifcfginfo = namedtuple('ifcfginfo', ['bootproto', 'ipaddr', 'netmask', 'gateway', 'network', 'startmode',
#                                      'usercontrol', 'firewall'])
ifcfginfo = namedtuple('ifcfginfo', ['bootproto', 'ipaddr', 'netmask', 'gateway'])
ifcfg_path: str = f'{path_prefix}etc/sysconfig/network/'

dnsinfo = namedtuple('dnsinfo', ['auto', 'primary', 'secondary', 'hostname', 'search'])
resolv_path: str = f'{path_prefix}etc/resolv.conf'
hostname_path: str = f'{path_prefix}etc/hostname'
config_path: str = f'{path_prefix}etc/sysconfig/network/config'


def _init():
    global path_prefix, ifcfg_path, resolv_path, hostname_path, config_path
    if _PRODUCTIVE:
        path_prefix = "/"
    else:
        path_prefix = "/tmp/"
    ifcfg_path = f'{path_prefix}etc/sysconfig/network/'
    resolv_path = f'{path_prefix}etc/resolv.conf'
    hostname_path = f'{path_prefix}etc/hostname'
    config_path = f'{path_prefix}etc/sysconfig/network/config'


class DeviceInfo(object):
    """
    Holds all relevant device information.
    """
    dhcp: str = ""
    ipaddr: str = ""
    netmask: str = ""
    gateway: str = ""
    ext_stats: Dict[str, str] = {}

    reserved_keys: List[str] = ['bootproto', 'startmode', 'ipaddr', 'netmask', 'gateway']

    def __init__(self, devicename: str):
        _init()
        self.name = devicename
        self.autofill()

    def get_if_stats(self) -> snicstats:
        """
        Returns a stat object of the NIC.

        :return: The snicstat object.
        """
        if_stats = psutil.net_if_stats()
        if self.name == 'None':
            return snicstats(None, None, None, None)
        return if_stats.get(self.name)

    def get_if_addr(self) -> snicaddr:
        """
        Returns a addr object of NICs.

        :return: The snicaddr object.
        """
        if_addrs = psutil.net_if_addrs()
        if self.name == 'None':
            return snicaddr(None, None, None, None, None)
        addr: snicaddr
        for addr in if_addrs.get(self.name):
            if str(addr.family) == 'AddressFamily.AF_INET':
                return addr
        return snicaddr(None, None, None, None, None)

    def get_ifcfg_info(self) -> ifcfginfo:
        """
        Returns an info object containing information of the ifcfg* files in /etc/sysconfig/network/

        :return: The ifcfginfo object.
        """
        global ifcfg_path
        props = list(ifcfginfo._fields)
        confs: Dict[str, str] = {}
        # props = [prop for prop in dir(ifcfginfo) if not prop.startswith('_')]
        if exists(f"{ifcfg_path}/routes") and access(f"{ifcfg_path}/routes", R_OK):
            with open(f"{ifcfg_path}/routes", 'r') as f:
                line = f.readline()
                if line.startswith('default '):
                    confs['gateway'] = line.split('default ')[1].strip().split(' ')[0]
                    self.gateway = confs.get('gateway')
        else:
            if len(netifaces.gateways()['default']) > 0:
                confs['gateway'] = netifaces.gateways()['default'][netifaces.AF_INET][0]
            else:
                confs['gateway'] = ''
            self.gateway = confs.get('gateway')
        if exists(f"{ifcfg_path}/ifcfg-{self.name}") and access(f"{ifcfg_path}/ifcfg-{self.name}", R_OK):
            with open(f"{ifcfg_path}/ifcfg-{self.name}", "r") as f:
                for line in f.readlines():
                    if line.find('=') > 0:
                        k, v = line.split('=')
                        if k.lower() in props:
                            confs[k.lower()] = v.strip()
                        else:
                            self.ext_stats[k.lower()] = v.strip()
        else:
            for p in props:
                confs[p] = confs.get(p, '')
        return ifcfginfo(confs.get('bootproto'), confs.get('ipaddr'), confs.get('netmask'), confs.get('gateway'))

    def autofill(self):
        """
        Fills all properties by trying to set automatically.
        """
        ic = self.get_ifcfg_info()
        # s = self.get_if_stats()
        a = self.get_if_addr()
        self.dhcp = ic.bootproto if ic.bootproto is not None else ''
        self.ipaddr = a.address if a.address is not None else ''
        self.netmask = a.netmask if a.netmask is not None else ''

    def write_config(self, filename: str = None) -> bool:
        """
        Writes all properties to config file, usually /etc/sysconfig/network/ifcfg-*

        :param filename: Filename to which the information should be written.
        :return: True is file could be written, False otherwise.
        """
        rv: bool = True
        if filename is None:
            filename = f"{ifcfg_path}/ifcfg-{self.name}"
        if not self.gateway == "":
            if not exists(f"{ifcfg_path}/routes"):
                if access(f"{ifcfg_path}/", W_OK):
                    with open(f"{ifcfg_path}/routes", 'a') as f:
                        f.close()
                else:
                    rv = False
            if access(f"{ifcfg_path}/routes", W_OK):
                with open(f"{ifcfg_path}/routes", 'w') as f:
                    f.write(f"default {self.gateway} - -\n")
            else:
                rv = False
        if not exists(filename):
            with open(filename, 'a') as f:
                f.close()
        if access(filename, W_OK):
            with open(filename, 'w') as f:
                if self.dhcp.lower().find('dhcp') >= 0:
                    proto = "'dhcp'"
                    f.write(f"BOOTPROTO={self.dhcp if self.dhcp is not None else proto}\n")
                    f.write("STARTMODE='auto'\n")
                elif self.dhcp.lower().find('static') >= 0:
                    proto = "static"
                    f.write(f"BOOTPROTO={self.dhcp if self.dhcp is not None else proto}\n")
                    f.write("STARTMODE=nfsroot\n")
                    ip = self.ipaddr if self.ipaddr.find('/') < 0 else self.ipaddr.split('/')[0].strip()
                    nm = ''
                    if self.netmask is not None:
                        nm = f"/{sum(bin(int(x)).count('1') for x in self.netmask.split('.'))}"
                    f.write(f"IPADDR={ip}{nm}\n")
                    f.write(f"NETMASK={self.netmask}\n")
                    ip4 = ipaddress.IPv4Interface(f'{ip}{nm}')
                    f.write(f"NETWORK={ip4.network.network_address}\n")
                for k in self.ext_stats.keys():
                    if k not in self.reserved_keys:
                        f.write(f"{k.upper()}={self.ext_stats[k]}\n")
        else:
            rv = False
        return rv


class DNSInfo(object):
    """
    Holds all relevant information about DNS configuration.
    """
    auto: bool = True
    primary: str = ""
    secondary: str = ""
    hostname: str = ""
    search: str = ""
    ext_stats: Dict[str, str] = {}

    reserved_keys: List[str] = ['nameserver', 'search']

    def __init__(self):
        _init()
        self.autofill()

    def get_resolv_conf(self) -> dnsinfo:
        """
        Returns an info object containing information of the /etc/resolv.conf

        :return: The dnsinfo object.
        """
        global resolv_path, hostname_path
        props = list(dnsinfo._fields)
        confs: Dict[str, str] = {'commentlines': '# File generated automatically by grammm console user interface.\n'}
        confs['commentlines'] = ''.join([confs.get('commentlines'), '# DO NOT EDIT BY HAND!!!\n', '\n'])
        # props = [prop for prop in dir(ifcfginfo) if not prop.startswith('_')]
        if exists(config_path) and access(config_path, R_OK):
            with open(config_path, 'r') as f:
                for line in f.readlines():
                    grep_auto = re.findall('NETCONFIG_DNS_POLICY', line)
                    if len(grep_auto) > 0:
                        v = line.split('=')[1].strip()
                        splitchar: str
                        if v.find('"') >= 0:
                            splitchar = '"'
                        elif v.find("'") >= 0:
                            splitchar = "'"
                        else:
                            splitchar = ''
                        if not splitchar == '':
                            v = v.split(splitchar)[1]
                        if v == 'auto':
                            confs['auto'] = 'auto'
                        else:
                            confs['auto'] = ''
        if exists(resolv_path) and access(resolv_path, R_OK):
            with open(resolv_path, 'r') as f:
                count: int = 0
                for line in f.readlines():
                    if line.startswith('#'):
                        confs['commentlines'] = ''.join([confs.get('commentlines'), line])
                    elif line.startswith('search '):
                        confs['search'] = line.split('search ')[1].strip()
                    elif line.startswith('nameserver'):
                        count += 1
                        confs[f"nameserver{count}"] = line.split('nameserver ')[1].strip()
                    elif line.find('=') > 0:
                        k, v = line.split('=')
                        if k.lower() in props:
                            confs[k.lower()] = v.strip()
                        else:
                            self.ext_stats[k.lower()] = v.strip()
                self.ext_stats['commentlines'] = confs.get('commentlines')
        else:
            confs['search'] = ""
            confs['nameserver1'] = ""
            confs['nameserver2'] = ""
        if exists(hostname_path) and access(hostname_path, R_OK):
            with open(hostname_path, "r") as f:
                line = f.readline()
                confs["hostname"] = line.strip()
        return dnsinfo(confs.get('auto'), confs.get('nameserver1'), confs.get('nameserver2'), confs.get('hostname'),
                       confs.get('search'))

    def autofill(self):
        """
        Fills all properties by trying to set automatically.
        """
        i = self.get_resolv_conf()
        self.auto = i.auto == 'auto' if i.auto is not None else ''
        self.primary = i.primary if i.primary is not None else ''
        self.secondary = i.secondary if i.secondary is not None else ''
        self.hostname = i.hostname if i.hostname is not None else ''
        self.search = i.search if i.search is not None else ''

    def write_config(self, resolv_conf: str = None, hostname_conf: str = None) -> bool:
        """
        Writes all properties to config file, usually /etc/resolv.conf, /etc/hostname and /etc/sysconfig/network/config.

        :param resolv_conf: Filename to which the information should be written.
        :param hostname_conf: Filename to which the information should be written.
        :return: True is file could be written, False otherwise.
        """
        global config_path, hostname_path, resolv_path
        rv: bool = True
        if not exists(config_path):
            if access(dirname(config_path), W_OK):
                with open(config_path, 'a') as f:
                    f.close()
        if access(config_path, W_OK):
            with open(config_path, 'r') as f:
                memcopy: List[str] = f.readlines()
                f.close()
            with open(config_path, 'w') as f:
                for i, line in enumerate(memcopy):
                    grep_auto = re.findall('NETCONFIG_DNS_POLICY', line)
                    if len(grep_auto) > 0:
                        memcopy[i] = f'NETCONFIG_DNS_POLICY="{"auto" if self.auto else ""}"\n'
                f.write(''.join(memcopy))
        if hostname_conf is None:
            hostname_conf = hostname_path
        if not self.hostname == "":
            if not exists(hostname_conf):
                with open(hostname_conf, 'a') as f:
                    f.close()
            if access(hostname_conf, W_OK):
                with open(hostname_conf, 'w') as f:
                    f.writelines(f"{self.hostname}\n")
            else:
                rv = False
        if resolv_conf is None:
            resolv_conf = resolv_path
        if not exists(resolv_conf):
            with open(resolv_conf, 'a') as f:
                f.close()
        if access(resolv_conf, W_OK):
            with open(resolv_conf, 'w') as f:
                if not self.search == "":
                    f.write(f"search {self.search}\n")
                if not self.primary == "":
                    f.write(f"nameserver {self.primary}\n")
                if not self.secondary == "":
                    f.write(f"nameserver {self.secondary}\n")
        else:
            rv = False
        return rv


if __name__ == '__main__':
    _PRODUCTIVE = False
    _init()
    if exists(f"{ifcfg_path}/ifcfg-ethTEST"):
        remove(f"{ifcfg_path}/ifcfg-ethTEST")
    devices = [str(f).split('-')[1] for f in listdir(ifcfg_path)
               if isfile(join(ifcfg_path, f)) and str(f).startswith('ifcfg-')]
    for d in devices:
        test = DeviceInfo(d)
        s = test.get_if_stats()
        i = test.get_ifcfg_info()
        print(f"Device {test.name} has stats ({s}) and info ({i})")

    test = DeviceInfo('lo')
    test.name = 'ethTEST'
    test.dhcp = 'static'
    test.ipaddr = '193.99.72.111'
    test.ext_stats['bla'] = 'blubb'
    print(f"and writing returned {test.write_config()}!")

    dns = DNSInfo()
    print(f"{list(dns.get_resolv_conf())}")
    # dns.auto = False
    dns.auto = True
    print(f"{list(dns.get_resolv_conf())}")
    print(f"and writing returned {dns.write_config()}!")

#!/bin/bash

watch -d "ls -l /etc/resolv.conf /run/netconfig/resolv.conf /etc/hostname /etc/sysconfig/network/config /etc/hosts && grep NETCONFIG_DNS_POLICY /etc/sysconfig/network/config && cat /etc/hostname && cat /etc/resolv.conf && grep -v -e '^#' -e '^$' /etc/hosts"



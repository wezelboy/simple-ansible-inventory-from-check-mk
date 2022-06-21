#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# (c) 2015, Ravi Bhure <ravibhure@gmail.com>
#
# This file is not a part of Ansible,but is forked from a file that is.
# As such, it falls under the GNU General Public license of the parent file.
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

######################################################################
# Changes by Patrick Gavin
#
# 10/25/2017
# Added hostgroups option to allow ansible inventory grouping based on
# check_mk hostgroups.
#
# 6/3/2022
# Adding socketurl argument to query livestatus on remote servers
# and maybe get rid of the .ini file.
#
# 6/13/2022
# Added basic SSL support- cert checking is off. Nothing fancypants.
#
# 6/20/2022
# Switched to socketurls nargs argument to allow multiple queries to
# livestatus servers and aggregating the results.
#

"""
Check_MK / OMD Server external inventory script.
================================================

Returns hosts and hostgroups from Check_MK / OMD Server using LQL to livestatus socket.

Tested with Check_MK/Nagios/Icinga Server with OMD.

For more details, see: https://mathias-kettner.de/checkmk_livestatus.html
"""

import os,sys
import ConfigParser
import socket
import ssl
import argparse

try:
    import json
except:
    import simplejson as json

def do_connect(socketurl):
    """ Initialize socket connection """

    url = socketurl
    parts = url.split(":")
    if parts[0] == "unix":
        if len(parts) != 2:
            raise Exception("Invalid livestatus unix url: %s. "
                 "Correct example is 'unix:/var/run/nagios/rw/live'" % url)
        clearSocket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        target = parts[1]

    elif parts[0] == "tcp":
        try:
            host = parts[1]
            port = int(parts[2])
        except:
            raise Exception("Invalid livestatus tcp url '%s'. "
                 "Correct example is 'tcp:somehost:6557'" % url)
        clearSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target = (host, port)
    else:
        raise Exception("Invalid livestatus url '%s'. "
              "Must begin with 'tcp:' or 'unix:'" % url)

    # If using ssl, wrap the clear socket with an ssl socket
    if (len(parts) > 3) and (parts[3] == "ssl"):
        context = ssl.create_default_context()
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        sslSocket = context.wrap_socket(clearSocket)
        useSocket = sslSocket
    else:
        useSocket = clearSocket
      
    # Create connection
    try:
        useSocket.connect(target)
    except Exception, e:
        print >>sys.stderr, 'Error while connecting to socket on %s - %s' % (target,e)
        sys.exit(1)

    # Return the connected socket
    return useSocket

def inventory_data(socketurl, query):
    """ Generate inventory data """

    s = do_connect(socketurl)
    s.send(query)
    answer = ''

    read_buff = s.recv(4096)
    while (read_buff != ""):
        answer += read_buff
        read_buff = s.recv(4096)

    s.close()

    table = answer.split('\n')[:-1]

    return table

def print_table(table, table_name='hosts'):
    print json.dumps({table_name: table}, sort_keys=True, indent=2)

def print_list(socketurls, fields):
    """ Returns all host """

    master_table = []
    for socketurl in socketurls:
        query = "GET hosts \nColumns: %s \n\n" % fields
        master_table += inventory_data(socketurl, query)

    print_table(master_table)

def print_host(socketurls, host, fields):
    """ Returns a host """
  
    master_table = []
    for socketurl in socketurls:
        query = "GET hosts \nColumns: %s \nFilter: host_name = %s\n\n" % (fields, host)
        master_table += inventory_data(socketurl, query)

    print_table(master_table)

def print_group(socketurls, hostgroup, fields, extra_filter):
    """ Returns a list of all hosts in given hostgroup """

    master_table = []
    for socketurl in socketurls:
        query = "GET hosts \nColumns: %s \nFilter: host_groups >= %s\n%s\n\n" % (fields, hostgroup, extra_filter)
        master_table += inventory_data(socketurl, query)

    print_table(master_table)

def print_all_hostgroups(socketurls, fields, extra_filter):
    """ Prints a list of all defined hostgroups and the hosts in them"""
    collection = {}
    for socketurl in socketurls:
        query = "GET hostgroups \nColumns: name \n\n"
        hostgroups = inventory_data(socketurl, query)
        for hostgroup in hostgroups:
            query = "GET hosts \nColumns: %s \nFilter: host_groups >= %s\n%s\n\n" % (fields, hostgroup, extra_filter)
            if hostgroup in collection:
                collection[hostgroup] += (inventory_data(socketurl, query))
            else:
                collection[hostgroup] = (inventory_data(socketurl, query))
          
    print json.dumps(collection, sort_keys=True, indent=2)



def get_args(args_list):
    parser = argparse.ArgumentParser(
        description='ansible inventory script reading from check_mk / omd monitoring')
    mutex_group = parser.add_mutually_exclusive_group(required=True)
    help_list = 'list all hosts from check_mk / omd server'
    mutex_group.add_argument('--list', action='store_true', help=help_list)
    mutex_group.add_argument('--host', help='display variables for a host')
    help_hostgroup = 'display variables for a hostgroup'
    mutex_group.add_argument('--hostgroup', help=help_hostgroup)
    mutex_group.add_argument('--hostgroups', action='store_true', help='List all hostgroups and the hosts in them')
    parser.add_argument('--fields', default='host_name', help='Space delimited list of fields to return')
    parser.add_argument('--filtergroup', help='Additional group filter like dev_servers or prd_servers')
    parser.add_argument('socketurls', nargs='+', help='socket URLs i.e. tcp:mk.foobar.com:6557 add :ssl for ssl negotiation- i.e. tcp:mk.foobar.com:6557:ssl')
    return parser.parse_args(args_list)


def main(args_list):
    args = get_args(args_list)
    if args.filtergroup:
        add_filter = "Filter: host_groups >= %s\n" % args.filtergroup
    else:
        add_filter = ''
    if args.list:
        print_list(args.socketurls, args.fields)
    if args.host:
        print_host(args.socketurls, args.host, args.fields)
    if args.hostgroup:
        print_group(args.socketurls, args.hostgroup, args.fields, add_filter)
    if args.hostgroups:
        print_all_hostgroups(args.socketurls, args.fields, add_filter)

if __name__ == '__main__':
    main(sys.argv[1:])


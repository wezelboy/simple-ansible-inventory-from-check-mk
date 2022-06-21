# simple-ansible-inventory-from-check-mk
Provides simple dynamic inventory host info from check-mk to ansible. It also supports multisite and ssl.

mk-inv.py is based on omd.py by Ravi Bhure

Usage: mk-inv.py [-h]
                 (--list | --host HOST | --hostgroup HOSTGROUP | --hostgroups)
                 [--fields FIELDS] [--filtergroup FILTERGROUP]
                 socketurls [socketurls ...]
                 
Example: mk-inv.py --hostgroups tcp:local-server.example.com:6557 tcp:remote-server.example.com:6557:ssl

This will provide a json dump of the members of all hostgroups monitored by local-server.example.com
and remote-server.example.com. It will connect to the remote server via ssl.

I use the --hostgroups option exclusively to separate different servers into different groups in my
ansible playbooks.

Note: I may change the usage in the future- tacking ssl on the end of the socketurl isn't as elegant
as having ssl be a socket type

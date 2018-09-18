#!/usr/bin/env python

#
# test_pim.py
#
# Copyright (c) 2018 Cumulus Networks, Inc.
#                    Donald Sharp
#
# Permission to use, copy, modify, and/or distribute this software
# for any purpose with or without fee is hereby granted, provided
# that the above copyright notice and this permission notice appear
# in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND Cumulus Networks DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL NETDEF BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY
# DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
# WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS
# ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.
#

"""
test_pim.py: Test pim
"""

import os
import sys
import pytest

CWD = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(CWD, '../'))

# pylint: disable=C0413
from lib import topotest
from lib.topogen import Topogen, TopoRouter, get_topogen
from lib.topolog import logger

from mininet.topo import Topo

from time import sleep

pim_avail = True

class PIMTopo(Topo):
    def build(self, *_args, **_opts):
        "Build function"
        tgen = get_topogen(self)

        for routern in range(1, 3):
            tgen.add_router('r{}'.format(routern))

        # r1 <- sw1 -> r2
        sw = tgen.add_switch('sw1')
        sw.add_link(tgen.gears['r1'])
        sw.add_link(tgen.gears['r2'])


def setup_module(mod):
    global pim_avail
    "Sets up the pytest environment"
    tgen = Topogen(PIMTopo, mod.__name__)
    tgen.start_topology()

    # For all registered routers, load the zebra configuration file
    for rname, router in tgen.routers().iteritems():
        router.load_config(
            TopoRouter.RD_ZEBRA,
            os.path.join(CWD, '{}/zebra.conf'.format(rname))
        )
        router.load_config(
            TopoRouter.RD_PIM,
            os.path.join(CWD, '{}/pimd.conf'.format(rname))
        )

    # After loading the configurations, this function loads configured daemons.
    tgen.start_router()
    for rname, router in tgen.routers().iteritems():
        router.run("vtysh -f {}".format(os.path.join(CWD, '{}/frr.conf'.format(rname))))

    # We need to figure out if this is version 2 of FRR that
    # does not have json commands yet
    # I really don't care about testing version 2 of FRR against
    # basic pim functionality
    r1 = tgen.gears['r1']
    ver2_test = r1.vtysh_cmd("show ip pim upstream json")
    if "Unknown" in ver2_test:
        logger.info("We are running against a version 2 of FRR, we will skip tests")
        pim_avail = False

    pim_test = r1.run("cat /proc/net/ip_mr_vif")
    if "No such file or directory" in pim_test:
        logger.info("We are running against a kernel without pim installed, we will skip tetst")
        pim_avail = False

    #tgen.mininet_cli()

def teardown_module(mod):
    "Teardown the pytest environment"
    tgen = get_topogen()

    # This function tears down the whole topology.
    tgen.stop_topology()


def test_pim_send_mcast_stream():
    logger.info("Establish a Mcast stream from r2->r1 and then ensure S,G created")

    if pim_avail == False:
        logger.info("Skipping test.... PIM is not available")
        return

    tgen = get_topogen()

    r2 = tgen.gears['r2']
    r1 = tgen.gears['r1']

    # Let's establish a S,G stream from r2 -> r1
    CWD = os.path.dirname(os.path.realpath(__file__))
    out2 = r2.run("{}/mcast-tx.py --ttl 5 --count 5 --interval 10 229.1.1.1 r2-eth0 > /tmp/bar".format(CWD))

    sleep(2)
    # Let's see that it shows up and we have established some basic state
    out1 = r1.vtysh_cmd("show ip pim upstream json", isjson=True)

    sg = out1['229.1.1.1']['10.0.20.2']
    assert sg['firstHopRouter'] == 1
    assert sg['joinState']  == "NotJoined"
    assert sg['regState'] == "RegPrune"
    assert sg['inboundInterface'] == "r1-eth0"
    #tgen.mininet_cli()


def test_pim_igmp_report():
    logger.info("Send a igmp report from r2-r1 and ensure *,G created")

    if pim_avail == False:
        logger.info("Skipping test..... PIM is not available")
        return

    tgen = get_topogen()

    r2 = tgen.gears['r2']
    r1 = tgen.gears['r1']

    # Let's send a igmp report from r2->r1
    CWD = os.path.dirname(os.path.realpath(__file__))
    out2 = r2.run("{}/mcast-rx.py 229.1.1.2 r2-eth0 &".format(CWD))

    sleep(2)
    out1 = r1.vtysh_cmd("show ip pim upstream json", isjson=True)
    starg = out1['229.1.1.2']['*']
    assert starg['sourceIgmp'] == 1
    assert starg['joinState'] == "Joined"
    assert starg['regState'] == "RegNoInfo"
    assert starg['sptBit'] == 0
    #tgen.mininet_cli()


def test_memory_leak():
    "Run the memory leak test and report results."
    tgen = get_topogen()
    if not tgen.is_memleak_enabled():
        pytest.skip('Memory leak test/report is disabled')

    tgen.report_memory_leaks()


if __name__ == '__main__':
    args = ["-s"] + sys.argv[1:]
    sys.exit(pytest.main(args))

#!/usr/bin/env python

#
# test_ospf_sr_topo1.py
# Part of NetDEF Topology Tests
#
# Copyright (c) 2017 by
# Network Device Education Foundation, Inc. ("NetDEF")
#
# Permission to use, copy, modify, and/or distribute this software
# for any purpose with or without fee is hereby granted, provided
# that the above copyright notice and this permission notice appear
# in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND NETDEF DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL NETDEF BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY
# DAMAGES WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS,
# WHETHER IN AN ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS
# ACTION, ARISING OUT OF OR IN CONNECTION WITH THE USE OR PERFORMANCE
# OF THIS SOFTWARE.
#

"""
test_ospf_sr_topo1.py: Test the FRR/Quagga OSPF routing daemon
with Segment Routing.
"""

import os
import re
import sys
from functools import partial
import pytest

# Save the Current Working Directory to find configuration files.
CWD = os.path.dirname(os.path.realpath(__file__))
sys.path.append(os.path.join(CWD, '../'))

# pylint: disable=C0413
# Import topogen and topotest helpers
from lib import topotest
from lib.topogen import Topogen, TopoRouter, get_topogen
from lib.topolog import logger

# Required to instantiate the topology builder class.
from mininet.topo import Topo

import shutil

class OspfSrTopo(Topo):
    "Test topology builder"
    def build(self, *_args, **_opts):
        "Build function"
        tgen = get_topogen(self)

        # Check for mpls
        if tgen.hasmpls != True:
            logger.info('MPLS not available, tests will be skipped')
            return

        # Create 4 routers
        for routern in range(1, 5):
            tgen.add_router('r{}'.format(routern))

        # Interconect router 1 and 2
        switch = tgen.add_switch('s1')
        switch.add_link(tgen.gears['r1'])
        switch.add_link(tgen.gears['r2'])

        # Interconect router 3 and 2
        switch = tgen.add_switch('s2')
        switch.add_link(tgen.gears['r3'])
        switch.add_link(tgen.gears['r2'])

        # Interconect router 4 and 2
        switch = tgen.add_switch('s3')
        switch.add_link(tgen.gears['r4'])
        switch.add_link(tgen.gears['r2'])

def setup_module(mod):
    "Sets up the pytest environment"
    tgen = Topogen(OspfSrTopo, mod.__name__)
    tgen.start_topology()

    router_list = tgen.routers()

    for rname, router in router_list.iteritems():
        router.load_config(
            TopoRouter.RD_ZEBRA,
            os.path.join(CWD, '{}/zebra.conf'.format(rname))
        )
        router.load_config(
            TopoRouter.RD_OSPF,
            os.path.join(CWD, '{}/ospfd.conf'.format(rname))
        )

    # Initialize all routers.
    tgen.start_router()

    # Check version
    for router in router_list.values():
        if router.has_version('<', '4'):
            tgen.set_error('unsupported version')

def teardown_module(mod):
    "Teardown the pytest environment"
    tgen = get_topogen()
    tgen.stop_topology()

# Shared test function to validate expected output.
def compare_ospf_srdb(rname, expected):
    """
    Calls 'show ip ospf database segment-routing json' for router `rname`
    and compare the obtained result with the expected output.
    """
    tgen = get_topogen()
    current = tgen.gears[rname].vtysh_cmd('show ip ospf database segment-routing json')
    return topotest.difflines(current, expected,
                              title1="Current output",
                              title2="Expected output")

def compare_mpls_table(rname, expected):
    """
    Calls 'show mpls table json' for router `rname` and compare the obtained
    result with the expected output.
    """
    tgen = get_topogen()
    current = tgen.gears[rname].vtysh_cmd('show mpls table json')
    return topotest.difflines(current, expected,
                              title1="Current output",
                              title2="Expected output")

def test_ospf_sr():
    "Test OSPF daemon Segment Routing"
    tgen = get_topogen()
    if tgen.routers_have_failure():
        pytest.skip(tgen.errors)

    for rnum in range(1, 5):
        router = 'r{}'.format(rnum)

        # Check that Segment Routing is available
        output = tgen.gears[router].vtysh_cmd("show ip ospf database segment-routing")
        if output.find("Unknown") != -1:
            pytest.skip('Segment Routing is not available')

        logger.info('Checking OSPF Segment Routing database on router "%s"',
                    router)

        # Load expected results from the command
        reffile = os.path.join(CWD, '{}/ospf_srdb.json'.format(router))
        expected = open(reffile).read()

        # Run test function until we get an result. Wait at most 60 seconds.
        test_func = partial(compare_ospf_srdb, router, expected)
        result, diff = topotest.run_and_expect(test_func, '',
                                               count=25, wait=3)
        assert result, 'OSPF did not start Segment Routing on {}:\n{}'.format(router, diff)

def test_ospf_kernel_route():
    "Test OSPF Segment Routing MPLS route installation"
    tgen = get_topogen()
    if tgen.routers_have_failure():
        pytest.skip(tgen.errors)

    for rnum in range(1, 5):
        router = 'r{}'.format(rnum)

        # Check that Segment Routing is available
        output = tgen.gears[router].vtysh_cmd("show ip ospf database segment-routing")
        if output.find("Unknown") != -1:
            pytest.skip('Segment Routing is not available')

        logger.info('Checking OSPF SR MPLS table in "%s"', router)

        # Load expected results from the command
        reffile = os.path.join(CWD, '{}/zebra_mpls.json'.format(router))
        expected = open(reffile).read()

        # Run test function until we get an result. Wait at most 60 seconds.
        test_func = partial(compare_mpls_table, router, expected)
        result, diff = topotest.run_and_expect(test_func, '',
                                               count=25, wait=3)
        assert result, 'OSPF did not properly instal MPLS table on {}:\n{}'.format(router, diff)

def test_memory_leak():
    "Run the memory leak test and report results."
    tgen = get_topogen()
    if not tgen.is_memleak_enabled():
        pytest.skip('Memory leak test/report is disabled')

    tgen.report_memory_leaks()

if __name__ == '__main__':
    args = ["-s"] + sys.argv[1:]
    sys.exit(pytest.main(args))
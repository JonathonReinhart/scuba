from __future__ import print_function

from nose.tools import *
from unittest import TestCase

import logging

import scuba.etcfiles

class TestEtcfiles(TestCase):

    def test_passwd_entry(self):
        '''passwd_entry returns a valid /etc/passwd entry'''
        ret = scuba.etcfiles.passwd_entry(
            username = 'nobody',
            password = 'x',
            uid = 99,
            gid = 99,
            gecos = 'Nobody',
            homedir = '/',
            shell = '/sbin/nologin')

        assert_equal('nobody:x:99:99:Nobody:/:/sbin/nologin', ret)

    def test_group_entry(self):
        '''group_entry returns a valid /etc/group entry'''
        ret = scuba.etcfiles.group_entry(
            groupname = 'nobody',
            password = 'x',
            gid = 99,
            users=['nope', 'uhuh', 'neep'])

        assert_equal('nobody:x:99:nope,uhuh,neep', ret)

    def test_shadow_entry(self):
        '''shadow_entry returns a valid /etc/shadow entry'''
        ret = scuba.etcfiles.shadow_entry(
            username = 'nobody',
            password = '*',
            lstchg = 12345,
            minchg = 0,
            maxchg = 99999,
            warn = 7,
            )

        assert_equal('nobody:*:12345:0:99999:7:::', ret)


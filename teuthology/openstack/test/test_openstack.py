#
# Copyright (c) 2015 Red Hat, Inc.
#
# Author: Loic Dachary <loic@dachary.org>
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
#
import argparse
import logging
import os
import pytest
import subprocess
import tempfile
from mock import patch

import teuthology
from teuthology import misc
from teuthology.config import set_config_attr
from teuthology.openstack import TeuthologyOpenStack, OpenStack, OpenStackInstance
import scripts.openstack


class TestOpenStackInstance(object):

    teuthology_instance = '[{"Field": "OS-DCF:diskConfig", "Value": "MANUAL"}, {"Field": "OS-EXT-AZ:availability_zone", "Value": "nova"}, {"Field": "OS-EXT-STS:power_state", "Value": 1}, {"Field": "OS-EXT-STS:task_state", "Value": null}, {"Field": "OS-EXT-STS:vm_state", "Value": "active"}, {"Field": "OS-SRV-USG:launched_at", "Value": "2015-11-12T14:18:42.000000"}, {"Field": "OS-SRV-USG:terminated_at", "Value": null}, {"Field": "accessIPv4", "Value": ""}, {"Field": "accessIPv6", "Value": ""}, {"Field": "addresses", "Value": "Ext-Net=167.114.233.32"}, {"Field": "config_drive", "Value": ""}, {"Field": "created", "Value": "2015-11-12T14:18:22Z"}, {"Field": "flavor", "Value": "eg-30 (3c1d6170-0097-4b5c-a3b3-adff1b7a86e0)"}, {"Field": "hostId", "Value": "b482bcc97b6b2a5b3569dc349e2b262219676ddf47a4eaf72e415131"}, {"Field": "id", "Value": "f3ca32d7-212b-458b-a0d4-57d1085af953"}, {"Field": "image", "Value": "teuthology-ubuntu-14.04 (4300a7ca-4fbd-4b34-a8d5-5a4ebf204df5)"}, {"Field": "key_name", "Value": "myself"}, {"Field": "name", "Value": "teuthology"}, {"Field": "os-extended-volumes:volumes_attached", "Value": [{"id": "627e2631-fbb3-48cd-b801-d29cd2a76f74"}, {"id": "09837649-0881-4ee2-a560-adabefc28764"}, {"id": "44e5175b-6044-40be-885a-c9ddfb6f75bb"}]}, {"Field": "progress", "Value": 0}, {"Field": "project_id", "Value": "131b886b156a4f84b5f41baf2fbe646c"}, {"Field": "properties", "Value": ""}, {"Field": "security_groups", "Value": [{"name": "teuthology"}]}, {"Field": "status", "Value": "ACTIVE"}, {"Field": "updated", "Value": "2015-11-12T14:18:42Z"}, {"Field": "user_id", "Value": "291dde1633154837be2693c6ffa6315c"}]'

    teuthology_instance_no_addresses = '[{"Field": "addresses", "Value": ""}, {"Field": "id", "Value": "f3ca32d7-212b-458b-a0d4-57d1085af953"}]'

    def test_init(self):
        with patch.multiple(
                misc,
                sh=lambda cmd: self.teuthology_instance,
        ):
            o = OpenStackInstance('NAME')
            assert o['id'] == 'f3ca32d7-212b-458b-a0d4-57d1085af953'
        o = OpenStackInstance('NAME', {"id": "OTHER"})
        assert o['id'] == "OTHER"

    def test_get_created(self):
        with patch.multiple(
                misc,
                sh=lambda cmd: self.teuthology_instance,
        ):
            o = OpenStackInstance('NAME')
            assert o.get_created() > 0

    def test_exists(self):
        with patch.multiple(
                misc,
                sh=lambda cmd: self.teuthology_instance,
        ):
            o = OpenStackInstance('NAME')
            assert o.exists()
        def sh_raises(cmd):
            raise subprocess.CalledProcessError('FAIL', 'BAD')
        with patch.multiple(
                misc,
                sh=sh_raises,
        ):
            o = OpenStackInstance('NAME')
            assert not o.exists()

    def test_volumes(self):
        with patch.multiple(
                misc,
                sh=lambda cmd: self.teuthology_instance,
        ):
            o = OpenStackInstance('NAME')
            assert len(o.get_volumes()) == 3

    def test_get_addresses(self):
        answers = [
            self.teuthology_instance_no_addresses,
            self.teuthology_instance,
        ]
        def sh(self):
            return answers.pop(0)
        with patch.multiple(
                misc,
                sh=sh,
        ):
            o = OpenStackInstance('NAME')
            assert o.get_addresses() == 'Ext-Net=167.114.233.32'

    def test_get_ip_neutron(self):
        instance_id = '8e1fd70a-3065-46f8-9c30-84dc028c1834'
        ip = '10.10.10.4'
        def sh(cmd):
            if 'neutron subnet-list' in cmd:
                return """
[
  {
    "ip_version": 6,
    "id": "c45b9661-b2ba-4817-9e3a-f8f63bf32989"
  },
  {
    "ip_version": 4,
    "id": "e03a3dbc-afc8-4b52-952e-7bf755397b50"
  }
]
                """
            elif 'neutron port-list' in cmd:
                return ("""
[
  {
    "device_id": "915504ad-368b-4cce-be7c-4f8a83902e28",
    "fixed_ips": "{\\"subnet_id\\": \\"e03a3dbc-afc8-4b52-952e-7bf755397b50\\", \\"ip_address\\": \\"10.10.10.1\\"}\\n{\\"subnet_id\\": \\"c45b9661-b2ba-4817-9e3a-f8f63bf32989\\", \\"ip_address\\": \\"2607:f298:6050:9afc::1\\"}"
  },
  {
    "device_id": "{instance_id}",
    "fixed_ips": "{\\"subnet_id\\": \\"e03a3dbc-afc8-4b52-952e-7bf755397b50\\", \\"ip_address\\": \\"{ip}\\"}\\n{\\"subnet_id\\": \\"c45b9661-b2ba-4817-9e3a-f8f63bf32989\\", \\"ip_address\\": \\"2607:f298:6050:9afc:f816:3eff:fe07:76c1\\"}"
  },
  {
    "device_id": "17e4a968-4caa-4cee-8e4b-f950683a02bd",
    "fixed_ips": "{\\"subnet_id\\": \\"e03a3dbc-afc8-4b52-952e-7bf755397b50\\", \\"ip_address\\": \\"10.10.10.5\\"}\\n{\\"subnet_id\\": \\"c45b9661-b2ba-4817-9e3a-f8f63bf32989\\", \\"ip_address\\": \\"2607:f298:6050:9afc:f816:3eff:fe9c:37f0\\"}"
  }
]
                """.replace('{instance_id}', instance_id).
                        replace('{ip}', ip))
            else:
                raise Exception("unexpected " + cmd)
        with patch.multiple(
                misc,
                sh=sh,
        ):
            assert ip == OpenStackInstance(
                instance_id,
                { 'id': instance_id },
            ).get_ip_neutron()

class TestOpenStack(object):

    def test_interpret_hints(self):
        defaults = {
            'machine': {
                'ram': 0,
                'disk': 0,
                'cpus': 0,
            },
            'volumes': {
                'count': 0,
                'size': 0,
            },
        }
        expected_disk = 10 # first hint larger than the second
        expected_ram = 20 # second hint larger than the first
        expected_cpus = 0 # not set, hence zero by default
        expected_count = 30 # second hint larger than the first
        expected_size = 40 # does not exist in the first hint
        hints = [
            {
                'machine': {
                    'ram': 2,
                    'disk': expected_disk,
                },
                'volumes': {
                    'count': 9,
                    'size': expected_size,
                },
            },
            {
                'machine': {
                    'ram': expected_ram,
                    'disk': 3,
                },
                'volumes': {
                    'count': expected_count,
                },
            },
        ]
        hint = OpenStack().interpret_hints(defaults, hints)
        assert hint == {
            'machine': {
                'ram': expected_ram,
                'disk': expected_disk,
                'cpus': expected_cpus,
            },
            'volumes': {
                'count': expected_count,
                'size': expected_size,
            }
        }
        assert defaults == OpenStack().interpret_hints(defaults, None)

    def test_set_provider(self):
        auth = os.environ.get('OS_AUTH_URL', None)
        os.environ['OS_AUTH_URL'] = 'cloud.ovh.net'
        assert OpenStack().set_provider() == 'ovh'
        if auth != None:
            os.environ['OS_AUTH_URL'] = auth
        else:
            del os.environ['OS_AUTH_URL']

class TestTeuthologyOpenStack(object):

    @classmethod
    def setup_class(self):
        if 'OS_AUTH_URL' not in os.environ:
            pytest.skip('no OS_AUTH_URL environment variable')

        teuthology.log.setLevel(logging.DEBUG)
        set_config_attr(argparse.Namespace())

        ip = TeuthologyOpenStack.create_floating_ip()
        if ip:
            ip_id = TeuthologyOpenStack.get_floating_ip_id(ip)
            misc.sh("openstack ip floating delete " + ip_id)
            self.can_create_floating_ips = True
        else:
            self.can_create_floating_ips = False

    def setup(self):
        self.key_filename = tempfile.mktemp()
        self.key_name = 'teuthology-test'
        self.name = 'teuthology-test'
        self.clobber()
        misc.sh("""
openstack keypair create {key_name} > {key_filename}
chmod 600 {key_filename}
        """.format(key_filename=self.key_filename,
                   key_name=self.key_name))
        self.options = ['--key-name', self.key_name,
                        '--key-filename', self.key_filename,
                        '--name', self.name,
                        '--verbose']

    def teardown(self):
        self.clobber()
        os.unlink(self.key_filename)

    def clobber(self):
        misc.sh("""
openstack server delete {name} --wait || true
openstack keypair delete {key_name} || true
        """.format(key_name=self.key_name,
                   name=self.name))

    def test_create(self, caplog):
        teuthology_argv = [
            '--suite', 'upgrade/hammer',
            '--dry-run',
            '--ceph', 'master',
            '--kernel', 'distro',
            '--flavor', 'gcov',
            '--distro', 'ubuntu',
            '--suite-branch', 'hammer',
            '--email', 'loic@dachary.org',
            '--num', '10',
            '--limit', '23',
            '--subset', '1/2',
            '--priority', '101',
            '--timeout', '234',
            '--filter', 'trasher',
            '--filter-out', 'erasure-code',
            '--throttle', '3',
        ]
        argv = (self.options +
                ['--upload',
                 '--archive-upload', 'user@archive:/tmp'] +
                teuthology_argv)
        args = scripts.openstack.parse_args(argv)
        teuthology = TeuthologyOpenStack(args, None, argv)
        teuthology.user_data = 'teuthology/openstack/test/user-data-test1.txt'
        teuthology.teuthology_suite = 'echo --'

        teuthology.main()
        assert 'Ubuntu 14.04' in teuthology.ssh("lsb_release -a")
        variables = teuthology.ssh("grep 'substituded variables' /var/log/cloud-init.log")
        assert "nworkers=" + str(args.simultaneous_jobs) in variables
        assert "username=" + teuthology.username in variables
        assert "upload=--archive-upload user@archive:/tmp" in variables
        assert "clone=git clone" in variables
        assert os.environ['OS_AUTH_URL'] in variables

        assert " ".join(teuthology_argv) in caplog.text()

        if self.can_create_floating_ips:
            ip = teuthology.get_floating_ip(self.name)
        teuthology.teardown()
        if self.can_create_floating_ips:
            assert teuthology.get_floating_ip_id(ip) == None

    def test_floating_ip(self):
        if not self.can_create_floating_ips:
            pytest.skip('unable to create floating ips')

        expected = TeuthologyOpenStack.create_floating_ip()
        ip = TeuthologyOpenStack.get_unassociated_floating_ip()
        assert expected == ip
        ip_id = TeuthologyOpenStack.get_floating_ip_id(ip)
        misc.sh("openstack ip floating delete " + ip_id)

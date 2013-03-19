# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 IBM Corp.
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
# @author: Yong Sheng Gong, IBM, Corp.
# @author: Yong Sheng Gong, UnistedStack, Inc
#

import contextlib

import mock
from webob import exc

from quantum.common import constants
from quantum.common import topics
from quantum import context
from quantum.extensions import portbindings
from quantum.manager import QuantumManager
from quantum.tests.unit import test_agent_ext_plugin


class MultihostDbTestCaseMixin(object):
    # we need mixin test_agent_ext_plugin.AgentDBTestMixIn
    # from quantum.tests.unit import test_agent_ext_plugin
    # in wrap case class
    fmt = 'json'
    hostname = 'testhost'

    def _get_non_admin_ctx(self):
        ctx = context.Context(user_id=None,
                              tenant_id=self._tenant_id,
                              is_admin=False,
                              read_deleted="no")
        return ctx

    def test_multihost_network_non_admin(self):
        multihost_arg = {constants.MULTIHOST: True}
        try:
            with self.network(set_context=True,
                              tenant_id='test',
                              arg_list=(constants.MULTIHOST,),
                              **multihost_arg):
                pass
        except exc.HTTPClientError:
            return
        self.assertFalse(True, 'Should not get to here')

    def test_multihost_network_with_admin(self):
        plugin = QuantumManager.get_plugin()
        multihost_arg = {constants.MULTIHOST: True}
        with self.network(arg_list=(constants.MULTIHOST,),
                          **multihost_arg) as net1:
            ctx = context.get_admin_context()
            network = plugin.get_network(ctx, net1['network']['id'])
            self.assertTrue(network[constants.MULTIHOST])
            non_admin_network = plugin.get_network(self._get_non_admin_ctx(),
                                                   net1['network']['id'])
            self.assertFalse(constants.MULTIHOST in non_admin_network)

    def test_multihost_network_with_admin_for_tenant(self):
        plugin = QuantumManager.get_plugin()
        multihost_arg = {constants.MULTIHOST: True}
        with self.network(tenant_id=self._tenant_id,
                          arg_list=(constants.MULTIHOST,),
                          **multihost_arg) as net1:
            ctx = context.get_admin_context()
            network = plugin.get_network(ctx, net1['network']['id'])
            self.assertTrue(network[constants.MULTIHOST])
            non_admin_network = plugin.get_network(self._get_non_admin_ctx(),
                                                   net1['network']['id'])
            self.assertFalse(constants.MULTIHOST in non_admin_network)

    def test_multihost_network_list_and_dhcp_notifier(self):
        multihost_arg = {constants.MULTIHOST: True}
        with mock.patch.object(self.dhcp_notifier, 'fanout_cast') as mock_dhcp:
            with contextlib.nested(
                self.network(arg_list=(constants.MULTIHOST,),
                             **multihost_arg),
                self.network()) as (net1, net2):
                plugin = QuantumManager.get_plugin()
                self.assertTrue(net1['network'][constants.MULTIHOST])
                self.assertFalse(net2['network'][constants.MULTIHOST])
                ctx = context.get_admin_context()
                networks = plugin.get_networks(ctx)
                self.assertEqual(len(networks), 2)
                for network in networks:
                    if network['id'] == net1['network']['id']:
                        self.assertTrue(network[constants.MULTIHOST])
                    else:
                        self.assertFalse(network[constants.MULTIHOST])
                networks = plugin.get_networks(self._get_non_admin_ctx())
                self.assertEqual(len(networks), 2)
                for network in networks:
                    self.assertFalse(constants.MULTIHOST in network)
            expected_calls = [
                mock.call(
                    mock.ANY,
                    self.dhcp_notifier.make_msg(
                        'network_create_end',
                        payload=net1),
                    topic=topics.DHCP_MULTI_HOST),
                mock.call(
                    mock.ANY,
                    self.dhcp_notifier.make_msg(
                        'network_delete_end',
                        payload={'network_id': net2['network']['id']}),
                    topic=topics.DHCP_AGENT),
                mock.call(
                    mock.ANY,
                    self.dhcp_notifier.make_msg(
                        'network_delete_end',
                        payload={'network_id': net1['network']['id']}),
                    topic=topics.DHCP_AGENT)]
            self.assertEqual(expected_calls, mock_dhcp.call_args_list)

    def test_multihost_network_list_filter(self):
        multihost_arg = {constants.MULTIHOST: True}
        with contextlib.nested(
            self.network(arg_list=(constants.MULTIHOST,),
                         **multihost_arg),
            self.network(),
            self.network(arg_list=(constants.MULTIHOST,),
                         **multihost_arg)) as (net1, net2, net3):
            self._test_list_resources(
                'network', (net1, net3),
                query_params='%s=%s' % (constants.MULTIHOST, True))
            self._test_list_resources(
                'network', (net2,),
                query_params='%s=%s' % (constants.MULTIHOST, False))

    def test_multihost_router_non_admin(self):
        multihost_arg = {constants.MULTIHOST: True}
        with self.network(arg_list=(constants.MULTIHOST,),
                          **multihost_arg) as net1:
            multihost_net_arg = {constants.MULTIHOST_NET:
                                 net1['network']['id']}
            try:
                with self.router(set_context=True,
                                 tenant_id=self._tenant_id,
                                 expected_code=exc.HTTPForbidden.code,
                                 arg_list=(constants.MULTIHOST_NET,),
                                 **multihost_net_arg):
                    pass
            except exc.HTTPClientError:
                return
        self.assertFalse(True, 'Should not get to here')

    def test_multihost_route_with_admin(self):
        plugin = QuantumManager.get_plugin()
        multihost_arg = {constants.MULTIHOST: True}
        with self.network(arg_list=(constants.MULTIHOST,),
                          **multihost_arg) as net1:
            multihost_net_arg = {constants.MULTIHOST_NET:
                                 net1['network']['id']}
            with self.router(tenant_id=self._tenant_id,
                             arg_list=(constants.MULTIHOST_NET,),
                             **multihost_net_arg) as router:
                ctx = context.get_admin_context()
                router = plugin.get_router(ctx, router['router']['id'])
                self.assertEqual(net1['network']['id'],
                                 router[constants.MULTIHOST_NET])
                non_admin_router = plugin.get_router(
                    self._get_non_admin_ctx(),
                    router['id'])
                self.assertFalse(constants.MULTIHOST_NET in non_admin_router)

    def test_multihost_router_error_one_network_many_routers(self):
        multihost_arg = {constants.MULTIHOST: True}
        with self.network(arg_list=(constants.MULTIHOST,),
                          **multihost_arg) as net1:
            try:
                multihost_net_arg = {constants.MULTIHOST_NET:
                                     net1['network']['id']}
                with contextlib.nested(
                    self.router(tenant_id=self._tenant_id,
                                arg_list=(constants.MULTIHOST_NET,),
                                **multihost_net_arg),
                    self.router(tenant_id=self._tenant_id,
                                arg_list=(constants.MULTIHOST_NET,),
                                **multihost_net_arg)):
                    pass
            except exc.HTTPClientError:
                return
            self.assertFalse(True, 'Should not get to here')

    def test_multihost_router_error_non_multihost_network(self):
        with self.network() as net1:
            try:
                multihost_net_arg = {constants.MULTIHOST_NET:
                                     net1['network']['id']}
                with self.router(tenant_id=self._tenant_id,
                                 expected_code=exc.HTTPConflict.code,
                                 arg_list=(constants.MULTIHOST_NET,),
                                 **multihost_net_arg):
                    pass
            except exc.HTTPClientError:
                return
        self.assertFalse(True, 'Should not get to here')

    def test_multihost_router_list_filter(self):
        multihost_arg = {constants.MULTIHOST: True}
        with contextlib.nested(
            self.network(arg_list=(constants.MULTIHOST,),
                         **multihost_arg),
            self.network(arg_list=(constants.MULTIHOST,),
                         **multihost_arg)) as (net1, net2):
            multihost_net1_arg = {constants.MULTIHOST_NET:
                                  net1['network']['id']}
            multihost_net2_arg = {constants.MULTIHOST_NET:
                                  net2['network']['id']}
            with contextlib.nested(
                self.router(tenant_id=self._tenant_id,
                            arg_list=(constants.MULTIHOST_NET,),
                            **multihost_net1_arg),
                self.router(),
                self.router(tenant_id=self._tenant_id,
                            arg_list=(constants.MULTIHOST_NET,),
                            **multihost_net2_arg)) as (
                    router1, router2, router3):
                    self._test_list_resources(
                        'router', (router1, router3),
                        query_params='%s=%s' % (constants.MULTIHOST, True))
                    self._test_list_resources(
                        'router', (router2,),
                        query_params='%s=%s' % (constants.MULTIHOST, False))

    def test_multihost_get_sync_data(self):
        plugin = QuantumManager.get_plugin()
        multihost_arg = {constants.MULTIHOST: True}
        hostname = 'testhost'
        host_arg = {portbindings.HOST_ID: hostname}
        with contextlib.nested(
            self.subnet(cidr='11.0.0.0/24'),
            self.network(arg_list=(constants.MULTIHOST,),
                         **multihost_arg)) as (
                public_sub, private_net):
            self._set_net_external(public_sub['subnet']['network_id'])
            multihost_net1_arg = {constants.MULTIHOST_NET:
                                  private_net['network']['id']}
            with self.subnet(network=private_net) as subnet1:
                with contextlib.nested(
                    self.port(subnet=subnet1,
                              arg_list=(portbindings.HOST_ID,),
                              **host_arg),
                    self.router(tenant_id=self._tenant_id,
                                arg_list=(constants.MULTIHOST_NET,),
                                **multihost_net1_arg)) as (private_port, r):
                    sid = private_port['port']['fixed_ips'][0]['subnet_id']
                    private_sub = {'subnet': {'id': sid}}
                    floatingip = None
                    try:
                        self._add_external_gateway_to_router(
                            r['router']['id'],
                            public_sub['subnet']['network_id'])
                        self._router_interface_action(
                            'add', r['router']['id'],
                            private_sub['subnet']['id'], None)

                        floatingip = self._make_floatingip(
                            self.fmt,
                            public_sub['subnet']['network_id'],
                            port_id=private_port['port']['id'],
                            set_context=False)
                        ctx = context.get_admin_context()
                        sync_routers = plugin.get_sync_data(ctx,
                                                            multi_host=True)
                    finally:
                        if floatingip:
                            self._delete('floatingips',
                                         floatingip['floatingip']['id'])
                        self._router_interface_action(
                            'remove', r['router']['id'],
                            private_sub['subnet']['id'], None)
                        self._remove_external_gateway_from_router(
                            r['router']['id'],
                            public_sub['subnet']['network_id'])
        self.assertEqual(1, len(sync_routers))
        for router in sync_routers:
            self.assertEqual(router['id'], r['router']['id'])
            floatingip = router[constants.FLOATINGIP_KEY][0]
            self.assertEqual(floatingip[portbindings.HOST_ID],
                             hostname)

    def test_multihost_add_router_interface_and_l3_notifier(self):
        plugin = QuantumManager.get_plugin()
        multihost_arg = {constants.MULTIHOST: True}
        with mock.patch.object(plugin.l3_agent_notifier,
                               'fanout_cast') as mock_l3:
            with contextlib.nested(
                self.subnet(cidr='11.0.0.0/24'),
                self.network(arg_list=(constants.MULTIHOST,),
                             **multihost_arg),
                self.network()) as (
                    first_sub, private_multihost_net, private_net):
                multihost_net1_arg = {constants.MULTIHOST_NET:
                                      private_multihost_net['network']['id']}
                with contextlib.nested(
                    self.subnet(cidr='11.0.1.0/24',
                                network=private_multihost_net),
                    self.subnet(cidr='11.0.2.0/24', network=private_net)) as (
                        private_multihost_subnet1, private_subnet2):
                    with contextlib.nested(
                        self.port(subnet=private_multihost_subnet1),
                        self.router(tenant_id=self._tenant_id,
                                    arg_list=(constants.MULTIHOST_NET,),
                                    **multihost_net1_arg),
                        self.router()) as (
                            port, multihost_router, router):
                        self._router_interface_action(
                            'add', multihost_router['router']['id'],
                            first_sub['subnet']['id'], None,
                            expected_code=exc.HTTPBadRequest.code)
                        self._router_interface_action(
                            'add', multihost_router['router']['id'],
                            None, port['port']['id'],
                            expected_code=exc.HTTPBadRequest.code)
                        self._router_interface_action(
                            'add', router['router']['id'],
                            private_multihost_subnet1['subnet']['id'], None,
                            expected_code=exc.HTTPBadRequest.code)
                        try:
                            self._router_interface_action(
                                'add', multihost_router['router']['id'],
                                private_multihost_subnet1['subnet']['id'],
                                None)
                            self._router_interface_action(
                                'add', router['router']['id'],
                                private_subnet2['subnet']['id'], None)
                        finally:
                            self._router_interface_action(
                                'remove', multihost_router['router']['id'],
                                private_multihost_subnet1['subnet']['id'],
                                None)
                            self._router_interface_action(
                                'remove', router['router']['id'],
                                private_subnet2['subnet']['id'], None)
            expected_calls = [
                mock.call(
                    mock.ANY,
                    plugin.l3_agent_notifier.make_msg(
                        'routers_updated',
                        routers=mock.ANY),
                    topic=topics.L3_MULTI_HOST),
                mock.call(
                    mock.ANY,
                    plugin.l3_agent_notifier.make_msg(
                        'routers_updated',
                        routers=mock.ANY),
                    topic=topics.L3_MULTI_HOST),
                mock.call(
                    mock.ANY,
                    plugin.l3_agent_notifier.make_msg(
                        'router_deleted',
                        router_id=mock.ANY),
                    topic=topics.L3_AGENT),
                mock.call(
                    mock.ANY,
                    plugin.l3_agent_notifier.make_msg(
                        'router_deleted',
                        router_id=mock.ANY),
                    topic=topics.L3_AGENT)]
            self.assertEqual(expected_calls, mock_l3.call_args_list)

    def test_multihost_update_gw_port(self):
        plugin = QuantumManager.get_plugin()
        multihost_arg = {constants.MULTIHOST: True}
        self._register_agent_states()
        with contextlib.nested(
            self.subnet(cidr='11.0.0.0/24'),
            self.network(arg_list=(constants.MULTIHOST,),
                         **multihost_arg)) as (
                public_sub, private_net):
            self._set_net_external(public_sub['subnet']['network_id'])
            multihost_net1_arg = {constants.MULTIHOST_NET:
                                  private_net['network']['id']}
            with self.subnet(network=private_net):
                with contextlib.nested(
                    self.router(tenant_id=self._tenant_id,
                                arg_list=(constants.MULTIHOST_NET,),
                                **multihost_net1_arg)) as (r,):
                    try:
                        self._add_external_gateway_to_router(
                            r['router']['id'],
                            public_sub['subnet']['network_id'])
                        ctx = context.get_admin_context()
                        gw_port_on_host = plugin.get_ex_gw_port_on_host(
                            ctx, r['router']['id'],
                            test_agent_ext_plugin.L3_HOSTA)
                        self.assertTrue(gw_port_on_host is not None)
                        host_ports = plugin.get_ports(
                            ctx, filters={
                                'device_owner':
                                [constants.MULTIHOST_OWNER_DEVICE_ROUTER_GW]})
                        self.assertEqual(1, len(host_ports))
                    finally:
                        self._remove_external_gateway_from_router(
                            r['router']['id'],
                            public_sub['subnet']['network_id'])
                        host_ports = plugin.get_ports(
                            ctx, filters={
                                'device_owner':
                                [constants.MULTIHOST_OWNER_DEVICE_ROUTER_GW]})
                        self.assertEqual(0, len(host_ports))

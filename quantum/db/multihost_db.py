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

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import exc
from sqlalchemy.sql import expression as expr

from quantum.api.v2 import attributes
from quantum.common import constants
from quantum.db import db_base_plugin_v2
from quantum.db import l3_db
from quantum.db import model_base
from quantum.db import models_v2
from quantum.extensions import l3
from quantum.extensions import multihost
from quantum import manager
from quantum.openstack.common import log as logging
from quantum import policy


LOG = logging.getLogger(__name__)


class MultiHostNetwork(model_base.BASEV2):
    network_id = sa.Column(sa.String(36),
                           sa.ForeignKey('networks.id', ondelete="CASCADE"),
                           primary_key=True)


class MultiHostRouter(model_base.BASEV2):
    router_id = sa.Column(sa.String(36),
                          sa.ForeignKey('routers.id', ondelete="CASCADE"),
                          primary_key=True)
    network_id = sa.Column(sa.String(36),
                           sa.ForeignKey('networks.id', ondelete="CASCADE"),
                           unique=True)


class MultiHostRouterGwPort(model_base.BASEV2, models_v2.HasId):
    router_id = sa.Column(
        sa.String(36), sa.ForeignKey('routers.id', ondelete="CASCADE"))
    host_gw_port_id = sa.Column(
        sa.String(36), sa.ForeignKey('ports.id'))
    host_gw_port = orm.relationship(models_v2.Port)
    host = sa.Column(sa.String(255), nullable=False)
    __table_args__ = (sa.UniqueConstraint(
        'router_id', 'host', name='_MultiHostRouterGwPort_uc'),)


class Multihost_db_mixin(object):

    def _network_model_hook(self, context, original_model, query):
        query = query.outerjoin(MultiHostNetwork,
                                (original_model.id ==
                                 MultiHostNetwork.network_id))
        return query

    def _network_result_filter_hook(self, query, filters):
        vals = filters and filters.get(multihost.MULTIHOST, [])
        if not vals:
            return query
        if vals[0]:
            return query.filter((MultiHostNetwork.network_id != expr.null()))
        return query.filter((MultiHostNetwork.network_id == expr.null()))

    def _router_model_hook(self, context, original_model, query):
        query = query.outerjoin(MultiHostRouter,
                                (original_model.id ==
                                 MultiHostRouter.router_id))
        return query

    def _router_result_filter_hook(self, query, filters):
        vals = filters and filters.get(multihost.MULTIHOST, [])
        if vals and vals[0]:
            query = query.filter(MultiHostRouter.router_id != expr.null())
        elif vals and not vals[0]:
            query = query.filter(MultiHostRouter.router_id == expr.null())
        vals = filters and filters.get(multihost.MULTIHOST_NET, [])
        if not vals:
            return query
        if len(vals) == 1:
            query = query.filter(MultiHostRouter.network_id == vals[0])
        else:
            query = query.filter(MultiHostRouter.network_id.in_(vals))
            return query

    db_base_plugin_v2.QuantumDbPluginV2.register_model_query_hook(
        models_v2.Network,
        "multihost_net",
        _network_model_hook,
        None,
        _network_result_filter_hook)

    db_base_plugin_v2.QuantumDbPluginV2.register_model_query_hook(
        l3_db.Router,
        "multihost_router",
        _router_model_hook,
        None,
        _router_result_filter_hook)

    def _check_mutihost_net_view_auth(self, context, network):
        return policy.check(context,
                            "extension:multihost_net:view",
                            network)

    def _enforce_multihost_net_set_auth(self, context, network):
        return policy.enforce(context,
                              "extension:multihost_net:set",
                              network)

    def _check_mutihost_router_view_auth(self, context, router):
        return policy.check(context,
                            "extension:multihost_router:view",
                            router)

    def _enforce_multihost_router_set_auth(self, context, router):
        return policy.enforce(context,
                              "extension:multihost_router:set",
                              router)

    def is_multihost_network(self, context, net_id):
        try:
            context.session.query(MultiHostNetwork).filter_by(
                network_id=net_id).one()
            return True
        except exc.NoResultFound:
            return False

    def get_multihost_net_by_router(self, context, router_id):
        try:
            mutihost = context.session.query(MultiHostRouter).filter_by(
                router_id=router_id).one()
            return mutihost.network_id
        except exc.NoResultFound:
            return ''

    def _extend_network_dict_multihost(self, context, network):
        if self._check_mutihost_net_view_auth(context, network):
            network[multihost.MULTIHOST] = self.is_multihost_network(
                context, network['id'])

    def _process_multihost_net_create(self, context, net_data, net_id):
        multihost_flat = net_data.get(multihost.MULTIHOST)
        multihost_flat_set = attributes.is_attr_set(multihost_flat)
        if not multihost_flat_set:
            return
        self._enforce_multihost_net_set_auth(context, net_data)
        if multihost_flat:
            # expects to be called within a plugin's session
            context.session.add(MultiHostNetwork(network_id=net_id))

    def _extend_router_dict_multihost(self, context, router):
        if self._check_mutihost_router_view_auth(context, router):
            router[multihost.MULTIHOST_NET] = self.get_multihost_net_by_router(
                context, router['id'])

    def _process_multihost_router_create(self, context, router_data,
                                         router_id):
        multihost_net_id = router_data.get(multihost.MULTIHOST_NET)
        multihost_net_id_set = attributes.is_attr_set(multihost_net_id)
        if not multihost_net_id_set:
            return
        self._enforce_multihost_router_set_auth(context, router_data)
        if multihost_net_id:
            if not self.is_multihost_network(context, multihost_net_id):
                raise multihost.InvalidMutihostNetwork(
                    net_id=multihost_net_id)
            # expects to be called within a plugin's session
            context.session.add(MultiHostRouter(router_id=router_id,
                                                network_id=multihost_net_id))

    def _get_multihost_gw_port(self, context, router_id, host):
        query = context.session.query(MultiHostRouterGwPort)
        query = query.filter(
            MultiHostRouterGwPort.router_id == router_id,
            MultiHostRouterGwPort.host == host)
        try:
            host_gw_port = query.one()
        except exc.NoResultFound:
            return None
        return host_gw_port

    def is_multihost_router(self, context, router_id):
        return (True if self._get_multihost_net_by_router(context, router_id)
                else False)

    def delete_router_gw_ports_on_hosts(self, context, router_id):
        with context.session.begin(subtransactions=True):
            query = context.session.query(MultiHostRouterGwPort)
            query = query.filter(
                MultiHostRouterGwPort.router_id == router_id)
            router_gw_ports = query.all()
            for router_gw_port in router_gw_ports:
                context.session.delete(router_gw_port.host_gw_port)
                router_gw_port.host_gw_port = None
                context.session.delete(router_gw_port)

    def get_router_by_multihost_net(self, context, network_id):
        try:
            mutihost = context.session.query(MultiHostRouter).filter_by(
                network_id=network_id).one()
            return mutihost.router_id
        except exc.NoResultFound:
            return ''

    def get_ex_gw_port_on_host(self, context, router_id, host):
        host_gw_port_id = None
        with context.session.begin(subtransactions=True):
            try:
                router_db = self._get_router(context, router_id)
            except l3.RouterNotFound:
                return None
            host_gw_port = self._get_multihost_gw_port(
                context, router_id, host)
            if host_gw_port:
                host_gw_port_id = host_gw_port.host_gw_port_id
            else:
                default_gw_port = router_db.gw_port
                if not default_gw_port:
                    return
                fixed_ips = default_gw_port.fixed_ips
                if not fixed_ips:
                    return
                # gw port should have only one IP
                subnet_id = fixed_ips[0]['subnet_id']
                host_gw_port = MultiHostRouterGwPort()
                port_dict = dict(
                    admin_state_up=True,
                    device_id=router_id,
                    network_id=default_gw_port.network_id,
                    tenant_id='',
                    mac_address=attributes.ATTR_NOT_SPECIFIED,
                    name='',
                    device_owner=constants.MULTIHOST_OWNER_DEVICE_ROUTER_GW,
                    fixed_ips=[{'subnet_id': subnet_id}])

                retval = self.create_port(context, dict(port=port_dict))
                port_db = self._get_port(context, retval['id'])
                host_gw_port.host = host
                host_gw_port.router_id = router_id
                host_gw_port.host_gw_port = port_db
                context.session.add(host_gw_port)
                host_gw_port_id = port_db.id
        if host_gw_port_id:
            gw_ports = self.get_sync_gw_ports(
                context, [host_gw_port.host_gw_port_id])
            return gw_ports[0] if gw_ports else None


class L3MultihostPluginApiCallback(object):
    """enable multihost L3 agent support in plugin implementations."""

    def get_ex_gw_port_on_host(self, context, **kwargs):
        """Get external gateway port for host."""
        host = kwargs.get('host')
        router_id = kwargs.get('router_id')
        LOG.debug(_('get_ex_gw_port_on_host requested from %s'), host)
        plugin = manager.QuantumManager.get_plugin()
        return plugin.get_ex_gw_port_on_host(
            context, router_id, host)

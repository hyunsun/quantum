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

from quantum.api.v2 import attributes
from quantum.db import db_base_plugin_v2
from quantum.db import model_base
from quantum.db import models_v2
from quantum.extensions import portbindings
from quantum.openstack.common import log as logging
from quantum import policy


LOG = logging.getLogger(__name__)


class PortBindingPort(model_base.BASEV2):
    port_id = sa.Column(sa.String(36),
                        sa.ForeignKey('ports.id', ondelete="CASCADE"),
                        primary_key=True)
    host = sa.Column(sa.String(255), nullable=False)
    port = orm.relationship(
        models_v2.Port,
        backref=orm.backref("portbinding",
                            lazy='joined', uselist=False,
                            cascade='delete'))


class PortBindingMixin(object):
    extra_binding_dict = None

    def _port_model_hook(self, context, original_model, query):
        query = query.outerjoin(PortBindingPort,
                                (original_model.id ==
                                 PortBindingPort.port_id))
        return query

    def _port_result_filter_hook(self, query, filters):
        values = filters and filters.get(portbindings.HOST_ID, [])
        if not values:
            return query
        if len(values) == 1:
            query = query.filter(PortBindingPort.host == values[0])
        else:
            query = query.filter(PortBindingPort.host.in_(values))
        return query

    db_base_plugin_v2.QuantumDbPluginV2.register_model_query_hook(
        models_v2.Port,
        "portbindings_port",
        _port_model_hook,
        None,
        _port_result_filter_hook)

    def _check_portbindings_view_auth(self, context, port):
        #TODO(salv-orlando): Remove this as part of bp/make-authz-orthogonal
        keys_to_delete = []
        for key in port:
            if key.startswith('binding'):
                policy_rule = "get_port:%s" % key
                if not policy.check(context, policy_rule, port):
                    keys_to_delete.append(key)
        for key in keys_to_delete:
            del port[key]
        return port

    def _process_portbindings_create_and_update(self, context, port_data,
                                                port):
        host = port_data.get(portbindings.HOST_ID)
        host_set = attributes.is_attr_set(host)
        if not host_set:
            # Port binding is not updated, use existing host_id or None
            host = self.get_port_host(context, port['id'])
        else:
            with context.session.begin(subtransactions=True):
                bind_port = context.session.query(
                    PortBindingPort).filter_by(port_id=port['id']).first()
                if not bind_port:
                    context.session.add(PortBindingPort(port_id=port['id'],
                                                        host=host))
                else:
                    bind_port.host = host
        _extend_port_dict_binding_host(self, port, host)

    def get_port_host(self, context, port_id):
        with context.session.begin(subtransactions=True):
            bind_port = context.session.query(
                PortBindingPort).filter_by(port_id=port_id).first()
            return bind_port and bind_port.host or None


def _extend_port_dict_binding_host(plugin, port_res, host):
    port_res[portbindings.HOST_ID] = host
    if plugin.extra_binding_dict:
        port_res.update(plugin.extra_binding_dict)
    return port_res


def _extend_port_dict_binding(plugin, port_res, port_db):
    if not isinstance(plugin, PortBindingMixin):
        return
    host = (port_db.portbinding and port_db.portbinding.host or None)
    return _extend_port_dict_binding_host(
        plugin, port_res, host)

    # Register dict extend functions for ports
db_base_plugin_v2.QuantumDbPluginV2.register_dict_extend_funcs(
    attributes.PORTS, [_extend_port_dict_binding])

# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright 2013 OpenStack Foundation.
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

from quantum.api import extensions
from quantum.api.v2 import attributes as attr
from quantum.common import constants
from quantum.common import exceptions as qexception


MULTIHOST = constants.MULTIHOST
MULTIHOST_NET = constants.MULTIHOST_NET
EXTENDED_ATTRIBUTES_2_0 = {
    'networks': {MULTIHOST: {'allow_post': True,
                             'allow_put': False,
                             'default': attr.ATTR_NOT_SPECIFIED,
                             'is_visible': True,
                             'convert_to': attr.convert_to_boolean,
                             'enforce_policy': True,
                             'required_by_policy': True}},
    # MULTIHOST attr of router is for query filters only
    # such as to query all multi-host routers
    'routers': {MULTIHOST: {'allow_post': False,
                            'allow_put': False,
                            'default': attr.ATTR_NOT_SPECIFIED,
                            'is_visible': False,
                            'convert_to': attr.convert_to_boolean},
                MULTIHOST_NET: {'allow_post': True,
                                'allow_put': False,
                                'default': attr.ATTR_NOT_SPECIFIED,
                                'validate': {'type:uuid': None},
                                'is_visible': True,
                                'enforce_policy': True,
                                'required_by_policy': True}}}


class InvalidMutihostNetwork(qexception.Conflict):
    message = _("Invalid multihost network %(net_id)s.")


class Multihost(extensions.ExtensionDescriptor):

    @classmethod
    def get_name(cls):
        return "Quantum Multihost"

    @classmethod
    def get_alias(cls):
        return constants.MULTIHOST_EXT_ALIAS

    @classmethod
    def get_description(cls):
        return ("Support multihost feature.")

    @classmethod
    def get_namespace(cls):
        return "http://docs.openstack.org/ext/quantum/multihost/api/v1.0"

    @classmethod
    def get_updated(cls):
        return "2013-03-18T10:00:00-00:00"

    def get_extended_resources(self, version):
        if version == "2.0":
            return EXTENDED_ATTRIBUTES_2_0
        else:
            return {}

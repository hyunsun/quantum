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

from quantum.openstack.common import log as logging
from quantum.openstack.common.rpc import proxy


LOG = logging.getLogger(__name__)


class L3MultihostPluginApi(proxy.RpcProxy):
    '''Agent side of the rpc API for multihost router.

    API version history:
        1.0 - Initial version.

    '''

    BASE_RPC_API_VERSION = '1.0'

    def __init__(self, topic, host):
        super(L3MultihostPluginApi, self).__init__(
            topic=topic, default_version=self.BASE_RPC_API_VERSION)
        self.host = host

    def get_ex_gw_port_on_host(self, context, router_id):
        return self.call(context,
                         self.make_msg('get_ex_gw_port_on_host',
                                       router_id=router_id,
                                       host=self.host),
                         topic=self.topic)

# -*- coding: utf-8 -*-
###
# (C) Copyright (2012-2016) Hewlett Packard Enterprise Development LP
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
###

import unittest

import mock
from mock import call

from hpOneView.connection import connection
from hpOneView.exceptions import HPOneViewUnknownType, HPOneViewException
from hpOneView.resources.resource import merge_resources, merge_default_values
from hpOneView.resources.resource import ResourceClient, RESOURCE_CLIENT_INVALID_ID, UNRECOGNIZED_URI, TaskMonitor, \
    RESOURCE_CLIENT_TASK_EXPECTED


class ResourceTest(unittest.TestCase):
    def test_merge_resources(self):
        resource1 = {'name': 'resource1', 'type': 'resource'}
        resource2 = {'name': 'resource2', 'port': '1'}

        expected_resource = {'name': 'resource2', 'type': 'resource', 'port': '1'}

        merged_resource = merge_resources(resource1, resource2)
        self.assertEqual(merged_resource, expected_resource)

    def test_merge_default_values(self):
        default_type = {'type': 'type1'}
        resource1 = {'name': 'resource1'}
        resource2 = {'name': 'resource2'}

        result_list = merge_default_values([resource1, resource2], default_type)

        expected_list = [
            {'name': 'resource1', 'type': 'type1'},
            {'name': 'resource2', 'type': 'type1'}
        ]

        self.assertEqual(result_list, expected_list)


class FakeResource(object):
    def __init__(self, con):
        self._connection = con
        self._client = ResourceClient(con, "/rest/fake/resource")

    def get_fake(self, uri):
        return self._client.get(uri)


class ResourceClientTest(unittest.TestCase):
    URI = "/rest/testuri"

    TYPE_V200 = 'typeV200'
    TYPE_V300 = 'typeV300'

    DEFAULT_VALUES = {
        '200': {'type': TYPE_V200},
        '300': {'type': TYPE_V300}
    }

    def setUp(self):
        super(ResourceClientTest, self).setUp()
        self.host = '127.0.0.1'
        self.connection = connection(self.host, 200)
        self.resource_client = ResourceClient(self.connection, self.URI)
        self.task = {"task": "task", "taskState": "Finished"}
        self.response_body = {"body": "body"}
        self.custom_headers = {'Accept-Language': 'en_US'}

    @mock.patch.object(connection, 'get')
    def test_get_all_called_once(self, mock_get):
        filter = "'name'='OneViewSDK \"Test FC Network'"
        sort = 'name:ascending'
        query = "name NE 'WrongName'"
        view = '"{view-name}"'

        mock_get.return_value = {"members": [{"member": "member"}]}

        result = self.resource_client.get_all(
            1, 500, filter, query, sort, view, 'name,owner,modified')

        uri = '{resource_uri}?start=1' \
              '&count=500' \
              '&filter=%27name%27%3D%27OneViewSDK%20%22Test%20FC%20Network%27' \
              '&query=name%20NE%20%27WrongName%27' \
              '&sort=name%3Aascending' \
              '&view=%22%7Bview-name%7D%22' \
              '&fields=name%2Cowner%2Cmodified'.format(resource_uri=self.URI)

        self.assertEqual([{'member': 'member'}], result)
        mock_get.assert_called_once_with(uri)

    @mock.patch.object(connection, 'get')
    def test_get_all_with_defaults(self, mock_get):
        self.resource_client.get_all()
        uri = "{resource_uri}?start=0&count=-1".format(resource_uri=self.URI)

        mock_get.assert_called_once_with(uri)

    @mock.patch.object(connection, 'get')
    def test_get_all_with_custom_uri(self, mock_get):
        self.resource_client.get_all(uri='/rest/testuri/12467836/subresources')
        uri = "/rest/testuri/12467836/subresources?start=0&count=-1"

        mock_get.assert_called_once_with(uri)

    @mock.patch.object(connection, 'get')
    def test_get_all_with_custom_uri_and_query_string(self, mock_get):
        self.resource_client.get_all(uri='/rest/testuri/12467836/subresources?param=value')

        uri = "/rest/testuri/12467836/subresources?param=value&start=0&count=-1"
        mock_get.assert_called_once_with(uri)

    @mock.patch.object(connection, 'get')
    def test_get_all_with_different_resource_uri_should_fail(self, mock_get):
        try:
            self.resource_client.get_all(uri='/rest/other/resource/12467836/subresources')
        except HPOneViewUnknownType as e:
            self.assertEqual(UNRECOGNIZED_URI, e.args[0])
        else:
            self.fail('Expected Exception was not raised')

    @mock.patch.object(connection, 'get')
    def test_get_all_should_do_multi_requests_when_response_paginated(self, mock_get):
        uri_list = ['/rest/testuri?start=0&count=-1',
                    '/rest/testuri?start=3&count=3',
                    '/rest/testuri?start=6&count=3']

        results = [{'nextPageUri': uri_list[1], 'members': [{'id': '1'}, {'id': '2'}, {'id': '3'}]},
                   {'nextPageUri': uri_list[2], 'members': [{'id': '4'}, {'id': '5'}, {'id': '6'}]},
                   {'nextPageUri': None, 'members': [{'id': '7'}, {'id': '8'}]}]

        mock_get.side_effect = results

        self.resource_client.get_all()

        expected_calls = [call(uri_list[0]), call(uri_list[1]), call(uri_list[2])]
        self.assertEqual(mock_get.call_args_list, expected_calls)

    @mock.patch.object(connection, 'get')
    def test_get_all_with_count_should_do_multi_requests_when_response_paginated(self, mock_get):
        uri_list = ['/rest/testuri?start=0&count=15',
                    '/rest/testuri?start=3&count=3',
                    '/rest/testuri?start=6&count=3']

        results = [{'nextPageUri': uri_list[1], 'members': [{'id': '1'}, {'id': '2'}, {'id': '3'}]},
                   {'nextPageUri': uri_list[2], 'members': [{'id': '4'}, {'id': '5'}, {'id': '6'}]},
                   {'nextPageUri': None, 'members': [{'id': '7'}, {'id': '8'}]}]

        mock_get.side_effect = results

        self.resource_client.get_all(count=15)

        expected_calls = [call(uri_list[0]), call(uri_list[1]), call(uri_list[2])]
        self.assertEqual(mock_get.call_args_list, expected_calls)

    @mock.patch.object(connection, 'get')
    def test_get_all_should_return_all_items_when_response_paginated(self, mock_get):
        uri_list = ['/rest/testuri?start=0&count=-1',
                    '/rest/testuri?start=3&count=3',
                    '/rest/testuri?start=6&count=1']

        results = [{'nextPageUri': uri_list[1], 'members': [{'id': '1'}, {'id': '2'}, {'id': '3'}]},
                   {'nextPageUri': uri_list[2], 'members': [{'id': '4'}, {'id': '5'}, {'id': '6'}]},
                   {'nextPageUri': None, 'members': [{'id': '7'}]}]

        mock_get.side_effect = results

        result = self.resource_client.get_all()

        expected_items = [{'id': '1'}, {'id': '2'}, {'id': '3'}, {'id': '4'}, {'id': '5'}, {'id': '6'}, {'id': '7'}]
        self.assertSequenceEqual(result, expected_items)

    @mock.patch.object(connection, 'get')
    def test_get_all_should_limit_results_to_requested_count_when_response_is_paginated(self, mock_get):
        uri_list = ['/rest/testuri?start=0&count=15',
                    '/rest/testuri?start=3&count=3',
                    '/rest/testuri?start=6&count=1']

        results = [{'nextPageUri': uri_list[1], 'members': [{'id': '1'}, {'id': '2'}, {'id': '3'}]},
                   {'nextPageUri': uri_list[2], 'members': [{'id': '4'}, {'id': '5'}, {'id': '6'}]},
                   {'nextPageUri': None, 'members': [{'id': '7'}]}]

        mock_get.side_effect = results

        result = self.resource_client.get_all(count=15)

        expected_items = [{'id': '1'}, {'id': '2'}, {'id': '3'}, {'id': '4'}, {'id': '5'}, {'id': '6'}, {'id': '7'}]
        self.assertSequenceEqual(result, expected_items)

    @mock.patch.object(connection, 'get')
    def test_get_all_should_stop_requests_when_requested_count_reached(self, mock_get):
        """
        In this case, the user provides a maximum number of results to be returned but for pagination purposes, a
        nextPageUri is returned by OneView.
        """
        uri_list = ['/rest/testuri?start=0&count=3',
                    '/rest/testuri?start=3&count=3',
                    '/rest/testuri?start=6&count=3']

        results = [{'nextPageUri': uri_list[1], 'members': [{'id': '1'}, {'id': '2'}, {'id': '3'}]},
                   {'nextPageUri': uri_list[2], 'members': [{'id': '4'}, {'id': '5'}, {'id': '6'}]},
                   {'nextPageUri': None, 'members': [{'id': '7'}, {'id': '8'}]}]

        mock_get.side_effect = results

        self.resource_client.get_all(count=3)

        mock_get.assert_called_once_with(uri_list[0])

    @mock.patch.object(connection, 'get')
    def test_get_all_should_stop_requests_when_next_page_is_equal_to_current_page(self, mock_get):
        uri = '/rest/testuri?start=0&count=-1'
        members = [{'id': '1'}, {'id': '2'}, {'id': '3'}]

        mock_get.return_value = {
            'nextPageUri': uri,
            'members': members,
            'uri': uri
        }

        result = self.resource_client.get_all()

        self.assertSequenceEqual(result, members)
        mock_get.assert_called_once_with(uri)

    @mock.patch.object(connection, 'get')
    def test_get_all_should_return_empty_list_when_response_has_no_items(self, mock_get):
        mock_get.return_value = {'nextPageUri': None, 'members': []}

        result = self.resource_client.get_all()

        self.assertEqual(result, [])

    @mock.patch.object(connection, 'delete')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_delete_all_called_once(self, mock_wait4task, mock_delete):
        mock_delete.return_value = self.task, self.response_body
        mock_wait4task.return_value = self.task

        filter = "name='Exchange Server'"
        uri = "/rest/testuri?filter=name%3D%27Exchange%20Server%27&force=True"
        self.resource_client.delete_all(filter=filter, force=True, timeout=-1)

        mock_delete.assert_called_once_with(uri)

    @mock.patch.object(connection, 'delete')
    def test_delete_all_should_return_true(self, mock_delete):
        mock_delete.return_value = None, self.response_body

        filter = "name='Exchange Server'"
        result = self.resource_client.delete_all(filter=filter, force=True, timeout=-1)

        self.assertTrue(result)

    @mock.patch.object(connection, 'delete')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_delete_all_should_wait_for_task(self, mock_wait4task, mock_delete):
        mock_delete.return_value = self.task, self.response_body
        mock_wait4task.return_value = self.task

        filter = "name='Exchange Server'"
        delete_task = self.resource_client.delete_all(filter=filter, force=True, timeout=-1)

        mock_wait4task.assert_called_with(self.task, timeout=-1)
        self.assertEqual(self.task, delete_task)

    @mock.patch.object(connection, 'delete')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_delete_by_id_called_once(self, mock_wait4task, mock_delete):
        mock_delete.return_value = self.task, self.response_body
        mock_wait4task.return_value = self.task

        delete_task = self.resource_client.delete('1', force=True, timeout=-1)

        self.assertEqual(self.task, delete_task)
        mock_delete.assert_called_once_with(self.URI + "/1?force=True", custom_headers=None)

    @mock.patch.object(connection, 'delete')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_delete_with_custom_headers(self, mock_wait4task, mock_delete):
        mock_delete.return_value = self.task, self.response_body
        mock_wait4task.return_value = self.task

        self.resource_client.delete('1', custom_headers=self.custom_headers)

        mock_delete.assert_called_once_with(mock.ANY, custom_headers={'Accept-Language': 'en_US'})

    def test_delete_dict_invalid_uri(self):
        dict_to_delete = {"task": "task",
                          "uri": ""}
        try:
            self.resource_client.delete(dict_to_delete, False, -1)
        except HPOneViewUnknownType as e:
            self.assertEqual("Unknown object type", e.args[0])
        else:
            self.fail()

    @mock.patch.object(connection, 'get')
    def test_get_schema_uri(self, mock_get):
        self.resource_client.get_schema()
        mock_get.assert_called_once_with(self.URI + "/schema")

    @mock.patch.object(connection, 'get')
    def test_get_by_id_uri(self, mock_get):
        self.resource_client.get('12345')
        mock_get.assert_called_once_with(self.URI + "/12345")

    @mock.patch.object(ResourceClient, 'get_by')
    def test_get_by_name_with_result(self, mock_get_by):
        mock_get_by.return_value = [{"name": "value"}]
        response = self.resource_client.get_by_name('Resource Name,')
        self.assertEqual(response, {"name": "value"})
        mock_get_by.assert_called_once_with("name", 'Resource Name,')

    @mock.patch.object(ResourceClient, 'get_by')
    def test_get_by_name_without_result(self, mock_get_by):
        mock_get_by.return_value = []
        response = self.resource_client.get_by_name('Resource Name,')
        self.assertIsNone(response)
        mock_get_by.assert_called_once_with("name", 'Resource Name,')

    @mock.patch.object(connection, 'get')
    def test_get_collection_uri(self, mock_get):
        mock_get.return_value = {"members": [{"key": "value"}, {"key": "value"}]}

        self.resource_client.get_collection('12345')

        mock_get.assert_called_once_with(self.URI + "/12345")

    @mock.patch.object(connection, 'get')
    def test_get_collection_with_filter(self, mock_get):
        mock_get.return_value = {}

        self.resource_client.get_collection('12345', 'name=name')

        mock_get.assert_called_once_with(self.URI + "/12345?filter=name%3Dname")

    @mock.patch.object(connection, 'get')
    def test_get_collection_with_multiple_filters(self, mock_get):
        mock_get.return_value = {}

        self.resource_client.get_collection('12345', ['name1=one', 'name2=two', 'name=three'])

        mock_get.assert_called_once_with(self.URI + "/12345?filter=name1%3Done&filter=name2%3Dtwo&filter=name%3Dthree")

    @mock.patch.object(connection, 'get')
    def test_get_collection_should_return_list(self, mock_get):
        mock_get.return_value = {"members": [{"key": "value"}, {"key": "value"}]}

        collection = self.resource_client.get_collection('12345')

        self.assertEqual(len(collection), 2)

    @mock.patch.object(ResourceClient, 'get_all')
    def test_get_by_property(self, mock_get_all):
        self.resource_client.get_by('name', 'MyFibreNetwork')
        mock_get_all.assert_called_once_with(filter="\"'name'='MyFibreNetwork'\"", uri='/rest/testuri')

    @mock.patch.object(ResourceClient, 'get_all')
    def test_get_by_property_with_uri(self, mock_get_all):
        self.resource_client.get_by('name', 'MyFibreNetwork', uri='/rest/testuri/5435534/sub')
        mock_get_all.assert_called_once_with(filter="\"'name'='MyFibreNetwork'\"", uri='/rest/testuri/5435534/sub')

    @mock.patch.object(ResourceClient, 'get_all')
    def test_get_by_property_with__invalid_uri(self, mock_get_all):
        try:
            self.resource_client.get_by('name', 'MyFibreNetwork', uri='/rest/other/5435534/sub')
        except HPOneViewUnknownType as e:
            self.assertEqual('Unrecognized URI for this resource', e.args[0])
        else:
            self.fail()

    @mock.patch.object(connection, 'put')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_update_with_zero_body_called_once(self, mock_wait4task, mock_update):
        mock_update.return_value = self.task, self.task
        mock_wait4task.return_value = self.task
        self.resource_client.update_with_zero_body('/rest/enclosures/09USE133E5H4/configuration',
                                                   timeout=-1)

        mock_update.assert_called_once_with(
            "/rest/enclosures/09USE133E5H4/configuration", None, custom_headers=None)

    @mock.patch.object(connection, 'put')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_update_with_zero_body_and_custom_headers(self, mock_wait4task, mock_update):
        mock_update.return_value = self.task, self.task
        mock_wait4task.return_value = self.task
        self.resource_client.update_with_zero_body('1', custom_headers=self.custom_headers)

        mock_update.assert_called_once_with(mock.ANY, mock.ANY, custom_headers={'Accept-Language': 'en_US'})

    @mock.patch.object(connection, 'put')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_update_with_zero_body_return_entity(self, mock_wait4task, mock_put):
        response_body = {"resource_name": "name"}

        mock_put.return_value = self.task, self.task
        mock_wait4task.return_value = response_body

        result = self.resource_client.update_with_zero_body(
            '/rest/enclosures/09USE133E5H4/configuration', timeout=-1)

        self.assertEqual(result, response_body)

    @mock.patch.object(connection, 'put')
    def test_update_with_zero_body_without_task(self, mock_put):
        mock_put.return_value = None, self.response_body

        result = self.resource_client.update_with_zero_body(
            '/rest/enclosures/09USE133E5H4/configuration', timeout=-1)

        self.assertEqual(result, self.response_body)

    @mock.patch.object(connection, 'put')
    def test_update_with_uri_called_once(self, mock_put):
        dict_to_update = {"name": "test"}
        uri = "/rest/resource/test"

        mock_put.return_value = None, self.response_body
        response = self.resource_client.update(dict_to_update, uri=uri)

        self.assertEqual(self.response_body, response)
        mock_put.assert_called_once_with(uri, dict_to_update, custom_headers=None)

    @mock.patch.object(connection, 'put')
    def test_update_with_custom_headers(self, mock_put):
        dict_to_update = {"name": "test"}
        mock_put.return_value = None, self.response_body

        self.resource_client.update(dict_to_update, uri="/path", custom_headers=self.custom_headers)

        mock_put.assert_called_once_with(mock.ANY, mock.ANY, custom_headers={'Accept-Language': 'en_US'})

    @mock.patch.object(connection, 'put')
    def test_update_with_force(self, mock_put):
        dict_to_update = {"name": "test"}
        uri = "/rest/resource/test"
        mock_put.return_value = None, self.response_body

        self.resource_client.update(dict_to_update, uri=uri, force=True)

        expected_uri = "/rest/resource/test?force=True"
        mock_put.assert_called_once_with(expected_uri, dict_to_update, custom_headers=None)

    @mock.patch.object(connection, 'put')
    def test_update_with_default_api_version_200(self, mock_put):
        dict_to_update = {"name": "test"}
        uri = "/rest/resource/test"

        mock_put.return_value = None, self.response_body

        expected_dict = {"name": "test", "type": self.TYPE_V200}

        self.resource_client.update(dict_to_update, uri=uri, default_values=self.DEFAULT_VALUES)
        mock_put.assert_called_once_with(uri, expected_dict, custom_headers=None)

    @mock.patch.object(connection, 'put')
    def test_update_with_api_version_300(self, mock_put):
        dict_to_update = {"name": "test"}
        uri = "/rest/resource/test"

        mock_put.return_value = None, self.response_body
        self.connection._apiVersion = 300

        expected_dict = {"name": "test", "type": self.TYPE_V300}

        self.resource_client.update(dict_to_update, uri=uri, default_values=self.DEFAULT_VALUES)
        mock_put.assert_called_once_with(uri, expected_dict, custom_headers=None)

    @mock.patch.object(connection, 'put')
    def test_update_should_not_override_resource_properties(self, mock_put):
        dict_to_update = {"name": "test", "type": "anotherType"}
        uri = "/rest/resource/test"

        mock_put.return_value = None, self.response_body

        self.resource_client.update(dict_to_update, uri=uri, default_values=self.DEFAULT_VALUES)
        mock_put.assert_called_once_with(uri, dict_to_update, custom_headers=None)

    @mock.patch.object(connection, 'put')
    def test_update_without_default_values(self, mock_put):
        dict_to_update = {"name": "test"}
        uri = "/rest/resource/test"

        mock_put.return_value = None, self.response_body

        resource_client = ResourceClient(self.connection, self.URI)
        resource_client.update(dict_to_update, uri=uri)

        mock_put.assert_called_once_with(uri, dict_to_update, custom_headers=None)

    @mock.patch.object(connection, 'put')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_update_uri(self, mock_wait4task, mock_update):
        dict_to_update = {"resource_data": "resource_data",
                          "uri": "a_uri"}

        mock_update.return_value = self.task, self.response_body
        mock_wait4task.return_value = self.task
        update_task = self.resource_client.update(dict_to_update, False)

        self.assertEqual(self.task, update_task)
        mock_update.assert_called_once_with("a_uri", dict_to_update, custom_headers=None)

    @mock.patch.object(connection, 'put')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_update_return_entity(self, mock_wait4task, mock_put):
        dict_to_update = {
            "resource_name": "a name",
            "uri": "a_uri",
        }
        mock_put.return_value = self.task, {}
        mock_wait4task.return_value = dict_to_update

        result = self.resource_client.update(dict_to_update, timeout=-1)

        self.assertEqual(result, dict_to_update)

    @mock.patch.object(connection, 'post')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_create_with_zero_body_called_once(self, mock_wait4task, mock_post):
        mock_post.return_value = self.task, self.task
        mock_wait4task.return_value = self.task
        self.resource_client.create_with_zero_body('/rest/enclosures/09USE133E5H4/configuration',
                                                   timeout=-1)

        mock_post.assert_called_once_with(
            "/rest/enclosures/09USE133E5H4/configuration", {}, custom_headers=None)

    @mock.patch.object(connection, 'post')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_create_with_zero_body_called_once_without_uri(self, mock_wait4task, mock_post):
        mock_post.return_value = self.task, self.task
        mock_wait4task.return_value = self.task
        self.resource_client.create_with_zero_body(timeout=-1)

        mock_post.assert_called_once_with(
            '/rest/testuri', {}, custom_headers=None)

    @mock.patch.object(connection, 'post')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_create_with_zero_body_and_custom_headers(self, mock_wait4task, mock_post):
        mock_post.return_value = self.task, self.task
        mock_wait4task.return_value = self.task
        self.resource_client.create_with_zero_body('1', custom_headers=self.custom_headers)

        mock_post.assert_called_once_with(mock.ANY, mock.ANY, custom_headers={'Accept-Language': 'en_US'})

    @mock.patch.object(connection, 'post')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_create_with_zero_body_return_entity(self, mock_wait4task, mock_post):
        response_body = {"resource_name": "name"}

        mock_post.return_value = self.task, self.task
        mock_wait4task.return_value = response_body

        result = self.resource_client.create_with_zero_body(
            '/rest/enclosures/09USE133E5H4/configuration', timeout=-1)

        self.assertEqual(result, response_body)

    @mock.patch.object(connection, 'post')
    def test_create_with_zero_body_without_task(self, mock_post):
        mock_post.return_value = None, self.response_body

        result = self.resource_client.create_with_zero_body(
            '/rest/enclosures/09USE133E5H4/configuration', timeout=-1)

        self.assertEqual(result, self.response_body)

    @mock.patch.object(connection, 'post')
    def test_create_uri(self, mock_post):
        dict_to_create = {"resource_name": "a name"}
        mock_post.return_value = {}, {}

        self.resource_client.create(dict_to_create, timeout=-1)
        mock_post.assert_called_once_with(self.URI, dict_to_create, custom_headers=None)

    @mock.patch.object(connection, 'post')
    def test_create_with_default_api_version(self, mock_post):
        dict_to_create = {"resource_name": "a name"}
        mock_post.return_value = {}, {}

        expected_dict = {"resource_name": "a name", "type": self.TYPE_V200}

        self.resource_client.create(dict_to_create, timeout=-1, default_values=self.DEFAULT_VALUES)
        mock_post.assert_called_once_with(self.URI, expected_dict, custom_headers=None)

    @mock.patch.object(connection, 'post')
    def test_create_with_api_version_300(self, mock_post):
        dict_to_create = {"resource_name": "a name"}
        mock_post.return_value = {}, {}

        self.connection._apiVersion = 300
        expected_dict = {"resource_name": "a name", "type": self.TYPE_V300}

        self.resource_client.create(dict_to_create, timeout=-1, default_values=self.DEFAULT_VALUES)
        mock_post.assert_called_once_with(self.URI, expected_dict, custom_headers=None)

    @mock.patch.object(connection, 'post')
    def test_create_should_not_override_resource_properties(self, mock_post):
        dict_to_create = {"resource_name": "a name", "type": "anotherType"}
        mock_post.return_value = {}, {}

        self.resource_client.create(dict_to_create, default_values=self.DEFAULT_VALUES)

        mock_post.assert_called_once_with(self.URI, dict_to_create, custom_headers=None)

    @mock.patch.object(connection, 'post')
    def test_create_without_default_values(self, mock_post):
        dict_to_create = {"resource_name": "a name"}
        mock_post.return_value = {}, {}

        resource_client = ResourceClient(self.connection, self.URI)
        resource_client.create(dict_to_create, timeout=-1)

        mock_post.assert_called_once_with(self.URI, dict_to_create, custom_headers=None)

    @mock.patch.object(connection, 'post')
    def test_create_with_custom_headers(self, mock_post):
        dict_to_create = {"resource_name": "a name"}
        mock_post.return_value = {}, {}

        self.resource_client.create(dict_to_create, custom_headers=self.custom_headers)

        mock_post.assert_called_once_with(mock.ANY, mock.ANY, custom_headers={'Accept-Language': 'en_US'})

    @mock.patch.object(connection, 'post')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_create_return_entity(self, mock_wait4task, mock_post):
        dict_to_create = {
            "resource_name": "a name",
        }
        created_resource = {
            "resource_id": "123",
            "resource_name": "a name",
        }

        mock_post.return_value = self.task, {}
        mock_wait4task.return_value = created_resource

        result = self.resource_client.create(dict_to_create, -1)

        self.assertEqual(result, created_resource)

    @mock.patch.object(connection, 'post')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_wait_for_activity_on_create(self, mock_wait4task, mock_post):
        mock_post.return_value = self.task, {}
        mock_wait4task.return_value = self.task

        self.resource_client.create({"test": "test"}, timeout=60)

        mock_wait4task.assert_called_once_with(self.task, 60)

    @mock.patch.object(connection, 'patch')
    def test_patch_request_when_id_is_provided(self, mock_patch):
        request_body = [{
            'op': 'replace',
            'path': '/name',
            'value': 'new_name',
        }]
        mock_patch.return_value = {}, {}

        self.resource_client.patch(
            '123a53cz', 'replace', '/name', 'new_name', 70)

        mock_patch.assert_called_once_with(
            '/rest/testuri/123a53cz', request_body, custom_headers={})

    @mock.patch.object(connection, 'patch')
    def test_patch_request_when_id_is_provided_v300(self, mock_patch):
        request_body = [{
            'op': 'replace',
            'path': '/name',
            'value': 'new_name',
        }]
        mock_patch.return_value = {}, {}

        self.connection._apiVersion = 300

        resource_client = ResourceClient(self.connection, self.URI)
        resource_client.patch(
            '123a53cz', 'replace', '/name', 'new_name', 70)

        mock_patch.assert_called_once_with(
            '/rest/testuri/123a53cz', request_body, custom_headers={'Content-Type': 'application/json-patch+json'})

    @mock.patch.object(connection, 'patch')
    def test_patch_request_when_uri_is_provided(self, mock_patch):
        request_body = [{
            'op': 'replace',
            'path': '/name',
            'value': 'new_name',
        }]
        mock_patch.return_value = {}, {}

        self.resource_client.patch(
            '/rest/testuri/123a53cz', 'replace', '/name', 'new_name', 60)

        mock_patch.assert_called_once_with(
            '/rest/testuri/123a53cz', request_body, custom_headers={})

    @mock.patch.object(connection, 'patch')
    def test_patch_with_custom_headers(self, mock_patch):
        mock_patch.return_value = {}, {}

        self.resource_client.patch('/rest/testuri/123', 'operation', '/field', 'value',
                                   custom_headers=self.custom_headers)

        mock_patch.assert_called_once_with(mock.ANY, mock.ANY, custom_headers={'Accept-Language': 'en_US'})

    @mock.patch.object(connection, 'patch')
    def test_patch_with_custom_headers_v300(self, mock_patch):
        mock_patch.return_value = {}, {}

        self.connection._apiVersion = 300

        resource_client = ResourceClient(self.connection, self.URI)
        resource_client.patch('/rest/testuri/123', 'operation', '/field', 'value',
                              custom_headers=self.custom_headers)

        mock_patch.assert_called_once_with(mock.ANY,
                                           mock.ANY,
                                           custom_headers={'Accept-Language': 'en_US',
                                                           'Content-Type': 'application/json-patch+json'})

    @mock.patch.object(connection, 'patch')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_patch_return_entity(self, mock_wait4task, mock_patch):
        entity = {"resource_id": "123a53cz"}
        mock_patch.return_value = self.task, self.task
        mock_wait4task.return_value = entity

        result = self.resource_client.patch(
            '123a53cz', 'replace', '/name', 'new_name', -1)

        self.assertEqual(result, entity)

    @mock.patch.object(connection, 'patch')
    @mock.patch.object(TaskMonitor, 'get_completed_task')
    def test_patch_request_custom_headers_with_content_type(self, mock_task, mock_patch):

        dict_info = {"resource_name": "a name"}

        mock_patch.return_value = {}, {}

        headers = {'Content-Type': 'application/json',
                   'Extra': 'extra'}
        self.connection._apiVersion = 300

        resource_client = ResourceClient(self.connection, self.URI)
        resource_client.patch_request('/rest/testuri/id', body=dict_info, custom_headers=headers)

        mock_patch.assert_called_once_with('/rest/testuri/id', dict_info, custom_headers=headers)

    @mock.patch.object(connection, 'patch')
    @mock.patch.object(TaskMonitor, 'get_completed_task')
    def test_patch_request_custom_headers(self, mock_task, mock_patch):

        dict_info = {"resource_name": "a name"}

        mock_patch.return_value = {}, {}
        headers = {'Extra': 'extra'}
        self.connection._apiVersion = 300

        resource_client = ResourceClient(self.connection, self.URI)
        resource_client.patch_request('/rest/testuri/id', body=dict_info, custom_headers=headers)

        mock_patch.assert_called_once_with(
            '/rest/testuri/id',
            dict_info,
            custom_headers={'Extra': 'extra',
                            'Content-Type': 'application/json-patch+json'})

    @mock.patch.object(connection, 'patch')
    @mock.patch.object(TaskMonitor, 'wait_for_task')
    def test_wait_for_activity_on_patch(self, mock_wait4task, mock_patch):
        entity = {"resource_id": "123a53cz"}
        mock_patch.return_value = self.task, self.task
        mock_wait4task.return_value = entity

        self.resource_client.patch(
            '123a53cz', 'replace', '/name', 'new_name', -1)

        mock_wait4task.assert_called_once_with(self.task, mock.ANY)

    def test_delete_with_none(self):
        try:
            self.resource_client.delete(None)
        except ValueError as e:
            self.assertTrue("Resource" in e.args[0])
        else:
            self.fail()

    @mock.patch.object(connection, 'delete')
    def test_delete_with_dict_uri(self, mock_delete):

        resource = {"uri": "uri"}

        mock_delete.return_value = {}, {}
        delete_result = self.resource_client.delete(resource)

        self.assertTrue(delete_result)
        mock_delete.assert_called_once_with("uri", custom_headers=None)

    def test_delete_with_empty_dict(self):
        try:
            self.resource_client.delete({})
        except ValueError as e:
            self.assertTrue("Resource" in e.args[0])
        else:
            self.fail()

    def test_get_with_none(self):
        try:
            self.resource_client.get(None)
        except ValueError as e:
            self.assertTrue("id" in e.args[0])
        else:
            self.fail()

    def test_get_collection_with_none(self):
        try:
            self.resource_client.get_collection(None)
        except ValueError as e:
            self.assertTrue("id" in e.args[0])
        else:
            self.fail()

    def test_create_with_none(self):
        try:
            self.resource_client.create(None)
        except ValueError as e:
            self.assertTrue("Resource" in e.args[0])
        else:
            self.fail()

    def test_create_with_empty_dict(self):
        try:
            self.resource_client.create({})
        except ValueError as e:
            self.assertTrue("Resource" in e.args[0])
        else:
            self.fail()

    def test_update_with_none(self):
        try:
            self.resource_client.update(None)
        except ValueError as e:
            self.assertTrue("Resource" in e.args[0])
        else:
            self.fail()

    def test_update_with_empty_dict(self):
        try:
            self.resource_client.update({})
        except ValueError as e:
            self.assertTrue("Resource" in e.args[0])
        else:
            self.fail()

    def test_get_by_with_name_none(self):
        try:
            self.resource_client.get_by(None, None)
        except ValueError as e:
            self.assertTrue("field" in e.args[0])
        else:
            self.fail()

    @mock.patch.object(connection, 'get')
    def test_get_with_uri_should_work(self, mock_get):
        mock_get.return_value = {}
        uri = self.URI + "/ad28cf21-8b15-4f92-bdcf-51cb2042db32"
        self.resource_client.get(uri)

        mock_get.assert_called_once_with(uri)

    def test_get_with_uri_with_incompatible_url_shoud_fail(self):
        message = "Unrecognized URI for this resource"
        uri = "/rest/interconnects/ad28cf21-8b15-4f92-bdcf-51cb2042db32"
        try:
            self.resource_client.get(uri)
        except HPOneViewUnknownType as exception:
            self.assertEqual(message, exception.args[0])
        else:
            self.fail("Expected Exception was not raised")

    def test_get_with_uri_from_another_resource_with_incompatible_url_shoud_fail(self):
        message = "Unrecognized URI for this resource"
        uri = "/rest/interconnects/ad28cf21-8b15-4f92-bdcf-51cb2042db32"
        fake_resource = FakeResource(None)
        try:
            fake_resource.get_fake(uri)
        except HPOneViewUnknownType as exception:
            self.assertEqual(message, exception.args[0])
        else:
            self.fail("Expected Exception was not raised")

    @mock.patch.object(connection, 'get')
    def test_get_utilization_with_args(self, mock_get):
        self.resource_client.get_utilization('09USE7335NW3', fields='AmbientTemperature,AveragePower,PeakPower',
                                             filter='startDate=2016-05-30T03:29:42.361Z',
                                             refresh=True, view='day')

        expected_uri = '/rest/testuri/09USE7335NW3/utilization' \
                       '?filter=startDate%3D2016-05-30T03%3A29%3A42.361Z' \
                       '&fields=AmbientTemperature%2CAveragePower%2CPeakPower' \
                       '&refresh=true' \
                       '&view=day'

        mock_get.assert_called_once_with(expected_uri)

    @mock.patch.object(connection, 'get')
    def test_get_utilization_with_multiple_filters(self, mock_get):
        self.resource_client.get_utilization(
            '09USE7335NW3',
            fields='AmbientTemperature,AveragePower,PeakPower',
            filter=['startDate=2016-05-30T03:29:42.361Z',
                    'endDate=2016-05-31T03:29:42.361Z'],
            refresh=True,
            view='day')

        expected_uri = '/rest/testuri/09USE7335NW3/utilization' \
                       '?filter=startDate%3D2016-05-30T03%3A29%3A42.361Z' \
                       '&filter=endDate%3D2016-05-31T03%3A29%3A42.361Z' \
                       '&fields=AmbientTemperature%2CAveragePower%2CPeakPower' \
                       '&refresh=true' \
                       '&view=day'

        mock_get.assert_called_once_with(expected_uri)

    @mock.patch.object(connection, 'get')
    def test_get_utilization_by_id_with_defaults(self, mock_get):
        self.resource_client.get_utilization('09USE7335NW3')

        expected_uri = '/rest/testuri/09USE7335NW3/utilization'

        mock_get.assert_called_once_with(expected_uri)

    @mock.patch.object(connection, 'get')
    def test_get_utilization_by_uri_with_defaults(self, mock_get):
        self.resource_client.get_utilization('/rest/testuri/09USE7335NW3')

        expected_uri = '/rest/testuri/09USE7335NW3/utilization'

        mock_get.assert_called_once_with(expected_uri)

    def test_get_utilization_with_empty(self):

        try:
            self.resource_client.get_utilization('')
        except ValueError as exception:
            self.assertEqual(RESOURCE_CLIENT_INVALID_ID, exception.args[0])
        else:
            self.fail("Expected Exception was not raised")

    def test_build_uri_with_id_should_work(self):
        input = '09USE7335NW35'
        expected_output = '/rest/testuri/09USE7335NW35'
        result = self.resource_client.build_uri(input)
        self.assertEqual(expected_output, result)

    def test_build_uri_with_uri_should_work(self):
        input = '/rest/testuri/09USE7335NW3'
        expected_output = '/rest/testuri/09USE7335NW3'
        result = self.resource_client.build_uri(input)
        self.assertEqual(expected_output, result)

    def test_build_uri_with_none_should_raise_exception(self):
        try:
            self.resource_client.build_uri(None)
        except ValueError as exception:
            self.assertEqual(RESOURCE_CLIENT_INVALID_ID, exception.args[0])
        else:
            self.fail("Expected Exception was not raised")

    def test_build_uri_with_empty_str_should_raise_exception(self):
        try:
            self.resource_client.build_uri('')
        except ValueError as exception:
            self.assertEqual(RESOURCE_CLIENT_INVALID_ID, exception.args[0])
        else:
            self.fail("Expected Exception was not raised")

    def test_build_uri_with_different_resource_uri_should_raise_exception(self):
        try:
            self.resource_client.build_uri(
                '/rest/test/another/resource/uri/09USE7335NW3')
        except HPOneViewUnknownType as exception:
            self.assertEqual(UNRECOGNIZED_URI, exception.args[0])
        else:
            self.fail("Expected Exception was not raised")

    def test_build_uri_with_incomplete_uri_should_raise_exception(self):
        try:
            self.resource_client.build_uri('/rest/')
        except HPOneViewUnknownType as exception:
            self.assertEqual(UNRECOGNIZED_URI, exception.args[0])
        else:
            self.fail("Expected Exception was not raised")

    @mock.patch.object(connection, 'post')
    @mock.patch.object(TaskMonitor, 'get_completed_task')
    def test_create_report_should_do_post_request(self, mock_get_completed_task, mock_post):
        task_with_output = self.task.copy()
        task_with_output['taskOutput'] = []

        mock_post.return_value = self.task, {}
        mock_get_completed_task.return_value = task_with_output

        self.resource_client.create_report("/rest/path/create-report")

        mock_post.assert_called_once_with("/rest/path/create-report", {})

    @mock.patch.object(connection, 'post')
    @mock.patch.object(TaskMonitor, 'get_completed_task')
    def test_create_report_should_wait_task_completion(self, mock_get_completed_task, mock_post):
        task_with_output = self.task.copy()
        task_with_output['taskOutput'] = []

        mock_post.return_value = self.task, {}
        mock_get_completed_task.return_value = task_with_output

        self.resource_client.create_report("/rest/path/create-report", timeout=60)

        mock_get_completed_task.assert_called_once_with(self.task, 60)

    @mock.patch.object(connection, 'post')
    @mock.patch.object(TaskMonitor, 'get_completed_task')
    def test_create_report_should_return_output_list_when_results(self, mock_get_completed_task, mock_post):
        task_output = [
            {"type": "FCIssueResponseV2", "created": "2015-03-24T15: 32: 50.889Z"},
            {"type": "FCIssueResponseV2", "created": "2015-03-13T14: 10: 50.322Z"}
        ]
        task_with_output = self.task.copy()
        task_with_output['taskOutput'] = task_output

        mock_post.return_value = self.task, {}
        mock_get_completed_task.return_value = task_with_output

        result = self.resource_client.create_report("/rest/path/create-report")

        self.assertEqual(result, task_output)

    @mock.patch.object(connection, 'post')
    @mock.patch.object(TaskMonitor, 'get_completed_task')
    def test_create_report_should_return_empty_list_when_output_is_empty(self, mock_get_completed_task, mock_post):
        task_with_output = self.task.copy()
        task_with_output['taskOutput'] = []

        mock_post.return_value = self.task, {}
        mock_get_completed_task.return_value = task_with_output

        result = self.resource_client.create_report("/rest/path/create-report")

        self.assertEqual(result, [])

    @mock.patch.object(connection, 'post')
    def test_create_report_should_raise_exception_when_not_task(self, mock_post):
        task_with_output = self.task.copy()
        task_with_output['taskOutput'] = []

        mock_post.return_value = None, {}

        try:
            self.resource_client.create_report("/rest/path/create-report")
        except HPOneViewException as exception:
            self.assertEqual(RESOURCE_CLIENT_TASK_EXPECTED, exception.args[0])
        else:
            self.fail("Expected Exception was not raised")

    @mock.patch.object(connection, 'post')
    def test_create_when_the_resource_is_a_list(self, mock_post):
        dict_to_create = [{"resource_name": "a name"}]
        mock_post.return_value = {}, {}

        resource_client = ResourceClient(self.connection, self.URI)
        resource_client.create(dict_to_create, timeout=-1)

        mock_post.assert_called_once_with(self.URI, dict_to_create, custom_headers=None)

    def test_merge_api_default_values(self):
        resource = {'name': 'resource1'}
        default_values = {
            '200': {"type": "EnclosureGroupV200"},
            '300': {"type": "EnclosureGroupV300"}
        }

        expected = {'name': 'resource1', "type": "EnclosureGroupV200"}

        resource_client = ResourceClient(self.connection, self.URI)
        result = resource_client.merge_default_values(resource, default_values)

        self.assertEqual(result, expected)

    def test_should_not_merge_when_default_values_not_defined(self):
        resource = {'name': 'resource1'}
        default_values = {}

        expected = {'name': 'resource1'}

        resource_client = ResourceClient(self.connection, self.URI)
        result = resource_client.merge_default_values(resource, default_values)

        self.assertEqual(result, expected)